"""
ProbeRat Report Generator

读取 Locust + GPU + System 三份 CSV，自动分析并生成 Markdown 报告。

用法:
    python report/generate_report.py
    或在 ProbeRat 根目录: python -m report.generate_report
"""

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# 配置（基于本文件位置，不用管在哪里运行）
# ============================================================
HERE = Path(__file__).resolve().parent
DEFAULT_REPORTS_DIR = HERE / "reports"
DEFAULT_TEMPLATE = HERE / "template.md"
DEFAULT_OUTPUT = DEFAULT_REPORTS_DIR / "report.md"

# 三份 CSV 的默认文件名
LOCUST_STATS_CSV = "locust_result_stats.csv"   # 和 --csv=...locust_result 对应
GPU_CSV = "gpu_metrics.csv"
SYSTEM_CSV = "system_metrics.csv"

# 目标服务信息（可改成从 app/config/settings.py 读）
TARGET_NAME = "FunASR ASR Service"
TARGET_ENDPOINT = "POST /asr/transcribe"
TARGET_HOST = "http://127.0.0.1:8001"


# ============================================================
# 工具函数
# ============================================================
def safe_read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        print(f"[Report] 警告：文件不存在 -> {path}")
        return None
    try:
        df = pd.read_csv(path)
        if df.empty:
            print(f"[Report] 警告：文件为空 -> {path}")
            return None
        return df
    except Exception as e:
        print(f"[Report] 读取 {path} 失败：{e}")
        return None


def fmt(value, digits=2, suffix=""):
    if value is None or pd.isna(value):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


# ============================================================
# 各模块解析
# ============================================================
def parse_locust(df: pd.DataFrame) -> dict:
    """优先取 POST 行；没 POST 就取 Aggregated；都没有就取第一行。"""
    post_df = df[df["Type"] == "POST"]
    if not post_df.empty:
        row = post_df.sort_values("Request Count", ascending=False).iloc[0]
    else:
        agg = df[df["Name"].astype(str).str.contains("Aggregated", case=False, na=False)]
        row = agg.iloc[0] if not agg.empty else df.iloc[0]

    total = int(row["Request Count"])
    failures = int(row["Failure Count"])
    failure_rate = (failures / total * 100) if total > 0 else 0.0

    return {
        "total_requests": total,
        "failures": failures,
        "failure_rate": failure_rate,
        "avg_rt": float(row["Average Response Time"]),
        "median_rt": float(row["Median Response Time"]),
        "p95_rt": float(row["95%"]),
        "p99_rt": float(row["99%"]),
        "avg_rps": float(row["Requests/s"]),
        "max_rt": float(row.get("Max Response Time", 0)),
    }


def parse_gpu(df: pd.DataFrame) -> dict:
    return {
        "avg_util": df["gpu_utilization_%"].mean(),
        "peak_util": df["gpu_utilization_%"].max(),
        "avg_mem": df["memory_used_MB"].mean(),
        "peak_mem": df["memory_used_MB"].max(),
        "total_mem": df["memory_total_MB"].iloc[0],
        "avg_temp": df["temperature_C"].mean(),
        "peak_temp": df["temperature_C"].max(),
    }


def parse_system(df: pd.DataFrame) -> dict:
    return {
        "avg_cpu": df["cpu_percent"].mean(),
        "peak_cpu": df["cpu_percent"].max(),
        "avg_mem": df["memory_percent"].mean(),
        "peak_mem": df["memory_percent"].max(),
    }


# ============================================================
# 生成各 Markdown 区块
# ============================================================
def build_gpu_section(gpu: dict | None) -> str:
    if gpu is None:
        return "_GPU 监控数据缺失，未采集到 GPU 指标。_\n"
    return (
        "| Metric | Value |\n"
        "|---|---|\n"
        f"| Average Utilization | {fmt(gpu['avg_util'], 2, '%')} |\n"
        f"| Peak Utilization | {fmt(gpu['peak_util'], 0, '%')} |\n"
        f"| Average Memory Used | {fmt(gpu['avg_mem'], 2, ' MB')} / {fmt(gpu['total_mem'], 0, ' MB')} |\n"
        f"| Peak Memory Used | {fmt(gpu['peak_mem'], 2, ' MB')} |\n"
        f"| Average Temperature | {fmt(gpu['avg_temp'], 1, ' ℃')} |\n"
        f"| Peak Temperature | {fmt(gpu['peak_temp'], 0, ' ℃')} |\n"
    )


def build_system_section(sys: dict | None) -> str:
    if sys is None:
        return "_System 监控数据缺失。_\n"
    return (
        "| Metric | Value |\n"
        "|---|---|\n"
        f"| Average CPU | {fmt(sys['avg_cpu'], 2, '%')} |\n"
        f"| Peak CPU | {fmt(sys['peak_cpu'], 2, '%')} |\n"
        f"| Average Memory | {fmt(sys['avg_mem'], 2, '%')} |\n"
        f"| Peak Memory | {fmt(sys['peak_mem'], 2, '%')} |\n"
    )


# ============================================================
# 自动分析 + 建议
# ============================================================
def build_analysis(locust: dict, gpu: dict | None, sys: dict | None):
    analysis, suggestions = [], []
    p95 = locust["p95_rt"]
    failure_rate = locust["failure_rate"]

    # ---------- 响应时间 ----------
    if p95 < 3000:
        analysis.append(f"- P95 = {p95:.2f} ms，小于 3s，符合设计目标。")
        suggestions.append("- ✅ 当前 P95 达标，系统稳定。")
    elif p95 < 6000:
        analysis.append(f"- P95 = {p95:.2f} ms，介于 3s ~ 6s，存在优化空间。")
    else:
        analysis.append(f"- P95 = {p95:.2f} ms，超过 6s，系统已出现瓶颈。")

    # ---------- 失败率 ----------
    if failure_rate == 0:
        analysis.append("- 失败率 0.00%，无失败请求。")
    else:
        analysis.append(f"- 失败率 {failure_rate:.2f}%。")
        suggestions.append("- ⚠️ 存在失败请求，查看 locust_result_failures.csv。")

    # ---------- ★ 核心诊断：资源 vs 延迟 ----------
    gpu_util = gpu["avg_util"] if gpu else None
    gpu_peak = gpu["peak_util"] if gpu else None
    cpu_util = sys["avg_cpu"] if sys else None
    cpu_peak = sys["peak_cpu"] if sys else None

    resource_idle = (
        gpu_util is not None and cpu_util is not None
        and gpu_util < 50 and cpu_util < 50
    )

    if resource_idle and p95 > 3000:
        analysis.append("")
        analysis.append("### ★ 瓶颈诊断")
        analysis.append(
            f"- **GPU 平均利用率 {gpu_util:.1f}%（峰值 {gpu_peak:.0f}%）**，"
            f"**CPU 平均 {cpu_util:.1f}%（峰值 {cpu_peak:.1f}%）**"
        )
        analysis.append(
            f"- 硬件资源**远未饱和**，但 P95 已达 {p95:.0f} ms、"
            f"RPS 仅 {locust['avg_rps']:.2f}"
        )
        analysis.append(
            "- **结论：瓶颈不在硬件，而在服务端推理调度（很可能是串行推理）。**"
        )
        suggestions.append(
            "- 🎯 **核心建议**：\n"
            "  - 检查 FunASR 服务端是否**串行处理请求**（一次只跑一个推理）。\n"
            "  - 启用 **batch inference**，一次推理多个请求。\n"
            "  - 检查 FastAPI 的 async 路由里是否跑了**同步阻塞代码**。\n"
            "  - 考虑增加推理 worker / 使用推理队列（如 Celery、Ray）。"
        )
    elif gpu is not None and gpu["avg_util"] > 85:
        analysis.append(
            f"- GPU 平均利用率 {gpu['avg_util']:.1f}%，"
            f"峰值 {gpu['peak_util']:.0f}%，GPU 已经打满。"
        )
        suggestions.append(
            "- ⚠️ GPU 饱和，建议：升级 GPU / 多卡 / 降精度 / 启用 TensorRT。"
        )

    # ---------- 汇总结论 ----------
    if failure_rate == 0 and p95 < 3000:
        conclusion = "系统在高并发下整体稳定，响应时间达标。"
    elif resource_idle and p95 > 3000:
        conclusion = (
            f"系统无失败请求，但 P95 达到 {p95/1000:.1f}s。"
            f"GPU/CPU 均处于低负载状态，**瓶颈在服务端调度而非硬件资源**。"
        )
    elif failure_rate == 0:
        conclusion = "系统无失败请求，但响应时间偏高，需要优化。"
    else:
        conclusion = "系统存在失败请求，需优先排查稳定性。"

    return "\n".join(analysis), conclusion, "\n".join(suggestions)

# ============================================================
# 主流程
# ============================================================
def generate(reports_dir: Path, template_path: Path, output_path: Path):
    print(f"[Report] 读取目录：{reports_dir}")

    locust_df = safe_read_csv(reports_dir / LOCUST_STATS_CSV)
    if locust_df is None:
        raise RuntimeError(f"关键文件缺失：{reports_dir / LOCUST_STATS_CSV}")

    gpu_df = safe_read_csv(reports_dir / GPU_CSV)
    sys_df = safe_read_csv(reports_dir / SYSTEM_CSV)

    locust = parse_locust(locust_df)
    gpu = parse_gpu(gpu_df) if gpu_df is not None else None
    sys_ = parse_system(sys_df) if sys_df is not None else None

    analysis, conclusion, suggestions = build_analysis(locust, gpu, sys_)

    # 测试时长：从 history CSV 或 stats CSV 的 Total 时间估算，简单取 360s
    duration_sec = 360
    duration_str = f"{duration_sec}s ({duration_sec / 60:.1f} min)"

    values = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_duration": duration_str,
        "target_name": TARGET_NAME,
        "target_endpoint": TARGET_ENDPOINT,
        "target_host": TARGET_HOST,
        "total_requests": locust["total_requests"],
        "failures": locust["failures"],
        "failure_rate": f"{locust['failure_rate']:.2f}%",
        "avg_rt": f"{locust['avg_rt']:.2f}",
        "median_rt": f"{locust['median_rt']:.2f}",
        "p95_rt": f"{locust['p95_rt']:.2f}",
        "p99_rt": f"{locust['p99_rt']:.2f}",
        "avg_rps": f"{locust['avg_rps']:.2f}",
        "gpu_section": build_gpu_section(gpu),
        "system_section": build_system_section(sys_),
        "analysis": analysis,
        "conclusion": conclusion,
        "suggestions": suggestions,
    }

    template = template_path.read_text(encoding="utf-8")
    report = template.format(**values)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"[Report] ✅ 报告已生成：{output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    generate(args.reports_dir, args.template, args.output)


if __name__ == "__main__":
    main()
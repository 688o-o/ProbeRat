import random
import sys
import threading
from pathlib import Path

from locust import HttpUser, task, between, events

# ========== 1. 修复导入路径 ==========
# 当前文件: ProbeRat/app/stress/locustfile.py
# 上 2 层:   ProbeRat/
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.monitor.gpu_monitor import GPUMonitor
from app.monitor.system_monitor import SystemMonitor

from load_shape import StepLoadShape


# ========== 2. 音频目录（改成基于 ROOT_DIR 计算）==========
AUDIO_DIR = ROOT_DIR / "tests" / "test"
audio_files = list(AUDIO_DIR.glob("*.wav"))

if not audio_files:
    raise RuntimeError(f"No wav files found in {AUDIO_DIR}")

print(f"[Locust] 已加载 {len(audio_files)} 个 wav 文件，来自 {AUDIO_DIR}")


# ========== 3. 监控全局变量 ==========
gpu_monitor = None
sys_monitor = None


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global gpu_monitor, sys_monitor

    runner = environment.runner
    if runner is not None and getattr(runner, "is_worker", False):
        print("[Monitor] Worker 节点，跳过监控启动")
        return

    print("\n[Monitor] ========== 压测开始，启动监控 ==========")

    # 输出目录: ProbeRat/report/reports/
    reports_dir = ROOT_DIR / "report" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    gpu_monitor = GPUMonitor(
        interval=1.0,
        output_file=str(reports_dir / "gpu_metrics.csv"),
        gpu_index=0,
    )
    sys_monitor = SystemMonitor(
        interval=1.0,
        output_file=str(reports_dir / "system_metrics.csv"),
    )

    threading.Thread(target=gpu_monitor.start, daemon=True).start()
    threading.Thread(target=sys_monitor.start, daemon=True).start()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    global gpu_monitor, sys_monitor

    runner = environment.runner
    if runner is not None and getattr(runner, "is_worker", False):
        return

    print("\n[Monitor] ========== 压测结束，停止监控 ==========")

    if gpu_monitor:
        gpu_monitor.stop()
    if sys_monitor:
        sys_monitor.stop()

    # ========== 压测结束后自动生成报告 ==========
    try:
        import subprocess

        report_script = ROOT_DIR / "report" / "generate_report.py"
        reports_dir = ROOT_DIR / "report" / "reports"

        print("\n[Report] ========== 开始生成报告 ==========")
        subprocess.run(
            [
                sys.executable,
                str(report_script),
                "--reports-dir", str(reports_dir),
                "--output", str(reports_dir / "report.md"),
            ],
            cwd=str(ROOT_DIR / "report"),
            check=True,
        )
        print(f"[Report] ✅ 报告已生成：{reports_dir / 'report.md'}")
    except Exception as e:
        # 报告失败不影响压测本身
        print(f"[Report] ⚠️ 生成报告失败：{e}")


# ========== 4. 业务逻辑 ==========
class ASRUser(HttpUser):
    host = "http://127.0.0.1:8001"
    wait_time = between(2, 5)

    @task
    def transcribe(self):
        audio = random.choice(audio_files)

        with open(audio, "rb") as f:
            files = {"audio": (audio.name, f, "audio/wav")}

            with self.client.post(
                "/asr/transcribe",
                files=files,
                catch_response=True,
                timeout=120,
            ) as response:

                if response.status_code != 200:
                    response.failure(f"HTTP {response.status_code}")
                    return

                try:
                    body = response.json()
                except Exception:
                    response.failure("Response is not JSON")
                    return

                if body.get("code") != 0:
                    response.failure(f"Business Error: {body}")
                    return

                response.success()
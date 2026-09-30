"""
ProbeRat 弱网压测 Locust
文件位置: ProbeRat/app/stress/locustfile_weaknet.py
依赖同目录的 config.py 和 load_shape.py
"""

import importlib.util
import random
import sys
import threading
from pathlib import Path

from locust import HttpUser, task, between, events


# ============================================================
# 1. 路径计算
# ============================================================
THIS_FILE = Path(__file__).resolve()
STRESS_DIR = THIS_FILE.parent           # app/stress/
ROOT_DIR = THIS_FILE.parents[2]          # ProbeRat/

# 把 ProbeRat/ 加到 sys.path，让 `from app.xxx` 能工作
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

assert (ROOT_DIR / "app").is_dir(), f"ROOT_DIR wrong: {ROOT_DIR}"
assert (ROOT_DIR / "report").is_dir(), f"ROOT_DIR wrong: {ROOT_DIR}"
assert (STRESS_DIR / "config.py").is_file(), f"config.py missing in {STRESS_DIR}"
assert (STRESS_DIR / "load_shape.py").is_file(), f"load_shape.py missing in {STRESS_DIR}"


# ============================================================
# 2. 用 importlib 直接加载 config.py（不依赖 sys.path 找包）
# ============================================================
def _load_local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = _load_local_module("stress_config", STRESS_DIR / "config.py")
load_shape = _load_local_module("stress_load_shape", STRESS_DIR / "load_shape.py")

TARGET = config.TARGET
PROXY = config.PROXY
USE_PROXY = config.USE_PROXY
REPORTS_DIR_WEAKNET = config.REPORTS_DIR_WEAKNET
REPORTS_DIR_NORMAL = config.REPORTS_DIR_NORMAL

StepLoadShape = load_shape.StepLoadShape


# ============================================================
# 3. 项目模块
# ============================================================
from app.monitor.gpu_monitor import GPUMonitor
from app.monitor.system_monitor import SystemMonitor


# ============================================================
# 4. 音频目录
# ============================================================
AUDIO_DIR = ROOT_DIR / "tests" / "test"
audio_files = list(AUDIO_DIR.glob("*.wav"))
if not audio_files:
    raise RuntimeError(f"No wav files found in {AUDIO_DIR}")

print(f"[Locust-WeakNet] ROOT_DIR    = {ROOT_DIR}")
print(f"[Locust-WeakNet] STRESS_DIR  = {STRESS_DIR}")
print(f"[Locust-WeakNet] 已加载 {len(audio_files)} 个 wav 文件")
print(f"[Locust-WeakNet] TARGET      = {TARGET}")
print(f"[Locust-WeakNet] PROXY       = {PROXY}")
print(f"[Locust-WeakNet] USE_PROXY   = {USE_PROXY}")


# ============================================================
# 5. 输出目录
# ============================================================
if USE_PROXY:
    REPORTS_DIR = ROOT_DIR / REPORTS_DIR_WEAKNET
else:
    REPORTS_DIR = ROOT_DIR / REPORTS_DIR_NORMAL

print(f"[Locust-WeakNet] REPORTS_DIR = {REPORTS_DIR}")


# ============================================================
# 6. 监控
# ============================================================
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
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    gpu_monitor = GPUMonitor(
        interval=1.0,
        output_file=str(REPORTS_DIR / "gpu_metrics.csv"),
        gpu_index=0,
    )
    sys_monitor = SystemMonitor(
        interval=1.0,
        output_file=str(REPORTS_DIR / "system_metrics.csv"),
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

    try:
        import subprocess

        report_script = ROOT_DIR / "report" / "generate_report.py"
        print("\n[Report] ========== 生成报告 ==========")
        subprocess.run(
            [
                sys.executable,
                str(report_script),
                "--reports-dir", str(REPORTS_DIR),
                "--output", str(REPORTS_DIR / "report.md"),
            ],
            cwd=str(ROOT_DIR / "report"),
            check=True,
        )
        print(f"[Report] ✅ 报告已生成：{REPORTS_DIR / 'report.md'}")
    except Exception as e:
        print(f"[Report] ⚠️ 生成报告失败：{e}")


# ============================================================
# 7. 业务逻辑
# ============================================================
class ASRUser(HttpUser):
    host = TARGET
    wait_time = between(2, 5)

    def __init__(self, environment):
        super().__init__(environment)

        # 关键：直接给 client 挂代理，不替换 client 对象，
        # 保留 Locust 自动设置的 base_url（= host = TARGET）
        if USE_PROXY:
            self.client.proxies = {
                "http": PROXY,
                "https": PROXY,
            }
            print(f"[ASRUser] proxy enabled → {PROXY}")
        else:
            print(f"[ASRUser] proxy disabled → {TARGET}")

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
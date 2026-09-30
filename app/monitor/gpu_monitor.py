"""
GPU Monitor

基于 pynvml 采集 NVIDIA GPU 指标：
    - GPU 利用率 (%)
    - 显存使用 (MB) / 总显存 (MB)
    - 温度 (℃)

已知问题：
    在 Windows 笔记本（混合显卡架构）上，pynvml 的
    nvmlDeviceGetUtilizationRates 可能间歇性返回 NVMLError_Unknown。
    本模块对利用率/温度采样单独做了异常保护，失败时降级为 0 / -1，
    不影响显存、也不中断整个监控循环。

推荐安装：
    pip install nvidia-ml-py
（不要装 pynvml，那个包已弃用，会提示 FutureWarning）
"""

import csv
import time
from datetime import datetime

import pynvml


class GPUMonitor:
    def __init__(self, interval=1.0, output_file="gpu_metrics.csv", gpu_index=0):
        self.interval = interval
        self.output_file = output_file
        self.gpu_index = gpu_index
        self._running = False
        self._handle = None
        self._available = False

        # 采样失败提示只打印一次，避免刷屏
        self._warned_util = False
        self._warned_temp = False

        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
            self._available = True

            name = pynvml.nvmlDeviceGetName(self._handle)
            if isinstance(name, bytes):
                name = name.decode()
            print(f"[GPUMonitor] NVML 初始化成功，GPU: {name}")
        except Exception as e:
            print(f"[GPUMonitor] 警告：无法初始化 NVML（{e}），GPU 监控将被跳过")

    # ------------------------------------------------------------
    # 内部：安全获取各项指标
    # ------------------------------------------------------------
    def _read_memory(self) -> tuple[float, float]:
        """显存信息通常最稳定，不单独 try。"""
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
        return mem_info.used / 1024 ** 2, mem_info.total / 1024 ** 2

    def _read_temperature(self) -> int:
        """温度：失败降级为 -1。"""
        try:
            return pynvml.nvmlDeviceGetTemperature(
                self._handle, pynvml.NVML_TEMPERATURE_GPU
            )
        except pynvml.NVMLError as e:
            if not self._warned_temp:
                print(f"[GPUMonitor] 温度采样失败（{e}），后续将以 -1 记录")
                self._warned_temp = True
            return -1

    def _read_utilization(self) -> int:
        """
        利用率：Windows 笔记本上最易失败。
        失败降级为 0，不中断监控。
        """
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            return util.gpu
        except pynvml.NVMLError as e:
            if not self._warned_util:
                print(
                    f"[GPUMonitor] 利用率采样失败（{e}），"
                    f"后续失败的采样将以 0 记录"
                )
                self._warned_util = True
            return 0

    # ------------------------------------------------------------
    # 启停
    # ------------------------------------------------------------
    def start(self):
        """启动监控（在线程中运行）。"""
        if not self._available:
            print("[GPUMonitor] GPU 不可用，监控线程退出")
            return

        self._running = True

        # 写表头
        with open(self.output_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "gpu_utilization_%",
                "memory_used_MB",
                "memory_total_MB",
                "temperature_C",
            ])

        print(f"[GPUMonitor] 开始监控 GPU {self.gpu_index}，写入 {self.output_file}")

        while self._running:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 显存（最稳定，失败则外层 catch）
                mem_used_mb, mem_total_mb = self._read_memory()

                # 温度 & 利用率：各自内部有降级逻辑
                temp = self._read_temperature()
                gpu_util = self._read_utilization()

                with open(self.output_file, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp,
                        gpu_util,
                        round(mem_used_mb, 2),
                        round(mem_total_mb, 2),
                        temp,
                    ])
            except Exception as e:
                # 显存等核心字段失败，只打印不退出
                print(f"[GPUMonitor] 采样失败：{e}")

            time.sleep(self.interval)

        print("[GPUMonitor] 监控线程已退出")

    def stop(self):
        """停止监控并释放 NVML。"""
        self._running = False
        if self._available:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
        print("[GPUMonitor] 监控已停止")


# ------------------------------------------------------------
# 单独运行测试
# ------------------------------------------------------------
if __name__ == "__main__":
    monitor = GPUMonitor(interval=1.0)
    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.stop()
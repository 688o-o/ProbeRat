import csv
import time
from datetime import datetime

import psutil


class SystemMonitor:
    def __init__(self, interval=1.0, output_file="system_metrics.csv"):
        self.interval = interval
        self.output_file = output_file
        self._running = False

    def start(self):
        """启动监控（在线程中运行）"""
        self._running = True

        # 写表头
        with open(self.output_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "cpu_percent", "memory_percent"])

        # 预热：第一次调用返回 0.0，丢弃
        psutil.cpu_percent(interval=None)

        print(f"[SystemMonitor] 开始监控，写入 {self.output_file}")

        while self._running:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent

                with open(self.output_file, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, cpu, mem])
            except Exception as e:
                print(f"[SystemMonitor] 采样失败：{e}")

            time.sleep(self.interval)

        print("[SystemMonitor] 监控线程已退出")

    def stop(self):
        self._running = False
        print("[SystemMonitor] 监控已停止")


if __name__ == "__main__":
    monitor = SystemMonitor(interval=1.0)
    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.stop()
from locust import LoadTestShape


class StepLoadShape(LoadTestShape):
    """
    阶梯加压：
      0-60s    → 5 users
      60-120s  → 10 users
      120-180s → 20 users
      180-240s → 30 users
      240-300s → 50 users
      300-360s → 50 users（保持 60 秒，观察峰值稳定性）
      > 360s   → 结束
    """

    stages = [
        (60, 5),
        (120, 10),
        (180, 20),
        (240, 30),
        (300, 50),
        (360, 50),   # 保持在 50 并发再压 60 秒
    ]

    spawn_rate = 2

    def tick(self):
        run_time = self.get_run_time()
        for duration, users in self.stages:
            if run_time < duration:
                return (users, self.spawn_rate)
        return None
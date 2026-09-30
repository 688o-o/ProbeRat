"""
弱网场景：随机延迟
每个请求随机延迟 0.5 ~ 5 秒，更接近真实网络抖动。
"""

import random
import time

from mitmproxy import http


MIN_DELAY = 0.5
MAX_DELAY = 5.0
TARGET_HOST = "127.0.0.1"


def request(flow: http.HTTPFlow) -> None:
    if TARGET_HOST not in flow.request.pretty_host:
        return

    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    print(f"[delay] {flow.request.method} {flow.request.pretty_url} → sleep {delay:.2f}s")
    time.sleep(delay)
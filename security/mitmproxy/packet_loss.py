"""
弱网场景：丢包
随机 20% 请求直接掐断，模拟丢包。
"""

import random

from mitmproxy import http


DROP_RATE = 0.2
TARGET_HOST = "127.0.0.1"


def request(flow: http.HTTPFlow) -> None:
    if TARGET_HOST not in flow.request.pretty_host:
        return

    if random.random() < DROP_RATE:
        print(f"[packet_loss] DROP {flow.request.pretty_url}")
        flow.kill()
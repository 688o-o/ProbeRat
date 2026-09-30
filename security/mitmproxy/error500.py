"""
弱网场景：服务端异常
随机 10% 请求直接返回 500。
"""

import random

from mitmproxy import http


INJECT_RATE = 0.1
TARGET_HOST = "127.0.0.1"
ERROR_BODY = b'{"code": 50000, "message": "Injected 500 by mitmproxy", "data": null}'


def request(flow: http.HTTPFlow) -> None:
    if TARGET_HOST not in flow.request.pretty_host:
        return

    if random.random() < INJECT_RATE:
        print(f"[error500] INJECT 500 → {flow.request.pretty_url}")
        flow.response = http.Response.make(
            500,
            ERROR_BODY,
            {"Content-Type": "application/json"},
        )
"""
弱网场景：超时
让请求挂起 30 秒，触发客户端 timeout。
"""

import time

from mitmproxy import http


TIMEOUT_SECONDS = 30.0
TARGET_HOST = "127.0.0.1"


def request(flow: http.HTTPFlow) -> None:
    if TARGET_HOST not in flow.request.pretty_host:
        return

    print(f"[timeout] hang {TIMEOUT_SECONDS}s → {flow.request.pretty_url}")
    time.sleep(TIMEOUT_SECONDS)
"""
ProbeRat 压测配置
"""

# ---- 目标服务 ----
TARGET = "http://127.0.0.1:8001"

# ---- 代理开关 ----
# False → Locust 直连 FastAPI（正常压测）
# True  → Locust 走 mitmproxy（弱网压测）
USE_PROXY = True
PROXY = "http://127.0.0.1:8080"

# ---- 输出目录（相对 ROOT_DIR） ----
REPORTS_DIR_NORMAL = "report/reports"
REPORTS_DIR_WEAKNET = "report/reports_weaknet"


def effective_host() -> str:
    return PROXY if USE_PROXY else TARGET


def effective_reports_dir() -> str:
    return REPORTS_DIR_WEAKNET if USE_PROXY else REPORTS_DIR_NORMAL
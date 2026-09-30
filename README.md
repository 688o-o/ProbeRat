# 🐭 ProbeRat

> **AI Reliability Engineering Platform**
>
> _Probe before Production._

ProbeRat 是一个面向 AI 服务（ASR / TTS / LLM）的**可靠性工程平台**，覆盖 **功能验证 → 性能压测 → 弱网故障注入 → 监控采集 → 自动报告** 的完整链路。

---

## ✨ 核心能力

| 模块                 | 能力                                                                  |
| -------------------- | --------------------------------------------------------------------- |
| **ASR Service**      | 基于 FastAPI + FunASR 封装 ASR 接口，统一异常体系、请求追踪、输入校验 |
| **Stress Testing**   | 基于 Locust 实现阶梯加压（5 → 50 并发），自定义 `LoadTestShape`       |
| **Observability**    | 自研 GPU / CPU 双维度监控（`pynvml` + `psutil`），压测期间每秒采样    |
| **Fault Injection**  | 基于 mitmproxy 注入弱网故障：延迟、丢包、5xx、超时                    |
| **Report Generator** | 读取 Locust + GPU + System CSV，自动生成 Markdown 报告并给出瓶颈诊断  |
| **Containerization** | Docker + Docker Compose，`docker compose up` 一键部署                 |

---

## 📊 压测亮点

在 RTX 4050 Laptop 上对 FunASR ASR 服务做阶梯加压（5 → 50 并发）：

| 指标           | 正常压测 | 弱网压测（随机延迟 0.5~5s） |
| -------------- | -------- | --------------------------- |
| 失败率         | 0%       | **6.60%**                   |
| P95            | 14 s     | **120 s**                   |
| GPU 平均利用率 | 26%      | 6.7%                        |
| CPU 平均利用率 | 8%       | 3.1%                        |
| RPS            | 2.96     | 0.29                        |

**核心发现**：GPU 只有 26%、CPU 只有 8%，但 P95 已达 14 秒 —— **资源远未饱和，瓶颈在服务端推理调度（串行推理）**。

> 这份"资源未饱和但吞吐饱和"的诊断，是 ProbeRat 自动分析给出的结论，无需人工判断。

---

## 🧪 弱网测试矩阵（mitmproxy）

| 场景     | 脚本                                | 用途                      |
| -------- | ----------------------------------- | ------------------------- |
| 随机延迟 | `security/mitmproxy/delay.py`       | 验证客户端超时 / 重试逻辑 |
| 500 注入 | `security/mitmproxy/error500.py`    | 验证上游 5xx 处理         |
| 丢包     | `security/mitmproxy/packet_loss.py` | 验证弱网下服务稳定性      |
| 超时     | `security/mitmproxy/timeout.py`     | 验证超时上限              |

**架构**：
Locust ──▶ mitmproxy(8080) ──▶ FastAPI(8001) ──▶ FunASR
│
└── fault injection: delay / 500 / drop / timeout

---

## 📁 项目结构

```
ProbeRat
├─ .dockerignore
├─ app
│  ├─ api
│  │  ├─ asr
│  │  │  └─ transcribe.py
│  │  ├─ health.py
│  │  ├─ llm
│  │  └─ tts
│  ├─ config
│  │  └─ settings.py
│  ├─ core
│  │  ├─ deps.py
│  │  └─ exceptions.py
│  ├─ main.py
│  ├─ models
│  │  └─ response.py
│  ├─ monitor
│  │  ├─ gpu_monitor.py
│  │  └─ system_monitor.py
│  ├─ service
│  │  ├─ asr
│  │  │  ├─ funasr_client.py
│  │  │  └─ funasr_service.py
│  │  ├─ llm
│  │  └─ tts
│  ├─ stress
│  │  ├─ config.py
│  │  ├─ load_shape.py
│  │  ├─ locustfile.py
│  │  └─ locustfile_weaknet.py
│  └─ utils
├─ docker-compose.yml
├─ Dockerfile
├─ README.md
├─ report
│  ├─ generate_report.py
│  └─ template.md
├─ requirements.txt
├─ security
│  └─ mitmproxy
│     ├─ delay.py
│     ├─ error500.py
│     ├─ packet_loss.py
│     └─ timeout.py
├─ tests
└─ test_funasr.py

```

---

## 🚀 快速开始

### 方式 1：Docker（推荐）

git clone https://github.com/<your-name>/ProbeRat.git
cd ProbeRat
cp .env.example .env # 按需修改 FUNASR_URL
docker compose up -d
curl http://127.0.0.1:8001/health/

### 方式 2：本地运行

# 1. 创建环境

conda create -n proberat python=3.12
conda activate proberat
pip install -r requirements.txt

# 2. 配置

cp .env.example .env

# 3. 启动 FastAPI

uvicorn app.main:app --reload --port 8001

# 4. 跑压测（另开终端）

locust -f app/stress/locustfile.py --headless --only-summary \
 --csv=report/reports/locust_result

🔧 环境说明（两套独立环境）
环境 用途 依赖
proberat 应用 + 压测 + 报告 见 requirements.txt
mitm 弱网测试（mitmproxy） 独立安装
为什么分开？ mitmproxy 与 FastAPI 对 typing_extensions 的版本要求冲突，隔离环境可避免依赖打架。

# mitm 环境

conda create -n mitm python=3.12
conda activate mitm
pip install mitmproxy
mitmdump -s security/mitmproxy/delay.py

📌 版本
v1.1.0 — Docker 化完成

v1.0.0 — 核心能力（FastAPI + Locust + Monitor + mitmproxy + Report）

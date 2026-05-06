# AngeVoice

> 轻量级中文 TTS 自托管服务。AngeVoice 基于 Kokoro v1.1 中文模型做工程化封装，提供 OpenAI 兼容 API、WebSocket 逐段流式、新版 Studio Web UI、中文文本规则、批量合成、缓存、统计和 Docker CPU/GPU/老显卡部署。

[English](README_EN.md) | 中文

[![CI](https://github.com/ang77712829/AngeVoice/actions/workflows/ci.yml/badge.svg)](https://github.com/ang77712829/AngeVoice/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 项目定位

AngeVoice 不是重新训练的新模型，而是围绕 Kokoro v1.1 中文模型做的服务化封装。目标是让本地部署、内网调用、OpenAI 风格接入、网页流式播放和 Docker 自托管更简单。

适合：

- 本地/NAS/家用服务器中文语音合成服务
- Agent、阅读器、有声书、配音工具的 TTS 后端
- OpenAI 兼容 TTS API 后端
- 需要逐段播放、停止生成、批量导出 ZIP 的 Web 应用
- CPU、NVIDIA GPU、Legacy GPU/保守 CUDA 环境

> 模型来源：本项目基于 Kokoro v1.1 / Kokoro-82M 及其中文模型构建。模型版权、许可证与限制请以原模型仓库为准。

## 功能亮点

| 能力 | 说明 |
|---|---|
| OpenAI 兼容 API | `POST /v1/audio/speech`，兼容 `model/input/voice/speed/response_format` |
| Studio Web UI | 内置前端页面，支持亮/暗主题、音色筛选、收藏、试听、流式播放、停止生成、API Key 设置和可折叠统计卡片 |
| 中文文本规则 | 自动断句标点、jieba 分词优先、内置兜底词典、常见多音字上下文修正 |
| WebSocket 流式 | `ws://.../ws/v1/tts` 逐段推送，支持 `cancel` / `stop` 控制帧 |
| 批量合成 | `POST /v1/audio/batch` 返回 ZIP 和 `manifest.json` |
| 服务治理 | 请求 ID、`/health`、`/stats`、`/requests`、超时、并发限制、LRU 缓存 |
| 管理接口 | 可选缓存清理、音色列表、`.pt` 音色上传 |
| 输出格式 | WAV、PCM s16le，可选 MP3，MP3 依赖 ffmpeg |
| Docker | CPU、GPU、Legacy GPU 三套 Compose 画像 |
| CLI | 推荐 `angevoice`，旧命令 `kokoro-tts` 继续兼容 |

## v2.5 模块化重构

v2.5 将原来较重的 `server.py` 拆成独立模块，保留原有对外入口：

```text
src/kokoro_tts/
├── server.py             # FastAPI 应用装配：create_app / run_server
├── service_state.py      # 运行时状态、缓存、统计、并发、合成调度
├── security.py           # HTTP / WebSocket API Key 校验
├── api_models.py         # Pydantic 请求模型
├── routes/
│   ├── status.py         # /, /health, /stats, /requests, voices, cancel
│   ├── audio.py          # /v1/audio/speech 与 /api/tts
│   └── ws.py             # /ws/v1/tts
├── service_extras.py     # batch/admin/mp3 扩展接口
├── zh_rules.py           # 中文自动断句、多音字与轻量分词规则
├── engine.py             # Kokoro 引擎、分段、文本规范化、音频编码
├── config.py             # 配置与环境变量
├── templates/index.html  # Studio Web UI shell
└── static/               # Studio Web UI 样式与脚本
```

兼容性说明：

- Python import 包名仍为 `kokoro_tts`，避免破坏旧代码。
- 发行包名/项目品牌改为 `angevoice`。
- CLI 新增 `angevoice`，旧 `kokoro-tts` 保留为 alias。
- Kokoro 模型加载不依赖发行包名，而依赖上游 `kokoro` 库、模型目录、模型文件名与 Hugging Face repo，因此改项目名不会影响模型加载。

## 快速开始

### Docker GPU

```bash
git clone https://github.com/ang77712829/AngeVoice.git
cd AngeVoice/docker/gpu
sudo docker compose up -d
```

默认访问：`http://localhost:8101`

```bash
curl http://127.0.0.1:8101/health
curl http://127.0.0.1:8101/stats
```

### Docker CPU / Legacy GPU

```bash
# CPU，默认端口 8100
cd docker/cpu && sudo docker compose up -d

# Legacy GPU，默认端口 8102，CUDA 11.8
cd docker/legacy-gpu && sudo docker compose up -d
```

本地构建：

```bash
sudo docker compose up -d --build
```

### pip 开发安装

```bash
git clone https://github.com/ang77712829/AngeVoice.git
cd AngeVoice
pip install -e .

angevoice serve --port 8000
angevoice synth "你好世界" -o hello.wav -v zm_010
angevoice voices

# 旧命令仍可用
kokoro-tts serve --port 8000
```

## API 示例

### OpenAI 兼容 TTS

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"你好世界","voice":"zm_010","response_format":"wav"}' \
  --output output.wav
```

启用 `KOKORO_API_KEY` 后增加：

```bash
-H "Authorization: Bearer YOUR_TOKEN"
```

支持格式：`wav`、`pcm`、`mp3`。MP3 需开启 `KOKORO_MP3_ENABLED=true` 且环境存在 ffmpeg。

### WebSocket 流式播放

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/v1/tts");

ws.onopen = () => {
  ws.send(JSON.stringify({
    text: "你好世界，这是一段流式合成测试。",
    voice: "zm_010",
    speed: 1.0,
    format: "pcm_s16le",
    binary: false,
    token: "YOUR_TOKEN" // 未启用 KOKORO_API_KEY 时可省略
  }));
};

ws.send(JSON.stringify({ type: "cancel" }));
```

消息类型：`started`、`audio`、`segment_error`、`done`、`cancelled`、`error`。

JSON 音频帧使用 `data` 字段携带 base64 PCM；如果启用 binary 模式，服务会先发送元信息 JSON，再发送二进制音频帧。

### 中文规则示例

AngeVoice 会在进入 Kokoro pipeline 前做轻量中文规则处理：

```text
春花秋月何时了 -> 春花秋月何时瞭。
我想了解一下 -> 我想瞭解一下
银行行长正在听音乐 -> 银杭杭掌正在听音悦
会议12:01开始 -> 会议十二点零一分开始
长中文无标点文本 -> 按词切分后补入停顿标点
```

规则目标是改善常见朗读错误，而不是替代完整中文 NLP。更复杂的人名、地名和专有名词建议在调用侧显式加标点或使用后续 SSML/词典能力。

### 批量合成 ZIP

```bash
curl -X POST http://localhost:8000/v1/audio/batch \
  -H "Content-Type: application/json" \
  -d '{"voice":"zm_010","speed":1.0,"response_format":"wav","items":[{"text":"第一段","filename":"001"},{"text":"第二段","filename":"002"}]}' \
  --output batch.zip
```

## 模型文件

首次运行时，如果本地没有完整模型文件，服务会自动从 Hugging Face 下载。离线部署或想提升冷启动速度，建议手动准备：

```bash
pip install huggingface_hub
huggingface-cli download hexgrad/Kokoro-82M-v1.1-zh \
  --local-dir models/ \
  --include "config.json" "kokoro-v1_1-zh.pth" "voices/*.pt"
```

至少需要：

```text
models/config.json
models/kokoro-v1_1-zh.pth
models/voices/*.pt
```

普通 `git clone` 可能只拿到 Git LFS 指针文件，不一定是真实模型文件。Docker Compose 已持久化 Hugging Face 缓存，避免容器重建后重复下载。

## 常用配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `KOKORO_MODEL_DIR` | `./models` | 模型目录 |
| `KOKORO_HOST` | `0.0.0.0` | 监听地址 |
| `KOKORO_PORT` | `8000` | 服务端口 |
| `KOKORO_DEVICE` | `auto` | `auto` / `cpu` / `cuda` |
| `KOKORO_WORKERS` | `1` | Uvicorn worker 数；GPU 建议保持 1 |
| `KOKORO_MAX_CONCURRENT_REQUESTS` | `1` | 单进程最大合成并发 |
| `KOKORO_REQUEST_TIMEOUT_SECONDS` | `300` | 单次合成超时 |
| `KOKORO_MAX_TEXT_LENGTH` | `10000` | 单次请求最大文本长度 |
| `KOKORO_SEGMENT_LENGTH` | `100` | 文本切分目标长度 |
| `KOKORO_DEFAULT_VOICE` | `zm_010` | 默认音色 |
| `KOKORO_STREAM_BINARY_ENABLED` | `true` | 是否允许 binary 音频帧 |
| `KOKORO_CACHE_ENABLED` | `true` | 是否启用内存 LRU 缓存 |
| `KOKORO_BATCH_ENABLED` | `true` | 是否启用批量合成 |
| `KOKORO_ADMIN_ENABLED` | `false` | 是否启用管理接口 |
| `KOKORO_VOICE_UPLOAD_ENABLED` | `false` | 是否允许上传音色 |
| `KOKORO_MP3_ENABLED` | `false` | 是否启用 MP3 输出 |
| `KOKORO_API_KEY` | - | 设置后启用 Bearer 认证；`change-me` 等占位值会被拒绝 |
| `KOKORO_CORS_ORIGINS` | `http://localhost:8000` | CORS 允许来源，逗号分隔 |

## 安全说明

- 公网部署建议设置 `KOKORO_API_KEY`，并在反向代理层限制来源。
- 管理接口默认关闭；开启 `KOKORO_ADMIN_ENABLED=true` 时必须设置强 API Key，否则服务会拒绝启动。
- `.pt` 音色上传默认关闭。只上传可信来源文件；PyTorch 权重文件不应来自不可信渠道。
- 不建议把 `/admin/*` 直接暴露到公网。
- `cancel/stop` 会阻止后续段落继续推送；如果当前段已进入同步推理，通常会在当前段结束后停止。

详见 [安全说明](docs/SECURITY.md)。

## 已知限制

- AngeVoice 不是独立训练的新模型，音质、许可证和语言能力受 Kokoro 上游模型影响。
- 长文本依赖分段合成，极长文本建议走批量/任务队列工作流。
- GPU 场景下不建议多 worker 同时加载模型，容易造成显存占用翻倍。
- MP3 输出依赖 ffmpeg。
- WebSocket 是逐段流式，不是模型内部 token 级真实流式。

## 测试

```bash
pip install -e '.[dev]'
pytest -q --cov=kokoro_tts --cov-report=term-missing
```

服务冒烟测试：

```bash
chmod +x scripts/smoke_test.sh scripts/loop_test.sh
BASE_URL=http://127.0.0.1:8101 ./scripts/smoke_test.sh
N=50 BASE_URL=http://127.0.0.1:8101 ./scripts/loop_test.sh
```

## 文档

- [架构说明](docs/ARCHITECTURE.md)
- [安全说明](docs/SECURITY.md)
- [排障手册](docs/TROUBLESHOOTING.md)
- [服务画像](docs/SERVICE_PROFILES.md)
- [v2.5 功能说明](docs/V2_5_FEATURES.md)
- [路线图](docs/ROADMAP.md)
- [Legacy GPU 部署说明](docker/legacy-gpu/README.md)

## License

MIT

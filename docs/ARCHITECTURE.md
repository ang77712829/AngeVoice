# AngeVoice 架构说明 / Architecture

本文档说明 AngeVoice v2.5 的模块化结构。v2.5 的目标不是改变模型能力，而是提升服务端可维护性、可测试性和后续扩展空间。

## 设计目标

- 保留 `kokoro_tts.server.create_app()` 与 `run_server()` 对外入口。
- 保留 `kokoro_tts` import 包名，避免破坏旧脚本。
- 新增 `angevoice` CLI，同时保留 `kokoro-tts` 兼容命令。
- 将原本集中的 `server.py` 拆成状态、鉴权、数据模型和路由模块。
- 批量、管理、MP3 等扩展继续通过 `service_extras.py` 注册。
- 内置 Studio Web UI 拆分为模板和静态资源，便于 Docker 热更新与包分发。
- 中文文本规则独立放入 `zh_rules.py`，避免把分词/多音字逻辑散落在引擎内。

## 模块布局

```text
src/kokoro_tts/
├── server.py             # FastAPI app factory，只负责装配
├── service_state.py      # 运行时状态、缓存、统计、请求队列、合成调度
├── security.py           # HTTP Bearer 与 WebSocket token 校验
├── api_models.py         # Pydantic 请求模型
├── routes/
│   ├── status.py         # /, /health, /stats, /requests, voices, cancel
│   ├── audio.py          # /v1/audio/speech, /api/tts
│   └── ws.py             # /ws/v1/tts
├── service_extras.py     # batch/admin/mp3 扩展接口
├── zh_rules.py           # 中文断句、多音字、轻量分词规则
├── engine.py             # Kokoro 引擎、分段、文本规范化、音频编码
├── config.py             # 配置和环境变量
├── cli.py                # angevoice / kokoro-tts CLI
├── templates/index.html  # Studio Web UI HTML shell
└── static/               # Studio Web UI CSS/JS
```

## 请求路径

### HTTP 合成

1. `routes/audio.py` 接收 `/v1/audio/speech` 或 `/api/tts` 请求。
2. `api_models.py` 校验 OpenAI 风格请求体。
3. `service_state.py` 记录 request id、排队状态、统计和缓存。
4. `engine.py` 清洗文本，调用 `zh_rules.py` 做中文标点/多音字规则，分段后调用 Kokoro pipeline 并编码音频。
5. `routes/audio.py` 返回 `StreamingResponse`，响应头包含 `X-Request-ID`。

### WebSocket 流式

1. `routes/ws.py` 接收首个 JSON 消息，读取 `text/voice/speed/format/binary/token`。
2. `security.py` 校验 WebSocket token 或 Authorization header。
3. `service_state.py` 用同一个并发信号量保护推理。
4. `engine.py` 逐段生成 `started/audio/segment_error/done` 消息。
5. 客户端发送 `cancel` 或 `stop` 后，服务停止后续段落推送。

## 状态对象

`ServiceState` 是当前进程内的运行时状态中心，包含：

- `tts_semaphore`：推理并发限制。
- `tts_cache`：内存 LRU 音频缓存。
- `active_requests`：最近请求状态。
- `cancelled_requests`：取消标记集合。
- `stats`：基础统计计数。

`tts_cache` 使用线程锁保护，因为同步合成路径会在线程池中运行，多请求并发时会同时读写 LRU 缓存。

这些状态是进程内状态。如果使用多个 worker，每个 worker 会有独立状态、独立模型和独立缓存。`run_server()` 在 `KOKORO_WORKERS>1` 时使用 Uvicorn import string + factory 模式启动，避免多 worker 启动失败。GPU 部署通常仍建议 `KOKORO_WORKERS=1`。

## Studio Web UI

`routes/status.py` 的首页路由会注入 bootstrap JSON，包含音色列表、默认音色、最大文本长度、采样率、认证和流式能力。前端静态资源由 `/static/app.css` 和 `/static/app.js` 提供，不需要额外构建步骤。

启用 `KOKORO_API_KEY` 时，Studio 设置面板保存的 Bearer Token 会同时用于 HTTP 请求和 WebSocket 首个 JSON 消息。

## 包名与模型加载关系

发行包名改为 `angevoice` 不会影响 Kokoro 模型加载。模型加载主要依赖：

- 上游 Python 包：`kokoro`
- Hugging Face repo：`hexgrad/Kokoro-82M-v1.1-zh`
- 本地模型文件：`models/kokoro-v1_1-zh.pth`
- 本地配置文件：`models/config.json`
- 音色目录：`models/voices/*.pt`

项目品牌名、发行包名和 CLI 名称不参与模型权重解析。

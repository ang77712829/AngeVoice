# v2.5 服务功能说明

v2.5 在 v2.4 功能基础上完成服务端模块化重构、中文规则补强、Studio Web UI 刷新和安全启动校验，并统一项目品牌为 AngeVoice。批量合成、管理接口、可选 MP3、WebSocket 取消能力保持兼容。

## v2.5 新增/调整

| 项目 | 说明 |
|---|---|
| 模块化服务端 | `server.py` 拆分为 `service_state.py`、`security.py`、`api_models.py`、`routes/*` |
| 多 worker 启动修复 | `KOKORO_WORKERS>1` 时使用 Uvicorn import string + factory 模式启动 |
| 并发缓存修复 | TTS LRU 缓存新增线程锁，避免多请求并发读写 `OrderedDict` |
| 中文规则 | 新增 `zh_rules.py`，支持自动停顿标点、jieba 分词优先和常见多音字上下文修正 |
| Studio Web UI | 前端拆分为 `templates/index.html`、`static/app.css`、`static/app.js`，支持亮/暗主题、API Key、流式播放、可折叠统计卡片、音色筛选/收藏 |
| Docker 热更新修复 | Docker 镜像改为 editable install，Compose 挂载模板和 static 目录，CPU/GPU/Legacy GPU 路径一致 |
| 安全启动校验 | 管理接口必须搭配强 API Key；占位 API Key 会被拒绝 |
| CLI 品牌统一 | 新增 `angevoice` 命令，保留 `kokoro-tts` alias |
| 发行包名 | `pyproject.toml` 项目名改为 `angevoice`，import 包名仍保留 `kokoro_tts` |
| 文档补强 | 新增架构、安全、排障文档，README 中英文重写 |
| CI 补强 | CLI smoke check 覆盖 `angevoice` 与 `kokoro-tts` |

## 功能总览

| 功能 | 接口/配置 | 默认状态 |
|---|---|---|
| OpenAI 兼容合成 | `POST /v1/audio/speech` | 开启 |
| 旧版兼容接口 | `POST/GET /api/tts` | 开启 |
| WebSocket 流式 | `GET /ws/v1/tts` | 开启 |
| 批量合成 ZIP | `POST /v1/audio/batch` | 开启 |
| 支持格式查询 | `GET /v1/audio/formats` | 开启 |
| 清理缓存 | `DELETE /admin/cache` | 管理接口关闭 |
| 查看音色目录 | `GET /admin/voices` | 管理接口关闭 |
| 上传 `.pt` 音色 | `POST /admin/voices/upload` | 上传关闭 |
| MP3 输出 | `response_format=mp3` | 关闭 |
| WebSocket 取消 | `{"type":"cancel"}` / `{"type":"stop"}` | 开启 |

## 中文文本规则

`engine.normalize_text_for_tts()` 会在数字/单位规则后调用 `normalize_chinese_rules()`：

```text
春花秋月何时了 -> 春花秋月何时瞭。
我想了解一下 -> 我想瞭解一下。
银行行长正在听音乐 -> 银杭杭掌正在听音悦
会议12:43开始 -> 会议十二点四十三分开始
长中文无标点文本 -> 按词切分后补入停顿标点
```

分词优先使用 `jieba`，不可用时使用内置小词典兜底。多音字规则以短语和上下文匹配为主，明确场景会替换为同音提示字来引导 G2P。规则是保守增强，目标是减少常见朗读错误，不替代完整中文 NLP。

## Studio Web UI

新版 Web UI 保持零构建链，适合直接随 Python 包和 Docker 镜像分发：

- `/` 注入服务端 bootstrap 数据，包含音色、默认音色、采样率、认证和流式能力。
- `/static/app.css` 提供液态玻璃背景、亮/暗主题、启动动画、面板 spotlight/glare 效果。
- `/static/app.js` 负责 API Key、WebSocket 流式播放、HTTP 兜底合成、取消、统计和音色库交互。
- 启用 `KOKORO_API_KEY` 后，前端可在设置面板保存 Bearer Token，并同时用于 HTTP 与 WebSocket 首包。

## 批量合成 ZIP

```http
POST /v1/audio/batch
```

请求示例：

```json
{
  "voice": "zm_010",
  "speed": 1.0,
  "response_format": "wav",
  "items": [
    {"text": "第一段", "filename": "001"},
    {"text": "第二段", "filename": "002", "voice": "zf_001"}
  ]
}
```

返回 `application/zip`，包含每条音频文件和 `manifest.json`。

限制项：

```bash
KOKORO_BATCH_ENABLED=true
KOKORO_BATCH_MAX_ITEMS=20
KOKORO_BATCH_CONCURRENCY=1
```

## 管理接口

管理接口默认关闭。开启时建议同时设置 API Key：

```bash
KOKORO_ADMIN_ENABLED=true
KOKORO_API_KEY=<paste-generated-token-here>
```

接口：

```http
DELETE /admin/cache
GET /admin/voices
POST /admin/voices/upload
```

上传音色还需要额外开启：

```bash
KOKORO_VOICE_UPLOAD_ENABLED=true
```

Docker 场景下需要将 voices 目录挂载为可写：

```yaml
- ../../models/voices:/app/models/voices:rw
```

安全建议：公网部署时不要裸开管理接口，至少设置 `KOKORO_API_KEY`，并通过反向代理限制来源。

## MP3 可选转码

MP3 默认关闭。开启前需要环境里存在 `ffmpeg`，官方 CPU/GPU Dockerfile 已包含该依赖。

```bash
KOKORO_MP3_ENABLED=true
KOKORO_MP3_BITRATE=192k
```

请求示例：

```json
{"response_format":"mp3"}
```

开启后返回 `audio/mpeg`。未开启时请求 `mp3` 会返回清晰的 400 错误，避免伪装格式。

## WebSocket 主动取消

流式合成过程中，客户端可以发送控制帧：

```json
{"type":"cancel"}
```

或：

```json
{"type":"stop"}
```

服务端会停止后续段落推送，并在 `/requests` 中记录 `cancelled` 状态。当前段落如果已经进入同步推理，会在当前段完成后停止后续段。

## 模块化后的开发建议

- 新增普通 HTTP 路由：优先放入 `routes/audio.py` 或新增 `routes/*.py`。
- 新增运行时共享状态：放入 `ServiceState`，避免在多个路由中重复维护全局变量。
- 新增鉴权逻辑：放入 `security.py`。
- 新增请求模型：放入 `api_models.py`。
- 批量/管理/MP3 后续可从 `service_extras.py` 继续拆分。

# API Reference / API 参考

This document is the hand-maintained API reference for AngeVoice v2.6.x. It
covers the built-in Studio UI, OpenAI-compatible HTTP synthesis, legacy
compatibility endpoints, model switching, MOSS-TTS-Nano reference-audio clone
mode, WebSocket streaming, batch export, and optional admin APIs.

本文档是 AngeVoice v2.6.x 的人工维护 API 参考，覆盖内置 Studio UI、
OpenAI 兼容 HTTP 合成、旧版兼容接口、模型切换、MOSS-TTS-Nano
参考音频克隆、WebSocket 流式、批量导出和可选管理接口。

## Base URLs / 调用地址

| Profile / 画像 | HTTP / Web UI | WebSocket |
|---|---|---|
| pip / development | `http://localhost:8000` | `ws://localhost:8000/ws/v1/tts` |
| Docker CPU | `http://localhost:8100` | `ws://localhost:8100/ws/v1/tts` |
| Docker GPU | `http://localhost:8101` | `ws://localhost:8101/ws/v1/tts` |
| Docker Legacy GPU / 老架构GPU | `http://localhost:8102` | `ws://localhost:8102/ws/v1/tts` |

Examples use:

```bash
BASE_URL=http://localhost:8000
WS_URL=ws://localhost:8000/ws/v1/tts
```

Docker users only need to replace the port. For a remote NAS, use the NAS host
or IP address, for example `http://192.168.1.2:8101`.

Docker 部署时只需要替换端口。远程 NAS 部署时，把 `localhost` 换成 NAS
主机名或 IP，例如 `http://192.168.1.2:8101`。

## Authentication / 鉴权

When `KOKORO_API_KEY` is empty, local trusted deployments can call APIs without
a token. When it is set, HTTP APIs require:

```bash
-H "Authorization: Bearer YOUR_TOKEN"
```

WebSocket clients can send the same token either through the `Authorization`
header or in the first JSON message:

```json
{
  "text": "你好世界",
  "voice": "zm_010",
  "token": "YOUR_TOKEN"
}
```

内置 Studio Web UI 会在设置面板保存 Bearer Token，并同时用于 HTTP 请求和
WebSocket 首包。

## Endpoint Matrix / 接口矩阵

| Method | Path | Description / 说明 | Auth |
|---|---|---|---|
| `GET` | `/` | Studio Web UI | No |
| `GET` | `/health` | Service health, current model, voices, stream capability | No |
| `GET` | `/stats` | Metrics snapshot | Yes when `KOKORO_API_KEY` is set |
| `GET` | `/requests` | Recent request states | Yes when `KOKORO_API_KEY` is set |
| `GET` | `/v1/models` | List enabled models and current model | No |
| `GET` | `/v1/models/current` | Current model metadata | No |
| `POST` | `/v1/models/switch` | Load and switch current model | Yes |
| `POST` | `/v1/models/{model_id}/load` | Warm-load a model | Yes |
| `POST` | `/v1/models/{model_id}/unload` | Unload a loaded model | Yes |
| `GET` | `/v1/audio/voices` | List voices, optional `?model=` | No |
| `GET` | `/v1/audio/formats` | List supported output formats | No |
| `POST` | `/v1/audio/speech` | OpenAI-compatible speech synthesis | Yes when `KOKORO_API_KEY` is set |
| `GET` | `/api/tts` | Legacy query-string speech synthesis | Yes when `KOKORO_API_KEY` is set |
| `POST` | `/api/tts` | Legacy JSON/form speech synthesis; multipart supports MOSS clone | Yes when `KOKORO_API_KEY` is set |
| `WS` | `/ws/v1/tts` | Streaming synthesis; first message carries request fields | Yes when `KOKORO_API_KEY` is set |
| `POST` | `/v1/audio/batch` | Batch synthesis ZIP with `manifest.json` | Yes when `KOKORO_API_KEY` is set |
| `POST` | `/v1/audio/requests/{request_id}/cancel` | Mark an active request as cancelling | Yes when `KOKORO_API_KEY` is set |
| `DELETE` | `/admin/cache` | Clear in-memory synthesis cache | Admin enabled + API key |
| `GET` | `/admin/voices` | Inspect local Kokoro voice directory | Admin enabled + API key |
| `POST` | `/admin/voices/upload` | Upload trusted `.pt` Kokoro voice files | Admin enabled + upload enabled + API key |

## Model IDs / 模型 ID

| Model ID | Description / 说明 | Notes |
|---|---|---|
| `kokoro` | Kokoro v1.1 Chinese, default startup engine | Low resource use, mechanical but stable |
| `moss-nano-cpu` | MOSS-TTS-Nano ONNX on CPU | Available in CPU/GPU/legacy Docker profiles |
| `moss-nano-cuda` | MOSS-TTS-Nano ONNX on CUDA | Experimental; enabled by default only in the modern GPU profile |

Aliases such as `moss` and `moss-nano` resolve according to
`MOSS_EXECUTION_PROVIDER`. CPU and legacy profiles hide `moss-nano-cuda` by
default for stability.

MOSS exposes two modes:

- `preset_voice`: choose a built-in MOSS voice such as `Junhao`.
- `voice_clone`: upload a short reference audio file through `/api/tts` or the
  first WebSocket message. The Studio UI only shows the upload control when the
  selected model declares `voice_clone_supported=true`.

## Status and Discovery / 状态与发现

```bash
curl "$BASE_URL/health"
curl "$BASE_URL/stats"
curl "$BASE_URL/requests"
curl "$BASE_URL/v1/audio/formats"
```

List voices for the current model or a specific model:

```bash
curl "$BASE_URL/v1/audio/voices"
curl "$BASE_URL/v1/audio/voices?model=moss-nano-cpu"
```

List, load, switch, and unload models:

```bash
curl "$BASE_URL/v1/models"
curl "$BASE_URL/v1/models/current"

curl -X POST "$BASE_URL/v1/models/moss-nano-cpu/load" \
  -H "Authorization: Bearer YOUR_TOKEN"

curl -X POST "$BASE_URL/v1/models/switch" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"model":"moss-nano-cpu","unload_previous":true}'

curl -X POST "$BASE_URL/v1/models/moss-nano-cpu/unload" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

`unload_previous=true` releases the old engine after switching and clears the
audio cache. For GPU/NAS deployments this is usually the recommended behavior.

## OpenAI-Compatible Speech / OpenAI 兼容合成

Endpoint:

```http
POST /v1/audio/speech
Content-Type: application/json
```

Request fields:

| Field | Type | Default | Notes |
|---|---|---|---|
| `model` | string | `kokoro` | `kokoro`, `moss-nano-cpu`, `moss-nano-cuda`, or alias |
| `input` | string | required | Text to synthesize. `text` is accepted as an alias |
| `voice` | string | `zm_010` | Kokoro voice ID or MOSS preset voice |
| `speed` | number | `1.0` | Range `0.5` to `2.0` |
| `response_format` | string | `wav` | `wav`, `pcm`, or `mp3` when enabled |

Kokoro example:

```bash
curl -X POST "$BASE_URL/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"model":"kokoro","input":"你好世界","voice":"zm_010","speed":1.0,"response_format":"wav"}' \
  --output kokoro.wav
```

MOSS preset voice example:

```bash
curl -X POST "$BASE_URL/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"model":"moss-nano-cpu","input":"派大星，我们一起去抓水母吧。","voice":"Junhao","response_format":"wav"}' \
  --output moss.wav
```

Response:

- Body: audio bytes.
- `Content-Type`: `audio/wav`, `application/octet-stream` for PCM, or
  `audio/mpeg` for MP3.
- Header: `X-Request-ID`.

## Legacy `/api/tts` / 旧版兼容接口

`/api/tts` accepts JSON, query-string, or form data. Use this endpoint when you
need MOSS reference-audio clone upload because multipart upload is not part of
the OpenAI-compatible JSON shape.

JSON request:

```bash
curl -X POST "$BASE_URL/api/tts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"model":"kokoro","text":"你好世界","voice":"zm_010","format":"wav"}' \
  --output output.wav
```

Query-string request:

```bash
curl --get "$BASE_URL/api/tts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --data-urlencode "text=你好世界" \
  --data-urlencode "voice=zm_010" \
  --data-urlencode "response_format=wav" \
  --output output.wav
```

Multipart request without clone:

```bash
curl -X POST "$BASE_URL/api/tts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F model=kokoro \
  -F text="你好世界" \
  -F voice=zm_010 \
  -F response_format=wav \
  --output output.wav
```

## MOSS Reference-Audio Clone / MOSS 参考音频克隆

MOSS has preset voices and a clone path. Clone mode needs a short reference
audio file. Supported suffixes: `wav`, `mp3`, `flac`, `ogg`, `m4a`, `aac`.
The upload is limited by `MOSS_PROMPT_UPLOAD_MAX_BYTES`, trimmed by
`MOSS_PROMPT_AUDIO_MAX_SECONDS`, and encoded prompt codes are cached by
`MOSS_PROMPT_CACHE_MAX_ITEMS`.

MOSS 有预设音色和克隆路径。克隆模式需要较短参考音频。支持后缀：
`wav/mp3/flac/ogg/m4a/aac`。上传大小由 `MOSS_PROMPT_UPLOAD_MAX_BYTES`
限制，推理前会按 `MOSS_PROMPT_AUDIO_MAX_SECONDS` 裁剪，并按
`MOSS_PROMPT_CACHE_MAX_ITEMS` 缓存编码后的 prompt codes。

Recommended flow:

```bash
curl "$BASE_URL/v1/models"

curl -X POST "$BASE_URL/v1/models/switch" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"model":"moss-nano-cpu","unload_previous":true}'

curl -X POST "$BASE_URL/api/tts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F model=moss-nano-cpu \
  -F text="这是参考音频克隆测试。" \
  -F voice=Junhao \
  -F response_format=wav \
  -F prompt_audio=@reference.wav \
  --output clone.wav
```

Field aliases:

| Field | Alias | Notes |
|---|---|---|
| `prompt_audio` | `reference_audio` | Multipart upload field |
| `response_format` | `format` | `wav`, `pcm`, or `mp3` when enabled |
| `text` | `input`, `prompt` | Text field for `/api/tts` |
| `voice` | `speaker` | Voice field for `/api/tts` |

Uploading `prompt_audio` to `kokoro` or another model without clone support
returns `400 当前模型不支持参考音频克隆`.

## WebSocket Streaming / WebSocket 流式

Connect to:

```text
ws://localhost:8000/ws/v1/tts
```

First JSON message:

| Field | Type | Default | Notes |
|---|---|---|---|
| `model` | string | current/default model | Optional model ID |
| `text` | string | required | Text to synthesize |
| `voice` | string | model default voice | Kokoro voice ID or MOSS preset |
| `speed` | number | configured default | Range `0.5` to `2.0` |
| `format` | string | `pcm_s16le` | `pcm_s16le` or `wav` |
| `binary` | boolean | `false` | Sends binary audio frames when enabled and allowed |
| `token` | string | empty | API key when configured |
| `prompt_audio.data` | string | empty | Base64 or data URL for MOSS clone streaming |
| `prompt_audio.filename` | string | `prompt.wav` | Used for suffix validation |

Browser example:

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/v1/tts");

ws.onopen = () => {
  ws.send(JSON.stringify({
    model: "kokoro",
    text: "你好世界，这是一段流式合成测试。",
    voice: "zm_010",
    speed: 1.0,
    format: "pcm_s16le",
    binary: false,
    token: "YOUR_TOKEN"
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "audio") {
    const pcmBytes = Uint8Array.from(atob(msg.data), (c) => c.charCodeAt(0));
    // Feed pcmBytes to an AudioWorklet, WebAudio buffer, or your player queue.
  }
};

// Stop later segments.
ws.send(JSON.stringify({ type: "cancel" }));
```

MOSS clone streaming first message:

```json
{
  "model": "moss-nano-cpu",
  "text": "这是参考音频克隆的流式测试。",
  "voice": "Junhao",
  "format": "pcm_s16le",
  "binary": false,
  "prompt_audio": {
    "filename": "reference.wav",
    "data": "<base64-or-data-url>"
  },
  "token": "YOUR_TOKEN"
}
```

For backwards-compatible custom clients, `prompt_audio_data`,
`reference_audio_data`, and `prompt_audio_filename` are also accepted.

Server message types:

| Type | Meaning / 含义 |
|---|---|
| `started` | Stream metadata: `segments`, `sample_rate`, `channels`, `format`, `dtype`, optional `voice_clone` |
| `audio` | Audio chunk: `index`, optional `segment_index`, `data`, `format`, `sample_rate`, `channels`, `request_id`, `model` |
| `segment_error` | One segment failed but the stream may continue or finish |
| `done` | Stream completed with `total_segments` and `total_audio_chunks` |
| `cancelled` | Client sent `cancel` / `stop` or request was marked cancelling |
| `error` | Request-level error |

Binary mode sends a metadata JSON `audio` message without `data`, followed by
the raw audio bytes. JSON mode always sends base64 in `data`.

## Batch ZIP / 批量 ZIP

Endpoint:

```http
POST /v1/audio/batch
Content-Type: application/json
```

Example:

```bash
curl -X POST "$BASE_URL/v1/audio/batch" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model":"kokoro",
    "voice":"zm_010",
    "speed":1.0,
    "response_format":"wav",
    "items":[
      {"text":"第一段","filename":"001"},
      {"text":"第二段","filename":"002","voice":"zf_001"},
      {"model":"moss-nano-cpu","text":"第三段使用 MOSS。","voice":"Junhao","filename":"003"}
    ]
  }' \
  --output angevoice_batch.zip
```

Response is `application/zip` and contains:

- One audio file per successful item.
- `manifest.json` with per-item status, filename, bytes, or error.

Batch items can override `model`, `voice`, `speed`, and `filename`. Batch clone
upload is not supported; use `/api/tts` multipart for MOSS reference-audio clone
requests.

## Cancel Requests / 取消请求

HTTP requests return `X-Request-ID`. WebSocket messages include `request_id`.
To mark a running request as cancelling:

```bash
curl -X POST "$BASE_URL/v1/audio/requests/REQUEST_ID/cancel" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

For WebSocket, the client can also send:

```json
{"type":"stop"}
```

or:

```json
{"type":"cancel"}
```

Cancellation prevents later segments from being pushed. If the current segment
is already inside synchronous model inference, it usually stops after that
segment finishes.

## Optional Admin APIs / 可选管理接口

Admin APIs are disabled by default. Enable them only in trusted environments:

```bash
KOKORO_ADMIN_ENABLED=true
KOKORO_API_KEY=<paste-generated-token-here>
```

Clear cache:

```bash
curl -X DELETE "$BASE_URL/admin/cache" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

List local Kokoro voices:

```bash
curl "$BASE_URL/admin/voices" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Upload trusted `.pt` voice files:

```bash
curl -X POST "$BASE_URL/admin/voices/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F file=@my_voice.pt
```

Voice upload also requires:

```bash
KOKORO_VOICE_UPLOAD_ENABLED=true
```

Do not expose `/admin/*` directly to the public internet.

## Output Formats / 输出格式

| Format | Request value | Response |
|---|---|---|
| WAV | `wav` | `audio/wav` |
| PCM s16le | HTTP: `pcm`; WebSocket: `pcm_s16le` | Raw PCM bytes |
| MP3 | `mp3` | `audio/mpeg`; requires `KOKORO_MP3_ENABLED=true` and ffmpeg |

Use `GET /v1/audio/formats` to check whether MP3 is enabled and whether ffmpeg
is available in the running container.

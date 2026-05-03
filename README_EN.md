# Kokoro TTS Chinese Speech Synthesis

> Lightweight Chinese TTS based on [Kokoro v1.1](https://huggingface.co/hexgrad/Kokoro-82M), with HTTP API + WebSocket streaming support

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Features

- **Bilingual** — Auto language detection, seamless Chinese/English mixed synthesis
- **CPU/GPU Adaptive** — Auto CUDA detection, works without GPU
- **OpenAI Compatible API** — Drop-in replacement for OpenAI TTS
- **WebSocket Streaming** — Real-time segment-by-segment playback
- **pip Installable** — `pip install -e .` and you're ready
- **Docker Deploy** — CPU and GPU images included
- **12+ Voices** — 10 Chinese + 2 English

## Quick Start

### pip Install

```bash
git clone https://github.com/ang77712829/kokoro-tts-zh.git
cd kokoro-tts-zh
pip install -e .

# Start server
kokoro-tts serve --port 8000

# CLI synthesis
kokoro-tts synth "Hello world" -o hello.wav -v zm_010
```

### Docker

```bash
# CPU (port 8100)
cd docker/cpu && docker-compose up -d

# GPU (port 8101)
cd docker/gpu && docker-compose up -d
```

Custom build:

```bash
# CPU
docker build -f docker/cpu/Dockerfile -t kokoro-tts:cpu .
docker run -d -p 8000:8000 -v $(pwd)/models:/app/models kokoro-tts:cpu

# GPU (requires nvidia-docker)
docker build -f docker/gpu/Dockerfile -t kokoro-tts:gpu .
docker run -d --gpus all -p 8000:8000 -v $(pwd)/models:/app/models kokoro-tts:gpu
```

### Direct Run

```bash
python run-tts.py           # Start server
python run-tts.py voices    # List voices
```

## API

### OpenAI Compatible

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "voice": "zm_010"}' \
  --output output.wav
```

### Legacy API

```bash
# JSON
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "zm_010"}' \
  --output output.wav

# GET
curl "http://localhost:8000/api/tts?text=Hello+world&voice=zm_010" --output output.wav

# Form
curl -X POST http://localhost:8000/api/tts -F "text=Hello world" --output output.wav
```

### WebSocket Streaming

Real-time segment-by-segment synthesis:

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/v1/tts");
ws.onopen = () => {
  ws.send(JSON.stringify({
    text: "Hello, this is streaming synthesis.",
    voice: "zm_010",
    speed: 1.0,
    format: "pcm_s16le"  // or "wav"
  }));
};
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === "audio") {
    playPCM(msg.data);  // base64 encoded PCM audio
  }
};
```

**Message Protocol:**

| Type | Description | Fields |
|------|-------------|--------|
| `started` | Synthesis started | `segments`, `sample_rate` |
| `audio` | Audio data | `index`, `data` (base64), `format` |
| `done` | Synthesis complete | `total_segments` |
| `error` | Error | `message` |

### Health Check

```bash
curl http://localhost:8000/health
```

## Available Voices

Run `kokoro-tts voices` for full list.

| Prefix | Language | Examples |
|--------|----------|----------|
| `zm_` | Chinese | `zm_010` |
| `zf_` | Chinese | `zf_001` ~ `zf_004` |
| `af_` | English | `af_maple`, `af_sol` |
| `bf_` | English | `bf_vale` |

## Library Usage

```python
from kokoro_tts import TTSEngine

engine = TTSEngine()
engine.load()

# Synthesize to memory
wav_bytes = engine.synthesize("Hello world", voice="zm_010", speed=1.0)

# Synthesize to file
engine.synthesize_file("Hello world", output_path="output.wav")

# Streaming synthesis (segment-by-segment)
for chunk in engine.synthesize_stream("Hello world", voice="zm_010"):
    if chunk["type"] == "audio":
        process_audio(chunk["data"])  # base64 PCM
```

## Configuration

Environment variables (override defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `KOKORO_MODEL_DIR` | `./models` | Model directory |
| `KOKORO_HOST` | `0.0.0.0` | Listen address |
| `KOKORO_PORT` | `8000` | Port |
| `KOKORO_DEVICE` | `auto` | Device (auto/cpu/cuda) |
| `KOKORO_API_KEY` | - | API Key (auth required when set) |
| `KOKORO_CORS_ORIGINS` | `http://localhost:8000` | CORS origins (comma-separated) |

## Project Structure

```
kokoro-tts-zh/
├── src/kokoro_tts/       # Core package
│   ├── __init__.py       # Package entry (lazy load)
│   ├── config.py         # Configuration
│   ├── engine.py         # TTS engine
│   ├── server.py         # FastAPI HTTP + WebSocket
│   ├── cli.py            # CLI tool
│   └── templates/        # Web UI
├── tests/                # Tests
├── docker/               # Docker configs
│   ├── cpu/              # CPU version
│   └── gpu/              # GPU version
├── models/               # Model files (Git LFS)
├── pyproject.toml        # Package config
└── README.md
```

## Changelog

### v2.1.0 (2026-05-03)

**Added**
- WebSocket streaming synthesis (`/ws/v1/tts`) for real-time playback
- PCM s16le and WAV audio format support
- Web UI streaming toggle + WebSocket status indicator
- Docker integration tests (17 test cases)

**Improved**
- `engine.py`: New `synthesize_stream()` generator method
- `server.py`: New WebSocket endpoint with API Key auth
- `config.py`: New `stream_enabled`, `stream_format` config options

### v2.0.1 (2026-05-03)

**Security**
- API Key timing attack prevention (`hmac.compare_digest`)
- CORS disabled by default, configurable via `KOKORO_CORS_ORIGINS`
- Error messages sanitized (no internal stack traces)
- Text length limit (10,000 chars) to prevent OOM

**Fixed**
- Missing `import os` in `engine.py`
- Duplicate function definition in `tts-project-cpu/main.py`
- Missing `static/` directory causing Docker mount crash
- Invalid fallback logic (retry with identical params)

**Removed**
- Unused `Dockerfile.new`
- Python version unified to `>=3.10`

### v1.1 (2026-05-02)

**Added**
- CORS middleware support
- `KOKORO_MODEL_DIR` environment variable
- CPU + GPU Docker images

**Fixed**
- `torch.set_num_interop_threads` duplicate setting protection

### v1.0 (2026-02-21)

**Initial Release**
- Chinese + English speech synthesis (Kokoro-82M-v1.1-zh)
- 12+ voices, speech rate control
- OpenAI-style API
- Docker CPU/GPU deployment
- One-click startup script

## Acknowledgements

- [Kokoro v1.1 Model](https://huggingface.co/hexgrad/Kokoro-82M) — hexgrad
- Original model [Apache 2.0](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/LICENSE) licensed
- This project MIT licensed

## License

MIT

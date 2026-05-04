# AngeVoice 服务版本说明 / Service Profiles

AngeVoice 从 v2.3.0 开始按两个部署画像维护：通用服务版和老显卡/保守兼容版。

AngeVoice is maintained with two deployment profiles: the general service profile and the legacy/conservative GPU profile.

## 重要说明：模型文件与缓存 / Important: model files and cache

仓库中的 `models/*.pth`、`models/voices/*.pt` 可能是 Git LFS 指针文件。普通 `git clone` 后如果没有执行 `git lfs pull`，这些文件不会是真实模型文件。AngeVoice 会自动回退到 Hugging Face 下载模型。

`models/*.pth` and `models/voices/*.pt` may be Git LFS pointer files. If you clone without `git lfs pull`, they are not real model files. AngeVoice will fall back to Hugging Face download.

三套 Docker Compose 都会持久化 Hugging Face 缓存：

All Docker Compose profiles persist the Hugging Face cache:

```yaml
- ../../.cache/huggingface:/root/.cache/huggingface
```

这样即使容器重建，已经下载过的模型和音色也不会重复下载。

This prevents repeated model/voice downloads after container recreation.

## 1. 通用服务版 / General service profile

适合大多数 CPU/GPU/云服务器环境，默认追求稳定、兼容和易部署。

Suitable for most CPU/GPU/cloud environments. Defaults target stability, compatibility and easy deployment.

推荐配置：

```bash
KOKORO_WORKERS=1
KOKORO_MAX_CONCURRENT_REQUESTS=1
KOKORO_CACHE_ENABLED=true
KOKORO_CACHE_MAX_ITEMS=128
KOKORO_STREAM_BINARY_ENABLED=true
KOKORO_REQUEST_TIMEOUT_SECONDS=300
HF_HOME=/root/.cache/huggingface
HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface/hub
```

能力：

- OpenAI 风格 `/v1/audio/speech`
- `/api/tts` 旧版接口
- `/ws/v1/tts` 逐段流式接口
- `/stats` 服务统计
- `/requests` 最近请求状态
- 内存 LRU 音频缓存
- 请求 ID 响应头 `X-Request-ID`
- WebSocket JSON + 可选 binary 音频帧
- 批量合成、可选 MP3、音色试听与前端收藏/最近试听

## 2. 老显卡/保守兼容版 / Legacy GPU conservative profile

适合旧驱动、旧 GPU、NAS、低功耗主机或不希望使用激进 GPU 运行时的环境。

Suitable for older drivers, older GPUs, NAS deployments, low-power hosts, or environments that prefer a conservative CUDA runtime.

推荐配置：

```bash
KOKORO_WORKERS=1
KOKORO_MAX_CONCURRENT_REQUESTS=1
KOKORO_CACHE_ENABLED=true
KOKORO_CACHE_MAX_ITEMS=64
KOKORO_STREAM_BINARY_ENABLED=false
KOKORO_REQUEST_TIMEOUT_SECONDS=600
KOKORO_SEGMENT_LENGTH=80
HF_HOME=/root/.cache/huggingface
HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface/hub
```

建议：

- 优先使用稳定的 PyTorch/CUDA 组合，不强求最新 CUDA。
- 不建议多 worker 同时加载 GPU 模型。
- 遇到音频噪声、爆音或推理异常时，优先关闭半精度、TensorRT、flash attention 等加速。
- 长文本建议降低 `KOKORO_SEGMENT_LENGTH`，减少单段失败概率。
- WebSocket 建议先使用 JSON base64 模式，确认稳定后再开启 binary 模式。

## API 快速检查 / API smoke check

```bash
curl http://localhost:8000/health
curl http://localhost:8000/stats
curl http://localhost:8000/requests
```

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"你好世界","voice":"zm_010","response_format":"wav"}' \
  --output output.wav
```

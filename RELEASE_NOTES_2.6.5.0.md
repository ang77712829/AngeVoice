# AngeVoice 2.6.5.0 最终发布说明

面向：将 2.6.4.6 升级到 2.6.5.0 的合并、打 tag、发布包和镜像构建。

建议发布版本：`2.6.5.0`

## 一句话总结

2.6.5.0 不是简单 UI 小改版，而是一轮“长文本自然合成 + Admin 后台重构 + NAS/P4 生产稳定性”的集中修复。重点解决 MOSS 长文本合成中的硬切、长静音、流式断流、重复读、变调、full codec OOM fallback、缓存过激、Admin 配置难维护和 Docker 默认值不一致等问题。

## 从 2.6.4.6 到 2.6.5.0 的主要替换

### 1. MOSS 默认参数替换为 NAS/P4 安全档

旧思路：偏质量/长文本旁白默认，容易在 8GB 显卡上触发 ONNXRuntime 大 buffer 分配失败。

新默认：

```env
MOSS_SEGMENT_LENGTH=180
MOSS_VOICE_CLONE_MAX_TEXT_TOKENS=64
MOSS_MAX_NEW_FRAMES=320
MOSS_STREAM_CHUNK_SECONDS=0.40
MOSS_STREAM_QUEUE_MAX_ITEMS=4
MOSS_STREAM_PREBUFFER_SECONDS=0.45
MOSS_MAX_SILENCE_MS=850
MOSS_CROSSFADE_MS=25
MOSS_SEGMENT_PAUSE_MS=100
MOSS_RUNTIME_PAUSE_MAX_MS=500
MOSS_OUTPUT_TARGET_PEAK=0.78
MOSS_OUTPUT_GAIN=0.88
MOSS_OUTPUT_EDGE_FADE_MS=3
```

说明：`260/90/450/queue=12` 不再是生产默认，只保留为 Admin 里的“长文本旁白”预设，推荐 12GB+ 显存手动开启。

### 2. MOSS 文本切片替换为自然分句器

新增/重构：

- `src/kokoro_tts/text_segmenter.py`
- `src/kokoro_tts/moss/text.py`

修复点：

- 支持中文标点、英文句号/问号/感叹号、段落边界。
- 不再把英文单词切成 `f\nierce` 这类断裂。
- 不误切 `v2.6.5.0`、`192.168.1.1`、`4.20`。
- 新增 `ANGEVOICE_SINGLE_NEWLINE_POLICY=auto`，对中文网页/小说复制文本自动合并段内硬换行。

### 3. MOSS 音频后处理替换为统一 polish 管线

主要文件：

- `src/kokoro_tts/moss/postprocess.py`
- `src/kokoro_tts/moss_engine.py`
- `src/kokoro_tts/moss_engine_streaming.py`

新增能力：

- chunk 首尾静音裁剪。
- 最终异常长静音压缩。
- HTTP 非流式拼接 crossfade。
- runtime pause 上限控制。
- last_output_quality 增加长静音、削波、静音占比等指标。

目标：降低长文本中的 2-5 秒空白、重复读、变调、硬切电流感和段间不自然。

### 4. 增加 VRAM Guard，替换“每段 OOM 后 fallback”的生产路径

新增：

- `src/kokoro_tts/moss/vram.py`
- MOSS engine 内部 low-vram / full-codec cooldown 状态

新增 ENV：

```env
MOSS_VRAM_GUARD_ENABLED=true
MOSS_VRAM_SAFE_FREE_MB=1200
MOSS_VRAM_CRITICAL_FREE_MB=600
MOSS_LOW_VRAM_SEGMENT_LENGTH=160
MOSS_LOW_VRAM_MAX_NEW_FRAMES=300
MOSS_LOW_VRAM_TEXT_TOKENS=56
MOSS_DISABLE_FULL_CODEC_AFTER_OOM=true
MOSS_FULL_CODEC_OOM_COOLDOWN_SECONDS=600
```

行为：

- 合成前检查 CUDA 剩余显存。
- 低显存时自动降分句长度、token 上限和帧预算。
- critical free VRAM 时优先走增量 codec decode。
- full codec decode OOM 后进入 cooldown，避免后续每段都先 OOM 再 fallback。

### 5. Admin 后台替换为五区块轻量控制台

主要文件：

- `src/kokoro_tts/templates/admin.html`
- `src/kokoro_tts/static/admin.js`
- `src/kokoro_tts/static/admin.css`
- `src/kokoro_tts/routes/admin.py`
- `src/kokoro_tts/routes/admin_runtime.py`
- `src/kokoro_tts/admin_config_schema.py`

新结构：

- Dashboard
- Models
- Tuning
- Security
- Diagnostics

新增能力：

- 配置项按 schema 分组编辑。
- 支持 NAS 稳定、均衡推荐、长文本旁白、低延迟流式、克隆质量优先预设。
- 支持保存到 `/app/outputs/runtime-config.json`。
- 支持导出 ENV patch。
- 显示 runtime-config 是否覆盖 ENV，并支持清除持久化配置。
- MOSS 配置变更时自动 drop 或 pending rebuild。
- 显示 low-vram、full decode OOM、cache bytes、active_count、pending rebuild、最近请求和失败。

设计约束：继续使用 vanilla JS，不引入 React/Vite/Webpack，不引入数据库，避免后台臃肿。

### 6. 缓存策略替换为长文本友好策略

新增 ENV：

```env
KOKORO_CACHE_MAX_BYTES=536870912
KOKORO_CACHE_SKIP_TEXT_OVER_CHARS=1200
KOKORO_CACHE_SKIP_AUDIO_OVER_BYTES=20971520
```

修复点：

- 内存缓存不再只按条目数限制。
- 长文本默认不写入缓存。
- 大音频默认不写入缓存。
- Admin 显示缓存条目和缓存字节数。

### 7. Docker Compose / env 默认值全部重新对齐

已检查并对齐：

- `docker/angevoice.env`
- `docker/.env.example`
- `.env.example`
- `.env.prod`
- `.env.staging`
- `docker/cpu/docker-compose.yml`
- `docker/gpu/docker-compose.yml`
- `docker/legacy-gpu/docker-compose.yml`
- `docker/legacy-gpu/docker-compose.moss-cuda.yml`

最终口径：

- 默认：NAS/P4 安全档，`MOSS_SEGMENT_LENGTH=180`。
- 均衡：`220`。
- 长文本旁白：`260+`，推荐 12GB+。
- legacy CUDA：比通用 GPU 更保守。

### 8. 管理后台默认凭据策略保留

保留 Docker/NAS 默认：

```env
KOKORO_ADMIN_ENABLED=true
ANGEVOICE_ADMIN_USERNAME=admin
ANGEVOICE_ADMIN_PASSWORD=admin123
```

原因：飞牛/群晖/普通 NAS 用户常直接用 compose 启动，如果默认关闭后台或随机密码不可见，会导致无法进入后台查看/生成 API Key。

文档已明确：`admin123` 仅适合内网首次启动，公网部署必须修改强密码。

### 9. 国内模型源站体验修复

- `ANGEVOICE_MODEL_SOURCE=auto` 改为先探测 Hugging Face / ModelScope 可达性，再做国家判断。
- 进程内缓存有效源站，避免重复探测拖慢冷启动。
- Admin 显示 model source 的 mode/effective/country/reachability。

### 10. 新增音频质量分析工具

新增：

```bash
python scripts/analyze_audio_quality.py output.wav
```

输出：

- 时长
- 采样率
- 声道
- 峰值
- RMS
- 削波比例
- 长静音段
- 最大静音
- 静音占比

## 验证摘要

本发布包建议在合并前执行以下检查：

```bash
pytest -q
python -m compileall -q src
node --check src/kokoro_tts/static/admin.js
node --check src/kokoro_tts/static/app.js
```

已验证内容：

- 单元测试覆盖分句、音频后处理、Admin schema、VRAM Guard、缓存限制和 runtime-config。
- Python 源码可编译。
- Admin 和 Studio 前端脚本语法通过。
- Docker Compose YAML 可解析。
- 默认 Docker / env 配置不再使用长文本旁白档作为生产默认。

## 发布前重点检查

- 发布版本统一为 `2.6.5.0`。
- Docker / env 默认配置使用 NAS/P4 安全档：`MOSS_SEGMENT_LENGTH=180`、`MOSS_STREAM_QUEUE_MAX_ITEMS=4`、`MOSS_STREAM_CHUNK_SECONDS=0.40`。
- 长文本旁白档 `260+` 仅作为 Admin 预设，推荐 12GB+ 显存手动开启。
- Docker/NAS 默认仍保留 `admin` / `admin123` 方便内网首次启动，公网部署必须修改强密码。
- README、README_EN、API Reference、Architecture、Service Profiles、MOSS Audio Quality 文档口径一致：默认 180，均衡 220，旁白 260+。
- `CHANGELOG.md` 仅保留一个 `2.6.5.0` 段落，并包含 `2.6.4.6` 历史版本记录。

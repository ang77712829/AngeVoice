# 更新日志 (CHANGELOG)

## v2.1.0 (2026-05-03)

### 新增功能
- **WebSocket 流式语音合成**：新增 `/ws/v1/tts` WebSocket 端点，支持逐段实时合成播放
  - 段级流式（~100字/段），延迟 100-300ms
  - 支持 PCM s16le 和 WAV 两种音频格式
  - base64 编码传输，前端 AudioContext 排队播放
- **Web UI 流式播放**：前端新增流式播放开关、WebSocket 状态指示灯、流式进度显示
- **Docker 集成测试**：新增 17 个端到端测试（HTTP/WebSocket/编码/配置/流式逻辑）

### 技术实现
- `engine.py`: 新增 `synthesize_stream()` 生成器方法，逐段 yield 音频数据
- `server.py`: 新增 `/ws/v1/tts` WebSocket 端点，含 API Key 验证
- `config.py`: 新增 `stream_enabled`、`stream_format` 配置项
- `pyproject.toml`: 新增 `websockets>=12.0` 依赖
- `docker/cpu/Dockerfile`: 适配新包结构，支持测试模式

---

## v2.0.1 (2026-05-03)

### 安全修复
- **API Key 时序攻击防护**：`server.py` 中 token 比较改用 `hmac.compare_digest()`，防止时序侧信道攻击
- **CORS 可配置化**：默认从 `["*"]`（全开）改为 `["http://localhost:8000"]`，支持 `KOKORO_CORS_ORIGINS` 环境变量自定义
- **错误信息脱敏**：API 返回的错误信息不再暴露内部异常堆栈，仅记录到日志
- **请求体大小限制**：合成文本超过 10000 字符时返回 400，防止 OOM

### Bug 修复
- **`import os` 遗漏**：`engine.py` 中 `os.cpu_count()` 缺少 `import os`，运行必报 `NameError`，已修复
- **重复 `en_callable` 定义**：`tts-project-cpu/app/main.py` 中同一函数定义两次，删除冗余版本并保留 try/except 保护
- **缺失 `static/` 目录**：CPU/GPU 版本挂载不存在的 `app/static` 目录会崩溃，已创建 `.gitkeep`
- **无效 fallback 逻辑**：`engine.py` 中 fallback 使用完全相同参数重试，第一次失败第二次必然也失败，已移除

### 清理
- **删除 `Dockerfile.new`**：引用不存在的 `requirements.txt` 和 `templates/` 目录，启动命令路径错误，且已有 `docker/cpu/` 和 `docker/gpu/` 正常工作
- **Python 版本统一**：`pyproject.toml` 统一为 `>=3.10`
- **添加 MIT LICENSE 文件**

---

## v1.1 (2026-05-02)

### 新增功能
- **CORS 中间件**：添加跨域资源共享支持，允许第三方应用（如 Tavern AI、Web 前端等）直接调用 API
- **环境变量配置**：新增 `KOKORO_MODEL_DIR` 环境变量，支持自定义模型文件路径，无需修改代码
- **CPU + GPU 双版本**：同时提供 CPU 和 GPU 两个版本，用户可根据硬件环境自由选择

### 改进与修复
- **torch 线程保护**：添加 `torch.set_num_interop_threads` 的 try/except 保护，避免重复设置导致 RuntimeError
- 使用环境变量 `KOKORO_MODEL_DIR` 替代原有的 monkey patch 方式配置模型路径，代码更优雅

---

## v1.0 (2026-02-21)

### 初始版本发布
- **中文 + 英文语音合成**：基于 Kokoro-82M-v1.1-zh 模型，支持中英文文本转语音
- **多种声音模型**：内置多种中文/英文声音模型（如 `zf_001`、`af_maple` 等）
- **语速调节**：支持通过 API 参数调整合成语速
- **Docker 部署**：提供 CPU 和 GPU 两个 Docker 配置，一键部署
- **OpenAI 风格 API**：兼容 OpenAI TTS API 调用格式，方便集成到现有系统
- **RESTful API**：提供标准 HTTP 接口，支持 Tavern AI 等第三方应用集成
- **一键启动脚本**：`run-tts.py` 自动检测环境并安装依赖

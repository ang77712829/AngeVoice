# AngeVoice — 魔搭 PAI-DSW 部署指南

在 PAI-DSW 终端里依次执行：

```bash
# 1. 克隆代码
git clone https://github.com/ang77712829/AngeVoice.git
cd AngeVoice

# 2. 安装依赖 (用预装的 torch，不用重装)
pip install --no-cache-dir -e .
pip install --no-cache-dir "sentencepiece>=0.1.99" "huggingface_hub>=0.23" "onnxruntime>=1.20.0"
pip install --no-cache-dir gradio soundfile

# 3. 克隆 MOSS 模型仓库
git clone --depth 1 https://github.com/OpenMOSS/MOSS-TTS-Nano.git

# 4. 设置环境变量
export ANGEVOICE_ENABLED_MODELS="kokoro,moss-nano-cpu"
export ANGEVOICE_DEFAULT_MODEL="kokoro"
export MOSS_TTS_NANO_PATH="$(pwd)/MOSS-TTS-Nano"
export MOSS_EXECUTION_PROVIDER="cpu"
export MOSS_CPU_THREADS="4"
export KOKORO_WORKERS="1"
export KOKORO_REQUEST_TIMEOUT_SECONDS="120"
export KOKORO_IDLE_TIMEOUT_SECONDS="0"

# 5. 启动 (PAI-DSW 会自动暴露 7860 端口)
python hf-demo/app.py
```

启动后 PAI-DSW 会在界面显示访问链接，点击即可打开 Gradio 演示页面。

## 注意事项

- PAI-DSW 免费实例 8核32G，跑 Kokoro CPU 够用
- 首次加载模型会从 HuggingFace 下载 (~312MB)，需要等待
- 关闭终端会停止服务，需要重新启动
- 如需长期运行，考虑用 PAI-DLC (容器服务)

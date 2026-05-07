FROM python:3.10-slim

WORKDIR /app

# 系统依赖
# ffmpeg 用于可选 MP3 转码；未开启 KOKORO_MP3_ENABLED 时不会影响默认路径
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# CPU 版 PyTorch
RUN python3 -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 复制项目
COPY pyproject.toml README.md ./
COPY src/ src/

# 安装项目。使用 editable 模式让 Compose 挂载的模板/静态资源能立即生效。
RUN python3 -m pip install --no-cache-dir -e .

# 预装 spaCy 英文模型（misaki/kokoro 依赖，避免每次启动重新下载）
RUN python3 -m pip install --no-cache-dir \
    en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

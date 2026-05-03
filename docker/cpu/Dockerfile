FROM python:3.10-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# CPU 版 PyTorch
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 复制项目
COPY pyproject.toml README.md ./
COPY src/ src/
COPY models/ models/

# 安装项目
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python3", "-c", "from kokoro_tts.server import run_server; run_server()"]

FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

WORKDIR /app

# Python 3.10 + 系统依赖
RUN apt-get update && \
    apt-get install -y python3.10 python3-pip python3.10-venv libsndfile1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# GPU 版 PyTorch
RUN pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 复制项目
COPY pyproject.toml README.md ./
COPY src/ src/
COPY models/ models/

# 安装项目
RUN pip3 install --no-cache-dir -e .

EXPOSE 8000

CMD ["python3", "-c", "from kokoro_tts.server import run_server; run_server()"]

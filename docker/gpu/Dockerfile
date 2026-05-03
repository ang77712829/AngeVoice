FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 安装 Python 3.10 + 系统依赖
RUN apt-get update && \
    apt-get install -y python3.10 python3.10-dev python3.10-venv python3-pip libsndfile1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 确保 python3 和 pip3 都指向 3.10
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    python3.10 -m pip install --upgrade pip

# GPU 版 PyTorch
RUN python3 -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 复制项目
COPY pyproject.toml README.md ./
COPY src/ src/

# 安装项目（不用 -e）
RUN python3 -m pip install --no-cache-dir .

EXPOSE 8000

CMD ["python3", "-c", "from kokoro_tts.server import run_server; run_server()"]

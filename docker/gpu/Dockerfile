FROM nvidia/cuda:11.7.1-cudnn8-runtime-ubuntu22.04

WORKDIR /app

# 安装 Python 3.10
RUN apt-get update && \
    apt-get install -y python3.10 python3-pip python3.10-venv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装项目
COPY pyproject.toml README.md ./
COPY src/ src/
COPY models/ models/

RUN pip3 install --no-cache-dir -e .

EXPOSE 8000

CMD ["python3", "-c", "from kokoro_tts.server import run_server; run_server()"]

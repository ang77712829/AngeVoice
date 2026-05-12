# ============================================================
#  ⚠️⚠️⚠️  仅用于 Hugging Face Spaces / 魔搭创空间在线演示  ⚠️⚠️⚠️
# ============================================================
#  本地 Docker 部署请用: docker/cpu/Dockerfile
#  此文件内容与 hf-demo/Dockerfile 一致
# ============================================================

FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    libsndfile1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    torch==2.5.1+cpu \
    torchaudio==2.5.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu

ENV MOSS_TTS_NANO_PATH=/app/MOSS-TTS-Nano
RUN git clone --depth 1 https://github.com/OpenMOSS/MOSS-TTS-Nano.git "$MOSS_TTS_NANO_PATH" && \
    pip install --no-cache-dir \
    "sentencepiece>=0.1.99" \
    "huggingface_hub>=0.23" \
    "onnxruntime>=1.20.0"

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY hf-demo/ hf-demo/

RUN pip install --no-cache-dir -e .

RUN pip install --no-cache-dir \
    en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

RUN pip install --no-cache-dir gradio soundfile

EXPOSE 7860

ENV PYTHONUNBUFFERED=1
ENV ANGEVOICE_ENABLED_MODELS=kokoro,moss-nano-cpu
ENV ANGEVOICE_DEFAULT_MODEL=kokoro
ENV KOKORO_DEFAULT_VOICE=zm_010
ENV MOSS_DEFAULT_VOICE=Junhao
ENV KOKORO_WORKERS=1
ENV KOKORO_MAX_CONCURRENT_REQUESTS=1
ENV KOKORO_REQUEST_TIMEOUT_SECONDS=120
ENV KOKORO_IDLE_TIMEOUT_SECONDS=0
ENV MOSS_EXECUTION_PROVIDER=cpu
ENV MOSS_CPU_THREADS=2
ENV MOSS_APPLYANGEVOICE_RULES=true

CMD ["python", "hf-demo/app.py"]

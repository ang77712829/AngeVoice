"""小智 AngeVoice 克隆非流式适配器。

安装到：
    /opt/xiaozhi-esp32-server/core/providers/tts/angevoice_clone.py

本适配器通过 AngeVoice multipart `/api/tts` 端点上传固定参考音频。MOSS 缺少参考
音频时会退回普通音色；ZipVoice 必须同时提供参考音频和 `prompt_text`。

参考音频路径会兼容常见 NAS 填写习惯：如果用户在智控台填入
`/vol*/.../data/angevoice_prompts/` 这类宿主机路径，会映射到小智容器内的
`/opt/xiaozhi-esp32-server/data/angevoice_prompts`。
"""

from __future__ import annotations

import os

import httpx

from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase

TAG = __name__
logger = setup_logging()

MAX_PROMPT_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB
PROMPT_CONTAINER_DIR = "/opt/xiaozhi-esp32-server/data/angevoice_prompts"


class TTSProvider(TTSProviderBase):
    """AngeVoice 克隆非流式适配器。"""

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.api_key = config.get("api_key", "") or ""
        self.api_url = _resolve_clone_url(config.get("api_url") or config.get("base_url") or "http://host.docker.internal:8101")
        self.model = config.get("model", "moss")
        self.voice = config.get("private_voice") or config.get("voice", "Junhao")
        self.audio_file_type = config.get("response_format") or config.get("format", "wav")
        self.prompt_audio_path = config.get("prompt_audio_path", "") or ""
        self.prompt_audio_filename = config.get("prompt_audio_filename") or os.path.basename(self.prompt_audio_path) or "reference.wav"
        self.prompt_text = str(config.get("prompt_text") or "").strip()
        self.timeout = int(config.get("tts_timeout", config.get("timeout", 180)))
        self.output_file = config.get("output_dir", "tmp/")

    async def text_to_speak(self, text, output_file):
        prompt_audio_path = _normalize_prompt_audio_path(self.prompt_audio_path, self.prompt_audio_filename)
        if not prompt_audio_path or not os.path.exists(prompt_audio_path) or os.path.isdir(prompt_audio_path):
            if self.model == "zipvoice":
                raise Exception(
                    f"AngeVoice ZipVoice克隆需要可访问的参考音频: raw={self.prompt_audio_path!r}, normalized={prompt_audio_path!r}"
                )
            logger.bind(tag=TAG).warning(
                f"AngeVoice MOSS克隆参考音频不可用，已退回普通请求: raw={self.prompt_audio_path!r}, normalized={prompt_audio_path!r}"
            )
            return await self._text_to_speak_without_prompt(text, output_file)
        if self.model == "zipvoice" and not self.prompt_text:
            raise Exception("AngeVoice ZipVoice克隆需要 prompt_text，请填写参考音频实际朗读的文本")

        file_size = os.path.getsize(prompt_audio_path)
        if file_size > MAX_PROMPT_AUDIO_SIZE:
            raise Exception(f"AngeVoice克隆参考音频过大: {file_size / 1024 / 1024:.1f}MB > {MAX_PROMPT_AUDIO_SIZE / 1024 / 1024:.0f}MB 限制")

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = {
            "model": self.model,
            "text": text,
            "voice": self.voice,
            "response_format": self.audio_file_type,
        }
        if self.prompt_text:
            data["prompt_text"] = self.prompt_text

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(prompt_audio_path, "rb") as audio_file:
                files = {"prompt_audio": (os.path.basename(prompt_audio_path), audio_file)}
                response = await client.post(self.api_url, data=data, files=files, headers=headers)

            if response.status_code != 200:
                raise Exception(f"AngeVoice克隆请求失败: {response.status_code} - {response.text[:500]}")

            if output_file:
                with open(output_file, "wb") as out:
                    out.write(response.content)
                return None
            return response.content

    async def _text_to_speak_without_prompt(self, text, output_file):
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = {
            "model": self.model,
            "text": text,
            "voice": self.voice,
            "response_format": self.audio_file_type,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.api_url, data=data, headers=headers)
        if response.status_code != 200:
            raise Exception(f"AngeVoice MOSS请求失败: {response.status_code} - {response.text[:500]}")
        if output_file:
            with open(output_file, "wb") as out:
                out.write(response.content)
            return None
        return response.content


def _resolve_clone_url(url: str) -> str:
    url = str(url or "").strip().rstrip("/")
    if not url:
        url = "http://host.docker.internal:8101"
    if url.endswith("/api/tts"):
        return url
    return f"{url}/api/tts"


def _normalize_prompt_audio_path(path: str, filename: str) -> str:
    raw = str(path or "").strip()
    filename = str(filename or "reference.wav").strip() or "reference.wav"
    if not raw:
        return ""

    candidates: list[str] = []

    def add(candidate: str) -> None:
        candidate = str(candidate or "").strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    add(raw)
    if raw.endswith("/"):
        add(os.path.join(raw, filename))

    marker = "/data/angevoice_prompts"
    if marker in raw:
        suffix = raw.split(marker, 1)[1].lstrip("/")
        if not suffix:
            suffix = filename
        elif suffix.endswith("/"):
            suffix += filename
        add(os.path.join(PROMPT_CONTAINER_DIR, suffix))

    if os.path.isdir(raw):
        add(os.path.join(raw, filename))

    for candidate in candidates:
        if os.path.isdir(candidate):
            candidate_file = os.path.join(candidate, filename)
            if os.path.exists(candidate_file):
                return candidate_file
        if os.path.exists(candidate):
            return candidate

    for candidate in candidates:
        if candidate.startswith(PROMPT_CONTAINER_DIR):
            return candidate
    return candidates[-1] if candidates else ""

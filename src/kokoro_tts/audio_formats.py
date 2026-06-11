"""Public audio response format normalization and optional FFmpeg transcoding."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)

TRANSCODE_FORMATS = {"mp3", "ogg_opus", "m4a"}
ALLOWED_MP3_BITRATES = {"64k", "96k", "128k", "160k", "192k", "256k", "320k"}


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def ffmpeg_effective_enabled(cfg) -> bool:
    """旧 ``KOKORO_MP3_ENABLED`` 继续视为启用 FFmpeg 转码。"""

    return bool(getattr(cfg, "ffmpeg_enabled", False) or getattr(cfg, "mp3_enabled", False))


def normalize_audio_format_name(value: str | None) -> str:
    fmt = str(value or "wav").strip().lower().replace("-", "_")
    if fmt in {"", "wave"}:
        return "wav"
    if fmt in {"pcm_s16le", "s16le", "raw_pcm"}:
        return "pcm"
    if fmt in {"ogg", "opus", "oggopus", "ogg_opus", "telegram", "telegram_voice", "tg_voice"}:
        return "ogg_opus"
    if fmt in {"aac", "mp4_audio", "x_m4a"}:
        return "m4a"
    return fmt


def supported_response_formats(cfg) -> list[str]:
    formats = ["wav", "pcm"]
    if ffmpeg_effective_enabled(cfg):
        formats.extend(["mp3", "ogg_opus", "telegram_voice", "m4a"])
    return formats


def normalize_response_format(fmt: str | None, cfg) -> str:
    normalized = normalize_audio_format_name(fmt)
    if normalized in {"wav", "pcm"}:
        return normalized
    if normalized in TRANSCODE_FORMATS:
        if ffmpeg_effective_enabled(cfg):
            return normalized
        raise HTTPException(
            status_code=400,
            detail=_detail(
                "FFMPEG_DISABLED",
                "当前未启用 FFmpeg 转码；如需 mp3、ogg_opus、telegram_voice 或 m4a，请在管理后台启用 FFmpeg 转码。",
            ),
        )
    raise HTTPException(status_code=400, detail=f"不支持的输出格式。当前支持：{', '.join(supported_response_formats(cfg))}")


def _normalize_mp3_bitrate(bitrate: str = "192k") -> str:
    value = str(bitrate or "192k").strip().lower()
    if value not in ALLOWED_MP3_BITRATES:
        raise ValueError(f"Unsupported MP3 bitrate: {bitrate}. Allowed: {', '.join(sorted(ALLOWED_MP3_BITRATES))}")
    return value


def _normalize_ffmpeg_bitrate(value: str, fallback: str, *, min_kbps: int, max_kbps: int) -> str:
    raw = str(value or fallback).strip().lower()
    match = re.fullmatch(r"(\d{1,4})k", raw)
    if not match:
        return fallback
    kbps = int(match.group(1))
    if not (min_kbps <= kbps <= max_kbps):
        return fallback
    return f"{kbps}k"


def _ffmpeg_binary(cfg) -> str:
    return str(getattr(cfg, "ffmpeg_binary", "ffmpeg") or "ffmpeg").strip() or "ffmpeg"


def _require_ffmpeg(cfg) -> str:
    if not ffmpeg_effective_enabled(cfg):
        raise HTTPException(
            status_code=400,
            detail=_detail("FFMPEG_DISABLED", "当前未启用 FFmpeg 转码，请在管理后台启用后重试。"),
        )
    binary = _ffmpeg_binary(cfg)
    if not shutil.which(binary):
        raise HTTPException(
            status_code=400,
            detail=_detail("FFMPEG_UNAVAILABLE", f"FFmpeg 不可用，请确认已安装并可执行：{binary}"),
        )
    return binary


def transcode_wav_bytes(wav_bytes: bytes, cfg, fmt: str) -> tuple[bytes, str]:
    """把 PCM16 WAV 转为公开 API 的可选完整文件格式。"""

    normalized = normalize_response_format(fmt, cfg)
    if normalized not in TRANSCODE_FORMATS:
        raise ValueError(f"不需要 FFmpeg 转码的格式：{normalized}")
    binary = _require_ffmpeg(cfg)
    timeout = max(1.0, float(getattr(cfg, "ffmpeg_timeout_seconds", 30.0) or 30.0))

    if normalized == "mp3":
        codec_args = ["-codec:a", "libmp3lame", "-b:a", _normalize_mp3_bitrate(getattr(cfg, "mp3_bitrate", "192k")), "-f", "mp3"]
        media_type = "audio/mpeg"
    elif normalized == "ogg_opus":
        bitrate = _normalize_ffmpeg_bitrate(getattr(cfg, "audio_opus_bitrate", "32k"), "32k", min_kbps=8, max_kbps=256)
        codec_args = ["-codec:a", "libopus", "-b:a", bitrate, "-vbr", "on", "-f", "ogg"]
        media_type = "audio/ogg"
    else:  # m4a
        bitrate = _normalize_ffmpeg_bitrate(getattr(cfg, "audio_aac_bitrate", "96k"), "96k", min_kbps=24, max_kbps=512)
        codec_args = ["-codec:a", "aac", "-b:a", bitrate, "-f", "ipod"]
        media_type = "audio/mp4"

    if normalized == "m4a":
        # FFmpeg 的 ipod/mp4 muxer 需要 seekable 输出，不能稳定写到 pipe:1。
        # 因此 m4a 使用受控临时目录落盘，再读取完整文件返回；mp3/ogg 继续走管道。
        with tempfile.TemporaryDirectory(prefix="angevoice_ffmpeg_") as tmpdir:
            output_path = Path(tmpdir) / "output.m4a"
            proc = subprocess.run(
                [binary, "-hide_banner", "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-vn", *codec_args, str(output_path)],
                input=wav_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
            )
            if proc.returncode != 0 or not output_path.exists():
                err = proc.stderr.decode("utf-8", errors="ignore").strip() or "ffmpeg conversion failed"
                logger.warning("FFmpeg audio conversion failed: %s", err)
                raise HTTPException(status_code=400, detail=_detail("FFMPEG_CONVERSION_FAILED", "音频转码失败，请检查 FFmpeg 编码器支持。"))
            return output_path.read_bytes(), media_type

    proc = subprocess.run(
        [binary, "-hide_banner", "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-vn", *codec_args, "pipe:1"],
        input=wav_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore").strip() or "ffmpeg conversion failed"
        logger.warning("FFmpeg audio conversion failed: %s", err)
        raise HTTPException(status_code=400, detail=_detail("FFMPEG_CONVERSION_FAILED", "音频转码失败，请检查 FFmpeg 编码器支持。"))
    return proc.stdout, media_type


def media_type_for_format(fmt: str) -> str:
    normalized = normalize_audio_format_name(fmt)
    if normalized == "mp3":
        return "audio/mpeg"
    if normalized == "ogg_opus":
        return "audio/ogg"
    if normalized == "m4a":
        return "audio/mp4"
    if normalized == "pcm":
        return "audio/pcm"
    return "audio/wav"

"""Optional service endpoints for Kokoro TTS.

This module keeps product/service features out of server.py so the core server stays
small and easy to review.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional


def _safe_zip_filename(name: Optional[str], index: int, ext: str) -> str:
    raw = (name or f"speech_{index + 1:03d}").strip()
    raw = raw.replace("/", "_").replace("\\", "_")
    raw = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in raw)
    if not raw:
        raw = f"speech_{index + 1:03d}"
    if not raw.lower().endswith(f".{ext}"):
        raw = f"{raw}.{ext}"
    return raw


def _wav_to_mp3(wav_bytes: bytes, bitrate: str = "192k") -> bytes:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found")
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "wav",
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            "-f",
            "mp3",
            "pipe:1",
        ],
        input=wav_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore") or "ffmpeg mp3 conversion failed"
        raise RuntimeError(err)
    return proc.stdout


def register_extra_routes(
    *,
    app,
    cfg,
    eng,
    verify_api_key,
    tts_cache,
    active_requests,
    stats,
    synthesize_threaded: Callable,
    new_request_id: Callable[[], str],
    normalize_response_format: Callable[[str], str],
    mark_request: Callable,
    finish_request: Callable,
):
    """Register optional v2.4 service routes on the existing FastAPI app."""
    from fastapi import Depends, File, HTTPException, UploadFile
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field

    class BatchItem(BaseModel):
        text: str = Field(..., description="Text to synthesize")
        voice: Optional[str] = Field(default=None, description="Voice name")
        speed: Optional[float] = Field(default=None, ge=0.5, le=2.0, description="Speed")
        filename: Optional[str] = Field(default=None, description="File name in zip")

    class BatchTTSRequest(BaseModel):
        items: list[BatchItem]
        voice: str = "zm_010"
        speed: float = Field(default=1.0, ge=0.5, le=2.0)
        response_format: str = "wav"

    async def verify_admin(_=Depends(verify_api_key)):
        if not cfg.admin_enabled:
            raise HTTPException(status_code=404, detail="Admin API disabled")

    def normalize_extra_format(fmt: str) -> str:
        fmt = (fmt or "wav").lower()
        if fmt == "mp3":
            if not cfg.mp3_enabled:
                raise HTTPException(
                    status_code=400,
                    detail="MP3 output disabled. Set KOKORO_MP3_ENABLED=true and install ffmpeg.",
                )
            return "mp3"
        return normalize_response_format(fmt)

    async def synthesize_optional_mp3(text: str, voice: str, speed: float, fmt: str, request_id: str):
        fmt = normalize_extra_format(fmt)
        if fmt != "mp3":
            return await synthesize_threaded(text, voice, speed, fmt, request_id)
        # Generate WAV first, then convert. This keeps MP3 optional and out of the core path.
        wav_bytes, _ = await synthesize_threaded(text, voice, speed, "wav", request_id)
        try:
            mp3_bytes = _wav_to_mp3(wav_bytes, getattr(cfg, "mp3_bitrate", "192k"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return mp3_bytes, "audio/mpeg"

    @app.post("/v1/audio/batch")
    async def batch_tts(req: BatchTTSRequest, _=Depends(verify_api_key)):
        """Batch synthesize multiple texts and return a ZIP file."""
        if not cfg.batch_enabled:
            raise HTTPException(status_code=404, detail="Batch API disabled")
        if not req.items:
            raise HTTPException(status_code=400, detail="items cannot be empty")
        if len(req.items) > cfg.batch_max_items:
            raise HTTPException(status_code=400, detail=f"too many items, max {cfg.batch_max_items}")

        fmt = normalize_extra_format(req.response_format)
        ext = "raw" if fmt == "pcm" else fmt
        batch_id = new_request_id()
        stats["batch_requests_total"] = stats.get("batch_requests_total", 0) + 1
        stats["batch_items_total"] = stats.get("batch_items_total", 0) + len(req.items)
        mark_request(batch_id, "queued", batch=True, items=len(req.items), format=fmt)

        manifest = []
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for index, item in enumerate(req.items):
                text = item.text
                if not text:
                    manifest.append({"index": index, "status": "error", "error": "text is empty"})
                    continue
                item_id = f"{batch_id}-{index + 1:03d}"
                voice = item.voice or req.voice
                speed = item.speed if item.speed is not None else req.speed
                filename = _safe_zip_filename(item.filename, index, ext)
                try:
                    audio_bytes, _media_type = await synthesize_optional_mp3(text, voice, speed, fmt, item_id)
                    zf.writestr(filename, audio_bytes)
                    manifest.append({"index": index, "status": "ok", "filename": filename, "bytes": len(audio_bytes)})
                except Exception as exc:
                    manifest.append({"index": index, "status": "error", "error": str(exc)})
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        finish_request(batch_id, "done", items=len(req.items))
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "X-Request-ID": batch_id,
                "Content-Disposition": f'attachment; filename="kokoro_batch_{batch_id}.zip"',
            },
        )

    @app.delete("/admin/cache")
    async def clear_cache(_=Depends(verify_admin)):
        size = len(tts_cache)
        tts_cache.clear()
        return {"ok": True, "cleared": size}

    @app.get("/admin/voices")
    async def admin_voices(_=Depends(verify_admin)):
        return {"voices": cfg.get_voices(), "voices_dir": str(cfg.voices_dir)}

    @app.post("/admin/voices/upload")
    async def upload_voice(file: UploadFile = File(...), _=Depends(verify_admin)):
        if not cfg.voice_upload_enabled:
            raise HTTPException(status_code=404, detail="Voice upload disabled")
        filename = Path(file.filename or "").name
        if not filename.endswith(".pt"):
            raise HTTPException(status_code=400, detail="Only .pt voice files are accepted")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        cfg.voices_dir.mkdir(parents=True, exist_ok=True)
        target = cfg.voices_dir / filename
        target.write_bytes(content)
        return {"ok": True, "voice": target.stem, "bytes": len(content), "path": str(target)}

    @app.get("/v1/audio/formats")
    async def audio_formats():
        formats = ["wav", "pcm"]
        if cfg.mp3_enabled:
            formats.append("mp3")
        return {
            "formats": formats,
            "mp3_enabled": cfg.mp3_enabled,
            "mp3_requires_ffmpeg": True,
            "mp3_available": bool(shutil.which("ffmpeg")),
        }

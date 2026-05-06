"""AngeVoice FastAPI application factory.

The historical public API remains ``kokoro_tts.server.create_app`` and
``kokoro_tts.server.run_server``. Route implementations live under
``kokoro_tts.routes`` so this file stays focused on application assembly.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from .config import TTSConfig, load_config
from .engine import TTSEngine
from .routes import create_audio_router, create_status_router, create_ws_router
from .security import make_verify_api_key
from .service_state import ServiceState

logger = logging.getLogger(__name__)


_WORKER_ENV_EXPORTS = {
    "KOKORO_MODEL_DIR": "model_path",
    "KOKORO_DEVICE": "device",
    "KOKORO_DEFAULT_VOICE": "default_voice",
    "KOKORO_STREAM_FORMAT": "stream_format",
    "KOKORO_MP3_BITRATE": "mp3_bitrate",
    "KOKORO_MAX_CONCURRENT_REQUESTS": "max_concurrent_requests",
    "KOKORO_MAX_TEXT_LENGTH": "max_text_length",
    "KOKORO_SEGMENT_LENGTH": "segment_length",
    "KOKORO_CACHE_MAX_ITEMS": "cache_max_items",
    "KOKORO_BATCH_MAX_ITEMS": "batch_max_items",
    "KOKORO_BATCH_CONCURRENCY": "batch_concurrency",
    "KOKORO_DEFAULT_SPEED": "default_speed",
    "KOKORO_REQUEST_TIMEOUT_SECONDS": "request_timeout_seconds",
    "KOKORO_STREAM_BINARY_ENABLED": "stream_binary_enabled",
    "KOKORO_CACHE_ENABLED": "cache_enabled",
    "KOKORO_QUEUE_STATUS_ENABLED": "queue_status_enabled",
    "KOKORO_METRICS_ENABLED": "metrics_enabled",
    "KOKORO_BATCH_ENABLED": "batch_enabled",
    "KOKORO_ADMIN_ENABLED": "admin_enabled",
    "KOKORO_VOICE_UPLOAD_ENABLED": "voice_upload_enabled",
    "KOKORO_MP3_ENABLED": "mp3_enabled",
}


def _stringify_env_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _export_config_for_workers(cfg: TTSConfig) -> None:
    for env_name, attr in _WORKER_ENV_EXPORTS.items():
        os.environ[env_name] = _stringify_env_value(getattr(cfg, attr))
    os.environ["KOKORO_CORS_ORIGINS"] = ",".join(cfg.cors_origins)
    if cfg.api_key:
        os.environ["KOKORO_API_KEY"] = cfg.api_key


def create_app(config: Optional[TTSConfig] = None, engine: Optional[TTSEngine] = None):
    """Create the AngeVoice FastAPI app with delayed heavyweight imports."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    cfg = config or load_config()
    cfg.validate_security()
    eng = engine or TTSEngine(cfg)
    state = ServiceState(cfg, eng)
    verify_api_key = make_verify_api_key(cfg)

    @asynccontextmanager
    async def lifespan(app):
        eng.load()
        logger.info("AngeVoice service started (device=%s)", eng._device)
        yield

    app = FastAPI(
        title="AngeVoice",
        description="Lightweight Chinese TTS service built on Kokoro v1.1 model",
        version="2.5.0",
        lifespan=lifespan,
    )
    app.state.angevoice = state

    allow_credentials = "*" not in cfg.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        try:
            from fastapi.staticfiles import StaticFiles
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        except Exception:
            logger.debug("Static file serving is unavailable", exc_info=True)

    templates = None
    try:
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    except Exception:
        logger.debug("Jinja2 templates are unavailable", exc_info=True)

    app.include_router(create_status_router(state, verify_api_key, templates=templates))
    app.include_router(create_audio_router(state, verify_api_key))
    app.include_router(create_ws_router(state))

    from .service_extras import register_extra_routes
    register_extra_routes(app=app, cfg=cfg, eng=eng, verify_api_key=verify_api_key, **state.as_service_extras_kwargs())
    return app


def run_server(config: Optional[TTSConfig] = None):
    import uvicorn

    cfg = config or load_config()
    logger.info("Starting AngeVoice service: %s:%s", cfg.host, cfg.port)
    if cfg.workers > 1:
        _export_config_for_workers(cfg)
        uvicorn.run(
            "kokoro_tts.server:create_app",
            factory=True,
            host=cfg.host,
            port=cfg.port,
            workers=cfg.workers,
        )
        return

    eng = TTSEngine(cfg)
    app = create_app(config=cfg, engine=eng)
    uvicorn.run(app, host=cfg.host, port=cfg.port, workers=1)

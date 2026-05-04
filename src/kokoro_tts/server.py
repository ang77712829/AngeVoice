"""Kokoro TTS HTTP 服务

提供 OpenAI 兼容的 TTS API 和 Web UI。
FastAPI 在启动时才导入。
"""

import asyncio
import hmac
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

from .config import TTSConfig, load_config
from .engine import TTSEngine

logger = logging.getLogger(__name__)


def create_app(config: Optional[TTSConfig] = None, engine: Optional[TTSEngine] = None):
    """创建 FastAPI 应用（延迟导入 FastAPI）

    可传入自定义 config 和 engine，用于嵌入场景。
    """
    from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, StreamingResponse
    from pydantic import BaseModel, ConfigDict, Field
    from starlette.concurrency import run_in_threadpool

    cfg = config or load_config()
    eng = engine or TTSEngine(cfg)
    tts_semaphore = asyncio.Semaphore(max(1, int(cfg.max_concurrent_requests)))

    # Lifespan
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        eng.load()
        logger.info(f"Kokoro TTS 服务启动 (device={eng._device})")
        yield

    app = FastAPI(
        title="Kokoro TTS",
        description="轻量级中文 TTS 服务 (Kokoro v1.1)",
        version="2.1.3",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 模板（可选）
    templates = None
    try:
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    except Exception:
        pass

    # 请求模型
    class TTSRequest(BaseModel):
        model: str = Field(default="kokoro", description="模型名称，兼容 OpenAI 请求")
        input: str = Field(..., description="要合成的文本", alias="text")
        voice: str = Field(default="zm_010", description="音色名称")
        speed: float = Field(default=1.0, ge=0.5, le=2.0, description="语速")
        response_format: str = Field(default="wav", description="音频格式：wav 或 pcm")

        model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # API Key 验证
    async def verify_api_key(request: Request):
        if cfg.api_key:
            auth = request.headers.get("Authorization", "")
            token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
            if not hmac.compare_digest(token, cfg.api_key or ""):
                raise HTTPException(status_code=401, detail="Invalid API key")

    def _normalize_response_format(fmt: str) -> str:
        fmt = (fmt or "wav").lower()
        if fmt in {"wav", "pcm"}:
            return fmt
        raise HTTPException(
            status_code=400,
            detail="Unsupported response_format. Currently supported: wav, pcm",
        )

    def _synthesize_response_bytes(text: str, voice: str, speed: float, fmt: str) -> tuple[bytes, str]:
        fmt = _normalize_response_format(fmt)
        if fmt == "pcm":
            wav = eng.synthesize_array(text=text, voice=voice, speed=speed)
            return eng._encode_segment(wav, "pcm_s16le"), "audio/pcm"
        return eng.synthesize(text=text, voice=voice, speed=speed), "audio/wav"

    async def _synthesize_response_threaded(text: str, voice: str, speed: float, fmt: str):
        async with tts_semaphore:
            return await run_in_threadpool(
                _synthesize_response_bytes,
                text,
                voice,
                speed,
                fmt,
            )

    async def _verify_ws_key(websocket: WebSocket, token: str = "") -> bool:
        if not cfg.api_key:
            return True

        auth = websocket.headers.get("authorization", "")
        header_token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
        supplied = token or header_token
        return hmac.compare_digest(supplied, cfg.api_key or "")

    # ── 路由 ──

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if templates:
            voices = cfg.get_voices()
            return templates.TemplateResponse(request, "index.html", {"voices": voices})
        return HTMLResponse("<h1>Kokoro TTS</h1><p>API 文档: <a href='/docs'>/docs</a></p>")

    @app.get("/health")
    async def health():
        return {
            "status": "ok" if eng.is_loaded else "loading",
            "device": eng._device,
            "voices": cfg.get_voices(),
            "sample_rate": cfg.sample_rate,
            "max_concurrent_requests": cfg.max_concurrent_requests,
        }

    @app.get("/v1/audio/voices")
    async def list_voices():
        return {"voices": cfg.get_voices()}

    @app.post("/v1/audio/speech")
    async def openai_tts(req: TTSRequest, _=Depends(verify_api_key)):
        """OpenAI 兼容 TTS 接口"""
        try:
            audio_bytes, media_type = await _synthesize_response_threaded(
                text=req.input,
                voice=req.voice,
                speed=req.speed,
                fmt=req.response_format,
            )
            return StreamingResponse(BytesIO(audio_bytes), media_type=media_type)
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"TTS 合成失败: {e}")
            raise HTTPException(status_code=500, detail="合成失败，请检查参数")

    @app.post("/api/tts")
    async def tts_post(request: Request, _=Depends(verify_api_key)):
        """兼容旧版接口（支持 JSON 和 Form）"""
        content_type = request.headers.get("Content-Type", "")

        if "application/json" in content_type:
            data = await request.json()
            text = data.get("text") or data.get("input") or data.get("prompt")
            voice = data.get("voice") or data.get("speaker") or cfg.default_voice
            speed = data.get("speed", data.get("rate", cfg.default_speed))
            fmt = data.get("response_format", data.get("format", "wav"))
        else:
            form = await request.form()
            text = form.get("text")
            voice = form.get("voice", cfg.default_voice)
            speed = form.get("speed", cfg.default_speed)
            fmt = form.get("response_format", form.get("format", "wav"))

        if not text:
            raise HTTPException(status_code=400, detail="缺少 text 参数")
        if len(text) > cfg.max_text_length:
            raise HTTPException(status_code=400, detail=f"文本过长，上限 {cfg.max_text_length} 字符")

        try:
            audio_bytes, media_type = await _synthesize_response_threaded(
                text=text,
                voice=voice,
                speed=float(speed),
                fmt=fmt,
            )
            return StreamingResponse(BytesIO(audio_bytes), media_type=media_type)
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"TTS 合成失败: {e}")
            raise HTTPException(status_code=500, detail="合成失败，请检查参数")

    @app.get("/api/tts")
    async def tts_get(
        text: str,
        voice: str = "zm_010",
        speed: float = 1.0,
        response_format: str = "wav",
        _=Depends(verify_api_key),
    ):
        """GET 方式调用"""
        if not text:
            raise HTTPException(status_code=400, detail="缺少 text 参数")
        try:
            audio_bytes, media_type = await _synthesize_response_threaded(
                text=text,
                voice=voice,
                speed=speed,
                fmt=response_format,
            )
            return StreamingResponse(BytesIO(audio_bytes), media_type=media_type)
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"TTS 合成失败: {e}")
            raise HTTPException(status_code=500, detail="合成失败，请检查参数")

    # ── WebSocket 流式合成 ──

    @app.websocket("/ws/v1/tts")
    async def ws_tts(websocket: WebSocket):
        await websocket.accept()
        try:
            msg = await websocket.receive_json()
            text = msg.get("text", "")
            voice = msg.get("voice", cfg.default_voice)
            speed = msg.get("speed", cfg.default_speed)
            fmt = msg.get("format", cfg.stream_format)
            token = msg.get("token", "")

            # API Key 验证：支持首帧 token 或 Authorization: Bearer
            if not await _verify_ws_key(websocket, token=token):
                await websocket.send_json({"type": "error", "message": "Unauthorized"})
                return

            if not cfg.stream_enabled:
                await websocket.send_json({"type": "error", "message": "流式合成未启用"})
                return

            if not text:
                await websocket.send_json({"type": "error", "message": "缺少 text 参数"})
                return

            if len(text) > cfg.max_text_length:
                await websocket.send_json(
                    {"type": "error", "message": f"文本过长，上限 {cfg.max_text_length}"}
                )
                return

            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            done_marker = object()

            def producer():
                try:
                    for chunk in eng.synthesize_stream(text, voice, speed, fmt):
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
                except Exception as exc:
                    logger.error(f"WS TTS 生产者错误: {exc}")
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"type": "error", "message": str(exc)},
                    )
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, done_marker)

            async with tts_semaphore:
                producer_task = asyncio.create_task(asyncio.to_thread(producer))
                try:
                    while True:
                        chunk = await queue.get()
                        if chunk is done_marker:
                            break
                        await websocket.send_json(chunk)
                finally:
                    await producer_task
        except Exception as e:
            logger.error(f"WS TTS 错误: {e}")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    return app


def run_server(config: Optional[TTSConfig] = None):
    """启动 HTTP 服务"""
    import uvicorn

    cfg = config or load_config()
    app = create_app(config=cfg)
    logger.info(f"启动服务: {cfg.host}:{cfg.port}")
    uvicorn.run(app, host=cfg.host, port=cfg.port, workers=cfg.workers)

"""模型无关的流式请求、事件和取消契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .synthesis import GenerationParameters, VoiceCondition


@dataclass(frozen=True)
class StreamingRequest:
    text: str
    model_id: str
    voice: str
    speed: float
    audio_format: str = "pcm_s16le"
    binary: bool = False
    condition: VoiceCondition = field(default_factory=VoiceCondition)
    generation: GenerationParameters = field(default_factory=GenerationParameters)
    request_id: str = ""

    @property
    def engine_params(self) -> dict[str, Any]:
        return self.generation.as_dict()


@dataclass(frozen=True)
class StreamingResult:
    """通过 WebSocket 传输的稳定事件封装。"""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_frame(cls, frame: dict[str, Any], *, model_id: str, request_id: str = "") -> "StreamingResult":
        data = dict(frame)
        event_type = str(data.pop("type", "event") or "event")
        data.setdefault("model", model_id)
        if request_id:
            data.setdefault("request_id", request_id)
        return cls(event_type, data)

    def as_frame(self) -> dict[str, Any]:
        return {"type": self.type, **self.payload}


@dataclass(frozen=True)
class CancellationContext:
    """任意适配器都可读取的传输无关取消信号。"""

    request_id: str = ""
    is_cancelled: Callable[[], bool] | None = None

    def cancelled(self) -> bool:
        return bool(self.is_cancelled and self.is_cancelled())

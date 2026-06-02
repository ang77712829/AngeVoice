"""模型无关的合成请求、参数、结果和音色条件契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VoiceConditionKind(str, Enum):
    """模型接收音色身份或参考条件的方式。"""

    PRESET = "preset"
    UPLOADED_REFERENCE = "uploaded_reference"
    SAVED_PROFILE = "saved_profile"


@dataclass(frozen=True)
class VoiceCondition:
    """所有适配器共享的已解析音色输入。

    路由层不需要知道用户选择的是内置音色、已保存参考音色，
    还是浏览器上传的临时录音。新模型通过能力声明和档案存储接入，
    避免继续增加路由分支。
    """

    kind: VoiceConditionKind = VoiceConditionKind.PRESET
    engine_id: str = ""
    voice_id: str = ""
    prompt_audio_path: str | None = None
    prompt_audio_id: str = ""
    prompt_text: str = ""
    revision: str = ""
    language: str = ""
    speaker_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_reference_conditioned(self) -> bool:
        return bool(self.prompt_audio_path)

    @property
    def cache_audio_id(self) -> str:
        return str(self.prompt_audio_id or "")

    def as_dict(self, *, include_path: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind.value,
            "engine_id": self.engine_id,
            "voice_id": self.voice_id,
            "prompt_audio_id": self.prompt_audio_id,
            "prompt_text_present": bool(self.prompt_text),
            "revision": self.revision,
            "language": self.language,
            "speaker_id": self.speaker_id,
            "metadata": dict(self.metadata),
            "reference_conditioned": self.is_reference_conditioned,
        }
        if include_path:
            payload["prompt_audio_path"] = self.prompt_audio_path
        return payload


@dataclass(frozen=True)
class GenerationParameters:
    """由模型参数 schema 校验后的生成控制项。"""

    values: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)


@dataclass(frozen=True)
class SynthesisRequest:
    """非流式合成使用的已校验内部请求。"""

    text: str
    model_id: str
    voice: str
    speed: float
    response_format: str = "wav"
    response_encoding: str = "binary"
    condition: VoiceCondition = field(default_factory=VoiceCondition)
    generation: GenerationParameters = field(default_factory=GenerationParameters)
    request_id: str = ""

    @property
    def engine_params(self) -> dict[str, Any]:
        """兼容旧服务调用方的参数别名。"""
        return self.generation.as_dict()

    def cache_controls(self) -> dict[str, Any]:
        return self.generation.as_dict()


@dataclass(frozen=True)
class SynthesisResult:
    """服务适配器使用的模型无关合成结果封装。"""

    audio_bytes: bytes
    media_type: str
    model_id: str
    request_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_response_tuple(self) -> tuple[bytes, str]:
        return self.audio_bytes, self.media_type

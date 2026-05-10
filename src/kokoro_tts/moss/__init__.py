"""MOSS 推理辅助模块。

这里放置 MOSS 引擎中可独立测试、可复用的纯逻辑。旧的
``kokoro_tts.moss_engine.MossNanoEngine`` 对外路径保持不变，避免破坏
历史导入；后续可以逐步把旧类内部实现迁移到本包。
"""

from .postprocess import MossAudioQuality, concat_waveforms, normalize_waveform, silence_array, split_waveform_for_stream
from .streaming import StreamBudgetThresholds, merge_codec_audio, resolve_stream_decode_frame_budget, runtime_supports_frame_streaming

__all__ = [
    "MossAudioQuality",
    "StreamBudgetThresholds",
    "concat_waveforms",
    "merge_codec_audio",
    "normalize_waveform",
    "resolve_stream_decode_frame_budget",
    "runtime_supports_frame_streaming",
    "silence_array",
    "split_waveform_for_stream",
]

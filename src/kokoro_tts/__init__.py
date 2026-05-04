"""AngeVoice — lightweight Chinese TTS service built on Kokoro v1.1.

Usage:
    # Library
    from kokoro_tts import TTSEngine
    engine = TTSEngine()
    engine.load()
    wav_bytes = engine.synthesize("你好世界")

    # CLI
    kokoro-tts serve
    kokoro-tts synth "你好" -o out.wav
    kokoro-tts voices
"""

__version__ = "2.4.0"

# Lazy imports — don't force numpy/torch at package import time.
def __getattr__(name):
    if name == "TTSEngine":
        from .engine import TTSEngine
        return TTSEngine
    if name == "TTSConfig":
        from .config import TTSConfig
        return TTSConfig
    if name == "load_config":
        from .config import load_config
        return load_config
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["TTSEngine", "TTSConfig", "load_config"]

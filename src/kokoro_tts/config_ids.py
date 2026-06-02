"""AngeVoice 模型 ID 与兼容别名归一化。"""

MODEL_FILENAME = "kokoro-v1_1-zh.pth"

PLACEHOLDER_API_KEYS = {
    "change-me",
    "change-me-to-a-real-secret-key",
    "change-me-to-a-real-secret",
    "replace-with-a-long-random-token",
    "<paste-generated-token-here>",
    "paste-generated-token-here",
    "<your-generated-secret>",
    "your-generated-secret",
    "staging-change-me-to-real-key",
}

PLACEHOLDER_ADMIN_PASSWORDS = {
    "change-me",
    "change-me-please-use-a-strong-password",
    "your-real-strong-password",
    "你的真实强密码",
    "请改为至少16位强密码",
    "<strong-password>",
    "strong-password",
}

MOSS_GENERIC_MODEL_IDS = {"moss", "moss-nano", "moss-tts-nano"}
MOSS_CPU_MODEL_IDS = {"moss-cpu", "moss-nano-cpu", "moss-tts-nano-cpu"}
MOSS_CUDA_MODEL_IDS = {"moss-cuda", "moss-gpu", "moss-nano-cuda", "moss-tts-nano-cuda"}
MOSS_BUILTIN_VOICES = (
    "Junhao",
    "Zhiming",
    "Weiguo",
    "Xiaoyu",
    "Yuewen",
    "Lingyu",
    "Trump",
    "Ava",
    "Bella",
    "Adam",
    "Nathan",
    "Soyo",
    "Saki",
    "Mortis",
    "Umiri",
    "Mei",
    "Anon",
    "Arisa",
)


def moss_voice_catalog(default_voice: str = "Junhao") -> list[str]:
    """返回 MOSS 预设音色目录，并确保配置默认音色排在最前。"""
    default = str(default_voice or "").strip()
    voices = [default] if default else []
    for voice in MOSS_BUILTIN_VOICES:
        if voice and voice not in voices:
            voices.append(voice)
    return voices or ["Junhao"]


def normalize_config_model_id(model_id: str, moss_provider: str) -> str:
    """归一化环境变量和配置文件中的模型别名。"""
    raw = str(model_id or "").strip().lower()
    if raw in MOSS_GENERIC_MODEL_IDS:
        return "moss-nano-cuda" if moss_provider == "cuda" else "moss-nano-cpu"
    if raw in MOSS_CPU_MODEL_IDS:
        return "moss-nano-cpu"
    if raw in MOSS_CUDA_MODEL_IDS:
        return "moss-nano-cuda"
    return raw

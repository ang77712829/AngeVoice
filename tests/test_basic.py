"""AngeVoice 基础测试

测试配置和引擎初始化逻辑（不需要实际模型文件）。
模型加载测试需要在有模型文件的环境中运行。
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 确保能导入包
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


class TestConfig:
    """测试配置模块"""

    def test_default_config(self):
        from kokoro_tts.config import TTSConfig
        config = TTSConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.sample_rate == 24000
        assert config.device == "auto"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("KOKORO_PORT", "9000")
        monkeypatch.setenv("KOKORO_HOST", "127.0.0.1")
        monkeypatch.setenv("KOKORO_DEVICE", "cpu")

        from kokoro_tts.config import load_config
        config = load_config()
        assert config.port == 9000
        assert config.host == "127.0.0.1"
        assert config.device == "cpu"

    def test_function_params_override(self):
        from kokoro_tts.config import load_config
        config = load_config(port=3000, device="cuda")
        assert config.port == 3000
        assert config.device == "cuda"

    def test_voices_empty_when_no_dir(self):
        from kokoro_tts.config import TTSConfig
        config = TTSConfig(model_dir=Path("/nonexistent"))
        assert config.get_voices() == []

    def test_voices_discovery(self, tmp_path):
        from kokoro_tts.config import TTSConfig
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        (voices_dir / "zm_001.pt").touch()
        (voices_dir / "zm_002.pt").touch()

        config = TTSConfig(model_dir=tmp_path)
        voices = config.get_voices()
        assert "zm_001" in voices
        assert "zm_002" in voices

    def test_model_file_property(self, tmp_path):
        from kokoro_tts.config import TTSConfig
        config = TTSConfig(model_dir=tmp_path)
        assert config.model_file == tmp_path / "kokoro-v1_1-zh.pth"

    def test_voices_dir_property(self, tmp_path):
        from kokoro_tts.config import TTSConfig
        config = TTSConfig(model_dir=tmp_path)
        assert config.voices_dir == tmp_path / "voices"


class TestTextNormalization:
    """测试中文 TTS 文本规范化。"""

    def test_date_in_chinese_context(self):
        from kokoro_tts.engine import normalize_text_for_tts

        assert normalize_text_for_tts("今天是2026-05-05。") == "今天是二零二六年五月五日。"
        assert normalize_text_for_tts("版本于2026/5/5发布") == "版本于二零二六年五月五日发布"

    def test_money_in_chinese_context(self):
        from kokoro_tts.engine import normalize_text_for_tts

        assert normalize_text_for_tts("价格100元") == "价格一百元"
        assert normalize_text_for_tts("费用为¥1000.50") == "费用为一千元五角"
        assert normalize_text_for_tts("预算12000元") == "预算一万二千元"

    def test_percent_and_phone_number(self):
        from kokoro_tts.engine import normalize_text_for_tts

        assert normalize_text_for_tts("成功率98.5%") == "成功率百分之九八点五"
        assert normalize_text_for_tts("电话13800138000") == "电话幺三八，零零幺三，八零零零"

    def test_plain_id_is_grouped_but_short_plain_number_is_unchanged(self):
        from kokoro_tts.engine import normalize_text_for_tts

        assert normalize_text_for_tts("编号12345678") == "编号幺二三四，五六七八"
        assert normalize_text_for_tts("模型版本123") == "模型版本123"


class TestEngine:
    """测试引擎模块（不需要实际模型）"""

    def test_engine_not_loaded(self):
        from kokoro_tts.engine import TTSEngine
        engine = TTSEngine()
        assert not engine.is_loaded

    def test_clean_text(self):
        from kokoro_tts.engine import TTSEngine
        engine = TTSEngine()
        assert engine._clean_text("hello\x00world") == "hello world"
        assert engine._clean_text("hello   world") == "hello world"
        assert engine._clean_text("  hello  ") == "hello"

    def test_detect_language(self):
        from kokoro_tts.engine import TTSEngine
        engine = TTSEngine()
        assert engine._detect_language("hello world test") == "en"
        assert engine._detect_language("你好世界") == "zh"
        assert engine._detect_language("") == "zh"

    def test_segment_text(self):
        from kokoro_tts.engine import TTSEngine
        engine = TTSEngine()
        text = "你好"
        segments = engine._segment_text(text)
        assert len(segments) == 1

        engine.config.segment_length = 20
        text = (
            "第一句话用于测试分段逻辑，内容需要足够长才能触发切分。"
            "第二句话继续补充长度，确保超过一倍半的切分阈值。"
            "第三句话用于验证标点优先切分。"
        )
        segments = engine._segment_text(text)
        assert len(segments) >= 2
        assert all(s for s in segments)

    def test_make_speed_fn(self):
        from kokoro_tts.engine import TTSEngine
        engine = TTSEngine()
        fn = engine._make_speed_fn(1.5)
        assert fn(100) == 1.5
        assert fn(200) == 1.5


class TestServiceState:
    """测试服务状态收尾逻辑。"""

    @pytest.mark.asyncio
    async def test_http_exception_finishes_request_state(self):
        from fastapi import HTTPException
        from kokoro_tts.config import TTSConfig
        from kokoro_tts.service_state import ServiceState

        cfg = TTSConfig(mp3_enabled=False)
        engine = MagicMock()
        state = ServiceState(cfg, engine)

        with pytest.raises(HTTPException) as exc_info:
            await state.synthesize_response_threaded("你好", "zm_010", 1.0, "mp3", "req-http-error")

        assert exc_info.value.status_code == 400
        assert state.active_requests["req-http-error"]["status"] == "error"
        assert state.active_requests["req-http-error"]["status_code"] == 400
        assert state.stats["requests_error"] == 1
        assert state.stats["requests_ok"] == 0

    @pytest.mark.asyncio
    async def test_cancelled_request_finishes_as_cancelled(self):
        from fastapi import HTTPException
        from kokoro_tts.config import TTSConfig
        from kokoro_tts.service_state import ServiceState

        cfg = TTSConfig()
        engine = MagicMock()
        state = ServiceState(cfg, engine)
        state.request_cancel("req-cancelled")

        with pytest.raises(HTTPException) as exc_info:
            await state.synthesize_response_threaded("你好", "zm_010", 1.0, "wav", "req-cancelled")

        assert exc_info.value.status_code == 499
        assert state.active_requests["req-cancelled"]["status"] == "cancelled"
        assert state.stats["requests_error"] == 1


class TestServer:
    """测试服务器模块"""

    @pytest.mark.skipif(not _has_module("fastapi"), reason="fastapi not installed")
    def test_create_app(self):
        from kokoro_tts.server import create_app
        from kokoro_tts.config import TTSConfig
        with patch("kokoro_tts.engine.TTSEngine.load"):
            config = TTSConfig(model_dir=Path("/nonexistent"))
            app = create_app(config=config)
            assert app.title == "AngeVoice"

    @pytest.mark.skipif(not _has_module("fastapi"), reason="fastapi not installed")
    def test_tts_request_model(self):
        from kokoro_tts.server import create_app
        from kokoro_tts.config import TTSConfig
        with patch("kokoro_tts.engine.TTSEngine.load"):
            app = create_app(config=TTSConfig(model_dir=Path("/nonexistent")))
            assert app.title == "AngeVoice"


class TestCLI:
    """测试 CLI 模块"""

    def test_cli_help(self):
        from kokoro_tts.cli import main
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["kokoro-tts", "--help"]):
                main()
        assert exc_info.value.code == 0

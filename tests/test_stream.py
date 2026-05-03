"""流式语音合成测试

验证 synthesize_stream 逐段 yield、PCM 编码正确性、WebSocket 端点可连接等。
"""

import asyncio
import base64
import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestEncodeSegment:
    """测试 _encode_segment 方法"""

    def test_pcm_s16le_encoding(self):
        """PCM s16le 编码：float32 -> int16 -> bytes"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        engine = TTSEngine(config)

        # 创建一个简单的音频数组
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        result = engine._encode_segment(audio, format="pcm_s16le")

        assert isinstance(result, bytes)
        # 5 samples * 2 bytes = 10 bytes
        assert len(result) == 10

        # 解码验证
        samples = struct.unpack("<5h", result)
        assert samples[0] == 0
        assert samples[1] == 16383  # 0.5 * 32767
        assert samples[2] == -16383  # -0.5 * 32767
        assert samples[3] == 32767  # 1.0 * 32767
        assert samples[4] == -32767  # -1.0 * 32767

    def test_wav_encoding(self):
        """WAV 编码：返回有效的 WAV 字节"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        engine = TTSEngine(config)

        audio = np.random.randn(1000).astype(np.float32)
        audio = np.clip(audio, -1.0, 1.0)
        result = engine._encode_segment(audio, format="wav")

        assert isinstance(result, bytes)
        # WAV 文件头 "RIFF"
        assert result[:4] == b"RIFF"
        assert result[8:12] == b"WAVE"

    def test_unsupported_format(self):
        """不支持的格式应抛出 ValueError"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        engine = TTSEngine(config)

        audio = np.array([0.0, 0.5], dtype=np.float32)
        with pytest.raises(ValueError, match="Unsupported format"):
            engine._encode_segment(audio, format="mp3")


class TestSynthesizeStream:
    """测试 synthesize_stream 方法"""

    def test_engine_not_loaded(self):
        """未加载引擎时应返回 error"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        engine = TTSEngine(config)
        # 不调用 load()

        results = list(engine.synthesize_stream("你好"))
        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "未加载" in results[0]["message"]

    def test_empty_text(self):
        """空文本应返回 error"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        engine = TTSEngine(config)

        results = list(engine.synthesize_stream(""))
        assert len(results) == 1
        assert results[0]["type"] == "error"

    def test_text_too_long(self):
        """超长文本应返回 error"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig(max_text_length=10)
        engine = TTSEngine(config)

        results = list(engine.synthesize_stream("这是一段超过十个字符的文本"))
        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "过长" in results[0]["message"]

    @patch("kokoro_tts.engine.TTSEngine._loaded", True)
    @patch("kokoro_tts.engine.TTSEngine._zh_pipeline")
    def test_stream_yields_segments(self, mock_pipeline):
        """正常流式合成应 yield started -> audio... -> done"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        engine = TTSEngine(config)
        engine._loaded = True

        # Mock pipeline 返回
        mock_result = MagicMock()
        mock_result.audio = np.random.randn(1000).astype(np.float32)
        mock_pipeline.return_value = iter([mock_result])

        results = list(engine.synthesize_stream("你好世界", voice="zm_010"))

        # 至少应该有 started 和 done
        types = [r["type"] for r in results]
        assert "started" in types
        assert "done" in types

        # 应该有 audio 类型的消息
        audio_msgs = [r for r in results if r["type"] == "audio"]
        assert len(audio_msgs) >= 1

        # 验证 audio 消息结构
        for msg in audio_msgs:
            assert "index" in msg
            assert "data" in msg
            assert "format" in msg
            assert msg["format"] == "pcm_s16le"
            # data 应该是合法的 base64
            decoded = base64.b64decode(msg["data"])
            assert len(decoded) > 0

    def test_format_param(self):
        """format 参数应被正确传递"""
        from kokoro_tts.engine import TTSEngine
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        engine = TTSEngine(config)

        with patch.object(engine, "_loaded", True), \
             patch.object(engine, "_zh_pipeline") as mock_pipe:
            mock_result = MagicMock()
            mock_result.audio = np.array([0.5], dtype=np.float32)
            mock_pipe.return_value = iter([mock_result])

            # 使用 wav 格式
            results = list(engine.synthesize_stream("你好", fmt="wav"))
            audio_msgs = [r for r in results if r["type"] == "audio"]
            if audio_msgs:
                decoded = base64.b64decode(audio_msgs[0]["data"])
                # WAV 格式应以 RIFF 开头
                assert decoded[:4] == b"RIFF"


class TestConfigStreamFields:
    """测试 config 流式配置字段"""

    def test_stream_defaults(self):
        """默认流式配置"""
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        assert config.stream_enabled is True
        assert config.stream_format == "pcm_s16le"

    def test_stream_custom(self):
        """自定义流式配置"""
        from kokoro_tts.config import TTSConfig

        config = TTSConfig(stream_enabled=False, stream_format="wav")
        assert config.stream_enabled is False
        assert config.stream_format == "wav"


class TestWebSocketEndpoint:
    """测试 WebSocket 端点（仅验证结构，不实际连接模型）"""

    def test_app_has_ws_route(self):
        """create_app 返回的 app 应包含 /ws/v1/tts 路由"""
        from kokoro_tts.server import create_app
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        app = create_app(config=config)

        # 检查路由
        routes = [route.path for route in app.routes]
        assert "/ws/v1/tts" in routes

    def test_existing_routes_unchanged(self):
        """原有路由不应被修改"""
        from kokoro_tts.server import create_app
        from kokoro_tts.config import TTSConfig

        config = TTSConfig()
        app = create_app(config=config)

        routes = [route.path for route in app.routes]
        assert "/v1/audio/speech" in routes
        assert "/api/tts" in routes
        assert "/health" in routes
        assert "/v1/audio/voices" in routes
        assert "/" in routes

"""代码质量审查反馈的回归测试。"""

from unittest.mock import MagicMock

from kokoro_tts.config import TTSConfig
from kokoro_tts.engine import normalize_text_for_tts
from kokoro_tts.engine_manager import EngineManager, EngineSpec
from kokoro_tts.service_state import ServiceState


def test_large_money_amount_is_read_naturally():
    """十亿以上金额不能被静默跳过，也不能触发高位组异常。"""

    text = normalize_text_for_tts("合同金额为¥1234567890.50。")
    assert "十二亿" in text
    assert "三千四百五十六万" in text
    assert "七千八百九十元五角" in text


def test_model_snapshot_protects_core_identity_fields():
    """运行时 metadata 不应静默覆盖模型基础身份字段。"""

    manager = EngineManager(TTSConfig(enabled_models=["kokoro"], default_model="kokoro"))
    engine = MagicMock()
    engine.is_loaded = True
    engine.is_healthy = True
    engine.metadata.return_value = {
        "id": "evil-id",
        "name": "bad-name",
        "backend": "bad-backend",
        "loaded": True,
        "voices": ["zf_001"],
    }
    manager._engines["kokoro"] = engine

    snapshot = manager._model_snapshot(EngineSpec("kokoro", "Kokoro v1.1 Chinese", "kokoro", "cpu"))
    assert snapshot["id"] == "kokoro"
    assert snapshot["name"] == "Kokoro v1.1 Chinese"
    assert snapshot["backend"] == "kokoro"
    assert snapshot["voices"] == ["zf_001"]


def test_config_get_voices_uses_directory_signature_cache(tmp_path):
    """音色列表应缓存，并在目录变更后自动失效。"""

    model_dir = tmp_path / "models--hexgrad--Kokoro-82M-v1.1-zh"
    voices_dir = model_dir / "voices"
    voices_dir.mkdir(parents=True)
    (voices_dir / "zf_001.pt").write_bytes(b"PK\x03\x04valid")

    config = TTSConfig(model_dir=model_dir)
    assert config.get_voices() == ["zf_001"]
    (voices_dir / "zf_002.pt").write_bytes(b"PK\x03\x04valid")
    # 有些文件系统 mtime 粒度较粗，显式 touch 确保缓存签名变化。
    voices_dir.touch()
    assert config.get_voices() == ["zf_001", "zf_002"]


def test_cache_get_updates_hit_miss_stats_once():
    """缓存命中/未命中统计与读取路径保持一致。"""

    state = ServiceState(TTSConfig(cache_enabled=True, cache_max_items=2))
    assert state.cache_get("missing") is None
    state.cache_set("hit", (b"audio", "audio/wav"), text="短文本")
    assert state.cache_get("hit") == (b"audio", "audio/wav")
    stats = state.snapshot_stats()
    assert stats["cache_misses"] == 1
    assert stats["cache_hits"] == 1


def test_percent_reads_three_digits_as_number():
    """三位以上百分比应按自然数字读法，不应逐位读成一零零。"""

    text = normalize_text_for_tts("完成率达到100%，峰值为12.5%。")
    assert "百分之一百" in text
    assert "百分之一零零" not in text
    assert "百分之十二点五" in text


def test_worker_env_exports_cover_runtime_env_specs():
    """多 worker 模式应继承运行时配置里的关键环境变量。"""

    from kokoro_tts.config_env import BOOL_ENV, FLOAT_ENV, INT_ENV, STR_ENV
    from kokoro_tts.server import _WORKER_ENV_EXPORTS

    all_runtime_envs = set(STR_ENV) | set(INT_ENV) | set(FLOAT_ENV) | set(BOOL_ENV)
    process_level_only = {
        "KOKORO_HOST",
        "KOKORO_PORT",
        "KOKORO_WORKERS",
        "KOKORO_CORS_ORIGINS",
        "KOKORO_API_KEY",
        "KOKORO_AUTO_API_KEY",
    }
    missing = sorted(all_runtime_envs - set(_WORKER_ENV_EXPORTS) - process_level_only)
    assert missing == []
    assert _WORKER_ENV_EXPORTS["ANGEVOICE_IDLE_UNLOAD_CURRENT"] == "model_idle_unload_current"
    assert _WORKER_ENV_EXPORTS["KOKORO_TTS_REQUEST_MAX_BYTES"] == "tts_request_max_bytes"
    assert _WORKER_ENV_EXPORTS["KOKORO_VOICE_UPLOAD_MAX_BYTES"] == "voice_upload_max_bytes"


def test_moss_model_assets_reject_lfs_only_dir(tmp_path):
    """MOSS 目录不能只因非空就被当作有效模型目录。"""

    from kokoro_tts.model_sources import has_valid_moss_model_assets

    model_dir = tmp_path / "MOSS-TTS-Nano-100M-ONNX"
    model_dir.mkdir()
    (model_dir / "decoder.onnx").write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:dummy\n"
        "size 123456789\n",
        encoding="utf-8",
    )
    assert not has_valid_moss_model_assets(model_dir)

    (model_dir / "browser_poc_manifest.json").write_text("{}", encoding="utf-8")
    real_model = model_dir / "encoder.onnx"
    with real_model.open("wb") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"\0")
    assert has_valid_moss_model_assets(model_dir)


def test_moss_model_assets_accept_nested_browser_dir(tmp_path):
    """MOSS 目录允许把官方资产放在下级兼容目录中。"""

    from kokoro_tts.model_sources import resolve_valid_moss_model_dir

    root = tmp_path / "MOSS-TTS-Nano-100M-ONNX"
    nested = root / "MOSS-TTS-Nano-ONNX-CPU"
    nested.mkdir(parents=True)
    (nested / "browser_poc_manifest.json").write_text("{}", encoding="utf-8")
    with (nested / "encoder.onnx").open("wb") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"\0")

    assert resolve_valid_moss_model_dir(root) == nested


def test_moss_model_assets_reject_onnx_without_manifest(tmp_path):
    """缺少 browser manifest 时不能把 ONNX 文件误判为可加载资产。"""

    from kokoro_tts.model_sources import has_valid_moss_model_assets

    root = tmp_path / "MOSS-TTS-Nano-100M-ONNX"
    root.mkdir()
    with (root / "encoder.onnx").open("wb") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"\0")

    assert not has_valid_moss_model_assets(root)


def test_drop_model_unload_failure_keeps_engine_and_marks_pending():
    """模型重建前卸载失败时不能误删引擎，应保留待重建标记。"""

    manager = EngineManager(TTSConfig(enabled_models=["kokoro"], default_model="kokoro"))
    engine = MagicMock()
    engine.unload.side_effect = RuntimeError("cuda unload failed")
    manager._engines["kokoro"] = engine

    assert manager.drop_model("kokoro", force=True, raise_if_busy=False) is False
    assert manager._engines["kokoro"] is engine
    assert "kokoro" in manager._pending_rebuild


def test_get_engine_load_failure_cleanup_catches_unload_fallback_failure():
    """加载失败后，兼容旧 unload() 签名的清理异常不能覆盖原始加载异常。"""

    from unittest.mock import MagicMock

    manager = EngineManager(TTSConfig(enabled_models=["kokoro"], default_model="kokoro"))
    engine = MagicMock()
    engine.is_loaded = False
    engine.load.side_effect = RuntimeError("load failed")
    engine.unload.side_effect = [TypeError("old signature"), RuntimeError("unload failed")]
    manager._engines["kokoro"] = engine

    import pytest

    with pytest.raises(RuntimeError, match="load failed"):
        manager.get_engine("kokoro", load=True)
    assert manager._active_counts["kokoro"] == 0



def test_ensure_moss_model_dir_downloads_when_target_is_empty(monkeypatch, tmp_path):
    """MOSS 目录存在但无资产时必须触发下载，而不是直接交给 runtime 报错。"""

    from kokoro_tts import model_sources

    target = tmp_path / "MOSS-TTS-Nano-100M-ONNX"
    target.mkdir()
    cfg = TTSConfig(moss_model_dir=target, model_source="huggingface")
    calls: list[tuple[str, str]] = []

    def fake_modelscope(repo_id, target_dir, *, logger):
        calls.append(("modelscope", repo_id))
        (target_dir / "browser_poc_manifest.json").write_text("{}", encoding="utf-8")
        model_file = target_dir / "encoder.onnx"
        with model_file.open("wb") as handle:
            handle.seek(1024 * 1024)
            handle.write(b"\0")
        return target_dir

    monkeypatch.setattr(model_sources, "resolve_model_source", lambda _cfg: "huggingface")
    monkeypatch.setattr(model_sources, "_huggingface_snapshot_download", lambda *args, **kwargs: None)
    monkeypatch.setattr(model_sources, "_modelscope_snapshot_download", fake_modelscope)

    resolved = model_sources.ensure_moss_model_dir(cfg, logger=MagicMock())
    assert resolved == target
    assert ("modelscope", cfg.moss_modelscope_repo) in calls
    assert model_sources.has_valid_moss_model_assets(target)


def test_ensure_moss_model_dir_rejects_readme_only_dir(monkeypatch, tmp_path):
    """只有 README 的 MOSS 目录不能被视为可用目录。"""

    from kokoro_tts import model_sources

    target = tmp_path / "MOSS-TTS-Nano-100M-ONNX"
    target.mkdir()
    (target / "README.md").write_text("占位说明", encoding="utf-8")
    cfg = TTSConfig(moss_model_dir=target, model_source="auto")
    monkeypatch.setattr(model_sources, "resolve_model_source", lambda _cfg: "modelscope")
    monkeypatch.setattr(model_sources, "_modelscope_snapshot_download", lambda *args, **kwargs: None)
    monkeypatch.setattr(model_sources, "_huggingface_snapshot_download", lambda *args, **kwargs: None)

    resolved = model_sources.ensure_moss_model_dir(cfg, logger=MagicMock())
    assert resolved is None  # M1 修复：失败时返回 None
    assert not model_sources.has_valid_moss_model_assets(target)



# === M3: config.moss_model_dir = None 回退路径 ===

def test_ensure_moss_model_dir_fallback_when_config_is_none(monkeypatch, tmp_path):
    """config.moss_model_dir 为 None 时应回退到 default_moss_model_dir()。"""
    from kokoro_tts import model_sources

    default_dir = tmp_path / "MOSS-TTS-Nano-100M-ONNX"
    default_dir.mkdir()
    # 放入有效资产
    (default_dir / "browser_poc_manifest.json").write_text("{}", encoding="utf-8")
    model_file = default_dir / "encoder.onnx"
    with model_file.open("wb") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"\0")

    cfg = TTSConfig(moss_model_dir=None, model_source="auto")
    monkeypatch.setattr(model_sources, "default_moss_model_dir", lambda: default_dir)

    resolved = model_sources.ensure_moss_model_dir(cfg, logger=MagicMock())
    assert resolved == default_dir


# === M4: _has_large_model_file 边界值测试 ===

def test_has_large_model_file_boundary_size(tmp_path):
    """1MB 边界值测试：不足 1MB 不应通过，超过 1MB 应通过。"""
    from kokoro_tts.model_sources import _has_large_model_file

    # 不足 1MB (1MB - 1 字节)
    under_dir = tmp_path / "under_1mb"
    under_dir.mkdir()
    (under_dir / "browser_poc_manifest.json").write_text("{}", encoding="utf-8")
    under_file = under_dir / "encoder.onnx"
    with under_file.open("wb") as handle:
        handle.write(b"\0" * (1024 * 1024 - 1))  # 1MB - 1 字节
    assert not _has_large_model_file(under_dir)

    # 恰好 1MB
    exact_dir = tmp_path / "exact_1mb"
    exact_dir.mkdir()
    (exact_dir / "browser_poc_manifest.json").write_text("{}", encoding="utf-8")
    exact_file = exact_dir / "encoder.onnx"
    with exact_file.open("wb") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"\0")
    assert _has_large_model_file(exact_dir)


def test_has_large_model_file_wrong_suffix(tmp_path):
    """只有 .json/.txt 文件不应视为有效模型资产。"""
    from kokoro_tts.model_sources import _has_large_model_file

    dir_path = tmp_path / "wrong_suffix"
    dir_path.mkdir()
    (dir_path / "browser_poc_manifest.json").write_text("{}", encoding="utf-8")
    # 创建一个大文件但后缀不对
    big_file = dir_path / "data.txt"
    with big_file.open("wb") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"\0")
    assert not _has_large_model_file(dir_path)


# === M5: resolve_valid_moss_model_dir 警告日志测试 ===

def test_resolve_valid_moss_model_dir_warns_lfs_only(tmp_path, caplog):
    """只有 LFS 指针的目录应触发 LFS 指针警告。"""
    import logging
    from kokoro_tts.model_sources import resolve_valid_moss_model_dir

    lfs_dir = tmp_path / "lfs_only"
    lfs_dir.mkdir()
    # 写一个 LFS 指针文件
    (lfs_dir / "encoder.onnx").write_text("version https://git-lfs.github.com/spec/v1", encoding="utf-8")

    logger = logging.getLogger("test")
    with caplog.at_level(logging.WARNING):
        result = resolve_valid_moss_model_dir(lfs_dir, log=logger)
    assert result is None
    assert any("LFS 指针" in msg for msg in caplog.messages)


def test_resolve_valid_moss_model_dir_warns_missing_manifest(tmp_path, caplog):
    """缺少 manifest 的目录应触发 manifest 缺失警告。"""
    import logging
    from kokoro_tts.model_sources import resolve_valid_moss_model_dir

    no_manifest_dir = tmp_path / "no_manifest"
    no_manifest_dir.mkdir()
    # 创建一个大文件但没有 manifest
    model_file = no_manifest_dir / "encoder.onnx"
    with model_file.open("wb") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"\0")

    logger = logging.getLogger("test")
    with caplog.at_level(logging.WARNING):
        result = resolve_valid_moss_model_dir(no_manifest_dir, log=logger)
    assert result is None
    assert any("browser_poc_manifest.json" in msg for msg in caplog.messages)

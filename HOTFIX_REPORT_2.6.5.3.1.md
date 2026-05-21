# AngeVoice 2.6.5.3.1 紧急修复报告

## 修复背景

在 2.6.5.3 中，模型目录统一到了 `/app/models`，MOSS 默认目录变为：

```text
/app/models/MOSS-TTS-Nano-100M-ONNX
```

实际部署后切换 `moss-nano-cpu` 或 `moss-nano-cuda` 时出现：

```text
browser_onnx model assets not found under the provided --model-dir
```

日志显示官方 OpenMOSS runtime 查找了以下路径但均未找到 `browser_poc_manifest.json`：

```text
/app/models/MOSS-TTS-Nano-100M-ONNX/browser_poc_manifest.json
/app/models/MOSS-TTS-Nano-100M-ONNX/MOSS-TTS-Nano-100M-ONNX/browser_poc_manifest.json
/app/models/MOSS-TTS-Nano-100M-ONNX/MOSS-TTS-Nano-ONNX-CPU/browser_poc_manifest.json
```

## 根因

`ensure_moss_model_dir()` 在统一模型目录后仍存在一个致命缺口：

1. 只要 `MOSS_MODEL_DIR` 被设置，就直接把该目录交给官方 runtime；
2. 没有检查目录里是否真的存在 `browser_poc_manifest.json`；
3. 没有检查目录里是否有真实 ONNX/ORT/bin/safetensors 模型文件；
4. 目录存在但为空、只有 README、只有 Git LFS 指针或只有占位文件时，不会触发自动下载；
5. CUDA fallback 到 CPU 后仍然使用同一个无效目录，所以 CPU/GPU 都会失败。

因此这不是 CUDA 独有问题，而是 MOSS 资产目录有效性判断和自动下载兜底的问题。

## 代码修复

### 1. MOSS 模型目录有效性校验升级

修改文件：

```text
src/kokoro_tts/model_sources.py
```

新增/强化：

- `_MOSS_BROWSER_MANIFEST = "browser_poc_manifest.json"`
- `_moss_browser_asset_dirs()`
- `_has_runtime_manifest()`
- `_has_large_model_file()`
- `resolve_valid_moss_model_dir()`
- `has_valid_moss_model_assets()`

新的有效目录判定必须同时满足：

1. 官方 runtime 可识别目录下存在 `browser_poc_manifest.json`；
2. 同目录或其子目录中存在真实模型权重文件；
3. 权重文件不能是 Git LFS 指针；
4. 权重文件大小需要达到真实模型资产级别。

兼容官方 runtime 的查找路径：

```text
<root>/browser_poc_manifest.json
<root>/MOSS-TTS-Nano-100M-ONNX/browser_poc_manifest.json
<root>/MOSS-TTS-Nano-ONNX-CPU/browser_poc_manifest.json
```

### 2. 目录存在但无效时自动下载

`ensure_moss_model_dir()` 现在逻辑为：

1. 优先检查当前 `MOSS_MODEL_DIR` 是否包含有效 MOSS ONNX 资产；
2. 如果目录为空、只有 README、只有 LFS 指针、缺少 manifest 或缺少真实 ONNX 权重，则继续下载；
3. 下载源按 `ANGEVOICE_MODEL_SOURCE` / 自动源站策略选择；
4. Hugging Face 源未配置或失败时，会继续尝试 ModelScope 兜底；
5. 下载后再次校验 manifest 和真实权重；
6. 校验成功才把 `config.moss_model_dir` 指向可加载目录；
7. 校验失败时给出明确 warning，提示手动放入 `browser_poc_manifest.json` 和 ONNX 文件。

### 3. 下载路径保持统一模型目录

下载目标仍然保持：

```text
/app/models/MOSS-TTS-Nano-100M-ONNX
```

不会重新引入旧的：

```text
moss_models/
/opt/MOSS-TTS-Nano/models
/root/.cache/huggingface
```

## 版本升级

版本号升级为：

```text
2.6.5.3.1
```

已同步：

```text
pyproject.toml
src/kokoro_tts/__init__.py
tests/test_basic.py
CHANGELOG.md
RELEASE_NOTES_2.6.5.3.1.md
docker/angevoice.env
docker/.env.example
```

## 文档更新

更新了排障说明：

```text
docs/TROUBLESHOOTING.md
```

新增说明：

- 出现 `browser_onnx model assets not found under the provided --model-dir` 的原因；
- 2.6.5.3.1 起会自动补全无效 MOSS 目录；
- 自动下载仍失败时如何手动放置模型；
- 必需文件包括 `browser_poc_manifest.json` 与 ONNX 资产。

## 测试补充

新增/加强测试：

```text
tests/test_quality_regressions.py
```

覆盖：

1. MOSS 目录只有 Git LFS 指针时必须判定无效；
2. 目录只有 README 时必须判定无效；
3. 目录只有 ONNX 但缺少 `browser_poc_manifest.json` 时必须判定无效；
4. manifest 和真实 ONNX 权重都存在时才判定有效；
5. MOSS 资产放在 `MOSS-TTS-Nano-ONNX-CPU` 子目录时可以正确解析；
6. 空目录会触发自动下载，而不是直接交给 runtime 报错。

## 本地验证

执行命令：

```bash
bash -n scripts/install.sh
bash -n docker/entrypoint.sh
python -m compileall -q src tests scripts
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q --disable-warnings
```

结果：

```text
131 passed
```

## 部署后预期行为

如果 `/app/models/MOSS-TTS-Nano-100M-ONNX` 为空或缺少资产，切换 MOSS 时应自动尝试下载。

若网络正常，下载完成后 `moss-nano-cpu` / `moss-nano-cuda` 应能正常加载。

若网络失败，日志会明确提示：

```text
未找到有效的 MOSS ONNX 模型资产，已尝试自动下载但仍不可用。请检查网络，或手动把 browser_poc_manifest.json 及 ONNX 资产放入：/app/models/MOSS-TTS-Nano-100M-ONNX
```

## 建议用户手动模型目录

```text
AngeVoice/models/MOSS-TTS-Nano-100M-ONNX/
├── browser_poc_manifest.json
├── *.onnx
└── 其他官方 MOSS ONNX 资产
```

或兼容子目录：

```text
AngeVoice/models/MOSS-TTS-Nano-100M-ONNX/MOSS-TTS-Nano-ONNX-CPU/browser_poc_manifest.json
```

## 总结

2.6.5.3.1 是一个紧急修复版本，目标是修复统一模型目录后 MOSS 无法自动兜底下载、切换模型 500 的致命问题。

本次修复没有改变 MOSS 的音频策略，也没有重新启用进程隔离；只修复模型资产发现、下载兜底、错误提示和测试覆盖。

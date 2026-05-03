# Kokoro TTS 中文项目修复方案

> 审查日期：2026-05-03 | 审查人：宏宏

## 修复清单

### 🔴 P0 — 必须修复（会崩溃）

#### 1. `src/kokoro_tts/engine.py:58` — os 模块未导入
- **问题**：`os.cpu_count()` 调用了 `os` 模块但文件顶部没有 `import os`
- **修复**：在文件顶部 import 区域添加 `import os`

#### 2. `Dockerfile.new` — 启动命令和引用全部错误
- **问题**：
  - `CMD ["python", "-m", "uvicorn", "src.app.main:app"]` 路径错误
  - `COPY requirements.txt .` 引用不存在的文件
  - `COPY templates/ src/kokoro_tts/templates/` 源目录不存在
- **修复**：
  - 删除 `Dockerfile.new`（已有 `docker/cpu/Dockerfile` 和 `docker/gpu/Dockerfile` 正常工作）
  - 或者修正 CMD 为 `kokoro_tts.cli:main` 入口

#### 3. `tts-project-cpu/app/main.py:91/113` — en_callable 重复定义
- **问题**：同文件定义了两次 `en_callable`，第二个覆盖第一个且缺少 try/except
- **修复**：删除第一个 `en_callable`（91行附近），保留第二个但加上 try/except 保护

#### 4. `tts-project-cpu/app/main.py:74` / `tts-project-gpu/app/main.py:70` — static 目录缺失
- **问题**：代码挂载 `app/static` 目录但不存在
- **修复**：创建 `tts-project-cpu/app/static/.gitkeep` 和 `tts-project-gpu/app/static/.gitkeep`

### ⚠️ P1 — 安全修复

#### 5. CORS 全开
- **位置**：`src/kokoro_tts/config.py:64`, `tts-project-cpu/app/main.py:67`, `tts-project-gpu/app/main.py:63`
- **修复**：改为从环境变量读取，默认 `["http://localhost:8000"]` 而非 `["*"]`

#### 6. API Key 时序攻击
- **位置**：`src/kokoro_tts/server.py:69`
- **修复**：将 `token != cfg.api_key` 改为 `not hmac.compare_digest(token, cfg.api_key or "")`
- 需要 `import hmac`

#### 7. 错误信息泄露
- **位置**：`src/kokoro_tts/server.py:113`
- **修复**：将 `detail=f"合成失败: {e}"` 改为 `detail="合成失败，请检查参数"`，原始错误只写日志

#### 8. 添加请求体大小限制
- **位置**：`src/kokoro_tts/server.py` 的 `/api/synthesize` 路由
- **修复**：在合成前检查 text 长度，超过 10000 字符返回 400

### 🟡 P2 — 功能/质量修复

#### 9. fallback 逻辑无效
- **位置**：`src/kokoro_tts/engine.py:196-206`
- **修复**：要么移除无效的 fallback，要么加入真正的重试逻辑（如换参数重试）

#### 10. 添加 LICENSE 文件
- **修复**：在项目根目录创建 `LICENSE` 文件，内容为 MIT 许可（与 pyproject.toml 一致）

#### 11. 旧版 GET 接口缺少 API Key 验证
- **位置**：`tts-project-cpu/app/main.py:195-197`, `tts-project-gpu/app/main.py:201-203`
- **修复**：给 GET `/api/tts` 和 `/api/tts/tts` 也加上 `verify_api_key` 检查

#### 12. pyproject.toml Python 版本统一
- **位置**：`pyproject.toml:11`
- **修复**：统一为 `requires-python = ">=3.10"`（与实际依赖兼容性一致）

### 🟢 P3 — 可选改进

#### 13. 创建 static 目录的 .gitkeep
#### 14. 旧版嵌套 try/except 精简（代码量大，低优先级）

## 验证步骤

1. `python -c "from kokoro_tts.engine import TTSEngine"` — 验证 import os 修复
2. `python -c "from kokoro_tts.config import Settings; s = Settings(); print(s.cors_origins)"` — 验证 CORS 配置
3. `docker build -f docker/cpu/Dockerfile .` — 验证 Docker 构建（可选）
4. 检查所有修改的文件无语法错误：`python -m py_compile <file>`

## Git 提交规范

```
fix: 修复 os 模块未导入导致的 NameError
fix: 删除无效的 Dockerfile.new
fix: 移除重复的 en_callable 定义
fix: 添加 static 目录解决挂载崩溃
security: CORS 改为可配置而非全开
security: API Key 比较使用 hmac.compare_digest
security: 隐藏内部错误信息
feat: 添加请求体大小限制
chore: 添加 MIT LICENSE 文件
chore: 统一 Python 版本要求为 >=3.10
```

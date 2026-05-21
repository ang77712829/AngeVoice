#!/bin/bash
# _lib.sh - AngeVoice FPK 公共函数库
# 被 install_callback / config_callback / upgrade_callback 共同引用

# upsert_env: 新增或覆盖 env 文件中的 KEY=*** 行
# 用法: upsert_env "KEY" "VALUE"
upsert_env() {
  local key="$1" val="$2"
  [ -z "${val}" ] && return 0
  if command -v python3 >/dev/null 2>&1; then
    python3 - "${ENV_FILE}" "${key}" "${val}" <<'PY'
import re, sys
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
def quote(v):
    if re.fullmatch(r'[A-Za-z0-9_./:@%+=,-]*', v or ''):
        return v
    return '"' + v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '') + '"'
try:
    lines = open(path, 'r', encoding='utf-8').read().splitlines()
except FileNotFoundError:
    lines = []
prefix = key + '='
out, done = [], False
for line in lines:
    if line.startswith(prefix):
        if not done:
            out.append(prefix + quote(val)); done = True
    else:
        out.append(line)
if not done:
    out.append(prefix + quote(val))
open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
PY
  else
    if grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
      sed -i "s|^${key}=.*|${key}=${val}|" "${ENV_FILE}"
    else
      echo "${key}=${val}" >> "${ENV_FILE}"
    fi
  fi
}

# ensure_env: 仅在 KEY 不存在时写入（用于升级时保留用户已有配置）
# 用法: ensure_env "KEY" "DEFAULT_VALUE"
ensure_env() {
  local key="$1" val="$2"
  grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null || upsert_env "${key}" "${val}"
}

# get_env_val: 从 env 文件读取 KEY 的值
# 用法: val="$(get_env_val KEY)"
get_env_val() {
  grep -E "^$1=" "${ENV_FILE}" 2>/dev/null | tail -n 1 | cut -d= -f2- | sed 's/^"//;s/"$//'
}

# sync_runtime_dir: 同步 compose 和 env 到 @appcenter 运行目录
# 用法: sync_runtime_dir "/vol3/@appcenter/AngeVoice/docker"
sync_runtime_dir() {
  local dir="$1"
  [ -d "${dir}" ] || return 0
  cp "${APP_DOCKER_DIR}/docker-compose.yaml" "${dir}/docker-compose.yaml" 2>/dev/null || true
  cp "${ENV_FILE}" "${dir}/angevoice.env" 2>/dev/null || true
  log "已同步运行目录：${dir}"
}

# sync_to_appcenter: 遍历所有 @appcenter 卷并同步
sync_to_appcenter() {
  sync_runtime_dir "${TRIM_APPDEST_VOL:-}/@appcenter/${APP_NAME}/docker"
  for dir in /vol*/@appcenter/${APP_NAME}/docker; do
    [ -d "${dir}" ] && sync_runtime_dir "${dir}"
  done
}

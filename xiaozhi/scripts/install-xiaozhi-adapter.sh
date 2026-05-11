#!/usr/bin/env bash
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/ang77712829/AngeVoice/main/xiaozhi"
XIAOZHI_DIR=""
ANGEVOICE_HTTP=""
ANGEVOICE_WS=""
MODE=""
MODEL=""
API_KEY=""
PROMPT_AUDIO=""
PATCH_COMPOSE="ask"
WRITE_CONFIG="ask"
RESTART="ask"
DRY_RUN="false"
YES="false"

log(){ printf '\033[1;32m[AngeVoice-xiaozhi]\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err(){ printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

usage(){ cat <<'USAGE'
AngeVoice 小智后端适配器安装脚本

交互式安装：
  bash <(curl -fsSL https://raw.githubusercontent.com/ang77712829/AngeVoice/main/xiaozhi/scripts/install-xiaozhi-adapter.sh)

参数：
  --xiaozhi-dir DIR       小智 compose 文件所在目录；不传则自动探测并可手动输入
  --angevoice-url URL     AngeVoice HTTP 地址；默认按运行中的 AngeVoice 容器推荐
  --angevoice-ws URL      AngeVoice WS 地址；默认按 HTTP 地址自动生成
  --mode MODE             kokoro|kokoro-stream|moss|moss-stream|moss-clone|moss-clone-stream
  --model MODEL           kokoro|moss-nano-cpu|moss-nano-cuda
  --api-key KEY           AngeVoice API Key，未启用鉴权可留空
  --prompt-audio FILE     MOSS clone 参考音频，会复制为 data/angevoice_prompts/reference.wav
  --adapters-only         只安装适配器，不 patch compose，不写配置，不重启
  --no-config             不写入 data/.config.yaml
  --no-compose            不修改 compose 文件
  --no-restart            不重启 xiaozhi-esp32-server 容器
  --yes, -y               非交互模式，使用默认/传入参数
  --dry-run               只显示将要执行的操作

兼容 compose 文件名：docker-compose_all.yml / docker-compose.yml / compose.yml
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --xiaozhi-dir) XIAOZHI_DIR="$2"; shift 2;;
    --angevoice-url) ANGEVOICE_HTTP="${2%/}"; shift 2;;
    --angevoice-ws) ANGEVOICE_WS="$2"; shift 2;;
    --mode) MODE="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --api-key) API_KEY="$2"; shift 2;;
    --prompt-audio) PROMPT_AUDIO="$2"; shift 2;;
    --adapters-only) PATCH_COMPOSE="false"; WRITE_CONFIG="false"; RESTART="false"; shift;;
    --no-config) WRITE_CONFIG="false"; shift;;
    --no-compose) PATCH_COMPOSE="false"; shift;;
    --no-restart) RESTART="false"; shift;;
    --yes|-y) YES="true"; shift;;
    --dry-run) DRY_RUN="true"; shift;;
    -h|--help) usage; exit 0;;
    *) err "未知参数: $1"; usage; exit 1;;
  esac
done

command -v curl >/dev/null || { err "缺少 curl"; exit 1; }
command -v sed >/dev/null || { err "缺少 sed"; exit 1; }
command -v python3 >/dev/null || { err "缺少 python3"; exit 1; }

is_interactive(){ [[ -t 0 && "$YES" != "true" ]]; }
ask_line(){ local p="$1" d="${2:-}" v; if is_interactive; then read -r -p "$p${d:+ [$d]}: " v || true; printf '%s' "${v:-$d}"; else printf '%s' "$d"; fi; }
ask_yes_no(){ local p="$1" d="${2:-Y}" v s; [[ "$d" =~ ^[Yy]$ ]] && s="Y/n" || s="y/N"; if is_interactive; then read -r -p "$p [$s]: " v || true; v="${v:-$d}"; else v="$d"; fi; [[ "$v" =~ ^[Yy]$ ]]; }

compose_file_in_dir(){ local d="$1" f; for f in docker-compose_all.yml docker-compose.yml compose.yml; do [[ -f "$d/$f" ]] && { printf '%s' "$f"; return 0; }; done; return 1; }
valid_dir(){ [[ -d "$1" ]] && compose_file_in_dir "$1" >/dev/null; }

CANDIDATES=()
add_candidate(){ local d="$1" e; [[ -n "$d" && -d "$d" ]] || return 0; d="$(cd "$d" 2>/dev/null && pwd || true)"; [[ -n "$d" ]] || return 0; valid_dir "$d" || return 0; for e in "${CANDIDATES[@]:-}"; do [[ "$e" == "$d" ]] && return 0; done; CANDIDATES+=("$d"); }

add_container_candidates(){ command -v docker >/dev/null 2>&1 || return 0; local name mounts source dest; while IFS= read -r name; do [[ -n "$name" ]] || continue; mounts=$(docker inspect "$name" --format '{{range .Mounts}}{{println .Source "|" .Destination}}{{end}}' 2>/dev/null || true); while IFS='|' read -r source dest; do [[ -n "${source:-}" && -n "${dest:-}" ]] || continue; case "$dest" in */data) add_candidate "$(dirname "$source")";; /opt/xiaozhi-esp32-server) add_candidate "$source";; esac; done <<< "$mounts"; done < <(docker ps --format '{{.Names}}' 2>/dev/null | grep -Ei 'xiaozhi|esp32' || true); }

find_dir(){
  if [[ -n "$XIAOZHI_DIR" ]]; then valid_dir "$XIAOZHI_DIR" && { cd "$XIAOZHI_DIR" && pwd; return; }; warn "传入目录不像小智目录: $XIAOZHI_DIR"; fi
  local cur="$PWD" root file d
  while [[ "$cur" != "/" && -n "$cur" ]]; do add_candidate "$cur"; cur="$(dirname "$cur")"; done
  add_container_candidates
  for d in "$HOME/xiaozhi-server" "$HOME/docker/xiaozhi-server" "/opt/xiaozhi-server" "/root/xiaozhi-server" "/vol1/1000/docker/xiaozhi-server" "/vol2/1000/docker/xiaozhi-server" "/vol3/1000/docker/xiaozhi-server"; do add_candidate "$d"; done
  for root in /vol1 /vol2 /vol3 /volume1 /volume2 /mnt /srv /data; do [[ -d "$root" ]] || continue; while IFS= read -r file; do add_candidate "$(dirname "$file")"; done < <(find "$root" -maxdepth 5 \( -name 'docker-compose_all.yml' -o -name 'docker-compose.yml' -o -name 'compose.yml' \) 2>/dev/null | head -n 30); done
  if [[ ${#CANDIDATES[@]} -eq 1 ]]; then printf '%s' "${CANDIDATES[0]}"; return; fi
  if [[ ${#CANDIDATES[@]} -gt 1 ]] && is_interactive; then echo "检测到多个可能的小智目录：" >&2; local i=1 c; for d in "${CANDIDATES[@]}"; do echo "  $i) $d ($(compose_file_in_dir "$d"))" >&2; i=$((i+1)); done; c=$(ask_line "请选择编号，或直接输入自定义目录" "1"); if [[ "$c" =~ ^[0-9]+$ ]] && (( c>=1 && c<=${#CANDIDATES[@]} )); then printf '%s' "${CANDIDATES[$((c-1))]}"; return; fi; valid_dir "$c" && { cd "$c" && pwd; return; }; fi
  if is_interactive; then local m; m=$(ask_line "请输入小智 compose 文件所在目录" "$PWD"); valid_dir "$m" && { cd "$m" && pwd; return; }; fi
  err "未找到小智目录。目录内需有 docker-compose_all.yml / docker-compose.yml / compose.yml。可传 --xiaozhi-dir 指定。"; exit 1
}

compose_cmd(){ if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo ""; fi; }

DETECTED_AV_NAME=""; DETECTED_AV_PROFILE="cpu"; DETECTED_AV_MODELS=""; DETECTED_AV_PORT="8101"
detect_angevoice(){ command -v docker >/dev/null 2>&1 || return 0; local line name image ports envs; line=$(docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | grep -i 'angevoice' | head -n 1 || true); [[ -n "$line" ]] || return 0; IFS='|' read -r name image ports <<< "$line"; envs=$(docker inspect "$name" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null || true); DETECTED_AV_NAME="$name"; DETECTED_AV_MODELS=$(printf '%s\n' "$envs" | sed -n 's/^ANGEVOICE_ENABLED_MODELS=//p' | head -n 1); [[ "$name $image $ports $DETECTED_AV_MODELS" =~ (gpu|cuda) ]] && DETECTED_AV_PROFILE="gpu"; [[ "$name $image $ports" =~ legacy ]] && DETECTED_AV_PROFILE="legacy-gpu"; [[ "$ports" == *8102* ]] && DETECTED_AV_PORT="8102"; [[ "$ports" == *8101* ]] && DETECTED_AV_PORT="8101"; [[ "$ports" == *8100* ]] && DETECTED_AV_PORT="8100"; }
resolve_urls(){ detect_angevoice; [[ -n "$DETECTED_AV_NAME" ]] && log "检测到 AngeVoice 容器: $DETECTED_AV_NAME (${DETECTED_AV_PROFILE}, port ${DETECTED_AV_PORT}, models=${DETECTED_AV_MODELS:-unknown})"; [[ -z "$ANGEVOICE_HTTP" ]] && ANGEVOICE_HTTP="http://host.docker.internal:${DETECTED_AV_PORT}"; is_interactive && ANGEVOICE_HTTP=$(ask_line "AngeVoice HTTP 地址" "$ANGEVOICE_HTTP"); if [[ -z "$ANGEVOICE_WS" ]]; then if [[ "$ANGEVOICE_HTTP" == http://* ]]; then ANGEVOICE_WS="ws://${ANGEVOICE_HTTP#http://}/ws/v1/tts"; elif [[ "$ANGEVOICE_HTTP" == https://* ]]; then ANGEVOICE_WS="wss://${ANGEVOICE_HTTP#https://}/ws/v1/tts"; else ANGEVOICE_WS="ws://host.docker.internal:8101/ws/v1/tts"; fi; fi; is_interactive && ANGEVOICE_WS=$(ask_line "AngeVoice WS 地址" "$ANGEVOICE_WS"); }

choose_mode(){ [[ -n "$MODE" ]] && return 0; if is_interactive; then echo >&2; echo "请选择接入模式：" >&2; echo "  1) Kokoro 流式，日常推荐" >&2; echo "  2) Kokoro 非流式，最快跑通" >&2; echo "  3) MOSS 预设音色流式" >&2; echo "  4) MOSS 预设音色非流式" >&2; echo "  5) MOSS 克隆流式，高级玩法" >&2; echo "  6) MOSS 克隆非流式" >&2; local c; c=$(ask_line "输入编号" "1"); case "$c" in 1) MODE="kokoro-stream";; 2) MODE="kokoro";; 3) MODE="moss-stream";; 4) MODE="moss";; 5) MODE="moss-clone-stream";; 6) MODE="moss-clone";; *) MODE="kokoro-stream";; esac; else MODE="kokoro-stream"; fi; }
recommend_model(){ case "$MODE" in kokoro*) echo "kokoro";; moss*) if [[ "$DETECTED_AV_MODELS" == *moss-nano-cuda* || "$DETECTED_AV_PROFILE" != "cpu" ]]; then echo "moss-nano-cuda"; else echo "moss-nano-cpu"; fi;; esac; }
choose_model(){ [[ -n "$MODEL" ]] && return 0; MODEL=$(recommend_model); if [[ "$MODE" == moss* ]] && is_interactive; then echo >&2; echo "请选择 MOSS 模型：" >&2; echo "  1) moss-nano-cpu，兼容性最好" >&2; echo "  2) moss-nano-cuda，适合 AngeVoice GPU/legacy-gpu 容器" >&2; local def="1" c; [[ "$MODEL" == "moss-nano-cuda" ]] && def="2"; c=$(ask_line "输入编号" "$def"); [[ "$c" == "2" ]] && MODEL="moss-nano-cuda" || MODEL="moss-nano-cpu"; fi; }

backup_file(){ local file="$1" bak; [[ -f "$file" ]] || return 0; bak="${file}.angevoice.$(date +%Y%m%d-%H%M%S).bak"; if [[ "$DRY_RUN" == "true" ]]; then log "[dry-run] 将备份: $bak"; else cp "$file" "$bak"; log "已备份: $bak"; fi; }

patch_compose(){ local cf="$1"; backup_file "$cf"; grep -q 'angevoice-adapter/angevoice.py' "$cf" && { log "$cf 已包含 AngeVoice 挂载，跳过 patch"; return; }; [[ "$DRY_RUN" == "true" ]] && { log "[dry-run] 将 patch $cf"; return; }; python3 - "$cf" <<'PY'
from pathlib import Path
import re, sys
p=Path(sys.argv[1]); lines=p.read_text(encoding='utf-8').splitlines(True)
vol=["      # AngeVoice TTS adapters\n","      - ./angevoice-adapter/angevoice.py:/opt/xiaozhi-esp32-server/core/providers/tts/angevoice.py:ro\n","      - ./angevoice-adapter/angevoice_stream.py:/opt/xiaozhi-esp32-server/core/providers/tts/angevoice_stream.py:ro\n","      - ./angevoice-adapter/angevoice_clone.py:/opt/xiaozhi-esp32-server/core/providers/tts/angevoice_clone.py:ro\n","      # MOSS clone prompt audio directory\n","      - ./data/angevoice_prompts:/opt/xiaozhi-esp32-server/data/angevoice_prompts:ro\n"]
host=["    extra_hosts:\n","      - \"host.docker.internal:host-gateway\"\n"]
start=None
for i,l in enumerate(lines):
    if re.match(r'^  [A-Za-z0-9_.-]+:\s*$', l):
        block=''.join(lines[i:i+120])
        if 'xiaozhi-esp32-server' in block or '/opt/xiaozhi-esp32-server' in block or 'SenseVoiceSmall' in block:
            start=i; break
if start is None: raise SystemExit('无法定位小智 server 服务，请手动参考 xiaozhi/examples/docker-compose.patch.example.yml')
end=len(lines)
for j in range(start+1,len(lines)):
    if re.match(r'^  [A-Za-z0-9_.-]+:\s*$', lines[j]): end=j; break
block=''.join(lines[start:end])
if 'host.docker.internal:host-gateway' not in block:
    pos=start+1
    for j in range(start+1,end):
        if re.match(r'^    (container_name|image|build|restart|networks|ports|volumes|environment|depends_on|security_opt):', lines[j]): pos=j; break
    lines[pos:pos]=host; end+=len(host)
block=''.join(lines[start:end])
if 'angevoice-adapter/angevoice.py' not in block:
    vline=None
    for j in range(start+1,end):
        if re.match(r'^    volumes:\s*$', lines[j]): vline=j; break
    if vline is None:
        lines[start+1:start+1]=['    volumes:\n']+vol
    else:
        pos=vline+1
        for j in range(vline+1,end):
            if re.match(r'^    [A-Za-z0-9_.-]+:\s*', lines[j]): break
            pos=j+1
        lines[pos:pos]=vol
p.write_text(''.join(lines), encoding='utf-8')
PY
log "已 patch $cf"; }

write_config(){ local selected="$1" type="$2" model="$3" voice="$4" fmt="$5" timeout="$6" prompt="$7"; cat >> data/.config.yaml <<YAML

# ===== AngeVoice Xiaozhi adapter begin =====
# 如果你使用智控台，下面配置可能会被数据库配置覆盖；请优先在智控台里新增同名模型。
selected_module:
  TTS: ${selected}

TTS:
  ${selected}:
    type: ${type}
    api_url: $([[ "$type" == "angevoice" || "$type" == "angevoice_clone" ]] && echo "$ANGEVOICE_HTTP" || echo "$ANGEVOICE_WS")
    http_url: ${ANGEVOICE_HTTP}
    api_key: "${API_KEY}"
    model: ${model}
    voice: ${voice}
    format: ${fmt}
    response_format: wav
    speed: 1.0
    output_dir: tmp/
    tts_timeout: ${timeout}
YAML
if [[ -n "$prompt" ]]; then cat >> data/.config.yaml <<'YAML'
    prompt_audio_path: /opt/xiaozhi-esp32-server/data/angevoice_prompts/reference.wav
    prompt_audio_filename: reference.wav
YAML
fi
cat >> data/.config.yaml <<'YAML'
# ===== AngeVoice Xiaozhi adapter end =====
YAML
}

tuple(){ case "$MODE" in kokoro) echo "AngeVoiceKokoro|angevoice|kokoro|zm_010|wav|120|";; kokoro-stream) echo "AngeVoiceKokoroStream|angevoice_stream|kokoro|zm_010|pcm_s16le|180|";; moss) echo "AngeVoiceMoss|angevoice|${MODEL}|Junhao|wav|180|";; moss-stream) echo "AngeVoiceMossStream|angevoice_stream|${MODEL}|Junhao|pcm_s16le|240|";; moss-clone) echo "AngeVoiceMossClone|angevoice_clone|${MODEL}|Junhao|wav|300|prompt";; moss-clone-stream) echo "AngeVoiceMossCloneStream|angevoice_stream|${MODEL}|Junhao|pcm_s16le|300|prompt";; esac; }

XIAOZHI_DIR=$(find_dir); cd "$XIAOZHI_DIR"; COMPOSE_FILE=$(compose_file_in_dir "$XIAOZHI_DIR")
resolve_urls; choose_mode; case "$MODE" in kokoro|kokoro-stream|moss|moss-stream|moss-clone|moss-clone-stream);; *) err "不支持的 mode: $MODE"; exit 1;; esac
choose_model; case "$MODEL" in kokoro|moss-nano-cpu|moss-nano-cuda);; *) err "不支持的 model: $MODEL"; exit 1;; esac
if [[ "$MODE" == moss-clone* && -z "$PROMPT_AUDIO" ]] && is_interactive; then PROMPT_AUDIO=$(ask_line "MOSS clone 参考音频路径；留空则稍后手动放入 data/angevoice_prompts/reference.wav" ""); fi
[[ "$PATCH_COMPOSE" == "ask" ]] && { if ask_yes_no "是否修改 ${COMPOSE_FILE} 挂载适配器和 host.docker.internal" "Y"; then PATCH_COMPOSE="true"; else PATCH_COMPOSE="false"; fi; }
[[ "$WRITE_CONFIG" == "ask" ]] && { if ask_yes_no "是否写入 data/.config.yaml 示例配置；使用智控台的用户可选否" "Y"; then WRITE_CONFIG="true"; else WRITE_CONFIG="false"; fi; }
[[ "$RESTART" == "ask" ]] && { if ask_yes_no "是否重启 xiaozhi-esp32-server 容器" "Y"; then RESTART="true"; else RESTART="false"; fi; }

log "小智目录: $XIAOZHI_DIR"; log "Compose 文件: $COMPOSE_FILE"; log "AngeVoice HTTP: $ANGEVOICE_HTTP"; log "AngeVoice WS: $ANGEVOICE_WS"; log "安装模式: $MODE"; log "模型: $MODEL"
if [[ "$DRY_RUN" != "true" ]]; then mkdir -p angevoice-adapter data/angevoice_prompts; curl -fsSL "$REPO_RAW/adapters/angevoice.py" -o angevoice-adapter/angevoice.py; curl -fsSL "$REPO_RAW/adapters/angevoice_stream.py" -o angevoice-adapter/angevoice_stream.py; curl -fsSL "$REPO_RAW/adapters/angevoice_clone.py" -o angevoice-adapter/angevoice_clone.py; fi
log "适配器目录: $XIAOZHI_DIR/angevoice-adapter"
if [[ -n "$PROMPT_AUDIO" ]]; then [[ -f "$PROMPT_AUDIO" ]] || { err "参考音频不存在: $PROMPT_AUDIO"; exit 1; }; [[ "$DRY_RUN" == "true" ]] || cp "$PROMPT_AUDIO" data/angevoice_prompts/reference.wav; log "MOSS 克隆参考音频已复制到: data/angevoice_prompts/reference.wav"; fi
[[ "$PATCH_COMPOSE" == "true" ]] && patch_compose "$COMPOSE_FILE"
if [[ "$WRITE_CONFIG" == "true" ]]; then [[ "$DRY_RUN" == "true" ]] || { mkdir -p data; [[ -f data/.config.yaml ]] || touch data/.config.yaml; }; backup_file data/.config.yaml; if [[ "$DRY_RUN" != "true" ]]; then sed -i '/# ===== AngeVoice Xiaozhi adapter begin =====/,/# ===== AngeVoice Xiaozhi adapter end =====/d' data/.config.yaml; IFS='|' read -r selected type cfg_model voice fmt timeout prompt <<< "$(tuple)"; write_config "$selected" "$type" "$cfg_model" "$voice" "$fmt" "$timeout" "$prompt"; fi; log "已写入 data/.config.yaml AngeVoice 示例配置"; fi
COMPOSE=$(compose_cmd)
if [[ -n "$COMPOSE" && "$RESTART" == "true" && "$DRY_RUN" != "true" ]]; then log "重启小智 server 容器"; $COMPOSE -f "$COMPOSE_FILE" restart xiaozhi-esp32-server || warn "重启失败，请手动执行: docker compose -f $COMPOSE_FILE restart xiaozhi-esp32-server"; fi
if command -v docker >/dev/null 2>&1 && [[ "$DRY_RUN" != "true" ]] && docker ps --format '{{.Names}}' | grep -q '^xiaozhi-esp32-server$'; then log "测试容器内适配器导入"; docker exec xiaozhi-esp32-server python - <<'PY' || warn "适配器导入测试失败，请查看容器日志"
from core.providers.tts import angevoice, angevoice_stream, angevoice_clone
print('AngeVoice adapters import OK')
PY
log "测试容器访问 AngeVoice /health"; docker exec xiaozhi-esp32-server sh -lc "curl -fsS '${ANGEVOICE_HTTP}/health' >/dev/null" || warn "容器访问 AngeVoice 失败，请确认 AngeVoice 已启动且 host.docker.internal 可用，或改用局域网 IP"; fi
cat <<EOF

✅ AngeVoice 小智适配器安装流程完成

适配器目录：$XIAOZHI_DIR/angevoice-adapter
当前选择：mode=$MODE, model=$MODEL
AngeVoice：$ANGEVOICE_HTTP
MOSS 克隆参考音频：$XIAOZHI_DIR/data/angevoice_prompts/reference.wav
容器内路径：/opt/xiaozhi-esp32-server/data/angevoice_prompts/reference.wav

如果使用智控台，请到“语音合成 → 新增/创建副本”，按 xiaozhi/manager/presets.yaml 填入配置。
更换 MOSS 克隆声音时，直接替换 reference.wav，或把 prompt_audio_path 改成其他容器内路径。

EOF

#!/usr/bin/env bash
# =============================================================================
# AngeVoice End-to-End Loop Test Script
# Covers: health, voices, HTTP WAV synthesis, WebSocket streaming, optional MOSS,
# cancel/recovery, optional idle unload/reload, loop stress.
#
# Usage:
#   ./scripts/e2e_loop_test.sh [BASE_URL] [API_KEY] [LOOPS]
#
# Examples:
#   ./scripts/e2e_loop_test.sh http://localhost:8101
#   ./scripts/e2e_loop_test.sh http://localhost:8101 my-secret-key 50
#
# Dependencies: curl, jq. websocat is optional; WebSocket tests are skipped if
# unavailable. This script validates real HTTP/audio behavior instead of relying
# on JSON placeholders from binary endpoints.
# =============================================================================

set -euo pipefail

BASE_URL="${1:-http://localhost:8101}"
API_KEY="${2:-}"
LOOPS="${3:-30}"
PASS=0
FAIL=0
SKIP=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "${GREEN}  ✓ PASS${NC} $1"; ((PASS++)); }
fail() { echo -e "${RED}  ✗ FAIL${NC} $1: $2"; ((FAIL++)); }
skip() { echo -e "${YELLOW}  ○ SKIP${NC} $1: $2"; ((SKIP++)); }
section() { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 2
    fi
}

require_cmd curl
require_cmd jq

AUTH_ARGS=()
if [[ -n "$API_KEY" ]]; then
    AUTH_ARGS=(-H "Authorization: Bearer $API_KEY")
fi

curl_json() {
    curl -s --max-time 30 "${AUTH_ARGS[@]}" "$@"
}

speech_request() {
    local model="$1"
    local text="$2"
    local voice="$3"
    local output="$4"
    curl -s -o "$output" -w '%{http_code}:%{content_type}' --max-time 90 \
        "${BASE_URL}/v1/audio/speech" \
        -H "Content-Type: application/json" \
        "${AUTH_ARGS[@]}" \
        -d "{\"model\":\"${model}\",\"input\":\"${text}\",\"voice\":\"${voice}\"}"
}

check_audio_file() {
    local label="$1"
    local response="$2"
    local file="$3"
    local http_code="${response%%:*}"
    local content_type="${response#*:}"
    local size
    size=$(stat -c%s "$file" 2>/dev/null || echo "0")
    if [[ "$http_code" == "200" && "$size" -gt 1000 && "$content_type" == audio/* ]]; then
        pass "$label ($size bytes, $content_type)"
        return 0
    fi
    fail "$label" "HTTP=$http_code content-type=$content_type size=$size body=$(head -c 200 "$file" 2>/dev/null || true)"
    return 1
}

section "1. Health Check"
HTTP_CODE=$(curl -s -o /tmp/av_health.json -w '%{http_code}' "${AUTH_ARGS[@]}" "${BASE_URL}/health" --max-time 10)
if [[ "$HTTP_CODE" == "200" ]]; then
    STATUS=$(jq -r '.status // "unknown"' /tmp/av_health.json 2>/dev/null || echo "parse_error")
    HEALTHY=$(jq -r '.healthy // true' /tmp/av_health.json 2>/dev/null || echo "true")
    MODEL=$(jq -r '.current_model // "unknown"' /tmp/av_health.json 2>/dev/null || echo "unknown")
    if [[ "$STATUS" == "ok" && "$HEALTHY" == "true" ]]; then
        pass "Health OK (model=$MODEL)"
    elif [[ "$STATUS" == "loading" ]]; then
        pass "Health endpoint reachable but model is still loading"
    else
        UNHEALTHY=$(jq -c '.unhealthy_models // []' /tmp/av_health.json 2>/dev/null || echo "[]")
        fail "Health degraded" "status=$STATUS unhealthy=$UNHEALTHY"
    fi
else
    fail "Health check" "HTTP $HTTP_CODE"
fi

section "2. Voices List"
BODY=$(curl_json "${BASE_URL}/v1/audio/voices")
VOICE_COUNT=$(echo "$BODY" | jq '.voices | length' 2>/dev/null || echo "0")
if [[ "$VOICE_COUNT" -gt 0 ]]; then
    pass "Voices listed ($VOICE_COUNT voices)"
else
    fail "Voices list" "0 voices returned: $(echo "$BODY" | head -c 200)"
fi

section "3. Kokoro WAV Synthesis"
KOKORO_WAV="/tmp/av_e2e_kokoro.wav"
KOKORO_RESP=$(speech_request "kokoro" "测试合成，这是一段中文语音。" "af_xiaobei" "$KOKORO_WAV")
check_audio_file "Kokoro WAV" "$KOKORO_RESP" "$KOKORO_WAV" || true

section "4. Kokoro WebSocket Stream"
if command -v websocat >/dev/null 2>&1; then
    WS_URL="${BASE_URL/#http/ws}/ws/v1/tts"
    WS_PAYLOAD='{ "model":"kokoro", "text":"WebSocket流式测试。", "voice":"af_xiaobei", "format":"pcm_s16le" }'
    if [[ -n "$API_KEY" ]]; then
        WS_PAYLOAD="{ \"model\":\"kokoro\", \"text\":\"WebSocket流式测试。\", \"voice\":\"af_xiaobei\", \"format\":\"pcm_s16le\", \"token\":\"${API_KEY}\" }"
    fi
    WS_RESULT=$(printf '%s\n' "$WS_PAYLOAD" | timeout 30 websocat -n1 "$WS_URL" 2>/tmp/av_ws_err || echo "ws_error")
    if [[ "$WS_RESULT" != *"ws_error"* && "$WS_RESULT" == *"started"* ]]; then
        pass "WebSocket stream endpoint /ws/v1/tts"
    else
        fail "WebSocket stream" "response=$(echo "$WS_RESULT" | head -c 200) stderr=$(cat /tmp/av_ws_err 2>/dev/null | head -c 200)"
    fi
else
    skip "WebSocket stream" "websocat not installed"
fi

section "5. Optional MOSS CPU HTTP Audio"
MODELS_JSON=$(curl_json "${BASE_URL}/v1/models")
if echo "$MODELS_JSON" | jq -e '.models[]? | select(.id == "moss-nano-cpu" and .available == true)' >/dev/null 2>&1; then
    MOSS_WAV="/tmp/av_e2e_moss_cpu.wav"
    MOSS_RESP=$(speech_request "moss-nano-cpu" "MOSS CPU合成测试。" "Junhao" "$MOSS_WAV")
    if ! check_audio_file "MOSS CPU audio" "$MOSS_RESP" "$MOSS_WAV"; then
        true
    fi
else
    skip "MOSS CPU audio" "moss-nano-cpu is not enabled/available"
fi

section "6. Optional MOSS CUDA HTTP Audio"
if echo "$MODELS_JSON" | jq -e '.models[]? | select(.id == "moss-nano-cuda" and .available == true)' >/dev/null 2>&1; then
    CUDA_WAV="/tmp/av_e2e_moss_cuda.wav"
    CUDA_RESP=$(speech_request "moss-nano-cuda" "MOSS CUDA合成测试。" "Junhao" "$CUDA_WAV")
    if ! check_audio_file "MOSS CUDA audio" "$CUDA_RESP" "$CUDA_WAV"; then
        true
    fi
else
    skip "MOSS CUDA audio" "moss-nano-cuda is not enabled/available"
fi

section "7. Cancel / Abort Recovery"
CANCEL_FILE="/tmp/av_e2e_cancel.wav"
timeout 2 curl -s -o "$CANCEL_FILE" --max-time 10 \
    "${BASE_URL}/v1/audio/speech" \
    -H "Content-Type: application/json" \
    "${AUTH_ARGS[@]}" \
    -d '{"model":"kokoro","input":"这段文字很长需要大量计算，我们会在中途取消它以测试取消功能是否正常工作。让我们继续添加更多文字来确保合成时间足够长以便能够成功取消。再来一些中文内容填充。","voice":"af_xiaobei","speed":0.3}' \
    >/dev/null 2>&1 || true
sleep 1
HEALTH_AFTER=$(curl -s -w '%{http_code}' -o /dev/null "${AUTH_ARGS[@]}" "${BASE_URL}/health" --max-time 5)
if [[ "$HEALTH_AFTER" == "200" ]]; then
    pass "Cancel/abort did not break health endpoint"
else
    fail "Cancel recovery" "Health after cancel: HTTP $HEALTH_AFTER"
fi

section "8. Optional Idle Unload + Reload"
IDLE_TIMEOUT=$(jq -r '.model.model_idle_timeout_seconds // .model_idle_timeout_seconds // 0' /tmp/av_health.json 2>/dev/null || echo "0")
CHECK_INTERVAL=$(jq -r '.model.model_idle_check_interval // .model_idle_check_interval // 30' /tmp/av_health.json 2>/dev/null || echo "30")
if [[ "$IDLE_TIMEOUT" =~ ^[0-9]+(\.[0-9]+)?$ ]] && awk "BEGIN {exit !($IDLE_TIMEOUT > 0)}"; then
    WAIT_TIME=$(awk "BEGIN {printf \"%.0f\", $IDLE_TIMEOUT + $CHECK_INTERVAL + 5}")
    echo "  Idle timeout is ${IDLE_TIMEOUT}s; waiting ${WAIT_TIME}s for an unload cycle..."
    sleep "$WAIT_TIME"
    RELOAD_WAV="/tmp/av_e2e_reload.wav"
    RELOAD_RESP=$(speech_request "kokoro" "重载测试。" "af_xiaobei" "$RELOAD_WAV")
    check_audio_file "Idle unload + auto reload" "$RELOAD_RESP" "$RELOAD_WAV" || true
else
    skip "Idle unload + reload" "ANGEVOICE_IDLE_TIMEOUT_SECONDS=0 or not exposed"
fi

section "9. Loop Stress Test ($LOOPS iterations)"
STRESS_PASS=0
STRESS_FAIL=0
for i in $(seq 1 "$LOOPS"); do
    OUT="/tmp/av_e2e_stress_${i}.wav"
    RESP=$(speech_request "kokoro" "压测第${i}轮测试语音合成稳定性。" "af_xiaobei" "$OUT")
    CODE="${RESP%%:*}"
    SIZE=$(stat -c%s "$OUT" 2>/dev/null || echo "0")
    if [[ "$CODE" == "200" && "$SIZE" -gt 1000 ]]; then
        ((STRESS_PASS++))
    else
        ((STRESS_FAIL++))
        echo -e "  ${RED}✗ Iteration $i failed (HTTP $CODE size=$SIZE)${NC}"
    fi
    if (( i % 10 == 0 )); then
        echo -e "  ${CYAN}Progress: $i/$LOOPS (pass=$STRESS_PASS fail=$STRESS_FAIL)${NC}"
    fi
done

if [[ "$STRESS_FAIL" -eq 0 ]]; then
    pass "Stress test: $STRESS_PASS/$LOOPS all passed"
else
    fail "Stress test" "$STRESS_FAIL/$LOOPS failed"
fi

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}PASS: $PASS${NC}  ${RED}FAIL: $FAIL${NC}  ${YELLOW}SKIP: $SKIP${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"

if [[ "$FAIL" -gt 0 ]]; then
    echo -e "\n${RED}Some tests failed!${NC}"
    exit 1
fi

echo -e "\n${GREEN}All required tests passed!${NC}"
exit 0

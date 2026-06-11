"""Authentication helpers for AngeVoice."""

import hmac

from fastapi import HTTPException, Request, WebSocket

from .config import TTSConfig
from .config_api_key import effective_api_key


def _extract_bearer_token(auth: str) -> str:
    """从 Authorization 头提取 Bearer token，支持大小写混合、前导/尾部空白。"""
    value = str(auth or "").strip()
    prefix = "bearer"
    if value.lower().startswith(prefix):
        rest = value[len(prefix):]
        # 必须有空白分隔符，防止 Bearerxxx 误通过
        if rest and rest[0].isspace():
            return rest[1:].strip()
    return ""


def _constant_time_equal(left: object, right: object) -> bool:
    """支持 Unicode 输入的 timing-safe 比较；非法值一律视为不匹配。"""
    try:
        return hmac.compare_digest(str(left if left is not None else "").encode("utf-8"), str(right if right is not None else "").encode("utf-8"))
    except Exception:
        return False


def make_verify_api_key(cfg: TTSConfig):
    """Return a FastAPI dependency that enforces Bearer auth when configured."""

    async def verify_api_key(request: Request):
        expected_key = effective_api_key(cfg)
        if expected_key:
            auth = request.headers.get("Authorization", "")
            token = _extract_bearer_token(auth)
            if not _constant_time_equal(token, expected_key):
                raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return verify_api_key


async def verify_ws_key(cfg: TTSConfig, websocket: WebSocket, token: str = "") -> bool:
    """Validate WebSocket credentials against ``KOKORO_API_KEY``.

    Query-string tokens and Authorization Bearer tokens are treated as
    alternative credentials so mixed clients/proxies remain compatible during
    token rotation and reconnect flows.
    """
    expected_key = effective_api_key(cfg)
    if not expected_key:
        return True

    auth = websocket.headers.get("authorization", "")
    header_token = _extract_bearer_token(auth)

    supplied_tokens = []
    if token:
        supplied_tokens.append(token)
    if header_token and header_token not in supplied_tokens:
        supplied_tokens.append(header_token)

    if not supplied_tokens:
        return False

    return any(_constant_time_equal(candidate, expected_key) for candidate in supplied_tokens)

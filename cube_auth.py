"""JWT auth for embedded Cube.js (required when CUBEJS_DEV_MODE=false)."""

from __future__ import annotations

import os
import time

import jwt

_jwt_token: str | None = None
_jwt_expires_at: int = 0


def cube_headers() -> dict[str, str]:
    global _jwt_token, _jwt_expires_at
    secret = os.getenv("CUBEJS_API_SECRET", "").strip()
    if not secret:
        raise ValueError("CUBEJS_API_SECRET must be set")
    now = int(time.time())
    if _jwt_token and now < _jwt_expires_at - 60:
        return {"Authorization": _jwt_token, "Content-Type": "application/json"}
    exp = now + 3600
    token = jwt.encode({"iat": now, "exp": exp}, secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    _jwt_token = token
    _jwt_expires_at = exp
    return {"Authorization": token, "Content-Type": "application/json"}

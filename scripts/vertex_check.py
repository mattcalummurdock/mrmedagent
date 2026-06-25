#!/usr/bin/env python3
"""Check Vertex service account token refresh from .env."""

from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account


def load_credentials_json(env_path: Path) -> str:
    text = env_path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\r\n", "\n")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not (
            line.startswith("GOOGLE_VERTEX_CREDENTIALS=")
            or line.startswith("VERTEX_CREDENTIALS=")
        ):
            continue
        _, _, value = line.partition("=")
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        return value
    raise RuntimeError("Missing GOOGLE_VERTEX_CREDENTIALS / VERTEX_CREDENTIALS in .env")


def main() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        raise RuntimeError("Missing .env in repo root")
    creds_json = load_credentials_json(env_path)
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    print("token ok", creds.token[:10])


if __name__ == "__main__":
    main()

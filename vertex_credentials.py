"""Load and normalize Vertex AI service-account credentials from environment."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from loguru import logger


def _normalize_private_key(data: dict[str, Any]) -> dict[str, Any]:
    if "private_key" in data and isinstance(data["private_key"], str):
        data["private_key"] = data["private_key"].replace("\\n", "\n")
    return data


def _parse_credentials_raw(raw: str) -> dict[str, Any]:
    creds = raw.strip()
    if (creds.startswith('"') and creds.endswith('"')) or (
        creds.startswith("'") and creds.endswith("'")
    ):
        creds = creds[1:-1].strip()

    if creds.endswith(".json") and os.path.isfile(creds):
        with open(creds, encoding="utf-8") as f:
            return _normalize_private_key(json.load(f))

    if creds.startswith("{"):
        return _normalize_private_key(json.loads(creds))

    raise ValueError(
        "VERTEX_CREDENTIALS must be a one-line JSON object or a path to a .json file."
    )


def load_vertex_credentials() -> tuple[str, str]:
    """Return (credentials JSON string, project_id) from env."""
    raw = (
        os.getenv("VERTEX_CREDENTIALS")
        or os.getenv("GOOGLE_VERTEX_CREDENTIALS")
        or ""
    ).strip()
    if not raw:
        raise ValueError(
            "Set VERTEX_CREDENTIALS or GOOGLE_VERTEX_CREDENTIALS in .env "
            "(inline service-account JSON or path to a .json file)."
        )

    data = _parse_credentials_raw(raw)
    return json.dumps(data), str(data["project_id"])


def prewarm_vertex_credentials(
    credentials_json: str,
    *,
    max_attempts: int = 5,
    base_delay_secs: float = 1.0,
) -> None:
    """Refresh the service-account token at startup to catch auth/network issues early."""
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = json.loads(credentials_json)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            creds.refresh(Request())
            logger.info("Vertex credentials prewarm succeeded")
            return
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            delay = min(base_delay_secs * (2 ** (attempt - 1)), 30.0)
            logger.warning(
                f"Vertex credentials prewarm attempt {attempt}/{max_attempts} "
                f"failed: {exc}; retrying in {delay:.1f}s"
            )
            time.sleep(delay)

    assert last_error is not None
    raise last_error

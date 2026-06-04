"""Load Vertex AI service-account credentials from environment."""

from __future__ import annotations

import json
import os


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

    if raw.endswith(".json") and os.path.isfile(raw):
        with open(raw, encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data), data["project_id"]

    if raw.startswith("{"):
        data = json.loads(raw)
        return raw, data["project_id"]

    raise ValueError(
        "VERTEX_CREDENTIALS must be a one-line JSON object or a path to a .json file."
    )

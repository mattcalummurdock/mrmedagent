"""Vertex AI Live defaults — shared by server.py and vertex.py.

Note: GOOGLE_CLOUD_LOCATION is for other GCP services (e.g. Cube). Vertex Live
uses VERTEX_LOCATION only; gemini-live-2.5-flash-native-audio is not in every region.
"""

from __future__ import annotations

import os

# Same defaults as vertex.py (europe-west4 — not asia-south1 from GOOGLE_CLOUD_LOCATION).
DEFAULT_VERTEX_LOCATION = "europe-west4"
DEFAULT_VERTEX_MODEL = "google/gemini-live-2.5-flash-native-audio"
DEFAULT_VERTEX_VOICE = "Autonoe"


def vertex_location() -> str:
    return os.getenv("VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION).strip()


def vertex_model() -> str:
    return os.getenv("VERTEX_MODEL", DEFAULT_VERTEX_MODEL).strip()


def vertex_voice() -> str:
    return (
        os.getenv("VERTEX_VOICE", "").strip()
        or os.getenv("GEMINI_VOICE_NAME", "").strip()
        or DEFAULT_VERTEX_VOICE
    )

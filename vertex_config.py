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


def vertex_publisher_model_path(project_id: str, location: str, model: str) -> str:
    """Full Vertex publisher resource path used for the Live API."""
    model_id = model.split("/", 1)[-1] if "/" in model else model
    return (
        f"projects/{project_id}/locations/{location}/"
        f"publishers/google/models/{model_id}"
    )


def log_vertex_llm_config(logger, *, project_id: str | None = None) -> None:
    """Log resolved Vertex Live model, region, voice, and config source."""
    model = vertex_model()
    location = vertex_location()
    voice = vertex_voice()

    model_source = (
        "VERTEX_MODEL env"
        if os.getenv("VERTEX_MODEL", "").strip()
        else f"code default ({DEFAULT_VERTEX_MODEL})"
    )
    location_source = (
        "VERTEX_LOCATION env"
        if os.getenv("VERTEX_LOCATION", "").strip()
        else f"code default ({DEFAULT_VERTEX_LOCATION})"
    )
    if os.getenv("VERTEX_VOICE", "").strip():
        voice_source = "VERTEX_VOICE env"
    elif os.getenv("GEMINI_VOICE_NAME", "").strip():
        voice_source = "GEMINI_VOICE_NAME env"
    else:
        voice_source = f"code default ({DEFAULT_VERTEX_VOICE})"

    logger.info(f"Vertex LLM model: {model} [{model_source}]")
    logger.info(f"Vertex LLM region: {location} [{location_source}]")
    logger.info(f"Vertex LLM voice: {voice} [{voice_source}]")
    if project_id:
        logger.info(
            f"Vertex LLM endpoint resource: "
            f"{vertex_publisher_model_path(project_id, location, model)}"
        )

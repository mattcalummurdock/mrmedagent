"""pgvector semantic medicine search — complements Cube text lookups."""

from __future__ import annotations

import os
import threading
from typing import Any

MODEL_NAME = os.getenv("SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEFAULT_MIN_SIMILARITY = float(os.getenv("SEMANTIC_MIN_SIMILARITY", "0.22"))
MIN_SIMILARITY_MARGIN = float(os.getenv("SEMANTIC_MIN_MARGIN", "0.04"))
SEMANTIC_ENABLED = os.getenv("SEMANTIC_SEARCH_ENABLED", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)

_model = None
_model_lock = threading.Lock()
_import_error: str | None = None

try:
    import psycopg2
    from pgvector.psycopg2 import register_vector
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    _import_error = str(exc)


def semantic_search_available() -> bool:
    return (
        SEMANTIC_ENABLED
        and _import_error is None
        and bool(os.getenv("DATABASE_URL"))
    )


def _get_model():
    global _model
    if _import_error:
        raise RuntimeError(f"semantic_search unavailable: {_import_error}")
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            _model = SentenceTransformer(MODEL_NAME)
    return _model


def prewarm_embedding_model() -> bool:
    """Load the embedding model (and run one encode) so first caller lookup is fast."""
    if not semantic_search_available():
        return False
    model = _get_model()
    model.encode("medicine lookup warmup")
    return True


def semantic_search(
    query: str,
    top_k: int = 3,
    *,
    min_similarity: float | None = None,
) -> list[dict[str, Any]]:
    """Find medicines by embedding similarity to a spoken or misspelled query."""
    if not query.strip():
        return []
    if not semantic_search_available():
        return []

    floor = DEFAULT_MIN_SIMILARITY if min_similarity is None else min_similarity
    model = _get_model()
    query_embedding = model.encode(query).tolist()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    register_vector(conn)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            name,
            generic_name,
            selling_price,
            is_available,
            prescription_required,
            therapeutic_class,
            1 - (embedding <=> %s::vector) AS similarity
        FROM medicines
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_embedding, query_embedding, top_k),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    parsed = [(r, float(r[7])) for r in rows]
    if not parsed:
        return []

    best_sim = parsed[0][1]
    second_sim = parsed[1][1] if len(parsed) > 1 else 0.0
    if best_sim < floor or (best_sim - second_sim) < MIN_SIMILARITY_MARGIN:
        return []

    results: list[dict[str, Any]] = []
    for r, similarity in parsed:
        if similarity < floor:
            break
        results.append(
            {
                "medicine_id": r[0],
                "medicine_name": r[1],
                "generic_name": r[2],
                "selling_price": float(r[3]) if r[3] is not None else None,
                "in_stock": r[4],
                "requires_rx": r[5],
                "therapeutic_class": r[6],
                "similarity": similarity,
            }
        )
    return results

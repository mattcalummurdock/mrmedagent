"""Generate medicine embeddings optimized for spoken / misspelled name lookup."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_repo = Path(__file__).resolve().parent.parent
load_dotenv(_repo / ".env")

import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.getenv("SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def build_lookup_embedding_text(row: dict) -> str:
    """Short, speakable fields — matches how callers say medicine names on the phone."""
    parts = [
        row.get("name", ""),
        row.get("brand_name", ""),
        row.get("generic_name", ""),
        row.get("form", ""),
        row.get("dosage_strength", ""),
        row.get("pack_size", ""),
    ]
    core = " ".join(p for p in parts if p).strip()
    return f"{core} | {core}" if core else ""


def main() -> None:
    force = "--force" in sys.argv
    print(f"Loading model {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    register_vector(conn)
    cur = conn.cursor()

    if force:
        cur.execute(
            """
            SELECT id, name, brand_name, generic_name, form, dosage_strength, pack_size
            FROM medicines
            """
        )
    else:
        cur.execute(
            """
            SELECT id, name, brand_name, generic_name, form, dosage_strength, pack_size
            FROM medicines
            WHERE embedding IS NULL
            """
        )

    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    if not rows:
        print("All medicines already have embeddings (use --force to regenerate).")
    else:
        print(f"Generating embeddings for {len(rows)} medicines...")
        for row in rows:
            med = dict(zip(columns, row))
            text = build_lookup_embedding_text(med)
            embedding = model.encode(text).tolist()
            cur.execute(
                "UPDATE medicines SET embedding = %s WHERE id = %s",
                (embedding, med["id"]),
            )
            print(f"  OK {med['name']}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()

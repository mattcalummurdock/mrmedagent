import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _resolve_db_scripts() -> Path | None:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "DB" / "scripts",
        here.parents[1] / "scripts",
        Path("/app/DB/scripts"),
        Path("/app/scripts"),
    ):
        if (candidate / "cube_tools.py").is_file():
            return candidate
    return None


_DB_SCRIPTS = _resolve_db_scripts()
_CUBE_ENV = Path(__file__).resolve().parents[2] / "DB" / "cube" / ".env"

if _DB_SCRIPTS and str(_DB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DB_SCRIPTS))

if _CUBE_ENV.is_file():
    load_dotenv(_CUBE_ENV, override=False)

# Skip extra Cube round-trips on alternatives (saves ~200ms+ per alt). Bulk upsell on detail only.
_ATTACH_BULK_ON_ALTERNATIVES = os.getenv(
    "CUBE_ATTACH_BULK_ON_ALTERNATIVES", "0"
).strip().lower() in ("1", "true", "yes")


def flatten_cube_rows(rows: list[dict]) -> list[dict]:
    flattened = []
    for row in rows:
        item = {}
        for key, value in row.items():
            if "." in key:
                _, field = key.split(".", 1)
                snake = "".join(
                    f"_{c.lower()}" if c.isupper() else c for c in field
                ).lstrip("_")
            else:
                snake = key
            item[snake] = value
        flattened.append(item)
    return flattened


async def run_cube(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


async def attach_bulk_pricing(item: dict, medicine_id: int) -> None:
    import cube_tools

    pricing = await run_cube(cube_tools.get_quantity_pricing, medicine_id)
    model = pricing.get("pricing_model")
    if model in ("quantity_tier", "flat_per_unit"):
        item["quantity_pricing"] = pricing
        upsell = pricing.get("upsell_line")
        if upsell:
            item["bulk_offer_line"] = upsell


async def attach_bulk_pricing_parallel(items: list[dict]) -> None:
    """Fetch bulk pricing for many medicines concurrently."""
    tasks = []
    for item in items:
        alt_id = item.get("alternative_id") or item.get("id")
        if alt_id is not None:
            tasks.append(attach_bulk_pricing(item, int(alt_id)))
    if tasks:
        await asyncio.gather(*tasks)


def should_attach_bulk_on_alternatives() -> bool:
    return _ATTACH_BULK_ON_ALTERNATIVES


async def prewarm_cube() -> None:
    """Warm HTTP pool + Cube/Postgres on server startup."""
    import cube_tools

    await run_cube(cube_tools.prewarm)


async def prewarm_cube_alternatives_path(medicine_name: str = "Oxiage LG") -> None:
    """Preload common medicine + alternatives queries into cache."""
    import cube_tools

    rows = await run_cube(cube_tools.get_medicine_detail, medicine_name)
    medicines = flatten_cube_rows(rows)
    if not medicines:
        return
    med_id = int(medicines[0]["id"])
    await run_cube(cube_tools.get_alternatives, med_id, cheaper_only=True)

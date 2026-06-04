import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

def _resolve_db_scripts() -> Path | None:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "DB" / "scripts",
        here.parents[1] / "scripts",
        Path("/app/DB/scripts"),
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

"""Smoke-test agent tool handlers against a running Cube instance."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _MockParams:
    def __init__(self, arguments: dict):
        self.arguments = arguments
        self.result = None

    async def result_callback(self, result):
        self.result = result


async def _run(name, handler, arguments):
    params = _MockParams(arguments)
    await handler(params)
    return params.result


async def main():
    from tools.get_medicine_detail import handler as detail_handler
    from tools.get_alternatives import handler as alt_handler

    detail = await _run("get_medicine_detail", detail_handler, {"name": "Oxiage"})
    assert detail and detail["medicines"], "Expected medicine detail rows"
    med_id = int(detail["medicines"][0]["id"])
    price = float(detail["medicines"][0]["selling_price"])
    stock_qty = int(detail["medicines"][0]["stock_quantity"])
    assert price == 3219.0, f"Expected price 3219, got {price}"
    assert stock_qty == 48, f"Expected stock_quantity 48, got {stock_qty}"
    print(f"get_medicine_detail: OK (id={med_id}, price={price}, stock={stock_qty})")

    glutone = await _run("get_medicine_detail", detail_handler, {"name": "Glutone"})
    assert glutone["medicines"][0].get("quantity_pricing"), "Expected quantity_pricing on Glutone"
    assert glutone["medicines"][0].get("bulk_offer_line")
    print(f"get_medicine_detail upsell: OK ({glutone['medicines'][0]['bulk_offer_line']})")

    alts = await _run(
        "get_alternatives", alt_handler, {"medicine_id": med_id, "cheaper_only": True}
    )
    assert alts and alts["alternatives"], "Expected alternatives"
    assert "Glutone" in alts["alternatives"][0]["alternative_name"]
    assert alts["alternatives"][0].get("bulk_offer_line"), "Expected bulk_offer_line on Glutone alternative"
    print(f"get_alternatives: OK ({alts['alternatives'][0]['alternative_name']}, bulk={alts['alternatives'][0]['bulk_offer_line'][:50]}...)")

    from tools.get_quantity_pricing import handler as qty_handler

    qty = await _run("get_quantity_pricing", qty_handler, {"medicine_id": 2})
    assert qty["pricing_model"] == "quantity_tier"
    assert len(qty["tiers"]) == 2
    print(f"get_quantity_pricing: OK (Glutone tiers={qty['tiers']})")

    print("\nAgent tool handler smoke tests passed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)

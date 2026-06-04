from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import attach_bulk_pricing_parallel, flatten_cube_rows, run_cube
from ._guards import is_non_medicine_lookup

SCHEMA = FunctionSchema(
    name="get_medicine_detail",
    description=(
        "Look up price, stock, Rx status, and bulk offers for a PHARMACEUTICAL PRODUCT "
        "(drug brand or generic) by name. "
        "DO NOT CALL if the user said Mr. Med, MrMed, Mister Med, Mr. V, Sarah, their "
        "own name, their city, or asked what Mr. Med is — that is the pharmacy company, "
        "not a medicine; answer without tools. "
        "ONLY CALL when the user explicitly asked for price/stock/info on a named "
        "medicine product (e.g. Glutone, Oxiage LG, Crocin). "
        "Returns stock_quantity (exact units) and bulk_offer_line when applicable."
    ),
    properties={
        "name": {
            "type": "string",
            "description": (
                "Exact medicine brand or generic the user asked to look up — e.g. "
                "'Glutone 1000', 'Oxiage LG Tablet'. Never 'Mr. Med', 'MrMed', or company names."
            ),
        },
    },
    required=["name"],
)


async def handler(params: FunctionCallParams):
    import cube_tools

    name = params.arguments["name"]
    if is_non_medicine_lookup(name):
        await params.result_callback(
            {
                "medicines": [],
                "skipped": True,
                "reason": (
                    f"'{name}' is not a medicine product — Mr. Med is the pharmacy. "
                    "Do not use this tool for company or caller meta questions."
                ),
            }
        )
        return
    rows = await run_cube(cube_tools.get_medicine_detail, name)
    medicines = flatten_cube_rows(rows)
    bulk_targets = [
        m
        for m in medicines
        if m.get("pricing_model") in ("quantity_tier", "flat_per_unit") and m.get("id")
    ]
    if bulk_targets:
        await attach_bulk_pricing_parallel(bulk_targets)
    await params.result_callback({"medicines": medicines})

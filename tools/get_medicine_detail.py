from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import attach_bulk_pricing, flatten_cube_rows, run_cube

SCHEMA = FunctionSchema(
    name="get_medicine_detail",
    description=(
        "Look up price, stock, Rx status, and bulk offers for a medicine by name. "
        "Returns stock_quantity (exact units in stock) and stock_status (label). "
        "When the user asks how many are available, say stock_quantity — not just "
        "the status label. Response includes bulk_offer_line when a bulk deal exists."
    ),
    properties={
        "name": {
            "type": "string",
            "description": "Medicine name or brand the user mentioned, e.g. Oxiage LG",
        },
    },
    required=["name"],
)


async def handler(params: FunctionCallParams):
    import cube_tools

    name = params.arguments["name"]
    rows = await run_cube(cube_tools.get_medicine_detail, name)
    medicines = flatten_cube_rows(rows)
    for med in medicines:
        if med.get("pricing_model") in ("quantity_tier", "flat_per_unit"):
            await attach_bulk_pricing(med, int(med["id"]))
    await params.result_callback({"medicines": medicines})

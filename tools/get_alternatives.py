from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import attach_bulk_pricing, flatten_cube_rows, run_cube

SCHEMA = FunctionSchema(
    name="get_alternatives",
    description=(
        "Find in-stock substitute medicines when the user is booking and wants "
        "cheaper or equivalent alternatives. Each alternative may include "
        "bulk_offer_line — you MUST mention it with the pack price when present. "
        "Requires medicine_id from get_medicine_detail."
    ),
    properties={
        "medicine_id": {
            "type": "integer",
            "description": "Medicine id from get_medicine_detail",
        },
        "cheaper_only": {
            "type": "boolean",
            "description": "If true, return only cheaper alternatives. Default true.",
        },
    },
    required=["medicine_id"],
)


async def handler(params: FunctionCallParams):
    import cube_tools

    medicine_id = int(params.arguments["medicine_id"])
    cheaper_only = params.arguments.get("cheaper_only", True)
    rows = await run_cube(
        cube_tools.get_alternatives, medicine_id, cheaper_only=cheaper_only
    )
    alternatives = flatten_cube_rows(rows)
    for alt in alternatives:
        alt_id = alt.get("alternative_id")
        if alt_id:
            await attach_bulk_pricing(alt, int(alt_id))
    await params.result_callback({"alternatives": alternatives})

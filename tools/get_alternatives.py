from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import (
    attach_bulk_pricing_parallel,
    flatten_cube_rows,
    run_cube,
    should_attach_bulk_on_alternatives,
)

SCHEMA = FunctionSchema(
    name="get_alternatives",
    description=(
        "Find in-stock substitute medicines. "
        "DO NOT CALL unless the user explicitly asked for substitutes/cheaper options "
        "for a medicine you already identified via get_medicine_detail on that same drug. "
        "Never call for Mr. Med/MrMed company questions. "
        "Requires medicine_id from a prior get_medicine_detail on a real product."
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
    if alternatives and should_attach_bulk_on_alternatives():
        await attach_bulk_pricing_parallel(alternatives)
    await params.result_callback({"alternatives": alternatives})

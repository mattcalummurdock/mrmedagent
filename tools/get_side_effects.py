from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import flatten_cube_rows, run_cube

SCHEMA = FunctionSchema(
    name="get_side_effects",
    description=(
        "List known side effects for a medicine already identified via "
        "get_medicine_detail. Optionally filter by severity."
    ),
    properties={
        "medicine_id": {
            "type": "integer",
            "description": "Medicine id from get_medicine_detail",
        },
        "severity": {
            "type": "string",
            "enum": ["common", "serious", "rare"],
            "description": "Optional severity filter",
        },
    },
    required=["medicine_id"],
)


async def handler(params: FunctionCallParams):
    import cube_tools

    medicine_id = int(params.arguments["medicine_id"])
    severity = params.arguments.get("severity")
    rows = await run_cube(
        cube_tools.get_side_effects, medicine_id, severity=severity
    )
    await params.result_callback({"side_effects": flatten_cube_rows(rows)})

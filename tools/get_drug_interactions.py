from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import flatten_cube_rows, run_cube

SCHEMA = FunctionSchema(
    name="get_drug_interactions",
    description=(
        "List known drug interactions for a medicine already identified via "
        "get_medicine_detail."
    ),
    properties={
        "medicine_id": {
            "type": "integer",
            "description": "Medicine id from get_medicine_detail",
        },
    },
    required=["medicine_id"],
)


async def handler(params: FunctionCallParams):
    import cube_tools

    medicine_id = int(params.arguments["medicine_id"])
    rows = await run_cube(cube_tools.get_drug_interactions, medicine_id)
    await params.result_callback({"interactions": flatten_cube_rows(rows)})

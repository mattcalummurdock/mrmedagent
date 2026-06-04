from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import run_cube

SCHEMA = FunctionSchema(
    name="get_quantity_pricing",
    description=(
        "Get quantity/bulk pricing for a medicine already looked up. "
        "DO NOT CALL unless the user asked about quantity/bulk pricing for that "
        "specific medicine and you have medicine_id from get_medicine_detail. "
        "Never call for Mr. Med company questions or during intake."
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
    result = await run_cube(cube_tools.get_quantity_pricing, medicine_id)
    await params.result_callback(result)

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import run_cube

SCHEMA = FunctionSchema(
    name="get_quantity_pricing",
    description=(
        "Get quantity-based or per-unit pricing for upselling when the user is "
        "booking or asking about bulk savings. Use after get_medicine_detail when "
        "discussing how many units to buy."
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

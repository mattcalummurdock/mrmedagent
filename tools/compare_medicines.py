from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import flatten_cube_rows, run_cube

SCHEMA = FunctionSchema(
    name="compare_medicines",
    description=(
        "Compare two medicines the user named side by side: price, form, "
        "therapeutic class, prescription requirement, and stock status."
    ),
    properties={
        "name_a": {
            "type": "string",
            "description": "First medicine name",
        },
        "name_b": {
            "type": "string",
            "description": "Second medicine name",
        },
    },
    required=["name_a", "name_b"],
)


async def handler(params: FunctionCallParams):
    import cube_tools

    rows = await run_cube(
        cube_tools.compare_medicines,
        params.arguments["name_a"],
        params.arguments["name_b"],
    )
    await params.result_callback({"comparison": flatten_cube_rows(rows)})

from pipecat.adapters.schemas.tools_schema import ToolsSchema

from ._announce import augment_schema
from . import (
    compare_medicines,
    get_alternatives,
    get_drug_interactions,
    get_medicine_detail,
    get_quantity_pricing,
    get_side_effects,
)

_TOOL_MODULES = [
    get_medicine_detail,
    get_quantity_pricing,
    get_alternatives,
    compare_medicines,
    get_side_effects,
    get_drug_interactions,
]

TOOLS_SCHEMA = ToolsSchema(
    standard_tools=[augment_schema(m.SCHEMA) for m in _TOOL_MODULES]
)


def register_tools(llm):
    for module in _TOOL_MODULES:
        llm.register_function(
            module.SCHEMA.name,
            module.handler,
            cancel_on_interruption=False,
        )

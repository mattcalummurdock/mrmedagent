"""Shared instruction: speak a brief hold line in the same turn before every tool call."""

from pipecat.adapters.schemas.function_schema import FunctionSchema

ANNOUNCE_SUFFIX = (
    " MANDATORY SAME TURN: first speak one brief natural hold line in the user's "
    "current language (vary wording — e.g. let me check that, I will look that up, "
    "just a second), then invoke this function immediately in that same turn. "
    "Do NOT end the turn or wait for the user to say okay — announce and call."
)


def augment_schema(schema: FunctionSchema) -> FunctionSchema:
    return FunctionSchema(
        name=schema.name,
        description=(schema.description or "") + ANNOUNCE_SUFFIX,
        properties=schema.properties,
        required=schema.required,
    )

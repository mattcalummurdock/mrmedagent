import asyncio

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from ._cube import attach_bulk_pricing_parallel
from ._guards import is_non_medicine_lookup
from ._medicine_search import search_medicines_by_mention, search_terms_from_mention

SCHEMA = FunctionSchema(
    name="get_medicine_detail",
    description=(
        "Look up price, stock, Rx status, and bulk offers for a PHARMACEUTICAL PRODUCT "
        "(drug brand or generic) by name. "
        "DO NOT CALL unless the user EXPLICITLY asked for medicine price/stock/info in their "
        "last message AND named a product. "
        "DO NOT CALL if the user only gave their name, city, greeting, yes/no, Mr. Med, "
        "MrMed, Mister Med, Mr. V, Sarah, or asked what Mr. Med is — answer without tools. "
        "DO NOT CALL speculatively on STT noise or words that merely sound like drug names. "
        "CALL when the user asked for price/stock/info on a medicine — pass their exact "
        "words even if misspelled, mispronounced, or garbled; do NOT ask them to say the "
        "name properly first. "
        "Returns stock_quantity (exact units), is_available, stock_status, form, "
        "pack_size, and bulk_offer_line when applicable. Fuzzy-matches spoken or "
        "misspelled names via text + embedding + pack-letter search (e.g. garbled "
        "'oksiage el gee' or pack letters 'atr' may resolve to a catalog product). "
        "Check match_method: confirm with caller when match_method is 'semantic' or "
        "'pack_letters'."
    ),
    properties={
        "name": {
            "type": "string",
            "description": (
                "Medicine clue exactly as the user said it — full name, garbled name, or "
                "partial pack letters (e.g. 'I only see atr on the pack'). Never 'Mr. Med', "
                "'MrMed', or company names."
            ),
        },
    },
    required=["name"],
)


async def handler(params: FunctionCallParams):
    name = params.arguments["name"]
    if is_non_medicine_lookup(name):
        await params.result_callback(
            {
                "medicines": [],
                "skipped": True,
                "reason": (
                    f"'{name}' is not a medicine product lookup — caller did not ask for this, "
                    "or this is Mr. Med / company / intake meta. Do NOT tell the caller you "
                    "could not find a medicine. Continue the conversation without mentioning tools."
                ),
            }
        )
        return

    medicines = await asyncio.to_thread(search_medicines_by_mention, name)
    if not medicines:
        await params.result_callback(
            {
                "medicines": [],
                "query": name,
                "search_terms_tried": search_terms_from_mention(name),
                "hint": (
                    "No catalog match. Tell the caller you could not find that exact product "
                    "in Mr. Med's catalog — do not invent stock or price."
                ),
            }
        )
        return

    bulk_targets = [
        m
        for m in medicines
        if m.get("pricing_model") in ("quantity_tier", "flat_per_unit") and m.get("id")
    ]
    if bulk_targets:
        await attach_bulk_pricing_parallel(bulk_targets)

    best = medicines[0]
    payload: dict = {
        "medicines": medicines,
        "best_match": best,
        "query": name,
        "resolved_name": best.get("name"),
        "resolved_id": best.get("id"),
        "match_method": best.get("match_method", "text"),
    }
    if best.get("match_method") in ("semantic", "pack_letters"):
        if best.get("match_method") == "pack_letters":
            clue = best.get("matched_clue") or name
            payload["confirm_with_caller"] = (
                f"The caller only gave partial pack letters ({clue!r}). "
                f"Ask: 'Are you looking for {best.get('name')}?' before quoting price or stock."
            )
        else:
            payload["confirm_with_caller"] = (
                f"The caller's wording did not exactly match the catalog. "
                f"Ask if they meant {best.get('name')!r} before quoting price or stock."
            )
    await params.result_callback(payload)

"""Inline call post-processor: Groq analysis + Cube pricing + Postgres CRM writes."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq
from loguru import logger
from psycopg2.pool import ThreadedConnectionPool

load_dotenv(override=True)

_AGENT_DIR = Path(__file__).resolve().parent


def _resolve_db_scripts() -> Path | None:
    for candidate in (
        _AGENT_DIR.parent / "DB" / "scripts",
        _AGENT_DIR / "scripts",
        Path("/app/DB/scripts"),
    ):
        if (candidate / "cube_tools.py").is_file():
            return candidate
    return None


_DB_SCRIPTS = _resolve_db_scripts()
_CUBE_ENV_PATHS = (
    _AGENT_DIR / "cube" / ".env",
    _AGENT_DIR.parent / "DB" / "cube" / ".env",
)

if _DB_SCRIPTS and str(_DB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DB_SCRIPTS))

for _cube_env in _CUBE_ENV_PATHS:
    if _cube_env.is_file():
        load_dotenv(_cube_env, override=False)

# Dedicated post-processor log (agent stderr still shows INFO+ via server)
logger.add(
    _AGENT_DIR / "postprocessor.log",
    rotation="10 MB",
    level="INFO",
    filter=lambda record: record["extra"].get("postprocessor", False),
)

_pp_logger = logger.bind(postprocessor=True)

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_DATABASE_URL = "postgresql://meduser:medpass@localhost:5433/meddb"

_postprocess_semaphore: asyncio.Semaphore | None = None
_db_pool: ThreadedConnectionPool | None = None
_groq_client: Groq | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _postprocess_semaphore
    if _postprocess_semaphore is None:
        limit = int(os.getenv("POSTPROCESS_MAX_CONCURRENT", "5"))
        _postprocess_semaphore = asyncio.Semaphore(limit)
    return _postprocess_semaphore


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GROQ_API_KEY must be set in .env")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _get_groq_model() -> str:
    return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip()


def _get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip()


def _get_db_pool() -> ThreadedConnectionPool:
    global _db_pool
    if _db_pool is None:
        _db_pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=_get_database_url(),
        )
        _pp_logger.info("Postgres connection pool initialized")
    return _db_pool


def _message_content(msg: dict) -> str:
    content = msg.get("content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif "text" in part:
                    parts.append(str(part["text"]))
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(p for p in parts if p).strip()
    return str(content).strip() if content else ""


def messages_to_transcript(messages: list[dict]) -> str:
    """Convert Pipecat LLMContext messages to User:/Agent: transcript."""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = _message_content(msg)
        if not content:
            continue
        if role == "user":
            lines.append(f"User: {content}")
        elif role in ("assistant", "model"):
            lines.append(f"Agent: {content}")
    return "\n".join(lines)


def normalize_phone_number(phone_number: str) -> str:
    digits_only = "".join(filter(str.isdigit, phone_number))
    if digits_only.startswith("91") and len(digits_only) > 10:
        return digits_only[2:]
    if len(digits_only) > 10:
        return digits_only[-10:]
    if len(digits_only) < 10:
        return digits_only.zfill(10) if digits_only else ""
    return digits_only


def normalize_conversation_tags(conversation: str) -> str:
    lines = conversation.split("\n")
    normalized: list[str] = []
    agent_pattern = re.compile(
        r"^(?:Sarah\s*\(Agent\)|Agent\s*\([^)]*\)|Sarah|Agent)\s*:\s*(.*)$",
        re.IGNORECASE,
    )
    user_pattern = re.compile(r"^User\s*:\s*(.*)$", re.IGNORECASE)

    for line in lines:
        agent_match = agent_pattern.match(line)
        if agent_match:
            normalized.append(f"Agent: {agent_match.group(1)}")
            continue
        user_match = user_pattern.match(line)
        if user_match:
            normalized.append(f"User: {user_match.group(1)}")
        else:
            normalized.append(line)
    return "\n".join(normalized)


def _groq_json(system: str, user: str) -> dict:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_get_groq_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)


def detect_languages(conversation: str) -> list[str]:
    try:
        result = _groq_json(
            "Detect all languages in the conversation including transliterated Indian languages. "
            "Return JSON: {\"languages\": [\"english\", \"hindi\", ...]}",
            f"Conversation:\n{conversation}",
        )
        languages = [
            lang.lower().strip()
            for lang in result.get("languages", [])
            if lang and str(lang).strip()
        ]
        languages = sorted(set(languages)) or ["english"]
        _pp_logger.info(f"Detected languages: {languages}")
        return languages
    except Exception as e:
        _pp_logger.error(f"Language detection failed: {e}")
        return ["english"]


def extract_caller_info(conversation: str) -> dict[str, Any]:
    try:
        result = _groq_json(
            "Extract caller contact info from a Mr. Med pharmacy call. "
            "Return JSON with keys: name (string), "
            "bulk_offers (array of bulk/promo offers mentioned, e.g. 'Bulk 200 tubes offer'). "
            "Do not extract phone, email, or medicine names.",
            f"Conversation:\n{conversation}",
        )
        name = str(result.get("name", "") or "").strip() or "Unknown Caller"
        bulk_offers = [
            str(o).strip()
            for o in result.get("bulk_offers", [])
            if o and str(o).strip()
        ]
        info = {
            "name": name,
            "bulk_offers": bulk_offers,
        }
        _pp_logger.info(f"Extracted caller info: {info}")
        return info
    except Exception as e:
        _pp_logger.error(f"Caller extraction failed: {e}")
        return {
            "name": "Unknown Caller",
            "bulk_offers": [],
        }


def extract_medicine_context(conversation: str) -> dict[str, Any]:
    """Use Groq only to detect what was discussed — not canonical DB names or prices."""
    try:
        result = _groq_json(
            "Analyze a Mr. Med pharmacy call for medicine interest. "
            "Return JSON with:\n"
            "- medicine_mentions: array of medicine/product names as spoken (verbatim from conversation)\n"
            "- primary_mention: the main medicine the caller enquired about or wanted to order\n"
            "- quantity: integer count if caller asked for a specific quantity (e.g. 200, 10, 3), else null\n"
            "- quantity_unit: short unit if stated (e.g. tubes, packs, tablets), else empty string\n"
            "- pricing_intent: one of bulk, single_pack, packs, units, unknown\n"
            "Use bulk when caller wants bulk deal / tier pricing. "
            "Use single_pack for one pack. Use packs for multiple packs. "
            "Use units for per-tablet/per-unit pricing.",
            f"Conversation:\n{conversation}",
        )
        mentions = [
            str(m).strip()
            for m in result.get("medicine_mentions", [])
            if m and str(m).strip()
        ]
        primary = str(result.get("primary_mention", "") or "").strip()
        if primary and primary not in mentions:
            mentions.insert(0, primary)
        quantity_raw = result.get("quantity")
        quantity = int(quantity_raw) if quantity_raw is not None else None
        if quantity is not None and quantity <= 0:
            quantity = None
        ctx = {
            "medicine_mentions": mentions,
            "primary_mention": primary or (mentions[0] if mentions else ""),
            "quantity": quantity,
            "quantity_unit": str(result.get("quantity_unit", "") or "").strip(),
            "pricing_intent": str(result.get("pricing_intent", "unknown") or "unknown").lower(),
        }
        _pp_logger.info(f"Extracted medicine context: {ctx}")
        return ctx
    except Exception as e:
        _pp_logger.error(f"Medicine context extraction failed: {e}")
        return {
            "medicine_mentions": [],
            "primary_mention": "",
            "quantity": None,
            "quantity_unit": "",
            "pricing_intent": "unknown",
        }


def generate_analytics(conversation: str) -> dict[str, Any]:
    """City and intent only — medication/budget come from Cube."""
    try:
        result = _groq_json(
            "Analyze a Mr. Med pharmacy sales call. Return JSON with: "
            "city (caller's city if mentioned, else empty string), "
            "intent_level (TOFU, MOFU, or BOFU — BOFU if ready to order).",
            f"Conversation:\n{conversation}",
        )
        city = str(result.get("city", "") or "").strip()
        intent_level = str(result.get("intent_level", "TOFU") or "TOFU").upper()
        if intent_level not in ("TOFU", "MOFU", "BOFU"):
            intent_level = "TOFU"
        analytics = {
            "city": city,
            "intent_level": intent_level,
        }
        _pp_logger.info(f"Generated analytics: {analytics}")
        return analytics
    except Exception as e:
        _pp_logger.error(f"Analytics generation failed: {e}")
        return {"city": "", "intent_level": "TOFU"}


def _price_from_cube_row(row: dict) -> float | None:
    for key in ("Medicines.sellingPrice", "selling_price", "sellingPrice"):
        val = row.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def _search_terms_from_mention(mention: str) -> list[str]:
    from tools._medicine_search import search_terms_from_mention

    return search_terms_from_mention(mention)


def _score_medicine_match(mention: str, row: dict) -> float:
    from tools._medicine_search import score_medicine_match

    return score_medicine_match(mention, row)


def _medicine_row_to_record(row: dict, match_score: float) -> dict[str, Any]:
    med_id = row.get("Medicines.id")
    selling_price = _price_from_cube_row(row)
    price_per_unit = row.get("Medicines.pricePerUnit")
    return {
        "id": int(med_id) if med_id is not None else None,
        "name": str(row.get("Medicines.name") or "").strip(),
        "generic_name": str(row.get("Medicines.genericName") or "").strip(),
        "selling_price": selling_price,
        "pricing_model": str(row.get("Medicines.pricingModel") or "single_pack").strip(),
        "price_per_unit": float(price_per_unit) if price_per_unit is not None else None,
        "match_score": match_score,
    }


def resolve_medicine_in_cube(mention: str) -> dict[str, Any] | None:
    """Resolve a spoken mention to an exact medicine row in Cube/Postgres."""
    import cube_tools

    if not mention.strip():
        return None

    best_row: dict | None = None
    best_score = 0.0

    for term in _search_terms_from_mention(mention):
        try:
            rows = cube_tools.get_medicine_detail(term)
        except Exception as e:
            _pp_logger.warning(f"Cube get_medicine_detail failed for {term!r}: {e}")
            continue
        for row in rows:
            score = _score_medicine_match(mention, row)
            if score > best_score:
                best_score = score
                best_row = row

    if best_row is None or best_score < 40.0:
        _pp_logger.warning(f"No confident Cube match for mention {mention!r}")
        return None

    record = _medicine_row_to_record(best_row, best_score)
    if not record["id"] or not record["name"] or record["selling_price"] is None:
        _pp_logger.warning(f"Cube match incomplete for {mention!r}: {record}")
        return None

    _pp_logger.info(
        f"Cube resolved {mention!r} → {record['name']!r} "
        f"(id={record['id']}, Rs. {record['selling_price']}, score={best_score:.1f})"
    )
    return record


def resolve_medicines_from_context(med_ctx: dict[str, Any]) -> dict[str, Any]:
    """Resolve primary + secondary mentions against Cube; DB is source of truth."""
    mentions = med_ctx.get("medicine_mentions") or []
    primary_mention = (med_ctx.get("primary_mention") or "").strip()
    ordered: list[str] = []
    seen: set[str] = set()
    for mention in [primary_mention, *mentions]:
        cleaned = mention.strip()
        key = cleaned.lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append(cleaned)

    resolved_by_id: dict[int, dict[str, Any]] = {}
    primary: dict[str, Any] | None = None
    for mention in ordered:
        record = resolve_medicine_in_cube(mention)
        if not record:
            continue
        if record["id"] not in resolved_by_id:
            resolved_by_id[record["id"]] = record
        if primary is None and (
            not primary_mention or mention.lower() == primary_mention.lower()
        ):
            primary = record

    resolved = list(resolved_by_id.values())
    if primary is None and resolved:
        primary = resolved[0]

    return {"primary": primary, "all": resolved}


def _pick_quantity_tier(tiers: list[dict[str, Any]], quantity: int | None, pricing_intent: str):
    if not tiers:
        return None
    if quantity is not None:
        exact = next((t for t in tiers if int(t.get("quantity") or 0) == quantity), None)
        if exact:
            return exact
        if pricing_intent == "bulk":
            return max(tiers, key=lambda t: int(t.get("quantity") or 0))
    if pricing_intent == "bulk":
        return max(tiers, key=lambda t: int(t.get("quantity") or 0))
    return None


def compute_budget_from_db(
    medicine: dict[str, Any],
    med_ctx: dict[str, Any],
) -> str:
    """Derive budget string only from Cube catalog pricing and caller quantity intent."""
    import cube_tools

    med_id = medicine["id"]
    quantity = med_ctx.get("quantity")
    pricing_intent = med_ctx.get("pricing_intent") or "unknown"
    quantity_unit = med_ctx.get("quantity_unit") or "units"

    try:
        pricing = cube_tools.get_quantity_pricing(med_id)
    except Exception as e:
        _pp_logger.warning(f"Cube get_quantity_pricing failed for id={med_id}: {e}")
        pricing = {}

    model = pricing.get("pricing_model") or medicine.get("pricing_model") or "single_pack"
    pack_price = pricing.get("selling_price")
    if pack_price is None:
        pack_price = medicine.get("selling_price")
    pack_price = float(pack_price or 0)

    if model == "quantity_tier":
        tiers = pricing.get("tiers") or []
        tier = _pick_quantity_tier(tiers, quantity, pricing_intent)
        if tier:
            label = tier.get("label") or f"{tier.get('quantity')} {quantity_unit}".strip()
            total = float(tier.get("total_price") or 0)
            return f"{_format_rupees(total)} ({label})"
        if pack_price > 0:
            suffix = " per pack"
            if quantity and pricing_intent == "packs":
                total = pack_price * quantity
                return f"{_format_rupees(total)} ({quantity} packs)"
            return f"{_format_rupees(pack_price)}{suffix}"

    if model == "flat_per_unit":
        unit_price = pricing.get("price_per_unit")
        if unit_price is None:
            unit_price = medicine.get("price_per_unit")
        unit_price = float(unit_price or 0)
        if unit_price <= 0:
            return ""
        if quantity and quantity > 0:
            total = unit_price * quantity
            return f"{_format_rupees(total)} ({quantity} {quantity_unit} @ {_format_rupees(unit_price)} each)"
        return f"{_format_rupees(unit_price)} per unit"

    if pack_price <= 0:
        return ""
    if quantity and quantity > 1 and pricing_intent in ("packs", "units", "unknown"):
        return f"{_format_rupees(pack_price * quantity)} ({quantity} packs)"
    return _format_rupees(pack_price)


def derive_medication_and_budget(med_ctx: dict[str, Any]) -> tuple[str, str]:
    """
    Resolve medication name and budget from Cube/DB only.
    Returns empty strings when no confident catalog match exists.
    """
    resolution = resolve_medicines_from_context(med_ctx)
    primary = resolution.get("primary")
    if not primary:
        _pp_logger.info("No Cube-resolved medicine — leaving Medication Enquired and Budget empty")
        return "", ""

    course_interest = primary["name"]
    budget = compute_budget_from_db(primary, med_ctx)
    if not budget:
        _pp_logger.info(
            f"Cube match found for {course_interest!r} but no price could be computed"
        )

    _pp_logger.info(
        f"CRM fields from Cube — medication={course_interest!r}, budget={budget!r}"
    )
    return course_interest, budget


def _format_rupees(amount: float) -> str:
    """Format a rupee amount using Indian grouping (e.g. 200000 → Rs. 2,00,000)."""
    n = int(round(amount))
    s = str(n)
    if len(s) <= 3:
        return f"Rs. {s}"
    last3 = s[-3:]
    rest = s[:-3]
    groups: list[str] = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return f"Rs. {','.join(groups + [last3])}"


def _find_caller(cur, phone: str) -> str | None:
    if phone:
        cur.execute(
            "SELECT id::text FROM callers WHERE phone_number = %s LIMIT 1",
            (phone,),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "SELECT id::text FROM callers WHERE phone_number = %s LIMIT 1",
            (f"91{phone}",),
        )
        row = cur.fetchone()
        if row:
            return row[0]
    return None


def _create_caller(cur, name: str, phone: str) -> str:
    phone_db = f"91{phone}" if phone else None
    cur.execute(
        """
        INSERT INTO callers (name, email, phone_number)
        VALUES (%s, NULL, %s)
        RETURNING id::text
        """,
        (name, phone_db or phone or None),
    )
    caller_id = cur.fetchone()[0]
    _pp_logger.info(f"Created caller id={caller_id} name={name!r} phone={phone_db or phone}")
    return caller_id


def _upsert_analytics(
    cur,
    caller_id: str,
    course_interest: str,
    city: str,
    budget: str,
    intent_level: str,
) -> None:
    cur.execute(
        """
        INSERT INTO caller_analytics (
            caller_id, course_interest, city, budget, hostel_needed, intent_level
        ) VALUES (%s, %s, %s, %s, FALSE, %s)
        ON CONFLICT (caller_id) DO UPDATE SET
            course_interest = EXCLUDED.course_interest,
            city = EXCLUDED.city,
            budget = EXCLUDED.budget,
            hostel_needed = FALSE,
            intent_level = EXCLUDED.intent_level
        """,
        (
            caller_id,
            course_interest or None,
            city or None,
            budget or None,
            intent_level,
        ),
    )
    _pp_logger.info(f"Upserted analytics for caller_id={caller_id}")


def _insert_conversation(
    cur,
    caller_id: str,
    conversation: str,
    languages: list[str],
    bulk_offers: list[str],
) -> str:
    cur.execute(
        """
        INSERT INTO conversation_history (
            caller_id, conversation, languages_used, scholarships
        ) VALUES (%s, %s, %s, %s)
        RETURNING id::text
        """,
        (
            caller_id,
            conversation,
            json.dumps(languages),
            json.dumps(bulk_offers) if bulk_offers else None,
        ),
    )
    conv_id = cur.fetchone()[0]
    _pp_logger.info(f"Inserted conversation_history id={conv_id}")
    return conv_id


def _process_call_sync(
    messages: list[dict],
    *,
    caller_phone: str | None = None,
    call_sid: str | None = None,
) -> None:
    started = time.monotonic()
    tag = call_sid or f"call-{int(time.time() * 1000) % 100000}"

    _pp_logger.info(f"[{tag}] Starting post-processing")

    transcript = messages_to_transcript(messages)
    if not transcript or "User:" not in transcript:
        _pp_logger.info(f"[{tag}] Skipping — no user turns in transcript")
        return

    conversation = normalize_conversation_tags(transcript)
    _pp_logger.info(f"[{tag}] Phase 1: extracting caller info and languages")

    languages = detect_languages(conversation)
    caller_info = extract_caller_info(conversation)

    phone = caller_phone or ""
    if phone:
        phone = normalize_phone_number(phone)
        if len(phone) != 10:
            phone = ""

    name = caller_info.get("name", "Unknown Caller")
    bulk_offers = caller_info.get("bulk_offers", [])

    _pp_logger.info(f"[{tag}] Phase 2: Cube medicine resolution and analytics")
    med_ctx = extract_medicine_context(conversation)
    course_interest, budget = derive_medication_and_budget(med_ctx)
    analytics = generate_analytics(conversation)

    _pp_logger.info(f"[{tag}] Phase 3: writing to Postgres")
    pool = _get_db_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            caller_id = _find_caller(cur, phone)
            if caller_id:
                _pp_logger.info(f"[{tag}] Matched existing caller id={caller_id}")
            else:
                caller_id = _create_caller(cur, name, phone)

            _upsert_analytics(
                cur,
                caller_id,
                course_interest,
                analytics.get("city", ""),
                budget,
                analytics.get("intent_level", "TOFU"),
            )
            conv_id = _insert_conversation(
                cur, caller_id, conversation, languages, bulk_offers
            )
        conn.commit()
        elapsed = time.monotonic() - started
        _pp_logger.info(
            f"[{tag}] Done in {elapsed:.1f}s — caller={caller_id} conversation={conv_id}"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


async def process_call_end(
    messages: list[dict],
    *,
    caller_phone: str | None = None,
    call_sid: str | None = None,
) -> None:
    """Run post-processing when a call ends. Safe for concurrent disconnects."""
    sem = _get_semaphore()
    async with sem:
        await asyncio.to_thread(
            _process_call_sync,
            messages,
            caller_phone=caller_phone,
            call_sid=call_sid,
        )


def shutdown_postprocessor() -> None:
    global _db_pool
    if _db_pool is not None:
        _db_pool.closeall()
        _db_pool = None
        _pp_logger.info("Postgres connection pool closed")

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

_here = Path(__file__).resolve().parent
_repo_root = _here.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

for _env in (
    _repo_root / ".env",
    _repo_root / "cube" / ".env",
    _repo_root.parent / "agent" / ".env",
    _repo_root.parent.parent / "agent" / ".env",
):
    if _env.is_file():
        load_dotenv(_env, override=False)

from cube_auth import cube_headers as _cube_headers  # noqa: E402
from cube_config import CUBE_BASE  # noqa: E402 — always localhost embedded Cube
CUBE_HTTP_TIMEOUT = float(os.getenv("CUBE_HTTP_TIMEOUT", "30"))
CUBE_CACHE_TTL_SECS = int(os.getenv("CUBE_CACHE_TTL_SECS", "300"))

_http = requests.Session()
_query_cache: dict[str, tuple[float, list]] = {}


def cube_query(query: dict) -> list[dict]:
    cache_key = json.dumps(query, sort_keys=True, default=str)
    if CUBE_CACHE_TTL_SECS > 0:
        cached = _query_cache.get(cache_key)
        if cached:
            ts, data = cached
            if time.time() - ts < CUBE_CACHE_TTL_SECS:
                return data

    resp = _http.post(
        f"{CUBE_BASE}/load",
        json={"query": query},
        headers=_cube_headers(),
        timeout=CUBE_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if CUBE_CACHE_TTL_SECS > 0:
        _query_cache[cache_key] = (time.time(), data)
    return data


def prewarm() -> None:
    """Lightweight query to keep Cube/DB connections warm (call on agent startup)."""
    cube_query({
        "dimensions": ["Medicines.id"],
        "filters": [
            {
                "member": "Medicines.id",
                "operator": "equals",
                "values": ["1"],
            }
        ],
        "limit": 1,
    })


def get_medicine_detail(name: str) -> list[dict]:
    return cube_query({
        "dimensions": [
            "Medicines.id",
            "Medicines.name",
            "Medicines.genericName",
            "Medicines.form",
            "Medicines.dosageStrength",
            "Medicines.mrp",
            "Medicines.sellingPrice",
            "Medicines.discountPercent",
            "Medicines.pricePerUnit",
            "Medicines.pricingModel",
            "Medicines.stockQuantity",
            "Medicines.stockStatus",
            "Medicines.isAvailable",
            "Medicines.prescriptionRequired",
            "Medicines.therapeuticClass",
            "Medicines.introduction",
            "Medicines.howToConsume",
            "Medicines.googleRating",
        ],
        "filters": [
            {
                "member": "Medicines.name",
                "operator": "contains",
                "values": [name],
            }
        ],
    })


def get_alternatives(medicine_id: int, cheaper_only: bool = True) -> list[dict]:
    filters = [
        {
            "member": "Alternatives.sourceMedicineId",
            "operator": "equals",
            "values": [str(medicine_id)],
        },
        {
            "member": "Alternatives.alternativeInStock",
            "operator": "equals",
            "values": ["true"],
        },
    ]
    if cheaper_only:
        filters.append({
            "member": "Alternatives.isCheaper",
            "operator": "equals",
            "values": ["Yes"],
        })

    return cube_query({
        "dimensions": [
            "Alternatives.alternativeId",
            "Alternatives.alternativeName",
            "Alternatives.alternativePrice",
            "Alternatives.priceDifference",
            "Alternatives.matchReason",
            "Alternatives.tier",
            "Alternatives.alternativeRequiresRx",
        ],
        "filters": filters,
        "order": {
            "Alternatives.tier": "asc",
            "Alternatives.priceDifference": "asc",
        },
    })


def get_medicines_by_class(therapeutic_class: str, max_price: float = None) -> list[dict]:
    filters = [
        {
            "member": "Medicines.therapeuticClass",
            "operator": "contains",
            "values": [therapeutic_class],
        },
        {
            "member": "Medicines.isAvailable",
            "operator": "equals",
            "values": ["true"],
        },
    ]
    if max_price is not None:
        filters.append({
            "member": "Medicines.sellingPrice",
            "operator": "lte",
            "values": [str(max_price)],
        })

    return cube_query({
        "dimensions": [
            "Medicines.name",
            "Medicines.genericName",
            "Medicines.sellingPrice",
            "Medicines.discountPercent",
            "Medicines.stockStatus",
            "Medicines.prescriptionRequired",
        ],
        "filters": filters,
        "order": {"Medicines.sellingPrice": "asc"},
    })


def compare_medicines(name_a: str, name_b: str) -> list[dict]:
    return cube_query({
        "dimensions": [
            "Medicines.name",
            "Medicines.genericName",
            "Medicines.sellingPrice",
            "Medicines.mrp",
            "Medicines.discountPercent",
            "Medicines.therapeuticClass",
            "Medicines.prescriptionRequired",
            "Medicines.stockStatus",
            "Medicines.form",
            "Medicines.dosageStrength",
            "Medicines.howToConsume",
            "Medicines.googleRating",
        ],
        "filters": [
            {
                "member": "Medicines.name",
                "operator": "contains",
                "values": [name_a, name_b],
            }
        ],
    })


def get_side_effects(medicine_id: int, severity: str = None) -> list[dict]:
    filters = [
        {
            "member": "SideEffects.medicineId",
            "operator": "equals",
            "values": [str(medicine_id)],
        }
    ]
    if severity:
        filters.append({
            "member": "SideEffects.severity",
            "operator": "equals",
            "values": [severity],
        })

    return cube_query({
        "dimensions": [
            "SideEffects.effectText",
            "SideEffects.severity",
        ],
        "filters": filters,
        "order": {"SideEffects.displayOrder": "asc"},
    })


def get_drug_interactions(medicine_id: int) -> list[dict]:
    return cube_query({
        "dimensions": [
            "DrugInteractions.interactingDrug",
            "DrugInteractions.interactionEffect",
            "DrugInteractions.severity",
        ],
        "filters": [
            {
                "member": "DrugInteractions.medicineId",
                "operator": "equals",
                "values": [str(medicine_id)],
            }
        ],
        "order": {"DrugInteractions.severity": "desc"},
    })


def _indication_matches(ailment: str) -> list[dict]:
    return cube_query({
        "dimensions": [
            "Indications.diseaseName",
            "Indications.diseaseCategory",
            "Indications.medicineId",
            "Indications.medicineName",
            "Indications.genericName",
            "Indications.sellingPrice",
            "Indications.prescriptionRequired",
            "Indications.therapeuticClass",
        ],
        "filters": [
            {
                "member": "Indications.diseaseName",
                "operator": "contains",
                "values": [ailment],
            }
        ],
        "order": {"Indications.sellingPrice": "asc"},
    })


def _ailment_keywords(ailment: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", ailment.lower())
    stop = {"i", "have", "my", "the", "a", "an", "for", "with", "is", "am", "something", "need"}
    keywords = [w for w in words if w not in stop and len(w) > 2]
    return keywords or [ailment.strip()]


def recommend_by_ailment(ailment: str, top_k: int = 3) -> list[dict]:
    from semantic_search import semantic_search

    seen: set[int] = set()
    results: list[dict] = []

    for keyword in _ailment_keywords(ailment):
        for row in _indication_matches(keyword):
            med_id = int(row["Indications.medicineId"])
            if med_id in seen:
                continue
            seen.add(med_id)
            results.append({
                "medicine_id": med_id,
                "medicine_name": row["Indications.medicineName"],
                "generic_name": row.get("Indications.genericName"),
                "selling_price": float(row["Indications.sellingPrice"]),
                "in_stock": True,
                "requires_rx": row["Indications.prescriptionRequired"] in (True, "true"),
                "therapeutic_class": row.get("Indications.therapeuticClass"),
                "match_reason": f"Indicated for: {row['Indications.diseaseName']}",
                "tier": 1,
                "similarity": None,
            })

    for row in semantic_search(ailment, top_k=top_k * 2):
        med_id = row["medicine_id"]
        if med_id in seen:
            continue
        seen.add(med_id)
        results.append({
            "medicine_id": med_id,
            "medicine_name": row["medicine_name"],
            "generic_name": row["generic_name"],
            "selling_price": row["selling_price"],
            "in_stock": row["in_stock"],
            "requires_rx": row["requires_rx"],
            "therapeutic_class": row["therapeutic_class"],
            "match_reason": f"Semantic match (similarity {row['similarity']:.2f})",
            "tier": 2,
            "similarity": row["similarity"],
        })

    results.sort(key=lambda r: (r["tier"], not r["in_stock"], r["selling_price"] or 0))
    return results[:top_k]


def get_quantity_pricing(medicine_id: int) -> dict:
    rows = cube_query({
        "dimensions": [
            "Medicines.id",
            "Medicines.name",
            "Medicines.sellingPrice",
            "Medicines.pricePerUnit",
            "Medicines.pricingModel",
        ],
        "filters": [
            {
                "member": "Medicines.id",
                "operator": "equals",
                "values": [str(medicine_id)],
            }
        ],
    })
    if not rows:
        return {"error": "Medicine not found"}

    med = rows[0]
    model = med.get("Medicines.pricingModel", "single_pack")
    result = {
        "medicine_id": med["Medicines.id"],
        "medicine_name": med["Medicines.name"],
        "pricing_model": model,
        "selling_price": med.get("Medicines.sellingPrice"),
        "price_per_unit": med.get("Medicines.pricePerUnit"),
    }

    if model == "flat_per_unit":
        unit = float(med.get("Medicines.pricePerUnit") or 0)
        result["note"] = f"Flat rate: Rs. {unit:.2f} per unit — total = quantity × unit price"
        return result

    if model == "quantity_tier":
        tiers = cube_query({
            "dimensions": [
                "MedicineQuantityTiers.quantity",
                "MedicineQuantityTiers.totalPrice",
                "MedicineQuantityTiers.label",
            ],
            "filters": [
                {
                    "member": "MedicineQuantityTiers.medicineId",
                    "operator": "equals",
                    "values": [str(medicine_id)],
                }
            ],
            "order": {"MedicineQuantityTiers.displayOrder": "asc"},
        })
        tier_list = []
        for t in tiers:
            qty = int(t["MedicineQuantityTiers.quantity"])
            total = float(t["MedicineQuantityTiers.totalPrice"])
            tier_list.append({
                "quantity": qty,
                "total_price": total,
                "price_per_unit": round(total / qty, 2),
                "label": t.get("MedicineQuantityTiers.label"),
            })
        result["tiers"] = tier_list
        if tier_list:
            best = tier_list[-1]
            label = best.get("label") or f"{best['quantity']} units"
            pack = float(med.get("Medicines.sellingPrice") or 0)
            result["upsell_line"] = (
                f"Bulk offer: {label} for Rs. {best['total_price']:.0f} "
                f"(Rs. {best['price_per_unit']:.2f} each)"
            )
            if pack > 0 and best["price_per_unit"] < pack:
                result["upsell_line"] += f" — much cheaper than Rs. {pack:.0f} per pack"
        if len(tier_list) >= 2:
            small, large = tier_list[0], tier_list[-1]
            savings = round(
                (small["total_price"] / small["quantity"] * large["quantity"])
                - large["total_price"],
                2,
            )
            result["bulk_savings_hint"] = (
                f"Buying {large['quantity']} saves Rs. {savings:.0f} vs buying "
                f"{large['quantity']} at the {small['quantity']}-unit rate"
            )
        return result

    result["note"] = "Single-pack pricing — use selling_price for one pack"
    return result

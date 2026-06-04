"""Reject tool calls that are not real medicine product lookups."""

from __future__ import annotations

# Company / meta queries — not pharmaceutical products.
_BLOCKED_LOOKUP_PHRASES = frozenset(
    {
        "mr med",
        "mr. med",
        "mrmed",
        "mister med",
        "mr v",
        "mr. v",
        "mrmed.in",
        "mr med india",
        "mister med india",
        "sarah",
        "mr med pharmacy",
        "about mr med",
        "about mrmed",
    }
)


def normalize_lookup_name(name: str) -> str:
    cleaned = "".join(c if c.isalnum() else " " for c in str(name or "").lower())
    return " ".join(cleaned.split())


def is_non_medicine_lookup(name: str) -> bool:
    """True if name is Mr. Med / company / helpline meta — not a drug to look up."""
    n = normalize_lookup_name(name)
    if not n:
        return True
    if n in _BLOCKED_LOOKUP_PHRASES:
        return True
    if n.startswith("mr ") and "med" in n:
        return True
    if "mrmed" in n.replace(" ", ""):
        return True
    return False

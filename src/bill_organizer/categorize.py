"""Step 3b -- assign a category to a bill via deterministic keyword matching.

Categories are scanned in config order; the first one with a keyword hit wins.
This is intentionally not an LLM task -- it is cheap, exact, and auditable.
"""

from __future__ import annotations

from .config import CategoriesConfig
from .models import ExtractedBill


def categorize_with_text(
    bill: ExtractedBill, raw_text: str, rules: CategoriesConfig
) -> tuple[str, bool]:
    """Return ``(category, ambiguous)`` for a bill.

    Searches the bill fields named in ``rules.match.fields_searched`` (vendor
    and/or the full ``raw_text``). ``ambiguous`` is True when more than one
    category matched -- the first by config order is chosen, but the bill
    should be reviewed.
    """
    searchable = _searchable_text(bill, raw_text, rules)

    matched = [
        c.name
        for c in rules.categories
        if any(_keyword_hit(kw, searchable, rules.match.case_sensitive) for kw in c.keywords)
    ]
    if not matched:
        return rules.default_category, False
    return matched[0], len(matched) > 1


def _searchable_text(bill: ExtractedBill, raw_text: str, rules: CategoriesConfig) -> str:
    """Concatenate the bill fields the config says to search."""
    parts: list[str] = []
    for field in rules.match.fields_searched:
        if field == "vendor" and bill.vendor:
            parts.append(bill.vendor)
        elif field == "raw_text":
            parts.append(raw_text)
    return " ".join(parts)


def _keyword_hit(keyword: str, text: str, case_sensitive: bool) -> bool:
    if case_sensitive:
        return keyword in text
    return keyword.lower() in text.lower()

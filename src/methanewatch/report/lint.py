"""Wording guardrails for generated reports (docs/PLAN.md section 9.4).

Results are screening indications from a retrospective tracker. Generated text
must not claim compliance findings, real-time monitoring, or health outcomes.
"""

from __future__ import annotations

import re
from typing import Literal

BANNED = {
    "saved": r"\bsaved\b",
    "real-time": r"\breal[- ]?time\b",
    "violation": r"\bviolations?\b",
    "non-compliant": r"\bnon[- ]?complian(t|ce)\b",
    "illegal": r"\billegal(ly)?\b",
    "lives": r"\blives\b",
    "health impact": r"\bhealth (impacts?|effects?|outcomes?)\b",
}

REQUIRED = {
    "site": [r"screening indication"],
    "index": [r"retrospective", r"screening indication"],
    "briefing": [r"retrospective", r"screening indication"],
}

PageKind = Literal["site", "index", "briefing", "verified-drop"]


def find_banned(text: str, *, allow: frozenset[str] = frozenset()) -> list[str]:
    """Return the banned phrases present in ``text``."""
    return [
        name
        for name, pattern in BANNED.items()
        if name not in allow and re.search(pattern, text, flags=re.IGNORECASE)
    ]


def check_page(text: str, kind: PageKind) -> list[str]:
    """Problems with a rendered page; an empty list means it passes."""
    # "saved" is allowed only on the template for a repair with a verified drop.
    allow = frozenset({"saved"}) if kind == "verified-drop" else frozenset()
    problems = [f"banned phrase: {p}" for p in find_banned(text, allow=allow)]
    for pattern in REQUIRED.get(kind, []):
        if not re.search(pattern, text, flags=re.IGNORECASE):
            problems.append(f"missing required phrase: {pattern}")
    return problems

"""Wording guardrails for generated pages (docs/PLAN.md section 9.4).

Results are screening indications from a retrospective tracker. Generated text
must not claim compliance findings, real-time monitoring, or health outcomes.

The word list lives in ``config/wording.json`` and is shared with the website
build, so the Python check and the web check cannot drift apart. An official
document title that contains a banned word may appear only inside an element
marked ``data-wording="source-title"`` (or, for plain records, in the
``source_doc_title`` field); everything else is checked.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from methanewatch.config import CONFIG_DIR

WORDING_PATH = CONFIG_DIR / "wording.json"

PageKind = Literal[
    "site",
    "index",
    "briefing",
    "verified-drop",
    "home",
    "map",
    "checks",
    "updates",
    "sites",
    "methods",
    "how-to-read",
    "data",
]


@lru_cache(maxsize=4)
def load_wording(path: Path = WORDING_PATH) -> dict:
    """The shared word list, read once."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_WORDING = load_wording()

BANNED: dict[str, str] = {name: entry["pattern"] for name, entry in _WORDING["banned"].items()}
REQUIRED: dict[str, list[str]] = {kind: list(v) for kind, v in _WORDING["required"].items()}
ALLOWANCES: dict[str, frozenset[str]] = {
    kind: frozenset(names) for kind, names in _WORDING["allowances"].items()
}
QUOTED = _WORDING["quoted_source_title"]

# An element carrying data-wording="source-title", with everything inside it. The element
# must not contain another element with the same tag name; a quoted title never needs one.
_QUOTED_ELEMENT = re.compile(
    r"<(?P<tag>[a-zA-Z][\w-]*)\b[^>]*\b"
    + re.escape(QUOTED["html_attribute"])
    + r'\s*=\s*"'
    + re.escape(QUOTED["html_value"])
    + r'"[^>]*>.*?</(?P=tag)\s*>',
    flags=re.IGNORECASE | re.DOTALL,
)


def strip_quoted(html: str) -> str:
    """Remove marked source-document titles before scanning for banned phrases."""
    return _QUOTED_ELEMENT.sub(" ", html)


def find_banned(text: str, *, allow: frozenset[str] = frozenset()) -> list[str]:
    """Return the banned phrases present in ``text``."""
    return [
        name
        for name, pattern in BANNED.items()
        if name not in allow and re.search(pattern, text, flags=re.IGNORECASE)
    ]


def check_text(text: str, *, field: str | None = None) -> list[str]:
    """Problems with one text field of a record (a description, a note, a plain reading).

    The ``source_doc_title`` field is the one place an official title may carry a
    banned word, so it is not scanned.
    """
    if field == QUOTED["text_field"]:
        return []
    return [f"banned phrase: {p}" for p in find_banned(text)]


def check_page(text: str, kind: PageKind) -> list[str]:
    """Problems with a rendered page; an empty list means it passes."""
    allow = ALLOWANCES.get(kind, frozenset())
    problems = [f"banned phrase: {p}" for p in find_banned(strip_quoted(text), allow=allow)]
    for pattern in REQUIRED.get(kind, []):
        if not re.search(pattern, text, flags=re.IGNORECASE):
            problems.append(f"missing required phrase: {pattern}")
    return problems

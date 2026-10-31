"""Evidence, size and colour labels for a check result, and its plain reading (ADR 0009).

Computed here, at publish time, so the website only displays them. Colour never carries
meaning alone: the website pairs each colour with an icon and the text label.
"""

from __future__ import annotations

import math
from typing import Literal

from methanewatch.config import Severity

Evidence = Literal["strong", "weak", "none"]
Size = Literal["slight", "moderate", "severe"]
Colour = Literal["red", "orange", "yellow", "green", "grey"]


def change_pct(effect: float | None) -> float | None:
    """A log effect as a percent change: (exp(effect) - 1) * 100."""
    if effect is None or (isinstance(effect, float) and math.isnan(effect)):
        return None
    return (math.exp(effect) - 1) * 100


def evidence(call: str) -> Evidence:
    """strong for a called drop or rise (ADR 0006), weak for inconclusive, none otherwise."""
    if call in ("drop", "rise"):
        return "strong"
    if call == "inconclusive":
        return "weak"
    return "none"


def size(effect_med: float | None, severity: Severity) -> Size | None:
    """Size of the change on the log scale: a rise to 2x and a drop to half are the same size."""
    if effect_med is None or (isinstance(effect_med, float) and math.isnan(effect_med)):
        return None
    magnitude = abs(effect_med)
    if magnitude < math.log(severity.slight_max_factor):
        return "slight"
    if magnitude < math.log(severity.moderate_max_factor):
        return "moderate"
    return "severe"


def colour(call: str, effect_med: float | None, sz: Size | None) -> Colour:
    """The owner's rule: red and orange only for strongly supported increases."""
    if call == "insufficient_data":
        return "grey"
    if call == "rise":
        return {"severe": "red", "moderate": "orange", "slight": "yellow"}[sz or "slight"]
    if call == "inconclusive" and effect_med is not None and effect_med > 0:
        return "yellow"
    return "green"


def plain_reading(
    call: str,
    change_med: float | None,
    change_lo: float | None,
    change_hi: float | None,
    mde_pct: float | None,
    reason: str | None = None,
) -> str:
    """One sentence a reader can take away, in the form agreed for the checks page."""
    if call == "insufficient_data" or change_med is None:
        why = f" ({reason})" if reason else ""
        return f"Not enough passes to test for a change after this record{why}."
    if change_med >= 1:
        verb = f"rose about {change_med:.0f}%"
    elif change_med <= -1:
        verb = f"fell about {-change_med:.0f}%"
    else:
        verb = "changed little"
    rng = f"90% range {_pct(change_lo)} to {_pct(change_hi)}"
    strength = {"strong": "strong evidence", "weak": "weak evidence"}[evidence(call)]
    if mde_pct is None:
        caught = "none of the tested drops could have been caught reliably"
    else:
        caught = f"this test could only have caught drops of {mde_pct:.0f}% or more"
    return f"Methane {verb} ({rng}) after this record; {strength}; {caught}."


def _pct(x: float | None) -> str:
    if x is None:
        return "?"
    return f"{x:+.0f}%"


def label_result(row: dict, severity: Severity) -> dict:
    """The labels and derived columns for one outcome row (``schemas.repair_outcomes``)."""
    call = row["call"]
    med, lo, hi = (change_pct(row.get(k)) for k in ("effect_med", "effect_lo", "effect_hi"))
    sz = size(row.get("effect_med"), severity)
    mde = row.get("mde_pct")
    mde = None if mde is None or (isinstance(mde, float) and math.isnan(mde)) else float(mde)
    return {
        "change_pct_med": med,
        "change_pct_lo": lo,
        "change_pct_hi": hi,
        "evidence": evidence(call),
        "size": sz,
        "colour": colour(call, row.get("effect_med"), sz),
        "plain_reading": plain_reading(call, med, lo, hi, mde, row.get("reason") or None),
    }

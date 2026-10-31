"""Evidence, size, colour and the plain reading (ADR 0009), table-driven."""

import math

import pytest

from methanewatch.config import Severity
from methanewatch.publish import labels

SEV = Severity()  # 1.33x and 2x, log scale


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        ("drop", "strong"),
        ("rise", "strong"),
        ("inconclusive", "weak"),
        ("insufficient_data", "none"),
    ],
)
def test_evidence_follows_the_call_rule(call, expected):
    assert labels.evidence(call) == expected


@pytest.mark.parametrize(
    ("effect", "expected"),
    [
        (0.0, "slight"),
        (math.log(1.2), "slight"),
        (-math.log(1.2), "slight"),
        (math.log(1.5), "moderate"),
        (-math.log(1.5), "moderate"),
        (math.log(2.0), "severe"),
        (math.log(3.0), "severe"),
        (-math.log(2.5), "severe"),
        (None, None),
        (float("nan"), None),
    ],
)
def test_size_is_symmetric_on_the_log_scale(effect, expected):
    assert labels.size(effect, SEV) == expected


@pytest.mark.parametrize(
    ("call", "effect", "expected"),
    [
        ("rise", math.log(3.0), "red"),
        ("rise", math.log(1.5), "orange"),
        ("rise", math.log(1.1), "yellow"),  # strong but slight increase: yellow (owner's choice)
        ("inconclusive", 0.2, "yellow"),  # any increase with weak evidence
        ("inconclusive", -0.2, "green"),
        ("inconclusive", 0.0, "green"),
        ("drop", -math.log(3.0), "green"),
        ("insufficient_data", None, "grey"),
    ],
)
def test_colour_rule(call, effect, expected):
    assert labels.colour(call, effect, labels.size(effect, SEV)) == expected


def test_change_pct_is_exp_minus_one():
    assert labels.change_pct(0.0) == 0
    assert labels.change_pct(math.log(2)) == pytest.approx(100)
    assert labels.change_pct(math.log(0.5)) == pytest.approx(-50)
    assert labels.change_pct(None) is None


def test_plain_reading_forms():
    rose = labels.plain_reading("inconclusive", 12.7, -33.6, 87.8, 75.0)
    assert rose == (
        "Methane rose about 13% (90% range -34% to +88%) after this record; weak evidence; "
        "this test could only have caught drops of 75% or more."
    )
    fell = labels.plain_reading("drop", -60.0, -80.0, -30.0, 50.0)
    assert fell.startswith(
        "Methane fell about 60% (90% range -80% to -30%) after this record; strong evidence;"
    )
    little = labels.plain_reading("inconclusive", 0.4, -20.0, 25.0, None)
    assert little.startswith("Methane changed little (90% range -20% to +25%)")
    assert little.endswith("none of the tested drops could have been caught reliably.")
    none = labels.plain_reading(
        "insufficient_data", None, None, None, None, "fewer than 5 overpasses in a window"
    )
    assert none == (
        "Not enough passes to test for a change after this record "
        "(fewer than 5 overpasses in a window)."
    )


def test_label_result_builds_every_column():
    row = {
        "call": "rise",
        "effect_med": math.log(1.5),
        "effect_lo": 0.1,
        "effect_hi": 0.9,
        "mde_pct": 50.0,
        "reason": "",
    }
    out = labels.label_result(row, SEV)
    assert out["evidence"] == "strong" and out["size"] == "moderate" and out["colour"] == "orange"
    assert out["change_pct_med"] == pytest.approx(50)
    assert out["plain_reading"].startswith("Methane rose about 50%")
    thin = labels.label_result(
        {"call": "insufficient_data", "effect_med": None, "mde_pct": float("nan"), "reason": "x"},
        SEV,
    )
    assert thin["colour"] == "grey" and thin["size"] is None and thin["change_pct_med"] is None

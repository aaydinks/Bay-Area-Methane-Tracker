"""Which old publications may be removed (ADR 0021). The rule is pure; the database side is
in tests/db/test_publish_prune.py."""

from datetime import UTC, datetime, timedelta

import pytest

from methanewatch.publish.load import prunable

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def _pubs(spec: str) -> list[dict]:
    """One letter per publication, oldest first: p public, r review, d draft."""
    names = {"p": "public", "r": "review", "d": "draft"}
    return [
        {"publish_id": f"pub-{i:02d}", "visibility": names[c], "created_at": T0 + timedelta(days=i)}
        for i, c in enumerate(spec)
    ]


def _ids(rows: list[dict]) -> list[str]:
    return [r["publish_id"] for r in rows]


def test_public_copies_and_the_newest_of_each_kind_stay():
    pubs = _pubs("rprrdrdd")
    out = prunable(pubs, keep_review=2, keep_draft=1)
    # review copies 00 and 02 are older than the two newest (03, 05); drafts 04 and 06 are
    # older than the newest (07); the public copy 01 is never chosen
    assert _ids(out) == ["pub-00", "pub-02", "pub-04", "pub-06"]
    assert all(p["visibility"] != "public" for p in out)


def test_nothing_to_remove_when_within_the_limits():
    assert prunable(_pubs("prrd"), keep_review=8, keep_draft=2) == []
    assert prunable([], keep_review=1, keep_draft=0) == []


def test_every_public_copy_stays_however_old():
    assert prunable(_pubs("ppppr"), keep_review=1, keep_draft=0) == []


def test_the_newest_review_copy_cannot_be_given_up():
    with pytest.raises(ValueError, match="at least 1"):
        prunable(_pubs("rr"), keep_review=0)
    with pytest.raises(ValueError, match="negative"):
        prunable(_pubs("dd"), keep_draft=-1)


def test_order_of_the_input_does_not_matter():
    pubs = _pubs("rrrr")
    assert _ids(prunable(pubs[::-1], keep_review=1)) == ["pub-00", "pub-01", "pub-02"]

import json
from pathlib import Path

import pytest

from methanewatch import population
from methanewatch.report import lint
from methanewatch.report.lint import check_page, check_text, find_banned, strip_quoted

TEMPLATES = Path(__file__).parents[1] / "src/methanewatch/report/templates"
WORDING = Path(__file__).parents[1] / "config/wording.json"


def test_banned_phrases_are_caught():
    text = "Real-time monitoring found a violation; the fix saved 40 t."
    assert set(find_banned(text)) == {"real-time", "violation", "saved"}


def test_saved_is_allowed_only_on_verified_drop_pages():
    text = "Retrospective screening indication: a verified drop saved 40 t (90% interval)."
    assert check_page(text, "verified-drop") == []
    assert "banned phrase: saved" in check_page(text, "site")


def test_required_phrases():
    assert check_page("Retrospective tracker. Screening indication only.", "index") == []
    assert check_page("Estimates by site.", "index") != []


def test_base_template_passes_lint():
    text = (TEMPLATES / "base.html.j2").read_text()
    assert check_page(text, "index") == []


def test_word_list_is_the_shared_file():
    data = json.loads(WORDING.read_text())
    assert set(data["banned"]) == {
        "saved",
        "real-time",
        "violation",
        "non-compliant",
        "illegal",
        "lives",
        "health impact",
    }
    assert {name: entry["pattern"] for name, entry in data["banned"].items()} == lint.BANNED
    assert data["required"] == lint.REQUIRED
    assert {"verified-drop": frozenset({"saved"})} == lint.ALLOWANCES


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("fourteen violations in June", "violation"),
        ("a history of non compliance", "non-compliant"),
        ("non-compliant with Rule 8-34", "non-compliant"),
        ("real time alerts", "real-time"),
        ("health outcomes nearby", "health impact"),
        ("health effect on residents", "health impact"),
        ("operated illegally", "illegal"),
        ("puts lives at risk", "lives"),
    ],
)
def test_each_pattern_matches_its_variants(text, name):
    assert find_banned(text) == [name]


def test_patterns_are_plain_enough_for_javascript():
    for pattern in lint.BANNED.values():
        for python_only in ("(?P<", "(?i)", "\\A", "\\Z", "(?#"):
            assert python_only not in pattern


def test_quoted_source_title_is_the_only_exception():
    quoted = (
        "<p>Screening indication. Source: "
        '<cite data-wording="source-title">Notice of Violation A12345</cite>.</p>'
    )
    assert check_page(quoted, "site") == []
    unquoted = "<p>Screening indication. Source: <cite>Notice of Violation A12345</cite>.</p>"
    assert check_page(unquoted, "site") == ["banned phrase: violation"]
    assert "Violation" not in strip_quoted(quoted)


def test_quoted_title_does_not_hide_the_rest_of_the_page():
    text = (
        '<p>Screening indication. <q data-wording="source-title">Notice of Violation</q> '
        "and a second violation outside the quote.</p>"
    )
    assert check_page(text, "site") == ["banned phrase: violation"]


def test_check_text_exempts_only_the_title_field():
    assert check_text("Notice of Violation A12345", field="source_doc_title") == []
    assert check_text("Notice of Violation A12345", field="description") == [
        "banned phrase: violation"
    ]
    assert check_text("Notice of Violation A12345") == ["banned phrase: violation"]
    assert check_text("Cover repaired on the north slope.") == []


@pytest.mark.parametrize("kind", ["home", "index", "briefing"])
def test_pages_that_need_the_retrospective_framing(kind):
    assert check_page("Retrospective tracker. Screening indication only.", kind) == []
    assert check_page("Screening indication only.", kind) == [
        "missing required phrase: retrospective"
    ]


@pytest.mark.parametrize(
    "kind", ["site", "map", "checks", "updates", "sites", "methods", "how-to-read", "data"]
)
def test_every_website_page_needs_the_screening_phrase(kind):
    assert check_page("A screening indication for investigation.", kind) == []
    assert check_page("Results by site.", kind) == ["missing required phrase: screening indication"]


def test_population_label_passes_the_check():
    assert find_banned(population.LABEL) == []
    assert check_text(population.LABEL) == []

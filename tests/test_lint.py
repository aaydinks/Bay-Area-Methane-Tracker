from pathlib import Path

from methanewatch.report.lint import check_page, find_banned

TEMPLATES = Path(__file__).parents[1] / "src/methanewatch/report/templates"


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

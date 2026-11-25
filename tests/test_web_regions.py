"""The website's region and air district names must be the ones the project's data gives."""

import json
import re
from pathlib import Path

from methanewatch import config

WEB_CONFIG = Path(__file__).resolve().parents[1] / "web" / "src" / "config.ts"


def _web_regions() -> dict[str, str]:
    text = WEB_CONFIG.read_text()
    block = re.search(r"export const REGION: Record<string, string> = \{(.*?)\n\};", text, re.S)
    assert block, "web/src/config.ts no longer defines REGION"
    return dict(re.findall(r"'([\w-]+)':\s*'([^']+)'", block.group(1)))


def test_the_website_names_every_region_as_the_project_config_does():
    regions = config.load_project().regions
    assert _web_regions() == {r.id: r.label for r in regions}


def test_the_website_lists_regions_in_the_config_order():
    regions = config.load_project().regions
    assert list(_web_regions()) == [r.id for r in regions]


def _web_districts() -> dict[str, str]:
    text = WEB_CONFIG.read_text()
    block = re.search(
        r"export const AIR_DISTRICT: Record<string, string> = \{(.*?)\n\};", text, re.S
    )
    assert block, "web/src/config.ts no longer defines AIR_DISTRICT"
    return dict(re.findall(r"'([^']+)':\s*'([^']+)'", block.group(1)))


def test_the_website_keys_air_districts_by_the_names_in_the_district_outlines():
    """A site carries CARB's outline name for its district; a label keyed by any other name
    would never be used."""
    outlines = WEB_CONFIG.parents[2] / "datasets" / "boundaries" / "air_districts.geojson"
    known = {f["properties"]["NAME"] for f in json.loads(outlines.read_text())["features"]}
    labels = _web_districts()
    assert labels and set(labels) <= known


def test_the_website_knows_the_region_terms_by_the_pipeline_names():
    """The methods page says a screening fit lets the regions differ when its manifest lists a
    region term; a term under another name would go unnoticed."""
    from methanewatch import features

    text = (WEB_CONFIG.parent / "lib" / "data.ts").read_text()
    block = re.search(r"const REGION_TERMS = \[(.*?)\];", text)
    assert block, "web/src/lib/data.ts no longer defines REGION_TERMS"
    assert set(re.findall(r"'(\w+)'", block.group(1))) == set(features.REGION_TERMS)

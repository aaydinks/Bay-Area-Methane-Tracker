"""The website's region names must be the ones config/project.yaml gives."""

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

"""Sentinel-2 scene search and cloud filtering (PLAN section 5, phase 3)."""

from __future__ import annotations

from datetime import date


def search_scenes(site_id: str, start: date, end: date, max_cloud: float = 0.3) -> list[dict]:
    raise NotImplementedError("S2 STAC search: week 3")

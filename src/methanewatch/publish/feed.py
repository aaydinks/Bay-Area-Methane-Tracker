"""What changed since the previous publication: the latest-update feed.

The feed is a difference of two snapshots. Rows are written to ``update_log`` and the new
plumes are flagged ``new_in_update``. Everything here is a count or an id, never a figure.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def _ids(df: pd.DataFrame | None, cols: list[str]) -> set[tuple]:
    if df is None or not len(df):
        return set()
    return set(map(tuple, df[cols].astype(str).to_numpy()))


def update_items(
    current: dict[str, pd.DataFrame],
    previous: dict[str, pd.DataFrame] | None,
    *,
    current_runs: dict[str, str | None],
    previous_runs: dict[str, str | None] | None,
    site_names: dict[str, str] | None = None,
    today: date | None = None,
) -> tuple[list[dict], set[tuple[str, str]]]:
    """Feed rows and the (source, plume_id) pairs that are new."""
    previous = previous or {}
    previous_runs = previous_runs or {}
    names = site_names or {}
    today = today or date.today()
    items: list[dict] = []

    def add(
        kind: str, text: str, *, site_id: str | None = None, count: int | None = None, when=None
    ):
        items.append(
            {
                "item_order": len(items) + 1,
                "kind": kind,
                "site_id": site_id,
                "event_date": pd.Timestamp(when) if when is not None else pd.Timestamp(today),
                "count": count,
                "text": text,
            }
        )

    plumes = current.get("plumes")
    new_plumes = _ids(plumes, ["source", "plume_id"]) - _ids(
        previous.get("plumes"), ["source", "plume_id"]
    )
    if plumes is not None and new_plumes:
        key = list(zip(plumes["source"].astype(str), plumes["plume_id"].astype(str), strict=True))
        is_new = pd.Series([k in new_plumes for k in key], index=plumes.index)
        for site_id, grp in plumes[is_new & plumes["site_id"].notna()].groupby("site_id"):
            n = len(grp)
            add(
                "new-plumes",
                f"{n} new plume{'s' if n != 1 else ''} near {names.get(site_id, site_id)}.",
                site_id=site_id,
                count=n,
                when=grp["acquired_utc"].max(),
            )
    checks = current.get("checks")
    new_checks = _ids(checks, ["check_id"]) - _ids(previous.get("checks"), ["check_id"])
    if checks is not None and new_checks:
        for site_id, grp in checks[
            checks["check_id"].astype(str).isin({c[0] for c in new_checks})
        ].groupby("site_id"):
            n = len(grp)
            add(
                "new-record",
                f"{n} new dated record{'s' if n != 1 else ''} for {names.get(site_id, site_id)}.",
                site_id=site_id,
                count=n,
                when=pd.to_datetime(grp["date_start"]).max(),
            )
    if current_runs.get("model_run_id") and current_runs.get("model_run_id") != previous_runs.get(
        "model_run_id"
    ):
        add("new-model-run", "New model run: persistence estimates were refitted.")
    if current_runs.get("check_run_id") and current_runs.get("check_run_id") != previous_runs.get(
        "check_run_id"
    ):
        add("new-check-run", "New before/after test run over the dated checks.")
    gates = current.get("validation_results")
    new_gates = _ids(gates, ["report_id"]) - _ids(previous.get("validation_results"), ["report_id"])
    if gates is not None and new_gates:
        for r in gates[gates["report_id"].astype(str).isin({g[0] for g in new_gates})].itertuples():
            add(
                "gate-result",
                f"Method check {r.gate}: {r.result} ({r.run_id}).",
                when=pd.to_datetime(r.created_at) if r.created_at else None,
            )
    sites = current.get("sites")
    prev_sites = previous.get("sites")
    if sites is not None and prev_sites is not None and len(prev_sites):
        before = prev_sites.set_index("site_id")["polygon_source"].astype(str)
        for r in sites.itertuples():
            if r.site_id in before.index and str(r.polygon_source) != before[r.site_id]:
                add(
                    "outline-change",
                    f"The outline of {names.get(r.site_id, r.site_id)} was updated.",
                    site_id=r.site_id,
                )
    return items, new_plumes

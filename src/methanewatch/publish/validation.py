"""Read the method checks in ``reports/validation`` into rows for the website.

The reports are Markdown written by ``mw validate``; the numbers are read from their text and
their embedded run manifest, never typed in by hand.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

GATE_BY_FOLDER = {"synthetic": "gate3", "holdout": "holdout"}


def _manifest(text: str) -> dict:
    m = re.search(r"```json\n(\{.*?\n\})\n```", text, re.S)
    return json.loads(m.group(1)) if m else {}


def _title_run_id(text: str) -> str | None:
    m = re.search(r"\(([\w-]+)\)\s*$", text.splitlines()[0])
    return m.group(1) if m else None


def _result(text: str) -> str:
    m = re.search(r"\*\*Result: (PASS|FAIL)\*\*", text)
    return m.group(1).lower() if m else "dry-run"


def _coverage(text: str) -> dict:
    out = {}
    for name, key in (("f", "coverage_f"), ("qbar", "coverage_qbar"), ("E_t_yr", "coverage_e")):
        m = re.search(
            rf"^\| {re.escape(name)} \| ([0-9.]+) \| ([0-9.]+) to ([0-9.]+) \|", text, re.M
        )
        if m:
            out[key] = float(m.group(1))
            out[f"{key}_wilson"] = [float(m.group(2)), float(m.group(3))]
    m = re.search(r"Fits failing diagnostics[^:]*: ([0-9.]+)%", text)
    if m:
        out["diag_fail_frac"] = float(m.group(1)) / 100
    m = re.search(r"(\d+) replicates x (\d+) sites", text)
    if m:
        out["replicates"], out["sites"] = int(m.group(1)), int(m.group(2))
    covs = re.search(r"Site covariates: ([^(\n]+?)\s*(\(|\.?$)", text, re.M)
    if covs and covs.group(1).strip(" .") != "none":
        out["covariates"] = [c.strip() for c in covs.group(1).strip(" .").split(",")]
    return out


def _holdout(text: str) -> dict:
    out = {}
    m = re.search(r"\*\*([0-9.]+)%\*\* of (\d+) site-folds \(target at least (\d+)%\)", text)
    if m:
        out["share_inside"] = float(m.group(1)) / 100
        out["folds"] = int(m.group(2))
        out["target"] = float(m.group(3)) / 100
    return out


def _placebo(text: str) -> dict:
    out = {}
    m = re.search(r"False-positive rate \(drop or rise\): \*\*([0-9.]+)\*\*", text)
    if m:
        out["false_positive_rate"] = float(m.group(1))
    m = re.search(r"95% Wilson interval: ([0-9.]+) to ([0-9.]+)", text)
    if m:
        out["wilson"] = [float(m.group(1)), float(m.group(2))]
    m = re.search(r"(\d+) usable fits, (\d+) insufficient", text)
    if m:
        out["fits"], out["insufficient"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"in (\d+) independent simulated worlds", text)
    if m:
        out["worlds"] = int(m.group(1))
    m = re.search(r"Gate 5 threshold: ([0-9.]+)", text)
    if m:
        out["threshold"] = float(m.group(1))
    m = re.search(r"drop if P\(decrease\) >= ([0-9.]+)", text)
    if m:
        out["call_probability"] = float(m.group(1))
    return out


def _power(text: str) -> dict:
    rows = re.findall(r"^\|\s+([0-9.]+) \|\s+[0-9.]+ \|\s+([0-9.]+) \|", text, re.M)
    out: dict = {"p_drop_by_factor": {f: float(p) for f, p in rows}, "target": 0.8}
    m = re.search(r"\*\*Minimum detectable effect \(80% power\):\*\* (.+)", text)
    if m:
        out["summary"] = m.group(1).strip()
    return out


def _triple(x: dict | None) -> list[float | None] | None:
    """{"value": v, "interval": [lo, hi]} as [v, lo, hi]."""
    if not x:
        return None
    lo, hi = x.get("interval") or [None, None]
    return [x.get("value"), lo, hi]


def _claim_metrics(block: dict, keys: tuple[str, ...], diff_keys: tuple[str, ...]) -> dict:
    out = {k: v for k, v in block.items() if k.startswith("n_")}
    out["rates"] = {m: {k: _triple(v.get(k)) for k in keys} for m, v in block["rates"].items()}
    out["comparisons"] = {
        m: {**{k: _triple(v.get(k)) for k in diff_keys}, "passed": v["passed"]}
        for m, v in block.get("comparisons", {}).items()
    }
    return out


BAY_AREA_COLUMNS = (
    "true_clear",
    "clear_model",
    "clear_sen2cor",
    "clear_s2cloudless",
    "clear_threshold",
    "tile_cloud_cover",
)


def _cloud_model_rows(md: Path, run_id: str, created: str | None) -> list[dict]:
    """Two rows from the Sentinel-2 cloud model's held-out test (ADR 0013), one per claim.

    The numbers come from the results file beside the report, never from its prose.
    """
    r = json.loads(md.with_suffix(".json").read_text())
    if r.get("rehearsal"):
        return []
    c1, c2 = r["claim1"], r["claim2"]
    m1 = _claim_metrics(
        c1["all_heldout"],
        ("false_usable", "false_unusable"),
        ("false_usable_diff", "false_unusable_diff"),
    )
    m1["west_coast"] = _claim_metrics(
        c1["west_coast"],
        ("false_usable", "false_unusable"),
        ("false_usable_diff", "false_unusable_diff"),
    )
    m1["band_means"] = r.get("band_means")
    # The held-out patches in the Bay Area: too few to test, listed one by one
    m1["bay_area"] = [
        {
            "site": p["roi_id"],
            "date": re.search(r"__(\d{8})T", p["sample_id"]).group(1),
            **{k: p.get(k) for k in BAY_AREA_COLUMNS},
        }
        for p in r.get("bay_area_patches", [])
    ]
    ref = c1["official_test_with_reference"]
    m1["reference"] = {
        "n_patches": ref["n_patches"],
        "rates": {
            m: {k: _triple(v.get(k)) for k in ("false_usable", "false_unusable")}
            for m, v in ref["rates"].items()
            if m in ("model", "unetmobv2_v2")
        },
    }
    m2 = _claim_metrics(
        c2["all_heldout"],
        ("cloud_caused_per_target", "detection_share"),
        ("cloud_caused_diff", "detection_share_diff"),
    )
    m2["amplitude"] = r["amplitude"]["amplitude"]
    ref2 = c2["official_test_with_reference"]
    m2["reference"] = {
        m: {k: _triple(v.get(k)) for k in ("cloud_caused_per_target", "detection_share")}
        for m, v in ref2["rates"].items()
        if m in ("model", "unetmobv2_v2")
    }
    common = {"run_id": run_id, "superseded": False, "created_at": created}
    return [
        {
            **common,
            "report_id": f"{run_id}-claim1",
            "gate": "s2_cloud_usable",
            "result": "pass" if c1["all_heldout"].get("passed") else "fail",
            "metrics": m1,
            "note": "Sentinel-2 cloud model, held-out test (ADR 0013): cloudy windows wrongly"
            " counted as usable.",
        },
        {
            **common,
            "report_id": f"{run_id}-claim2",
            "gate": "s2_cloud_detections",
            "result": "pass" if c2["all_heldout"].get("passed") else "fail",
            "metrics": m2,
            "note": "Sentinel-2 cloud model, held-out test (ADR 0013): false detections caused"
            " by clouds.",
        },
    ]


def validation_rows(reports_root: Path) -> list[dict]:
    """One row per method check (two for a repair dry run: placebo and power; two for the
    Sentinel-2 cloud model: one per pre-registered claim)."""
    rows = []
    for md in sorted((reports_root / "validation").glob("*/*.md")):
        text = md.read_text()
        folder = md.parent.name
        run_id = _title_run_id(text) or md.stem
        manifest = _manifest(text)
        created = manifest.get("created_at")
        if folder == "s2-cloud-model":
            rows.extend(_cloud_model_rows(md, run_id, created))
            continue
        if folder == "repair-synthetic":
            superseded = "Call rule:" not in text
            note = "Dry run on simulated data, not Gate 5."
            if superseded:
                note = "Earlier call rule (90% interval excludes 0); superseded by ADR 0006."
            rows.append(
                {
                    "report_id": f"{run_id}-placebo",
                    "gate": "placebo",
                    "run_id": run_id,
                    "result": "dry-run",
                    "metrics": _placebo(text),
                    "superseded": superseded,
                    "note": note,
                    "created_at": created,
                }
            )
            power = _power(text)
            if power["p_drop_by_factor"]:
                rows.append(
                    {
                        "report_id": f"{run_id}-power",
                        "gate": "power",
                        "run_id": run_id,
                        "result": "dry-run",
                        "metrics": power,
                        "superseded": superseded,
                        "note": power.get("summary", note),
                        "created_at": created,
                    }
                )
            continue
        gate = GATE_BY_FOLDER.get(folder, folder)
        metrics = (
            _coverage(text) if gate == "gate3" else _holdout(text) if gate == "holdout" else {}
        )
        if gate == "gate3":
            note = "Gate 3: 90% ranges contain the simulated truth 85 to 95% of the time."
            if metrics.get("covariates"):
                note = "Gate 3 with site covariates (ADR 0008)."
        elif gate == "holdout":
            note = "Dry run on simulated data, not Gate 4."
        else:
            note = text.splitlines()[0].lstrip("# ").strip()
        rows.append(
            {
                "report_id": run_id,
                "gate": gate,
                "run_id": run_id,
                "result": _result(text),
                "metrics": metrics,
                "superseded": False,
                "note": note,
                "created_at": created,
            }
        )
    return rows

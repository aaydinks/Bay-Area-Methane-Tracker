"""Static dashboard builder (docs/PLAN.md section 10).

Reads one model run from ``data/processed`` and writes plain HTML to
``reports/site``: an index ranking sites by annual emissions with 90%
intervals, one page per site, and a methods page summarizing the validation
reports. Every rendered page must pass ``report.lint``; the build fails
otherwise.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from methanewatch.config import ProjectConfig
from methanewatch.report.lint import check_page

TEMPLATES = Path(__file__).parent / "templates"
MISSING = chr(0x2013)  # en dash shown for missing values


class LintError(ValueError):
    pass


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["num"] = num
    return env


def num(x: float | None, digits: int = 3) -> str:
    """Round to ``digits`` significant figures, with thousands separators."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return MISSING
    if x == 0:
        return "0"
    places = digits - 1 - int(np.floor(np.log10(abs(x))))  # negative rounds to tens, hundreds
    return f"{round(x, places):,.{max(0, places)}f}"


def load_run(project: ProjectConfig, run_id: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    processed = project.resolve(project.paths.processed)
    est_path = processed / "site_estimates" / f"{run_id}.parquet"
    if not est_path.exists():
        raise FileNotFoundError(f"no run {run_id!r} in {processed / 'site_estimates'}")
    runs = processed / "runs"
    est = pd.read_parquet(est_path)
    det = pd.read_parquet(runs / f"{run_id}-detections.parquet")
    manifest = json.loads((runs / f"{run_id}.json").read_text())
    return est, det, manifest


def interval_chart(est: pd.DataFrame) -> dict:
    d = est.sort_values("E_t_yr_med", ascending=False)
    base = alt.Chart(d).encode(y=alt.Y("site_id:N", sort=None, title=None))
    rule = base.mark_rule(strokeWidth=2).encode(
        x=alt.X(
            "E_t_yr_lo:Q",
            scale=alt.Scale(type="log"),
            title="annual methane above the floor (t/yr), median and 90% interval",
        ),
        x2="E_t_yr_hi:Q",
    )
    point = base.mark_point(filled=True, size=60).encode(
        x="E_t_yr_med:Q",
        tooltip=[
            alt.Tooltip("site_id:N", title="site"),
            alt.Tooltip("E_t_yr_med:Q", title="median t/yr", format=",.0f"),
            alt.Tooltip("E_t_yr_lo:Q", title="5th percentile", format=",.0f"),
            alt.Tooltip("E_t_yr_hi:Q", title="95th percentile", format=",.0f"),
        ],
    )
    return (rule + point).properties(width="container", height=28 * max(len(d), 3)).to_dict()


TIMELINE_WIDTH = 820


def timeline_chart(det: pd.DataFrame) -> dict:
    """Detections with rates above, every overpass with nothing seen below, on one time axis."""
    d = det.assign(
        acquired_utc=pd.to_datetime(det["acquired_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    hits, misses = d[d["detected"]], d[~d["detected"]]
    x = alt.X("acquired_utc:T", title=None)
    color = alt.Color("instrument:N", legend=alt.Legend(orient="bottom", title=None))
    ticks = (
        alt.Chart(misses)
        .mark_tick(thickness=1, opacity=0.6)
        .encode(x=x, y=alt.Y("instrument:N", title="no plume seen"), color=color)
        .properties(width=TIMELINE_WIDTH, height=90)
    )
    if hits.empty:
        return ticks.to_dict()
    pts = (
        alt.Chart(hits)
        .mark_point(filled=True, size=50)
        .encode(
            x=x,
            y=alt.Y("q_obs_kg_hr:Q", scale=alt.Scale(type="log"), title="reported rate (kg/hr)"),
            color=color,
            tooltip=[
                alt.Tooltip("acquired_utc:T", title="date"),
                "instrument:N",
                alt.Tooltip("q_obs_kg_hr:Q", title="kg/hr", format=",.0f"),
            ],
        )
        .properties(width=TIMELINE_WIDTH, height=220)
    )
    return alt.vconcat(pts, ticks).resolve_scale(x="shared", color="shared").to_dict()


def validation_summaries(reports_root: Path) -> list[dict]:
    out = []
    for md in sorted((reports_root / "validation").glob("*/*.md")):
        text = md.read_text()
        title = text.splitlines()[0].lstrip("# ").strip()
        result = re.search(r"\*\*Result: (PASS|FAIL)\*\*", text)
        fpr = re.search(r"False-positive rate \(drop or rise\): \*\*([0-9.]+)\*\*", text)
        summary = result.group(1) if result else (f"placebo FPR {fpr.group(1)}" if fpr else "")
        out.append({"title": title, "path": f"{md.parent.name}/{md.name}", "result": summary})
    return out


def render_pages(project: ProjectConfig, run_id: str, out_dir: Path) -> dict[Path, tuple[str, str]]:
    """HTML for every page, keyed by output path, with the lint kind for each."""
    est, det, manifest = load_run(project, run_id)
    env = _env()
    is_demo = manifest.get("kind") == "synthetic-demo"
    common = {
        "run_id": run_id,
        "is_demo": is_demo,
        "provisional": manifest.get("provisional", False),
        "git_sha": (manifest.get("git_sha") or "")[:7],
        "created_at": manifest.get("created_at", "")[:10],
    }

    ops_path = project.resolve(project.paths.interim) / "operator_reports.parquet"
    ops = pd.read_parquet(ops_path) if (ops_path.exists() and not is_demo) else None
    latest_ops: dict[str, dict] = {}
    if ops is not None and len(ops):
        last = ops.sort_values("year").groupby("site_id").tail(1)
        latest_ops = {
            r.site_id: {"year": int(r.year), "ch4_t": float(r.reported_ch4_t)}
            for r in last.itertuples()
        }

    ranked = est[est["status"] != "insufficient_data"].sort_values("E_t_yr_med", ascending=False)
    thin = est[est["status"] == "insufficient_data"]
    pages: dict[Path, tuple[str, str]] = {
        out_dir / "index.html": (
            env.get_template("index.html.j2").render(
                **common,
                prefix="",
                ranked=ranked.to_dict("records"),
                thin=thin.to_dict("records"),
                latest_ops=latest_ops,
                chart=json.dumps(interval_chart(ranked)) if len(ranked) else None,
            ),
            "index",
        )
    }
    for row in est.to_dict("records"):
        site = row["site_id"]
        sdet = det[det["site_id"] == site]
        counts = (
            sdet.groupby("instrument")
            .agg(overpasses=("detected", "size"), detections=("detected", "sum"))
            .reset_index()
            .to_dict("records")
        )
        site_ops = (
            ops[ops["site_id"] == site].sort_values("year").to_dict("records")
            if ops is not None
            else []
        )
        pages[out_dir / "sites" / f"{site}.html"] = (
            env.get_template("site.html.j2").render(
                **common,
                prefix="../",
                row=row,
                counts=counts,
                ops=site_ops,
                truth=manifest.get("truth_E_t_yr", {}).get(site) if is_demo else None,
                chart=json.dumps(timeline_chart(sdet)),
            ),
            "site",
        )
    pages[out_dir / "methods.html"] = (
        env.get_template("methods.html.j2").render(
            **common,
            prefix="",
            validations=validation_summaries(project.resolve(project.paths.reports)),
            manifest=json.dumps(manifest, indent=2, default=str),
        ),
        "index",
    )
    return pages


def build_site(project: ProjectConfig, run_id: str, out_dir: Path) -> Path:
    pages = render_pages(project, run_id, out_dir)
    problems = {p: check_page(html, kind) for p, (html, kind) in pages.items()}
    problems = {p: v for p, v in problems.items() if v}
    if problems:
        detail = "; ".join(f"{p.name}: {', '.join(v)}" for p, v in problems.items())
        raise LintError(f"report wording check failed: {detail}")
    for path, (html, _) in pages.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
    return out_dir / "index.html"

"""The ADR 0014 transfer check: does the cloud model behave on 2025 pilot passes as it did on
the 2017 to 2020 test images?

There are no labels for the pilot passes, so this is not a second held-out test. Its
yardsticks, fixed in ADR 0014 before the run:

1. reflectance scale: Sen2Cor water pixels on clear windows have band 12 near 0;
2. P(model unusable | Sen2Cor >= 0.99 clear) at most R1 + 10 points;
3. P(model usable | Sen2Cor < 0.3 clear) at most R2 + 10 points;
4. mean (model - Sen2Cor) clear share differs by at most 0.05 between Sentinel-2C and 2A/2B;
5. no fixed false clouds: few pixels flagged on more than 20% of Sen2Cor-clear days;
6. a blind look by eye at a random draw of agreements and disagreements.

Intervals resample acquisition days (the five sites on one day share the weather).
``run`` computes 1 to 5 and draws the thumbnails; ``finish`` reads the labels made by eye,
opens the key and writes the verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio import features as rfeatures
from rasterio.transform import from_origin

from methanewatch import provenance
from methanewatch.config import REPO_ROOT
from methanewatch.sentinel2 import sitecloud as sc
from methanewatch.sentinel2.cloudmodel import BANDS, CLEAR, MODEL_DIR, CloudModel

YEAR = 2025
USABLE = 0.7  # min_valid_frac
SCL_CLEAR = 0.99
SCL_CLOUDY = 0.3
R1, R2 = 0.058, 0.087  # held-out reference rates (ADR 0014)
TOLERANCE = 0.10
WATER_B12 = (-0.02, 0.03)
MAX_PLATFORM_GAP = 0.05
HOTSPOT_DAYS = 0.2
MAX_HOTSPOT_AREA = 0.01
MAX_HOTSPOT_SITE = 0.05
EYE_DRAW = {"model_only": 8, "scl_only": 8, "both_usable": 4, "both_unusable": 4}
N_BOOT = 2000
SEED = 20261031
SCL_WATER = 6
RESULTS_DIR = REPO_ROOT / "reports" / "validation" / "s2-cloud-recent"


def _boot_weights(n_days: int, rng: np.random.Generator) -> np.ndarray:
    return rng.multinomial(n_days, np.full(n_days, 1 / n_days), size=N_BOOT).astype(float)


def day_rate(df: pd.DataFrame, event: str, given: str, seed: int = SEED) -> dict:
    """P(event | given) with a 90% interval from resampling days."""
    d = df.assign(e=df[event] & df[given], g=df[given]).groupby("day")[["e", "g"]].sum()
    d = d[d["g"] > 0]
    if d.empty:
        return {"value": None, "interval": [None, None], "n_windows": 0, "n_days": 0}
    w = _boot_weights(len(d), np.random.default_rng(seed))
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = (w @ d["e"].to_numpy()) / (w @ d["g"].to_numpy())
    return {
        "value": float(d["e"].sum() / d["g"].sum()),
        "interval": np.nanpercentile(boot, [5, 95]).tolist(),
        "n_windows": int(d["g"].sum()),
        "n_days": len(d),
    }


def platform_gap(df: pd.DataFrame, seed: int = SEED) -> dict:
    """Mean (model - Sen2Cor) clear share on Sentinel-2C minus that on 2A and 2B."""
    df = df.assign(diff=df["clear_model"] - df["clear_scl"], c=df["platform"] == "sentinel-2c")
    g = df.groupby("day").agg(
        sc=("diff", lambda s: s[df.loc[s.index, "c"]].sum()),
        nc=("c", "sum"),
        sab=("diff", lambda s: s[~df.loc[s.index, "c"]].sum()),
        nab=("c", lambda s: (~s).sum()),
    )
    w = _boot_weights(len(g), np.random.default_rng(seed))
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = (w @ g["sc"].to_numpy()) / (w @ g["nc"].to_numpy())
        boot -= (w @ g["sab"].to_numpy()) / (w @ g["nab"].to_numpy())
    c, ab = df[df["c"]], df[~df["c"]]
    return {
        "value": float(c["diff"].mean() - ab["diff"].mean()),
        "interval": np.nanpercentile(boot, [5, 95]).tolist(),
        "mean_diff_s2c": float(c["diff"].mean()),
        "mean_diff_s2ab": float(ab["diff"].mean()),
        "n_s2c": len(c),
        "n_s2ab": len(ab),
    }


def _canvas(x: float, y: float) -> tuple[float, float, int]:
    """A per-site 20 m grid a few pixels larger than any window around (x, y)."""
    margin = 4
    n = sc.WINDOW_PX + 2 * margin
    left = np.floor((x - sc.WINDOW_M / 2) / sc.RES_M) * sc.RES_M - margin * sc.RES_M
    top = np.ceil((y + sc.WINDOW_M / 2) / sc.RES_M) * sc.RES_M + margin * sc.RES_M
    return float(left), float(top), n


def hotspots(
    windows: pd.DataFrame, classes: dict[str, np.ndarray], sites: gpd.GeoDataFrame
) -> tuple[dict, dict[str, np.ndarray]]:
    """Per pixel, the share of Sen2Cor-clear days on which the model says cloud or shadow."""
    clear = windows[windows["scored"] & (windows["clear_scl"] >= SCL_CLEAR)]
    polys = sites.to_crs(sc.METRIC_CRS).set_index("site_id").geometry
    rs, cs = sc.scored_slice()
    out, maps = {}, {}
    for site, g in clear.groupby("site_id"):
        left, top, n = _canvas(g["x"].iloc[0], g["y"].iloc[0])
        obs = np.zeros((n, n))
        flag = np.zeros((n, n))
        for r in g.itertuples():
            valid = sc.Window13.load(Path(r.file)).valid
            dx = round((r.window_left - left) / sc.RES_M)
            dy = round((top - r.window_top) / sc.RES_M)
            sub = (slice(dy + rs.start, dy + rs.stop), slice(dx + cs.start, dx + cs.stop))
            ok = valid[rs, cs]
            obs[sub] += ok
            flag[sub] += ok & (classes[r.overpass_id][rs, cs] != CLEAR)
        seen = obs >= 0.5 * len(g)
        with np.errstate(invalid="ignore", divide="ignore"):
            share = np.where(seen, flag / obs, np.nan)
        transform = from_origin(left, top, sc.RES_M, sc.RES_M)
        in_site = rfeatures.geometry_mask(
            [polys[site]], out_shape=(n, n), transform=transform, invert=True
        )
        hot = seen & (share > HOTSPOT_DAYS)
        out[site] = {
            "n_clear_days": len(g),
            "area_share_flagged": float(hot.sum() / seen.sum()),
            "site_share_flagged": float(hot[in_site & seen].sum() / max((in_site & seen).sum(), 1)),
            "median_flag_share": float(np.nanmedian(share)),
            "passed": bool(
                hot.sum() / seen.sum() <= MAX_HOTSPOT_AREA
                and hot[in_site & seen].sum() / max((in_site & seen).sum(), 1) <= MAX_HOTSPOT_SITE
            ),
        }
        maps[site] = share
    return out, maps


def scale_check(windows: pd.DataFrame) -> dict:
    """Band 12 of Sen2Cor water on clear windows, and mean bands of other clear pixels."""
    clear = windows[windows["scored"] & (windows["clear_scl"] >= SCL_CLEAR)]
    rs, cs = sc.scored_slice()
    water, land_sum, land_n = [], np.zeros(len(BANDS)), 0
    for r in clear.itertuples():
        w = sc.Window13.load(Path(r.file))
        refl = sc.reflectance(w.dn, w.valid, w.consts)[:, rs, cs]
        scl = w.scl[rs, cs]
        ok = w.valid[rs, cs]
        water.append(refl[BANDS.index("B12")][ok & (scl == SCL_WATER)])
        land = ok & np.isin(scl, [4, 5])  # vegetation, bare soil
        land_sum += np.nansum(refl[:, land], axis=1)
        land_n += int(land.sum())
    water = np.concatenate(water) if water else np.array([])
    med = float(np.median(water)) if water.size else None
    return {
        "water_b12_median": med,
        "water_b12_p05_p95": np.percentile(water, [5, 95]).tolist() if water.size else None,
        "water_pixels": int(water.size),
        "limits": list(WATER_B12),
        "passed": med is not None and WATER_B12[0] <= med <= WATER_B12[1],
        "land_band_means": dict(zip(BANDS, (land_sum / max(land_n, 1)).round(4), strict=True)),
        "land_pixels": land_n,
    }


def eye_draw(windows: pd.DataFrame) -> pd.DataFrame:
    """The ADR 0014 random draw, shuffled and numbered."""
    w = windows[windows["scored"] & windows["clear_scl"].notna()]
    m, s = w["clear_model"] >= USABLE, w["clear_scl"] >= USABLE
    groups = {
        "model_only": w[m & ~s],
        "scl_only": w[~m & s],
        "both_usable": w[m & s],
        "both_unusable": w[~m & ~s],
    }
    rng = np.random.default_rng(SEED)
    picks = []
    for name, g in groups.items():
        k = min(EYE_DRAW[name], len(g))
        idx = rng.choice(len(g), k, replace=False) if k else []
        picks.append(g.iloc[sorted(idx)].assign(group=name))
    draw = pd.concat(picks, ignore_index=True)
    draw = draw.iloc[rng.permutation(len(draw))].reset_index(drop=True)
    draw["thumb"] = np.arange(1, len(draw) + 1)
    return draw


def true_colour(w: sc.Window13) -> np.ndarray:
    """Bands 4, 3, 2 on a fixed 0 to 0.3 stretch, no data black."""
    r = sc.reflectance(w.dn, w.valid, w.consts)[[BANDS.index(b) for b in ("B04", "B03", "B02")]]
    rgb = np.clip(np.nan_to_num(r, nan=0.0) / 0.3, 0, 1)
    return np.moveaxis(rgb, 0, -1)


def thumbnail_sheets(draw: pd.DataFrame, out_dir: Path, per_sheet: int = 12) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    rs, _ = sc.scored_slice()
    paths = []
    for k in range(0, len(draw), per_sheet):
        part = draw.iloc[k : k + per_sheet]
        fig, axes = plt.subplots(3, 4, figsize=(12, 9.6), dpi=110)
        for ax in axes.ravel():
            ax.axis("off")
        for ax, r in zip(axes.ravel(), part.itertuples(), strict=False):
            ax.imshow(true_colour(sc.Window13.load(Path(r.file))), interpolation="nearest")
            box = Rectangle((rs.start - 0.5, rs.start - 0.5), sc.SCORE_PX, sc.SCORE_PX)
            box.set(fill=False, edgecolor="#ffd400", linewidth=1)
            ax.add_patch(box)
            ax.set_title(f"{r.thumb:02d}", fontsize=12)
        fig.suptitle("Sentinel-2 true colour (B4, B3, B2; 0 to 0.3 reflectance). Box: scored 5 km")
        fig.tight_layout()
        p = out_dir / f"eye-sheet-{k // per_sheet + 1}.png"
        fig.savefig(p)
        plt.close(fig)
        paths.append(p)
    return paths


def hotspot_figure(maps: dict[str, np.ndarray], out: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(maps), figsize=(3.2 * len(maps), 3.6), dpi=110)
    for ax, (site, m) in zip(np.atleast_1d(axes), sorted(maps.items()), strict=True):
        im = ax.imshow(m, vmin=0, vmax=0.5, cmap="magma", interpolation="nearest")
        ax.set_title(site, fontsize=10)
        ax.axis("off")
    fig.colorbar(im, ax=axes, shrink=0.8, label="share of Sen2Cor-clear days flagged by model")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def _inputs(data_root: Path) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    interim = data_root / "data" / "interim"
    ov = pd.read_parquet(interim / "overpasses.parquet")
    year = pd.to_datetime(ov["acquired_utc"], utc=True).dt.year
    fp = gpd.read_parquet(interim / "footprints" / "sentinel2.parquet")
    sites = gpd.read_parquet(interim / "sites.parquet")
    return sc.pass_table(ov[year == YEAR], fp, sites), sites


def _key_dir(data_root: Path) -> Path:
    """Where the eye-check key waits, unread, until the labels are in (git-ignored)."""
    return data_root / "data" / "processed" / "s2cloud" / "recent"


def _criterion(x: dict, limit: float) -> dict:
    return {**x, "limit": limit, "passed": x["value"] is not None and x["value"] <= limit}


def run(data_root: Path = REPO_ROOT, model_path: Path | None = None, workers: int = 6) -> Path:
    """Criteria 1 to 5 and the blind thumbnails. Refuses to run twice (ADR 0014)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if any(RESULTS_DIR.glob("*.json")):
        raise FileExistsError(f"a result already exists in {RESULTS_DIR}; ADR 0014 runs once")
    model_path = model_path or MODEL_DIR / "cloud-model.pkl"
    model = CloudModel.load(model_path)
    passes, sites = _inputs(data_root)
    raw = data_root / "data" / "raw" / "s2windows"
    man = provenance.PullManifest.start(
        "s2windows", "gcp-public-data-sentinel-2 L1C; earth-search L2A scl", {"year": YEAR}
    )
    pull = raw / man.pull_id
    roots = sorted(p for p in raw.glob("*") if p.is_dir())
    windows, classes, new = sc.run(passes, model, roots, pull, workers=workers, keep_classes=True)
    if new:
        man.finish(pull, new, len(new))

    windows["usable_model"] = windows["clear_model"] >= USABLE
    windows["usable_scl"] = windows["clear_scl"] >= USABLE
    windows["usable_tile"] = windows["valid_frac"] >= USABLE
    windows["scl_clear"] = windows["clear_scl"] >= SCL_CLEAR
    windows["scl_cloudy"] = windows["clear_scl"] < SCL_CLOUDY
    scored = windows[windows["scored"] & windows["clear_scl"].notna()].copy()
    scored["model_unusable"] = ~scored["usable_model"]

    hot, maps = hotspots(windows, classes, sites)
    result = {
        "adr": "0014",
        **provenance.run_manifest(provenance.new_id("s2-cloud-recent")),
        "model_sha256": provenance.sha256_file(model_path),
        "year": YEAR,
        "windows": {
            "site_days": len(windows),
            "acquisition_days": int(windows["day"].nunique()),
            "scored": int(windows["scored"].sum()),
            "read_errors": int(windows["error"].notna().sum()),
            "partial": int((~windows["scored"] & windows["error"].isna()).sum()),
            "no_scl": int(windows["clear_scl"].isna().sum()),
            "scl_collections": windows["scl_collection"].value_counts().to_dict(),
            "platforms": windows["platform"].value_counts().to_dict(),
            "baselines": windows["baseline"].value_counts().to_dict(),
        },
        "criteria": {
            "1_scale": scale_check(windows),
            "2_clear_kept": _criterion(
                day_rate(scored, "model_unusable", "scl_clear"), R1 + TOLERANCE
            ),
            "3_cloudy_rejected": _criterion(
                day_rate(scored, "usable_model", "scl_cloudy"), R2 + TOLERANCE
            ),
            "4_platform": {
                **(g := platform_gap(scored)),
                "limit": MAX_PLATFORM_GAP,
                "passed": abs(g["value"]) <= MAX_PLATFORM_GAP,
            },
            "5_false_clouds": {
                "sites": hot,
                "passed": all(v["passed"] for v in hot.values()),
            },
            "6_eye": {"status": "pending"},
        },
        "reference": {"R1": R1, "R2": R2, "source": "s2-cloud-model held-out windows"},
        "per_site": per_site(windows),
    }
    rid = result["run_id"]
    windows.drop(columns=["file"]).to_csv(RESULTS_DIR / f"{rid}.windows.csv", index=False)
    hotspot_figure(maps, RESULTS_DIR / f"{rid}.false-clouds.png")

    draw = eye_draw(windows)
    thumbnail_sheets(draw, RESULTS_DIR)
    key_dir = _key_dir(data_root)
    key_dir.mkdir(parents=True, exist_ok=True)
    key = draw[["thumb", "overpass_id", "group", "clear_model", "clear_scl"]]
    key.to_json(key_dir / f"{rid}-eye-key.json", orient="records", indent=1)
    out = RESULTS_DIR / f"{rid}.json"
    out.write_text(json.dumps(_finite(result), indent=2, default=_default, allow_nan=False))
    labels = RESULTS_DIR / "eye-labels.csv"
    labels.write_text("thumb,usable,note\n" + "".join(f"{t},,\n" for t in draw["thumb"]))
    return out


def per_site(windows: pd.DataFrame) -> dict:
    s = windows[windows["scored"]]
    g = s.groupby("site_id")
    return {
        site: {
            "site_days": len(d),
            "usable_tile_rule": int(d["usable_tile"].sum()),
            "usable_sen2cor": int(d["usable_scl"].sum()),
            "usable_model": int(d["usable_model"].sum()),
            "mean_clear_model": float(d["clear_model"].mean()),
            "mean_clear_sen2cor": float(d["clear_scl"].mean()),
        }
        for site, d in g
    }


def finish(data_root: Path = REPO_ROOT) -> Path:
    """Criterion 6 from the labels in ``eye-labels.csv``, then the verdict and the report."""
    out = next(iter(sorted(RESULTS_DIR.glob("*.json"))))
    result = json.loads(out.read_text())
    if result["criteria"]["6_eye"].get("status") != "pending":
        raise FileExistsError("the eye check is already scored")
    labels = pd.read_csv(RESULTS_DIR / "eye-labels.csv")
    labels["usable"] = labels["usable"].astype(str).str.strip().str.lower()
    if not labels["usable"].isin(["yes", "no"]).all():
        raise ValueError("every thumbnail needs usable = yes or no in eye-labels.csv")
    key = pd.read_json(_key_dir(data_root) / f"{result['run_id']}-eye-key.json")
    eye = key.merge(labels, on="thumb")
    eye["eye_usable"] = eye["usable"] == "yes"
    eye["model_right"] = (eye["clear_model"] >= USABLE) == eye["eye_usable"]
    eye["scl_right"] = (eye["clear_scl"] >= USABLE) == eye["eye_usable"]
    dis = eye[eye["group"].isin(["model_only", "scl_only"])]
    agr = eye[eye["group"].isin(["both_usable", "both_unusable"])]
    agr_wrong = int((~agr["model_right"]).sum())
    result["criteria"]["6_eye"] = {
        "status": "scored",
        "disagreements": len(dis),
        "model_matches_eye": int(dis["model_right"].sum()),
        "sen2cor_matches_eye": int(dis["scl_right"].sum()),
        "agreements": len(agr),
        "agreements_against_eye": agr_wrong,
        "passed": bool(dis["model_right"].sum() >= dis["scl_right"].sum() and agr_wrong <= 1),
        "thumbnails": eye.drop(columns=["usable"]).to_dict(orient="records"),
    }
    c = result["criteria"]
    others = all(c[k]["passed"] for k in ("1_scale", "2_clear_kept", "3_cloudy_rejected"))
    others = others and c["4_platform"]["passed"] and c["6_eye"]["passed"]
    sites = c["5_false_clouds"]["sites"]
    # ADR 0014: a site with fixed false clouds falls back to Sen2Cor; any other failure
    # sends every site to Sen2Cor
    model_sites = sorted(s for s, v in sites.items() if v["passed"]) if others else []
    result["verdict"] = {
        "holds": bool(others and c["5_false_clouds"]["passed"]),
        "model_sites": model_sites,
        "sen2cor_sites": sorted(s for s in sites if s not in model_sites),
    }
    out.write_text(json.dumps(_finite(result), indent=2, default=_default, allow_nan=False))
    out.with_suffix(".md").write_text(report_markdown(result))
    return out


def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _rng(c: dict) -> str:
    lo, hi = c["interval"]
    return "n/a" if lo is None else f"{100 * lo:.1f} to {100 * hi:.1f}"


def report_markdown(r: dict) -> str:
    c = r["criteria"]
    ok = {True: "pass", False: "fail"}
    w = r["windows"]
    lines = [
        f"# Cloud model on 2025 pilot passes ({r['run_id']})",
        "",
        "Transfer check fixed in ADR 0014 before the run. Not a second held-out test: there are"
        " no labels, so Sen2Cor and a blind look by eye are the yardsticks. 90% ranges resample"
        " acquisition days.",
        "",
        f"{w['site_days']} site-days on {w['acquisition_days']} days; {w['scored']} scored"
        f" ({w['partial']} partial windows, {w['read_errors']} read errors,"
        f" {w['no_scl']} without Sen2Cor).",
        "",
        "| Criterion | Result | 90% range | Limit | |",
        "|---|---|---|---|---|",
        f"| 1. Band 12 of Sen2Cor water, clear windows | {c['1_scale']['water_b12_median']:.4f} |"
        f" | {c['1_scale']['limits'][0]} to {c['1_scale']['limits'][1]} |"
        f" {ok[c['1_scale']['passed']]} |",
        f"| 2. Model unusable when Sen2Cor >= 99% clear | {_pct(c['2_clear_kept']['value'])}"
        f" ({c['2_clear_kept']['n_windows']} windows) | {_rng(c['2_clear_kept'])} |"
        f" {_pct(c['2_clear_kept']['limit'])} | {ok[c['2_clear_kept']['passed']]} |",
        f"| 3. Model usable when Sen2Cor < 30% clear | {_pct(c['3_cloudy_rejected']['value'])}"
        f" ({c['3_cloudy_rejected']['n_windows']} windows) | {_rng(c['3_cloudy_rejected'])} |"
        f" {_pct(c['3_cloudy_rejected']['limit'])} | {ok[c['3_cloudy_rejected']['passed']]} |",
        f"| 4. Sentinel-2C minus 2A/2B, mean model - Sen2Cor clear share |"
        f" {c['4_platform']['value']:+.3f} | {c['4_platform']['interval'][0]:+.3f} to"
        f" {c['4_platform']['interval'][1]:+.3f} | +/-{c['4_platform']['limit']} |"
        f" {ok[c['4_platform']['passed']]} |",
        f"| 5. No fixed false clouds | see below | | 1% of area, 5% of site |"
        f" {ok[c['5_false_clouds']['passed']]} |",
    ]
    e = c["6_eye"]
    if e.get("status") == "scored":
        lines.append(
            f"| 6. Blind look by eye | model {e['model_matches_eye']} vs Sen2Cor"
            f" {e['sen2cor_matches_eye']} of {e['disagreements']} disagreements;"
            f" {e['agreements_against_eye']} of {e['agreements']} agreements against the eye |"
            f" | model >= Sen2Cor; <= 1 | {ok[e['passed']]} |"
        )
    lines += ["", "| Site | Sen2Cor-clear days | Area flagged > 20% | Site flagged > 20% | |"]
    lines += ["|---|---|---|---|---|"]
    for s, v in sorted(c["5_false_clouds"]["sites"].items()):
        lines.append(
            f"| {s} | {v['n_clear_days']} | {_pct(v['area_share_flagged'])} |"
            f" {_pct(v['site_share_flagged'])} | {ok[v['passed']]} |"
        )
    lines += ["", "Usable site-days in 2025 (clear share >= 0.7), descriptive only:", ""]
    lines += ["| Site | Site-days | Tile rule | Sen2Cor | Model |", "|---|---|---|---|---|"]
    for s, v in sorted(r["per_site"].items()):
        lines.append(
            f"| {s} | {v['site_days']} | {v['usable_tile_rule']} | {v['usable_sen2cor']} |"
            f" {v['usable_model']} |"
        )
    if "verdict" in r:
        v = r["verdict"]
        lines += [
            "",
            f"**Verdict: the check {'holds' if v['holds'] else 'does not hold'}.**"
            f" Model share for: {', '.join(v['model_sites']) or 'none'}."
            f" Sen2Cor share for: {', '.join(v['sen2cor_sites']) or 'none'}.",
        ]
    manifest = {k: r[k] for k in ("run_id", "created_at", "git_sha", "git_dirty", "model_sha256")}
    lines += ["", "```json", json.dumps(manifest, indent=2), "```", ""]
    return "\n".join(lines)


def _finite(o):
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_finite(v) for v in o]
    if isinstance(o, float | np.floating) and not np.isfinite(o):
        return None
    if isinstance(o, np.generic):
        return o.item()
    return o


def _default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)

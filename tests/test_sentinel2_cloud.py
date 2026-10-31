"""Cloud model for the Sentinel-2 retrieval (ADR 0012, ADR 0013), on small synthetic fixtures.

No network: CloudSEN12+ containers and patches are built in memory.
"""

import io

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import rasterio
from rasterio.io import MemoryFile
from typer.testing import CliRunner

from methanewatch.sentinel2 import cloudeval as ev
from methanewatch.sentinel2 import cloudmodel as cm
from methanewatch.sentinel2 import cloudsen12 as cs
from methanewatch.sentinel2 import detect

N = 96


# --- containers and patches ----------------------------------------------------------------


def container(parts: dict[str, bytes]) -> bytes:
    """A tortilla-style container: header, payloads, parquet footer indexing them."""
    body, rows, pos = b"", [], 18
    for name, data in parts.items():
        rows.append({"tortilla:id": name, "tortilla:offset": pos, "tortilla:length": len(data)})
        body += data
        pos += len(data)
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf)
    footer = buf.getvalue()
    header = b"WX" + pos.to_bytes(8, "little") + len(footer).to_bytes(8, "little")
    return header + body + footer


def geotiff(arr: np.ndarray) -> bytes:
    arr = arr if arr.ndim == 3 else arr[None]
    profile = {
        "driver": "GTiff",
        "count": arr.shape[0],
        "height": arr.shape[1],
        "width": arr.shape[2],
        "dtype": arr.dtype.name,
        "crs": "EPSG:32610",
        "transform": rasterio.transform.from_origin(580000, 4150000, 10, 10),
    }
    with MemoryFile() as mem:
        with mem.open(**profile) as dst:
            dst.write(arr)
        return mem.read()


def test_container_footer_round_trip():
    blob = container({"a": b"hello", "b": b"world!"})
    df = cs.read_footer(blob)
    assert df["tortilla:id"].tolist() == ["a", "b"]
    r = df.iloc[1]
    assert blob[r["tortilla:offset"] : r["tortilla:offset"] + r["tortilla:length"]] == b"world!"
    with pytest.raises(ValueError):
        cs.parse_header(b"NO" + bytes(16))


def test_l1c_arrays_reduce_to_20m_and_mark_padding():
    img = np.full((13, 32, 32), 1500, dtype=np.uint16)
    img[:, :, -3:] = 0  # padding columns
    lab = np.zeros((32, 32), dtype=np.uint8)
    lab[:4, :4] = 1
    blob = container({"s2l1c": geotiff(img), "target": geotiff(lab)})
    files = {
        r["tortilla:id"]: blob[r["tortilla:offset"] : r["tortilla:offset"] + r["tortilla:length"]]
        for _, r in cs.read_footer(blob).iterrows()
    }
    a = cs.l1c_arrays(files)
    assert a["bands"].shape == (13, 16, 16)
    assert a["bands"][0, 0, 0] == 1500
    assert not a["valid"][:, -2:].any() and a["valid"][:, :-2].all()
    assert (a["label"][:2, :2] == 1).all() and a["label"][5, 5] == 0


def test_label_votes_go_to_the_less_clear_class_on_ties():
    lab = np.array([[0, 0, 0, 3], [1, 2, 1, 3]], dtype=np.uint8)
    out = cs.to_20m_labels(lab)
    # left block: two clear, one thick, one thin -> clear wins outright (2 votes)
    # right block: two clear, two shadow -> tie goes to shadow
    assert out.tolist() == [[0, 3]]


def test_roles_hold_out_test_and_west_coast_sites_and_drop_shared_tiles():
    rows = [
        # roi, split, lat, lon, tile
        ("R1", "test", 10.0, 10.0, "31TAA"),
        ("R2", "train", 37.5, -122.0, "10SEG"),  # West Coast -> held out
        ("R3", "train", 10.0, 11.0, "31TAA"),  # shares a held-out tile -> dropped
        ("R4", "validation", 50.0, 10.0, "32UBB"),
        ("R5", "train", -20.0, 30.0, "35KAA"),
    ]
    index = pd.DataFrame(
        [
            {
                "sample_id": f"{r}_{d}",
                "roi_id": r,
                "split": split,
                "lat": lat,
                "lon": lon,
                "tile": tile,
                "label_type": "high",
                "real_proj_shape": 509,
            }
            for r, split, lat, lon, tile in rows
            for d in range(2)
        ]
    )
    roles = cs.assign_roles(index).drop_duplicates("roi_id").set_index("roi_id")
    assert roles.loc["R1", "role"] == "heldout"
    assert roles.loc["R2", "role"] == "heldout" and roles.loc["R2", "regional"]
    assert roles.loc["R3", "role"] == "dropped"
    assert roles.loc["R4", "role"] == "validation"
    assert roles.loc["R5", "role"] == "train"


# --- synthetic scenes ----------------------------------------------------------------------


def surface(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N]
    return 0.2 + 0.08 * np.sin(yy / 7) * np.cos(xx / 11) + rng.normal(0, 0.002, (N, N))


def patch(seed=0, cloud=None, shadow=None, noise=0.002):
    """A 13-band patch over one surface; ``cloud`` and ``shadow`` are boolean masks."""
    rng = np.random.default_rng(seed + 100)
    s = surface()
    bands = np.stack([s * f for f in np.linspace(0.5, 1.2, 13)]).astype(np.float32)
    bands[cm.B["B02"]] = 0.08 + 0.02 * (s - 0.2)
    bands[cm.B["B10"]] = 0.002
    bands[cm.B["B11"]] = s * 1.1
    bands[cm.B["B12"]] = s * 0.85 * (1 + rng.normal(0, noise, s.shape))
    label = np.zeros((N, N), np.uint8)
    if cloud is not None:
        bands[:, cloud] = bands[:, cloud] * 0.3 + 0.45
        bands[cm.B["B11"], cloud] *= 1.25  # clouds change the band 11/12 ratio
        bands[cm.B["B10"], cloud] = 0.05
        label[cloud] = 1
    if shadow is not None:
        bands[:, shadow] *= 0.35
        label[shadow] = 3
    return {
        "bands": bands,
        "label": label,
        "valid": np.ones((N, N), bool),
        "sen2cor": np.where(label == 1, 9, 4).astype(np.uint8),
        "s2cloudless": np.where(label == 1, 90.0, 5.0).astype(np.float32),
        "unetmobv2_v2": label.copy(),
    }


def blob(cx, cy, r):
    yy, xx = np.mgrid[0:N, 0:N]
    return (xx - cx) ** 2 + (yy - cy) ** 2 < r**2


def test_features_match_their_names_and_are_finite():
    f = cm.features(patch()["bands"])
    assert f.shape == (len(cm.feature_names()), N, N)
    assert np.isfinite(f).all()


def test_model_learns_bright_clouds_and_dark_shadows():
    rng = np.random.default_rng(0)
    xs, ys = [], []
    for i in range(6):
        c = blob(20 + 8 * i, 30, 10)
        sh = blob(30 + 8 * i, 70, 8) & ~c
        p = patch(i, cloud=c, shadow=sh)
        x, y = cm.sample_pixels(
            cm.features(p["bands"]), cm.to_classes(p["label"]), p["valid"], 900, rng
        )
        xs.append(x)
        ys.append(y)
    model = cm.fit(np.concatenate(xs), np.concatenate(ys), {"max_iter": 40, "max_leaf_nodes": 15})
    c, sh = blob(50, 40, 12), blob(60, 75, 9)
    test = patch(9, cloud=c, shadow=sh & ~c)
    pred = model.predict(test["bands"])
    assert (pred == cm.to_classes(test["label"])).mean() > 0.95


def test_model_round_trips_through_a_file(tmp_path):
    p = patch(cloud=blob(40, 40, 10))
    x, y = cm.sample_pixels(
        cm.features(p["bands"]),
        cm.to_classes(p["label"]),
        p["valid"],
        300,
        np.random.default_rng(1),
    )
    model = cm.fit(x, y, {"max_iter": 10})
    path = model.save(tmp_path / "m.pkl")
    again = cm.CloudModel.load(path)
    assert (again.predict(p["bands"]) == model.predict(p["bands"])).all()
    assert path.with_suffix(".json").exists()


# --- Claim 1 -------------------------------------------------------------------------------


def windows(model_errs: int, base_errs: int, n_sites: int = 40) -> pd.DataFrame:
    """Each site has one unusable and one usable patch; methods err on the first k sites."""
    rows = []
    for i in range(n_sites):
        for truly_usable in (False, True):
            true_clear = 0.9 if truly_usable else 0.3
            wrong = 1.0 - true_clear
            row = {"roi_id": f"S{i}", "true_clear": true_clear, "tile_cloud_cover": 10.0}
            row["clear_model"] = wrong if (i < model_errs and not truly_usable) else true_clear
            for m in ("threshold", "sen2cor", "s2cloudless"):
                row[f"clear_{m}"] = wrong if (i < base_errs and not truly_usable) else true_clear
            if not truly_usable:
                row["tile_cloud_cover"] = 10.0 if i < base_errs else 80.0
            rows.append(row)
    return pd.DataFrame(rows)


METHODS1 = ["tile_rule", "threshold", "sen2cor", "s2cloudless", "model"]


def test_claim1_passes_when_the_model_makes_far_fewer_false_usable_calls():
    res = ev.claim1(windows(model_errs=0, base_errs=20), METHODS1)
    assert res["rates"]["sen2cor"]["false_usable"]["value"] == pytest.approx(0.5)
    assert res["rates"]["model"]["false_usable"]["value"] == 0
    assert res["comparisons"]["tile_rule"]["passed"]
    assert res["passed"]


def test_claim1_fails_when_the_model_is_no_better():
    res = ev.claim1(windows(model_errs=10, base_errs=10), METHODS1)
    assert not res["passed"]
    lo, hi = res["comparisons"]["sen2cor"]["false_usable_diff"]["interval"]
    assert lo <= 0 <= hi


def test_claim1_scores_the_tile_rule_only_where_a_tile_figure_exists():
    w = windows(model_errs=0, base_errs=20)
    w.loc[w.index[:10], "tile_cloud_cover"] = np.nan
    res = ev.claim1(w, METHODS1)
    assert res["n_tile_rule_scored"] == len(w) - 10


# --- Claim 2 -------------------------------------------------------------------------------


def test_plume_shape_peaks_at_one_and_injection_touches_band_12_only():
    shape = ev.plume_shape(N, N, 30, 40, 0.0, 50)
    assert shape.max() == pytest.approx(1.0) and shape[40, 30] > 0.9
    assert shape[40, 10] < 0.01  # upwind
    p = patch()
    out = ev.inject(p["bands"], [shape], 0.1)
    assert np.allclose(out[cm.B["B11"]], p["bands"][cm.B["B11"]])
    assert out[cm.B["B12"], 40, 30] == pytest.approx(
        p["bands"][cm.B["B12"], 40, 30] * 0.9, rel=0.02
    )


def test_candidate_components_lists_every_component():
    vals = np.zeros((N, N))
    vals += np.random.default_rng(0).normal(0, 0.01, vals.shape)
    vals[10:15, 10:15] = 1
    vals[60:66, 60:66] = 1
    comps, sigma = detect.candidate_components(vals)
    big = [c for c in comps if c.sum() >= 25]
    assert len(big) == 2 and sigma > 0


def perfect(s):
    return s["label"] != 0


def test_unmasked_clouds_make_false_candidates_and_a_correct_mask_removes_them():
    ref = patch(1)
    target = patch(2, cloud=blob(30, 30, 9))
    methods = {"none": ev.no_mask, "perfect": perfect}
    counts = ev.pair_counts(target, ref, methods, 0.12, np.random.default_rng(3))
    assert counts["none"]["cloud_caused"] >= 1
    assert counts["perfect"]["cloud_caused"] == 0
    assert counts["perfect"]["plumes"] == ev.N_PLUMES
    assert counts["perfect"]["hits"] >= 2


def test_claim2_and_amplitude_choice_on_synthetic_sites():
    sites = []
    for i in range(12):
        dates = [patch(10 * i), patch(10 * i + 1), patch(10 * i + 2, cloud=blob(30 + i, 30, 8))]
        sites.append(ev.SitePatches(roi_id=f"S{i}", load=lambda d=dates: d))
    amp = ev.choose_amplitude(sites)
    assert amp["amplitude"] in ev.AMPLITUDES
    assert amp["reached_target"]
    methods = {"none": ev.no_mask, "threshold": ev.threshold_unusable, "model": perfect}
    counts = ev.claim2_counts(sites, methods, amp["amplitude"])
    res = ev.claim2(counts, ["none", "threshold", "model"])
    assert res["n_sites"] == 12 and res["n_targets"] == 24
    assert res["rates"]["model"]["cloud_caused_per_target"]["value"] == 0
    assert res["rates"]["none"]["cloud_caused_per_target"]["value"] > 0


def test_a_site_without_a_clear_date_has_no_pairs():
    cloudy = [patch(1, cloud=blob(30, 30, 20)), patch(2, cloud=blob(60, 60, 20))]
    assert ev.site_pairs(cloudy) is None


# --- running once ------------------------------------------------------------------------


def test_evaluate_runs_only_once(tmp_path, monkeypatch):
    from methanewatch.sentinel2 import cloudrun

    monkeypatch.setattr(cloudrun, "RESULTS_DIR", tmp_path)
    (tmp_path / "s2-cloud-model-earlier.json").write_text("{}")
    with pytest.raises(FileExistsError):
        cloudrun.evaluate()


def test_cli_lists_the_cloud_commands():
    from methanewatch.cli import app

    res = CliRunner().invoke(app, ["s2", "cloud", "--help"])
    assert res.exit_code == 0
    assert "evaluate" in res.output and "train" in res.output


def test_report_states_each_claim_and_its_verdict():
    from methanewatch.sentinel2 import cloudrun

    c1 = ev.claim1(windows(model_errs=0, base_errs=20), METHODS1)
    sites = [
        ev.SitePatches(
            roi_id=f"S{i}", load=lambda i=i: [patch(i), patch(i + 50, cloud=blob(40, 40, 8))]
        )
        for i in range(6)
    ]
    names = ["none", "threshold", "model"]
    c2 = ev.claim2(
        ev.claim2_counts(
            sites, {"none": ev.no_mask, "threshold": ev.threshold_unusable, "model": perfect}, 0.08
        ),
        names,
    )
    result = {
        "run_id": "s2-cloud-model-test",
        "created_at": "2026-10-31T00:00:00+00:00",
        "git_sha": "abc",
        "git_dirty": False,
        "dataset": "x@y",
        "amplitude": {"amplitude": 0.08},
        "claim1": {"all_heldout": c1},
        "claim2": {"all_heldout": c2},
    }
    md = cloudrun.report_markdown(cloudrun._finite(result))
    assert md.splitlines()[0].endswith("(s2-cloud-model-test)")
    assert "**Claim 1 (usable windows): PASS**" in md
    assert "**Claim 2 (cloud-caused detections):" in md
    assert '"run_id": "s2-cloud-model-test"' in md

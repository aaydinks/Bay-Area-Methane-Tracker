"""An instrument enters a real fit only once its plume search has run (ADR 0016)."""

import json
import typing

import numpy as np
import pandas as pd
import pytest

from methanewatch import config, schemas
from methanewatch.config import load_instruments, load_model, load_project
from methanewatch.model import persistence, run, searched


def _detections() -> pd.DataFrame:
    """Two sites: aircraft and EMIT passes, plus Sentinel-2 passes that nobody searched."""
    rows = []
    for site in ("newby-island", "potrero-hills"):
        for i in range(4):
            hit = i < 2
            rows.append((site, "aircraft", i, hit, 900.0 if hit else None))
            rows.append((site, "emit", i, False, None))
        rows += [(site, "sentinel2", i, False, None) for i in range(6)]
    # A site seen only by Sentinel-2 drops out of the fit with it
    rows += [("acme-fill", "sentinel2", i, False, None) for i in range(5)]
    det = pd.DataFrame(rows, columns=["site_id", "instrument", "day", "detected", "q_obs_kg_hr"])
    det["overpass_id"] = det["site_id"] + ":" + det["instrument"] + ":" + det["day"].astype(str)
    det["q_sigma_log"] = np.where(det["detected"], 0.4, np.nan)
    return det.drop(columns="day")


def test_config_names_the_plume_sources_of_every_instrument():
    assert typing.get_args(config.PlumeSource) == tuple(schemas.PLUME_SOURCES)
    inst = load_instruments().instruments
    assert inst["sentinel2"].plume_sources == ["s2-local"]
    # EMIT plumes with rates arrive through Carbon Mapper, so EMIT must count as searched
    assert "carbonmapper" in inst["emit"].plume_sources
    assert all(v.plume_sources for v in inst.values())


def test_unsearched_sentinel2_is_left_out():
    det = _detections()
    sel = searched.select(det, load_instruments(), {"carbonmapper": 614})
    assert sel.used == ["aircraft", "emit"]
    assert "sentinel2" not in set(sel.detections["instrument"])
    assert len(sel.detections) == 16
    why = sel.left_out["sentinel2"]
    assert why["reason"] == searched.NOT_SEARCHED
    assert why["plume_sources"] == ["s2-local"]
    assert (why["n_passes"], why["n_detections"]) == (17, 0)
    assert sel.sites_left_out == ["acme-fill"]
    assert sel.included_unsearched == []
    assert sel.manifest()["plume_tables"] == {"carbonmapper": 614}


def test_an_empty_plume_table_counts_as_a_search_that_ran():
    sel = searched.select(_detections(), load_instruments(), {"carbonmapper": 614, "s2-local": 0})
    assert sel.used == ["aircraft", "emit", "sentinel2"]
    assert sel.left_out == {} and sel.sites_left_out == []


def test_include_unsearched_keeps_the_passes_and_says_so():
    sel = searched.select(
        _detections(), load_instruments(), {"carbonmapper": 614}, include_unsearched=["sentinel2"]
    )
    assert "sentinel2" in sel.used and sel.left_out == {}
    assert sel.included_unsearched == ["sentinel2"]
    assert len(sel.detections) == len(_detections())


def test_unknown_instruments_are_refused():
    with pytest.raises(ValueError, match="not in config"):
        searched.select(_detections(), load_instruments(), {}, include_unsearched=["sentinel-two"])


def test_plume_tables_count_rows_and_an_empty_table(tmp_path):
    assert searched.plume_tables(tmp_path) == {}
    (tmp_path / "plumes").mkdir()
    pd.DataFrame({"plume_id": ["a", "b"]}).to_parquet(tmp_path / "plumes" / "carbonmapper.parquet")
    pd.DataFrame({"plume_id": pd.Series(dtype=str)}).to_parquet(
        tmp_path / "plumes" / "s2-local.parquet"
    )
    assert searched.plume_tables(tmp_path) == {"carbonmapper": 2, "s2-local": 0}


# --- the fit itself, with the sampler replaced --------------------------------------------


def _project(tmp_path):
    base = load_project()
    return base.model_copy(
        update={
            "paths": base.paths.model_copy(
                update={"processed": tmp_path / "processed", "interim": tmp_path / "interim"}
            )
        }
    )


class _FakePosterior:
    def to_zarr(self, path, mode="w"):
        path.mkdir(parents=True)


def _stub_sampling(monkeypatch, seen):
    def prepare(det, *args, **kwargs):
        seen["instruments"] = sorted(det["instrument"].unique())
        return real_prepare(det, *args, **kwargs)

    def summarize(idata, data, diag, cfg, *, run_id, provisional):
        return pd.DataFrame({"site_id": data.site_ids, "period": "all", "run_id": run_id})

    real_prepare = persistence.prepare
    monkeypatch.setattr(persistence, "prepare", prepare)
    monkeypatch.setattr(persistence, "build_model", lambda *a, **k: None)
    monkeypatch.setattr(persistence, "fit", lambda *a, **k: _FakePosterior())
    monkeypatch.setattr(
        persistence, "diagnostics", lambda *a, **k: persistence.Diagnostics(1.0, 900.0, 0, True)
    )
    monkeypatch.setattr(run, "summarize", summarize)


def _inputs(tmp_path):
    interim = tmp_path / "interim"
    (interim / "plumes").mkdir(parents=True)
    _detections().to_parquet(interim / "detections.parquet")
    pd.DataFrame({"plume_id": ["cm1"]}).to_parquet(interim / "plumes" / "carbonmapper.parquet")


def _manifest(tmp_path, run_id):
    runs = tmp_path / "processed" / "runs"
    return json.loads((runs / f"{run_id}.json").read_text()), pd.read_parquet(
        runs / f"{run_id}-detections.parquet"
    )


def test_a_default_fit_leaves_out_sentinel2_and_records_it(tmp_path, monkeypatch, capsys):
    _inputs(tmp_path)
    seen = {}
    _stub_sampling(monkeypatch, seen)
    run_id = run.fit_real(
        _project(tmp_path), load_model(), load_instruments(), allow_unconfirmed=True
    )
    assert seen["instruments"] == ["aircraft", "emit"]
    manifest, used = _manifest(tmp_path, run_id)
    assert manifest["instruments"] == ["aircraft", "emit"]
    assert manifest["instruments_left_out"]["sentinel2"]["reason"] == "plume search not run"
    assert manifest["instruments_left_out"]["sentinel2"]["n_passes"] == 17
    assert manifest["included_unsearched"] == []
    assert manifest["sites_left_out"] == ["acme-fill"]
    assert manifest["unconfirmed_pod"] == ["aircraft", "emit"]
    # The saved table is what the fit used, without the Sentinel-2 rows
    assert set(used["instrument"]) == {"aircraft", "emit"}
    assert manifest["n_overpasses"] == len(used) == 16
    assert "left out sentinel2" in capsys.readouterr().out


def test_include_unsearched_puts_sentinel2_back(tmp_path, monkeypatch):
    _inputs(tmp_path)
    seen = {}
    _stub_sampling(monkeypatch, seen)
    run_id = run.fit_real(
        _project(tmp_path),
        load_model(),
        load_instruments(),
        allow_unconfirmed=True,
        include_unsearched=("sentinel2",),
    )
    manifest, used = _manifest(tmp_path, run_id)
    assert seen["instruments"] == manifest["instruments"] == ["aircraft", "emit", "sentinel2"]
    assert manifest["included_unsearched"] == ["sentinel2"]
    assert manifest["instruments_left_out"] == {}
    assert len(used) == len(_detections())


def test_a_fit_with_nothing_searched_stops(tmp_path, monkeypatch):
    _inputs(tmp_path)
    (tmp_path / "interim" / "plumes" / "carbonmapper.parquet").unlink()
    _stub_sampling(monkeypatch, {})
    with pytest.raises(run.ConfigNotReadyError, match="searched for plumes"):
        run.fit_real(_project(tmp_path), load_model(), load_instruments(), allow_unconfirmed=True)

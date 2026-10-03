"""Phase gates and the five validation tests (PLAN section 8).

Each writes reports/validation/<name>/<run_id>.md and returns False on failure.
"""

from __future__ import annotations


def gate1_plume_table() -> bool:
    import pandas as pd

    from methanewatch.config import load_project
    from methanewatch.sites.registry import missing_polygons
    from methanewatch.validate import gate1

    project = load_project()
    interim = project.resolve(project.paths.interim)
    registry_dir = project.resolve(project.paths.registry)
    needed = ["plumes_attributed.parquet", "overpasses.parquet", "unmatched_plumes.parquet"]
    missing = [n for n in needed if not (interim / n).exists()]
    if missing:
        raise FileNotFoundError(f"run `mw coverage build` first; missing {missing}")
    sites = pd.read_csv(registry_dir / "sites.csv", dtype=str)
    pilots = sites.loc[sites["tier"] == "pilot", "site_id"].tolist()
    table = gate1.counts_by_year(
        pd.read_parquet(interim / "plumes_attributed.parquet"),
        pd.read_parquet(interim / "overpasses.parquet"),
        pilots,
    )
    result = gate1.evaluate(table, pilots, missing_polygons(registry_dir))
    out_root = project.resolve(project.paths.reports) / "validation"
    unmatched = len(pd.read_parquet(interim / "unmatched_plumes.parquet"))
    report = gate1.write_report(table, result, out_root, unmatched=unmatched)
    print(f"wrote {report}")
    return result.passed


def gate2_s2_reproduction() -> bool:
    raise NotImplementedError("Gate 2: week 4")


def synthetic_recovery(n_replicates: int = 200, n_scenario_replicates: int = 20) -> bool:
    from methanewatch.config import load_project
    from methanewatch.validate import synthetic

    project = load_project()
    out_root = project.resolve(project.paths.reports) / "validation"
    return synthetic.gate(
        n_replicates, out_root, n_scenario_replicates=n_scenario_replicates
    ).passed


def matched_pairs() -> bool:
    raise NotImplementedError("matched pairs: week 6-8")


def holdout(n_folds: int = 5) -> bool:
    raise NotImplementedError("hold-out: week 7")


def operator_comparison() -> bool:
    raise NotImplementedError("operator comparison: week 8")


def placebo() -> bool:
    raise NotImplementedError("Gate 5: week 10")

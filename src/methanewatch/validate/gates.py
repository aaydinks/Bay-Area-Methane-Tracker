"""Phase gates and the five validation tests (PLAN section 8).

Each writes reports/validation/<name>/<run_id>.md and returns False on failure.
"""

from __future__ import annotations


def gate1_plume_table() -> bool:
    raise NotImplementedError("Gate 1: week 2")


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

"""Typed configuration loaded from ``config/*.yaml``.

Disputed or derived constants (GWP factors, $/t, detection curves) carry a
``source`` and a ``confirmed`` flag so outputs can be stamped provisional.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Sourced(_Strict):
    """A numeric constant with its citation."""

    value: float | None
    source: str | None = None
    confirmed: bool = False
    note: str | None = None


# --- project.yaml -----------------------------------------------------------


class Paths(_Strict):
    registry: Path
    raw: Path
    interim: Path
    processed: Path
    reports: Path


class Attribution(_Strict):
    buffer_m: float = Field(gt=0)
    search_radius_km: float = Field(gt=0)


class Coverage(_Strict):
    min_coverage_frac: float = Field(ge=0, le=1)
    min_valid_frac: float = Field(ge=0, le=1)


class RepairWindows(_Strict):
    window_months: int = Field(gt=0)
    gap_days: int = Field(ge=0)
    min_overpasses_per_window: int = Field(gt=0)
    call_probability: float = Field(gt=0.5, lt=1)


class ProjectConfig(_Strict):
    crs_geographic: str
    crs_metric: str
    paths: Paths
    attribution: Attribution
    coverage: Coverage
    repair: RepairWindows

    def resolve(self, p: Path) -> Path:
        return p if p.is_absolute() else REPO_ROOT / p


# --- instruments.yaml -------------------------------------------------------


class PodCurve(_Strict):
    """Probit detection curve in log-rate: POD(q) = Phi((ln q - ln q50) / w)."""

    q50_kg_hr: float | None = Field(default=None, gt=0)
    w: float | None = Field(default=None, gt=0)
    source: str | None = None
    confirmed: bool = False

    @property
    def is_set(self) -> bool:
        return self.q50_kg_hr is not None and self.w is not None


class Instrument(_Strict):
    platform: Literal["satellite", "aircraft"]
    pod: PodCurve
    meas_sigma_log: Sourced
    release_prob: Sourced


class InstrumentsConfig(_Strict):
    instruments: dict[str, Instrument]

    def unconfirmed(self, names: list[str] | None = None) -> list[str]:
        names = names or list(self.instruments)
        return [n for n in names if not self.instruments[n].pod.confirmed]


# --- model.yaml -------------------------------------------------------------


class Grid(_Strict):
    n_points: int = Field(ge=16)
    q_min_kg_hr: float | None = Field(default=None, gt=0)
    q_max_kg_hr: float = Field(gt=0)


class Priors(_Strict):
    alpha_f_mu: float
    alpha_f_sd: float = Field(gt=0)
    tau_f_sd: float = Field(gt=0)
    alpha_mu_mu: float
    alpha_mu_sd: float = Field(gt=0)
    tau_mu_sd: float = Field(gt=0)
    sigma_log_mu: float
    sigma_log_sd: float = Field(gt=0)


class Sampler(_Strict):
    chains: int = Field(ge=1)
    draws: int = Field(ge=100)
    tune: int = Field(ge=100)
    target_accept: float = Field(gt=0, lt=1)
    seed: int


class Diagnostics(_Strict):
    rhat_max: float
    ess_bulk_min: int
    max_divergences: int


class InsufficientData(_Strict):
    min_usable_overpasses: int
    max_interval_orders_of_magnitude: float


class ModelConfig(_Strict):
    grid: Grid
    priors: Priors
    sampler: Sampler
    diagnostics: Diagnostics
    insufficient_data: InsufficientData
    interval_mass: float = Field(gt=0, lt=1)


# --- impact.yaml ------------------------------------------------------------


class YearRangeValue(_Strict):
    years: tuple[int, int]
    value: float = Field(gt=0)
    source: str | None = None
    confirmed: bool = False

    def by_year(self) -> dict[int, float]:
        return {y: self.value for y in range(self.years[0], self.years[1] + 1)}


class ImpactConfig(_Strict):
    gwp20: Sourced
    gwp100: Sourced
    usd_per_t_co2e: Sourced
    population_radius_km: list[float]
    ghgrp_gwp_ch4: YearRangeValue


# --- synthetic.yaml ---------------------------------------------------------


class SyntheticInstrument(_Strict):
    q50_kg_hr: float = Field(gt=0)
    w: float = Field(gt=0)
    meas_sigma_log: float = Field(gt=0)
    release_prob: float = Field(gt=0, le=1)
    overpasses_per_year: float = Field(ge=0)

    @property
    def pod(self) -> PodCurve:
        # Synthetic curves are "confirmed" only in the sense that they are the truth
        # used to generate the simulated data.
        return PodCurve(q50_kg_hr=self.q50_kg_hr, w=self.w, source="synthetic", confirmed=True)


class Scenario(_Strict):
    f: float = Field(gt=0, lt=1)
    qbar_kg_hr: float = Field(gt=0)
    sigma: float = Field(gt=0)


class SyntheticConfig(_Strict):
    label: Literal["SYNTHETIC"]
    q_min_kg_hr: float = Field(gt=0)
    q_max_kg_hr: float = Field(gt=0)
    years: float = Field(gt=0)
    n_sites: int = Field(ge=2)
    instruments: dict[str, SyntheticInstrument]
    sampler: Sampler
    coverage_target: tuple[float, float]
    scenarios: dict[str, Scenario]


# --- quantify.yaml ----------------------------------------------------------


class Ueff(_Strict):
    a: Sourced
    b: Sourced
    relative_sigma: float = Field(ge=0)


class QuantifyConfig(_Strict):
    ueff: Ueff
    u10_sigma_ms: float = Field(gt=0)
    min_u10_ms: float = Field(gt=0)
    surface_pressure_pa: float = Field(gt=0)
    n_draws: int = Field(ge=100)


# --- loaders ----------------------------------------------------------------


def _read(name: str, config_dir: Path) -> dict:
    with (config_dir / name).open() as fh:
        return yaml.safe_load(fh)


@lru_cache
def load_project(config_dir: Path = CONFIG_DIR) -> ProjectConfig:
    return ProjectConfig.model_validate(_read("project.yaml", config_dir))


@lru_cache
def load_instruments(config_dir: Path = CONFIG_DIR) -> InstrumentsConfig:
    return InstrumentsConfig.model_validate(_read("instruments.yaml", config_dir))


@lru_cache
def load_model(config_dir: Path = CONFIG_DIR) -> ModelConfig:
    return ModelConfig.model_validate(_read("model.yaml", config_dir))


@lru_cache
def load_synthetic(config_dir: Path = CONFIG_DIR) -> SyntheticConfig:
    return SyntheticConfig.model_validate(_read("synthetic.yaml", config_dir))


@lru_cache
def load_quantify(config_dir: Path = CONFIG_DIR) -> QuantifyConfig:
    return QuantifyConfig.model_validate(_read("quantify.yaml", config_dir))


@lru_cache
def load_impact(config_dir: Path = CONFIG_DIR) -> ImpactConfig:
    return ImpactConfig.model_validate(_read("impact.yaml", config_dir))

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from methanewatch.config import PodCurve
from methanewatch.model.grid import (
    LogRateGrid,
    mean_rate,
    rate_density,
    truncated_lognormal_mean,
)
from methanewatch.model.pod import UnsetPodCurveError, pod, pod_matrix

GRID = LogRateGrid.build(q_min=50, q_max=20_000, n_points=96)


def test_density_integrates_to_one():
    h = rate_density(GRID, mu=np.log(300), sigma=1.0)
    assert GRID.integrate(h) == pytest.approx(1.0)


@pytest.mark.parametrize("mu, sigma", [(np.log(300), 1.0), (np.log(800), 0.6), (np.log(150), 1.2)])
def test_grid_mean_matches_closed_form(mu, sigma):
    got = mean_rate(GRID, rate_density(GRID, mu, sigma))
    want = truncated_lognormal_mean(mu, sigma, q_min=50)
    assert got == pytest.approx(want, rel=0.01)


def test_grid_integral_matches_monte_carlo():
    rng = np.random.default_rng(0)
    mu, sigma, q50, w = np.log(300), 1.0, 400.0, 0.5
    q = rng.lognormal(mu, sigma, 2_000_000)
    q = q[(q >= 50) & (q <= 20_000)]
    mc = pod(q, q50, w).mean()
    grid_val = GRID.integrate(pod(GRID.q, q50, w) * rate_density(GRID, mu, sigma))
    assert grid_val == pytest.approx(mc, rel=0.01)


@given(st.floats(10, 5000), st.floats(0.1, 2.0))
def test_pod_is_monotone_and_bounded(q50, w):
    p = pod(GRID.q, q50, w)
    assert np.all(np.diff(p) >= 0)
    assert p.min() >= 0 and p.max() <= 1
    assert pod(q50, q50, w) == pytest.approx(0.5)


def test_pod_matrix_refuses_unset_or_unconfirmed_curves():
    with pytest.raises(UnsetPodCurveError):
        pod_matrix(GRID, {"emit": PodCurve()})
    curve = PodCurve(q50_kg_hr=500, w=0.5, confirmed=False)
    with pytest.raises(UnsetPodCurveError):
        pod_matrix(GRID, {"emit": curve})
    names, m = pod_matrix(GRID, {"emit": curve}, allow_unconfirmed=True)
    assert names == ["emit"] and m.shape == (1, 96)

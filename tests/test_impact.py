import numpy as np
import pytest

from methanewatch import impact


def test_worked_example_from_project_plan():
    # 100 kg/hr for 6 months -> 438 t CH4 -> ~11,000 t CO2e (GWP 25) -> ~$0.9M at $80/t
    ch4 = impact.ch4_from_rate(100, 4380)
    assert ch4 == pytest.approx(438)
    co2e = impact.to_co2e(ch4, "gwp100")
    assert co2e.values == pytest.approx(10_950)
    assert not co2e.confirmed
    usd = impact.to_usd(co2e.values)
    assert usd.values == pytest.approx(876_000)


def test_annual_total():
    assert impact.annual_t(0.5, 100) == pytest.approx(438)


def test_nothing_is_avoided_without_a_verified_drop():
    before, after = np.array([100.0, 120.0]), np.array([50.0, 60.0])
    for call in ("rise", "inconclusive", "insufficient_data"):
        assert impact.ch4_avoided_t(before, after, 1.0, call) is None
    assert impact.ch4_avoided_t(before, after, 2.0, "drop") == pytest.approx([100.0, 120.0])


def test_interval():
    draws = np.random.default_rng(1).normal(10, 1, 100_000)
    iv = impact.interval(draws, mass=0.9)
    assert iv.median == pytest.approx(10, abs=0.02)
    assert iv.hi - iv.lo == pytest.approx(2 * 1.645, rel=0.02)

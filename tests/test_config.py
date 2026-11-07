from methanewatch import config


def test_all_configs_load():
    assert config.load_project().attribution.buffer_m > 0
    assert set(config.load_instruments().instruments) == {
        "tanager1",
        "emit",
        "aircraft",
        "sentinel2",
    }
    assert config.load_model().interval_mass == 0.90
    assert config.load_impact().gwp100.value == 25


def test_derived_constants_start_unconfirmed():
    impact = config.load_impact()
    assert not impact.gwp100.confirmed
    assert not impact.usd_per_t_co2e.confirmed
    assert config.load_instruments().unconfirmed() != []


def test_sourced_curves_stay_unconfirmed():
    # ADR 0015: every curve and the floor are derived from published figures, not confirmed
    for name, inst in config.load_instruments().instruments.items():
        assert inst.pod.is_set, name
        assert inst.pod.source and not inst.pod.confirmed, name
        assert inst.meas_sigma_log.value is not None and not inst.meas_sigma_log.confirmed, name
    grid = config.load_model().grid
    assert grid.q_min_kg_hr is not None and grid.q_min_source
    assert not grid.q_min_confirmed

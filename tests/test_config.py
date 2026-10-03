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

# Repair test on synthetic data (repair-synthetic-20261003T232115Z)

Dry run, not Gate 5. Gate 5 runs placebos on the real overpass schedules. Instrument settings come from `config/synthetic.yaml` (SYNTHETIC), over 3 years of simulated overpasses.

## Placebo false-positive rate

Pseudo-repairs at sites where nothing changed: 147 usable fits, 3 insufficient. Calls: {'inconclusive': 128, 'drop': 11, 'rise': 8, 'insufficient_data': 3}.

- False-positive rate (drop or rise): **0.129**
- 95% Wilson interval: 0.084 to 0.193 (optimistic: pseudo-dates at the same sites overlap)
- Site block bootstrap: 0.033 to 0.246
- Gate 5 threshold: 0.10

## Power: injected drops at one site

The treated site is the `typical` scenario (f = 0.3, Qbar = 500 kg/hr); its emitting fraction is multiplied by the factor after the repair date.

|   factor |   fits |   p_drop |   p_rise |   effect_median |   true_effect |   covered |
|---------:|-------:|---------:|---------:|----------------:|--------------:|----------:|
|    0.250 | 17.000 |    0.588 |    0.000 |          -1.425 |        -1.386 |     0.941 |
|    0.500 | 18.000 |    0.222 |    0.000 |          -0.934 |        -0.693 |     0.944 |
|    0.750 | 16.000 |    0.000 |    0.062 |           0.007 |        -0.288 |     0.875 |

`p_drop` is the share of fits calling a drop; `covered` is the share whose 90% interval for the log effect contains the injected log(factor).

## Run manifest

```json
{
  "run_id": "repair-synthetic-20261003T232115Z",
  "created_at": "2026-10-03T23:21:15.560064+00:00",
  "git_sha": "b4ee70e247a0b1ab80ec3ab9ad8700b065423709",
  "git_dirty": false,
  "config_sha256": {
    "impact.yaml": "daff7df8f31e870b31b97498e9d69e5f154fd7d33e7f959160d95c3cdeab6819",
    "instruments.yaml": "1a5a3da021ca9cfb6dde1deeb19a6d59f7137965cb8d931a0c04fe473f152129",
    "model.yaml": "5c326770a251a91eaefc34cdff1286105265bdc4551111caf04e4e6101f284e1",
    "project.yaml": "280b7d928f0e2bcd847e5094e41435240fc6f83e0c17ad459c59ca77c3c24d57",
    "synthetic.yaml": "69785b159e118ff9e7b6128d161851119b966ff20b9d4becf0bf6b72a156a926"
  },
  "versions": {
    "pymc": "6.3.2",
    "pytensor": "3.3.3",
    "numpy": "2.5.3"
  },
  "fpr": {
    "fpr": 0.1292517006802721,
    "wilson_lo": 0.08432985363284276,
    "wilson_hi": 0.19305781661197038,
    "bootstrap_lo": 0.03310713663297316,
    "bootstrap_hi": 0.24615671641791045,
    "n_usable": 147,
    "n_insufficient": 3
  },
  "years": 3.0
}
```

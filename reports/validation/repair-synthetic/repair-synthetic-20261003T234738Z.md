# Repair test on synthetic data (repair-synthetic-20261003T234738Z)

Dry run, not Gate 5. Gate 5 runs placebos on the real overpass schedules. Instrument settings come from `config/synthetic.yaml` (SYNTHETIC), over 3 years of simulated overpasses.

Call rule: drop if P(decrease) >= 0.975, rise if P(decrease) <= 0.025 (two-sided, nominal false-positive rate 5%); intervals reported at 90%. See ADR 0006.

**Minimum detectable effect (80% power):** none of the tested drops reached 80% power; even a 90% drop was called in 21% of fits.

## Placebo false-positive rate

Pseudo-repairs at sites where nothing changed, in 40 independent simulated worlds: 153 usable fits, 7 insufficient. Calls: {'inconclusive': 150, 'insufficient_data': 7, 'rise': 2, 'drop': 1}.

- False-positive rate (drop or rise): **0.020**
- 95% Wilson interval: 0.007 to 0.056 (optimistic: pseudo-dates at the same sites overlap)
- Bootstrap over worlds: 0.000 to 0.044
- Gate 5 threshold: 0.10

## Power: injected drops at one site

The treated site is the `typical` scenario (f = 0.3, Qbar = 500 kg/hr); its emitting fraction is multiplied by the factor after the repair date.

|   factor |   fits |   p_drop |   p_rise |   p_decrease_median |   effect_median |   true_effect |   covered |
|---------:|-------:|---------:|---------:|--------------------:|----------------:|--------------:|----------:|
|    0.100 | 14.000 |    0.214 |    0.000 |               0.965 |          -1.531 |        -2.303 |     0.929 |
|    0.250 | 14.000 |    0.429 |    0.000 |               0.890 |          -1.285 |        -1.386 |     0.929 |
|    0.500 | 14.000 |    0.143 |    0.000 |               0.789 |          -0.565 |        -0.693 |     1.000 |
|    0.750 | 14.000 |    0.000 |    0.000 |               0.650 |          -0.276 |        -0.288 |     0.857 |

`p_drop` is the share of fits calling a drop; `covered` is the share whose 90% interval for the log effect contains the injected log(factor).

## Run manifest

```json
{
  "run_id": "repair-synthetic-20261003T234738Z",
  "created_at": "2026-10-03T23:47:38.743151+00:00",
  "git_sha": "346ba7f40e8d3d7776e1f0889ef2453cd2237efe",
  "git_dirty": false,
  "config_sha256": {
    "impact.yaml": "daff7df8f31e870b31b97498e9d69e5f154fd7d33e7f959160d95c3cdeab6819",
    "instruments.yaml": "1a5a3da021ca9cfb6dde1deeb19a6d59f7137965cb8d931a0c04fe473f152129",
    "model.yaml": "5c326770a251a91eaefc34cdff1286105265bdc4551111caf04e4e6101f284e1",
    "project.yaml": "aded6b64ae223bb0a39c856456bc9ce5a4c214684e3f147abe59b62552732b3b",
    "synthetic.yaml": "69785b159e118ff9e7b6128d161851119b966ff20b9d4becf0bf6b72a156a926"
  },
  "versions": {
    "pymc": "6.3.2",
    "pytensor": "3.3.3",
    "numpy": "2.5.3"
  },
  "fpr": {
    "fpr": 0.0196078431372549,
    "wilson_lo": 0.0066903672665462426,
    "wilson_hi": 0.05605829125262214,
    "bootstrap_lo": 0.0,
    "bootstrap_hi": 0.044032123238595615,
    "n_usable": 153,
    "n_insufficient": 7,
    "block": "world",
    "n_blocks": 40
  },
  "years": 3.0,
  "call_probability": 0.975
}
```

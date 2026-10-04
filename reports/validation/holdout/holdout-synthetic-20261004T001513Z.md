# Hold-out prediction, SYNTHETIC dry run (holdout-synthetic-20261004T001513Z)

**Result: PASS**. Observed held-out detections fall inside the 90% predictive interval for **98.0%** of 50 site-folds (target at least 80%).

Dry run, not Gate 4: simulated sites drawn from the priors, instrument settings from `config/synthetic.yaml`. Gate 4 runs on real detections.

## Calibration: predicted vs observed detections

| bin   |   site_folds |   predicted |   observed |
|:------|-------------:|------------:|-----------:|
| <0.5  |         16.0 |         4.1 |        4.0 |
| 0.5-2 |         22.0 |        22.3 |       23.0 |
| 2-5   |         12.0 |        30.2 |       30.0 |

Fits failing diagnostics: 0 of 5.

## Run manifest

```json
{
  "run_id": "holdout-synthetic-20261004T001513Z",
  "created_at": "2026-10-04T00:15:13.712792+00:00",
  "git_sha": "938417d8f17e0a9c7fabe1a94c4254bd5d5d055c",
  "git_dirty": false,
  "config_sha256": {
    "impact.yaml": "04043a72046ae032c34f072d49d808d2b5c5b8961dcc20c1df23c843420def29",
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
  "holdout": {
    "passed": true,
    "share_inside": 0.98,
    "n_site_folds": 50,
    "target": 0.8
  },
  "kind": "synthetic",
  "n_folds": 5
}
```

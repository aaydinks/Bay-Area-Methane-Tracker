# 0012: Telling clouds from methane plumes in the Sentinel-2 retrieval: what is feasible

- **Status:** accepted
- **Date:** 2026-10-31

## Context

The Sentinel-2 retrieval (multi-band multi-pass, `sentinel2/retrieval.py`) compares band 12 with
band 11 on a target pass and a clean reference pass. Clouds, thin cirrus, cloud edges and cloud
shadows in either pass change that ratio and leave plume-like candidates for `detect.py`. Two
pieces of the current code handle clouds crudely:

- `masks.py` drops pixels with blue (B02) reflectance above 0.25 and applies fixed band 12 and
  water (NDWI) limits.
- `valid_frac` comes from the tile-level `eo:cloud_cover` (ADR 0007). A pass counts as usable
  at `valid_frac >= 0.7`.

The tile figure can be badly wrong for a 6 km site window. The 2025-08-01 pass over tile
T10SEG (relative orbit 113) is listed as 42% cloudy, so it is set aside. Its L2A scene
classification shows no cloud in the 6 km window around Newby Island. The reverse also happens:
a mostly clear tile can have its cloud over the site.

The question here is whether a model that separates clouds from plumes is feasible: are there
usable labels, are their terms compatible with publishing, can pixels be fetched, what must it
beat, and which of the hoped-for results can be tested at all. Everything below was checked
live on 2026-10-31 unless marked "check". Sentinel-2 sees only plumes of about 1 to 2 t/hr and
up (Gorroño et al. 2023, AMT 16:89–107, doi:10.5194/amt-16-89-2023, over uniform surfaces;
the paper gives conflicting figures for varied surfaces).

## Findings

### Cloud labels: open and plentiful

| Dataset | Licence (as stated) | Size | Level | Classes | Bay Area? |
|---|---|---|---|---|---|
| **CloudSEN12+ v1.1** (Aybar et al. 2024, *Data in Brief* 56:110852, doi:10.1016/j.dib.2024.110852), Hugging Face `tacofoundation/cloudsen12` | CC0 1.0 | 50,247 patches; 10,000 expert-labelled 509 x 509 at 10 m, plus scribble and unlabelled | L1C and L2A | clear, thick cloud, thin cloud, shadow | Yes: three expert-labelled sites (one on tile T10SEG, the Newby Island tile) and 31 sites on the US West Coast |
| Sentinel-2 Cloud Mask Catalogue (Francis et al. 2020, doi:10.5281/zenodo.4172871) | CC BY 4.0 | 513 subscenes, 1022 px at 20 m | L1C | clear, cloud, shadow | One subscene on the Central Coast |
| KappaSet (Domnich et al. 2021; data doi:10.5281/zenodo.7100327) | CC BY 4.0 | 9,251 tiles | L1C | clear, shadow, semi-transparent, cloud | check |
| Baetens and Hagolle 2019 (zenodo 1460961) | CC BY 4.0 | 38 scenes at 60 m | L1C | cloud, shadow, land, water, snow | check |
| Hollstein et al. 2016 | CC BY-NC 4.0 | 59 scenes, polygons | L1C | cloud, cirrus, shadow, water, snow, clear | check |
| CMIX PixBox-S2 and GSFC (Skakun et al. 2022) | CC BY 4.0 | 17,351 pixels; 28 scenes | L1C | 10 and 4 classes | GSFC: Maryland only |

CloudSEN12+ is the one to use:

- **Splits:** it has an official train, validation and test split. Every site (ROI) sits in
  exactly one split.
- **Dates:** each site has about five dates on one fixed grid. 193 of the 195 test sites have
  both a clear date and a cloudy date, so multi-pass pairs can be built from it.
- **Baselines:** its `cloudsen12-extra` collection carries precomputed Sen2Cor, s2cloudless and
  UNetMobV2 masks for every patch.
- **Licence conflict (check):** older copies disagree. The v1 Zenodo record is restricted with
  no licence, and `csaybar/CloudSEN12-nolabel` says CC BY-NC 4.0. The two v1.1 cards checked
  here, `tacofoundation/cloudsen12` at revision `f9490f7` and `isp-uv-es/CloudSEN12Plus` at
  `2bcd2e9`, both say CC0. Only the v1.1 copy is used.

### Plume labels: scarce, and every real-label set is non-commercial

| Dataset | Licence (as stated) | Size | Sensor | Labels | Clouds labelled? |
|---|---|---|---|---|---|
| MARS-S2L (UNEP IMEO; arXiv:2511.21777), `UNEP-IMEO/MARS-S2L` | CC BY-NC-SA 4.0 | about 88,000 images, about 5,500 with a plume, 1,315 sites | Sentinel-2 L1C (6 bands), Landsat | manual | Model-made cloud masks only |
| CH4Net (Vaughan et al. 2024, AMT), `av555/ch4net` | CC BY-NC-ND 4.0; terms must be accepted | 10,046 images, 925 with a plume, 23 sites in Turkmenistan | Sentinel-2 L1C | manual | No |
| S2CH4 (Gorroño et al.), doi:10.7910/DVN/KRNPEH | CC0 1.0 | 1,345 files, 3 oil and gas sites | Sentinel-2 L1C | synthetic (injected) | No |
| STARCOP (Růžička et al. 2023), doi:10.5281/zenodo.7863343 | CC BY-NC 4.0 | 1,878 plume tiles | AVIRIS-NG, WorldView-3, EMIT | manual | No |
| Methane Hot Spots (Kumar et al. 2023) | none stated | over 10 TB | AVIRIS-NG | from Carbon Mapper maps | No |
| IMEO Eye on Methane export | CC BY-NC-SA 4.0 | point detections, no masks | Sentinel-2, Landsat, EMIT, others | analyst-checked | No |

None of these covers a California landfill. In the pilot area itself, Sentinel-2-sized plumes
are rare:

- EMIT has 4 plume complexes in the pilot area.
- The Carbon Mapper catalog lists 614 plumes near the pilot sites. 407 carry a rate, and only
  14 of those are 2 t/hr or more.
- Only 7 plume days have a same-day pass at 20% tile cloud or less (`datasets/sentinel2/`).
- Gate 2 has not been passed.

Published work names clouds, thin cirrus and cloud shadow as the main source of false
Sentinel-2 plume detections: Varon et al. 2021, CH4Net, the MARS-S2L paper, and Rouet-Leduc and
Hulbert 2024.

### Carbon Mapper terms and what they mean for each design

The terms at carbonmapper.org/terms (version dated 13 January 2026) do three things:

- They allow derived works for non-commercial use only.
- Anything shared must carry the same non-commercial terms.
- Carbon Mapper can revoke the licence at any time.

They say nothing about non-commercial model training, or whether a trained model counts as a
derived product (check). `config/data_terms.yaml` keeps Carbon Mapper unconfirmed and
restricted. For each design this means:

- **Trained on Carbon Mapper plumes:** the weights would inherit the non-commercial terms and
  the open question, so they could not be published. There are also too few Sentinel-2-sized
  plumes to train on.
- **Tested against Carbon Mapper plumes:** allowed internally. Any figure derived from it
  stays restricted until the terms are confirmed.
- **No Carbon Mapper data in training or test labels:** the weights depend only on CC0 data
  and the project's MIT code, so they and their outputs are publishable. **Chosen.**

### Pixel source

Four ways to get pixels now work:

- **Copernicus Data Space (login): works.** The `.env` credentials returned a token, and one
  live call fetched the L2A scene classification file (1.8 MB) of
  `S2B_MSIL2A_20250801T184919_N0511_R113_T10SEG`. File downloads work through
  `zipper.dataspace.copernicus.eu`. The documented `download.dataspace.copernicus.eu` host did
  not resolve from this machine.
- **Google Cloud's public L1C mirror (no login):** already used by `sentinel2/crops.py`. A
  13-band 6 km window took about 190 s, reading the bands one after another.
- **AWS L1C bucket `sentinel-s2-l1c`:** answered an anonymous HTTPS request for one band file
  on 2026-10-31 (HEAD 200, range GET 206, valid JPEG 2000). ADR 0007 records it as
  requester-pays, so whether the bucket policy changed is "check". One file is not enough to
  rely on.
- **Earth Search Collection-1 L2A COGs (no login):** include the scene classification (`scl`)
  and Sen2Cor cloud probability (`cloud`), but no band 10.

**ADR 0004.** Its pixel-source question is settled: L1C pixels come from the Google mirror,
with Copernicus Data Space as a second source. Its signal-to-ppb question stays open. Varon et
al. 2021 (AMT 14:2771–2785, doi:10.5194/amt-14-2771-2021) gives a forward model inverted pixel
by pixel, not a lookup table, and its radiative transfer code is available only on request. So
plume strength here is expressed as fractional absorption in band 12, not ppb or t/hr.

### Baselines any model must beat

1. **The current threshold mask** (`masks.py`).
2. **Sen2Cor scene classification (L2A SCL):** classes 3 (cloud shadow), 8 and 9 (cloud medium
   and high probability) and 10 (thin cirrus).
3. **s2cloudless** (PyPI `s2cloudless` 1.7.3, LightGBM, CC BY-SA 4.0): needs L1C bands B01, B02,
   B04, B05, B08, B8A, B09, B10, B11 and B12. CMIX (Skakun et al. 2022, *RSE* 274:112990)
   reported overall accuracy of 86.3% for s2cloudless and 81.2% for Sen2Cor on PixBox-S2.

A reference that is not a pass/fail baseline: UNetMobV2-V2, the CloudSEN12+ authors' network
(CC0 weights), also precomputed in `cloudsen12-extra`. It needs a deep-learning runtime.

### Masked pretraining

Masked autoencoders learn from unlabelled images by hiding patches and predicting them (He et
al. 2022, CVPR, doi:10.1109/CVPR52688.2022.01553). Sentinel-2 versions exist:

| Model | Input | Licence |
|---|---|---|
| SSL4EO-S12 (Wang et al. 2023; MAE, DINO and MoCo weights for 13-band L1C, shipped in torchgeo as `ViTSmall16_Weights.SENTINEL2_ALL_MAE` and others) | 13-band L1C | weights CC BY 4.0 |
| Prithvi-EO-2.0 | HLS, 6 bands | Apache 2.0 |
| Clay | several sensors | Apache 2.0 |
| DOFA | any channels | weights CC BY 4.0 |
| TerraMind | several sensors | Apache 2.0 |
| Copernicus-FM | several sensors | weights CC BY 4.0 |

This is the route when labels are scarce. Here the scarce labels are plumes, and pretraining
does not fix that: plume scarcity is a test problem, not a training one.

## What can and cannot be tested

| Hoped-for result | Testable now? | How |
|---|---|---|
| Fewer cloudy windows wrongly counted as usable, and more usable passes | **Yes** | Window-level clear share against expert labels on held-out CloudSEN12+ sites, including the West Coast ones |
| Fewer false Sentinel-2 detections | **Yes** | Cloud-caused multi-pass candidates per scene on held-out CloudSEN12+ date pairs, with synthetic plumes injected to check that real-looking plumes survive the mask |
| Narrower 90% ranges and a smaller minimum detectable drop | **Only in simulation** | No real fit exists and the Sentinel-2 detection curve is unsourced (`confirmed: false`). Any figure is labelled simulated |
| Sentinel-2 candidates later confirmed by EMIT or Carbon Mapper | **No** | 14 large Carbon Mapper plumes and 7 cropped plume days give no power. Descriptive only, and restricted where it uses Carbon Mapper |

## Options considered

1. **Train on Carbon Mapper plumes.** Rejected: too few Sentinel-2-sized plumes, and the
   weights could not be published.
2. **Train on a real Sentinel-2 plume set** (MARS-S2L or CH4Net). Rejected for training:
   - Both are non-commercial; MARS-S2L is also ShareAlike, CH4Net also NoDerivatives.
   - CH4Net needs terms accepted, which only the user may do.
   - MARS-S2L carries only 6 bands, and neither covers landfills.
   - MARS-S2L stays a possible test-only check of real-plume survival, credited, with no
     weights trained on it.
3. **A per-pixel cloud and shadow classifier trained on CloudSEN12+, with plume survival
   checked by injection.** Chosen.
4. **Masked pretraining or a foundation model.** Deferred:
   - Cloud labels are not scarce.
   - Pretraining does not create plume labels.
   - It would add a deep-learning runtime to every CI run, because CI installs all extras.
5. **No model: use Sen2Cor or s2cloudless per site.** This is the comparison every model
   claim must beat. Replacing the tile-level `valid_frac` with a per-site mask is a separate
   change that needs no model.

## Decision

- **Model.** The smallest model first: scikit-learn gradient-boosted trees
  (`HistGradientBoostingClassifier`).
  - It classifies each 20 m pixel as clear, cloud (thick or thin) or cloud shadow.
  - Inputs are the 13 L1C bands, a few band ratios, and local means and spreads.
  - Plumes are not a training class. A plume class trained on the project's own injected
    plumes would be graded against itself. Plume survival is checked instead.
- **Training data.** CloudSEN12+ v1.1 expert-labelled 509 px patches, pinned to a revision,
  from the official train and validation splits only.
- **Held out.**
  - The official test split, plus every site on the US West Coast (32 to 49 N, 125 to 114 W,
    reported as a regional subset).
  - Splits are by site, so all dates of a site sit in the same split.
  - Training patches on a tile that also holds a held-out patch are dropped.
  - No pixel-level split.
- **Plumes.** Synthetic absorption is added to bands 11 and 12 of held-out patches, in
  fractional-absorption units. It is used only to test that masks do not remove plumes.
- **Baselines.** The threshold mask, Sen2Cor and s2cloudless, with UNetMobV2-V2 as a reference.
  The claim and the success rule are pre-registered in ADR 0013 before any held-out number is
  seen.
- **Carbon Mapper.** Not used for training or test labels.
- **Storage.** Training data and weights stay out of git: downloads in `data/raw/cloudsen12/`,
  weights in `data/processed/`. CI tests use small recorded fixtures and no network.

## Consequences

- A model trained this way is publishable. Its inputs are CC0, s2cloudless outputs are used
  only as a baseline, and no restricted data enters it.
- **If the model does not beat the best baseline,** it is not published as a result. The report
  says so plainly and recommends the per-site baseline instead.
- **The per-site `valid_frac` change** (Sen2Cor or s2cloudless per site instead of the tile
  figure) is worth doing whatever the model's result. It is left to its own change.
- **Plume strength stays in fractional absorption** until ADR 0004 has a signal-to-ppb table.
  No result here is stated in t/hr.
- **Running the model on every pilot pass costs time.** There are 2,101 scenes, and a 13-band
  window takes about 3 minutes from the Google mirror. Running it on all of them needs parallel
  or reduced-resolution reads.

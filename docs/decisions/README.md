# Decision records

One short file per decision: context, options, choice, consequences. Copy `0000-template.md`.

| ADR | Decision | Due |
|---|---|---|
| 0001 | Carbon Mapper API: endpoints, fields, footprint/coverage availability, rate limits | week 1 |
| 0002 | [Wind product and U_eff](0002-wind-product.md) (proposed): HRRR primary, ERA5 cross-check | week 3 |
| 0003 | Detection-probability curves per instrument: written as [0015](0015-detection-curves.md) | week 3–4 |
| 0004 | Open Sentinel-2 pipeline: inputs, license, what was reused | week 3 |
| 0005 | Priors and prior predictive check ([proposed](0005-priors.md)) | week 5 |
| 0006 | [Repair call rule](0006-repair-call-rule.md): calls at P = 0.975, intervals at 90% | week 9 |
| 0007 | [Public sources needing no login](0007-public-sources.md): EMIT CMR, Sentinel-2 STAC, EPA GHGRP | week 1–2 |
| 0008 | [Site traits as model covariates](0008-site-covariates.md) (accepted): closed, log area; empty by default | Month 2 |
| 0009 | [Public website and publishing database](0009-website-and-database.md) (accepted): Cloudflare Pages behind Access, Astro, Supabase snapshots with visibility and restricted flags, build-time data | Month 2 |
| 0010 | [Dated checks as the unit of the before/after test](0010-dated-checks.md) (accepted): one registry of inspections, notices, repairs and plume notices, one test | Month 2 |
| 0011 | [Chunked and out-of-core processing](0011-chunked-processing.md) (accepted): measured; tables stay in pandas; Sentinel-2 search pages of 100 and parallel band reads | Month 2 |
| 0012 | [Telling clouds from plumes in the Sentinel-2 retrieval: feasibility](0012-cloud-plume-feasibility.md) (accepted): CloudSEN12+ (CC0) for cloud labels, no real plume labels usable for training, pixels from the Google mirror or Copernicus Data Space, a small tree model against Sen2Cor and s2cloudless | Month 2 |
| 0013 | [Pre-registered test of the Sentinel-2 cloud model](0013-cloud-model-preregistration.md) (accepted): held-out sites and tiles, false-usable rate and cloud-caused detections against the tile rule, threshold mask, Sen2Cor and s2cloudless, 90% site bootstrap, published only if it passes | Month 2 |
| 0014 | [Checking the cloud model on recent pilot passes](0014-cloud-model-recent-passes.md) (accepted): on 2025 passes the model matched Sen2Cor's clear and cloudy calls, but kept flagging rooftops, dark ponds and parts of the landfills as cloud or shadow on clear days, so the check failed; `valid_frac` moves to the per-site Sen2Cor share | Month 2 |
| 0015 | [Detection curves per instrument and the emission floor](0015-detection-curves.md) (proposed): sourced q50 and width for Tanager-1, EMIT, aircraft and Sentinel-2, floor 18 kg/hr, all unconfirmed | Month 2 |
| 0016 | [An instrument enters a fit only once its plume search has run](0016-searched-instruments.md) (accepted): each instrument names its plume sources; the model fit, the repair checks and the hold-out check leave out an instrument with no plume table from any of them (an empty table counts) and record why; `--include-unsearched` keeps one on purpose | Month 2 |
| 0017 | [Display-only data on the public website](0017-display-only-data.md) (accepted): a source confirmed for display only keeps its rows restricted and marked display-only; read views give the public build dots without rates, counts, estimates and results, and the downloads leave them out | Month 2 |
| 0018 | [Two regions: the Bay Area and the North Valley](0018-regions.md) (accepted): regions as one list in config; five North Valley counties, all west of 120°W so the map projection stays; air district by overlay; the screening tier built from CalRecycle's list and boundary layer | Month 2 |
| 0019 | [Measures beyond the methane estimate](0019-site-measures.md) (accepted): one long `site_metrics` table with a catalogue; CO2 shown as reported or as a plume count, never modelled; the methane tables get no gas column | Month 2 |
| 0020 | [How context measures and records are worded](0020-context-wording.md) (accepted): air monitors, population and CalEnviroScreen shown as labelled context, never attributed to a landfill and never ranked; records named by the regulator's own neutral terms | Month 2 |
| 0021 | [What the public site may show, two fits side by side, and old copies](0021-public-scope-two-fits.md) (accepted): an allowlist of regions and tiers enforced in the database, the build and the output check; an official fit plus an optional screening fit; a prune command for old review copies | Month 2 |
| 0022 | [Sector tags and which plumes count for a landfill](0022-sector-tags.md) (accepted): a plume on or beside a landfill that Carbon Mapper tags with a sector other than solid waste is marked ambiguous and never assigned; a plume with no tag follows the distance rule; "Other" counts as another sector | Month 2 |
| 0023 | [The region term, and the coverage test at the real site count](0023-region-term-and-coverage-at-scale.md) (accepted): a pooled fit carries a yes/no North Valley term and stops without it; the coverage test can take the sites, regions and pass counts of a real fit, and each region must pass; the first screening fit covers all 52 sites and supplies the 47 the official fit lacks | Month 2 |
| 0024 | [CO2 plumes are counted near each landfill, and the count is review-only](0024-co2-plume-counts.md) (accepted): two counts per landfill and year from Carbon Mapper's CO2 plume and scene lists, with the methane geometry; a count is nearness, not attribution; CO2 pulls are a separate raw source; restricted until the terms for CO2 counts are confirmed | Month 2 |
| 0025 | [How each landfill is run comes from EPA's landfill gas file, as a list of facts](0025-epa-landfill-operations.md) (accepted): seven measures per landfill from EPA's California workbook, in EPA's units, under the file's edition; a blank is never a zero; landfills are matched by hand and an unchecked match says so on the page; the source is open | Month 2 |

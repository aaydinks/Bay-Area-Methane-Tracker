# Decision records

One short file per decision: context, options, choice, consequences. Copy `0000-template.md`.

| ADR | Decision | Due |
|---|---|---|
| 0001 | Carbon Mapper API: endpoints, fields, footprint/coverage availability, rate limits | week 1 |
| 0002 | [Wind product and U_eff](0002-wind-product.md) (proposed): HRRR primary, ERA5 cross-check | week 3 |
| 0003 | Detection-probability curves per instrument, with citations | week 3–4 |
| 0004 | Open Sentinel-2 pipeline: inputs, license, what was reused | week 3 |
| 0005 | Priors and prior predictive check ([proposed](0005-priors.md)) | week 5 |
| 0006 | [Repair call rule](0006-repair-call-rule.md): calls at P = 0.975, intervals at 90% | week 9 |
| 0007 | [Public sources needing no login](0007-public-sources.md): EMIT CMR, Sentinel-2 STAC, EPA GHGRP | week 1–2 |
| 0008 | [Site traits as model covariates](0008-site-covariates.md) (accepted): closed, log area; empty by default | Month 2 |
| 0009 | [Public website and publishing database](0009-website-and-database.md) (accepted): Cloudflare Pages behind Access, Astro, Supabase snapshots with visibility and restricted flags, build-time data | Month 2 |
| 0010 | [Dated checks as the unit of the before/after test](0010-dated-checks.md) (accepted): one registry of inspections, notices, repairs and plume notices, one test | Month 2 |
| 0011 | [Chunked and out-of-core processing](0011-chunked-processing.md) (accepted): measured; tables stay in pandas; Sentinel-2 search pages of 100 and parallel band reads | Month 2 |

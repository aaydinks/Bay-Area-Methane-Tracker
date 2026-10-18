# Carbon Mapper

**The data files in this folder are not committed.** Carbon Mapper's data are free for
non-commercial use, must be credited, and must not be redistributed. Only this README
and the pull manifests in `pulls/` are tracked; `.gitignore` keeps everything else out.
Run the commands below to rebuild the files locally.

```bash
uv run mw ingest carbonmapper --start 2022-08-01 --bbox=-123.64,36.89,-121.20,38.87
uv run mw datasets build --only carbonmapper
```

| File (local only) | Endpoint | Contents |
|---|---|---|
| `plumes_solid-waste.csv` | `/api/v1/catalog/plume-csv`, `sectors=6A` | Methane plumes labelled solid-waste disposal |
| `plumes_all-sectors.csv` | `/api/v1/catalog/plume-csv`, no sector filter | Every methane plume, so plumes with a missing or wrong sector label are not lost before attribution |
| `scenes_l2b-ch4-mfa-v3e.geojson` | `/api/v1/stac/search`, collection `l2b-ch4-mfa-v3e` | Scene outline, time, platform, and Carbon Mapper's detection limits for that scene (`pod10/50/90_kg_hr`) |

Both plume pulls ask for `plume_gas=CH4`, the nine-county box, `datetime` from
2022-08-01, and leave `instruments` unset. Asset links (signed image URLs) are dropped
from the tables.

## What the pull showed (2026-10-17)

These are summary counts, not the data. Confirm with Carbon Mapper that counts like these
may be published before the repository goes public.

- **613 methane plumes** in the nine-county box, 597 of them labelled solid waste (6A).
  By instrument: 405 GAO aircraft, 109 AVIRIS-3 aircraft (`av3`), 79 Tanager (`tan`),
  20 EMIT (`emi`).
- **Near the pilot sites** (within 3 km of the CalRecycle reference point): 269 at Newby
  Island, 17 at Potrero Hills, 6 near Acme Fill (all about 2.6 km away, so possibly a
  neighbouring source), none at Sonoma Central or Shoreline.
- **No-plume scenes are included.** The scene collection has 199 scenes. 81 of 98 EMIT
  scenes, 27 of 62 Tanager scenes and 3 of 39 AVIRIS-3 scenes have no plume. So this
  collection can serve as a pass table for Carbon Mapper's own looks. It may still be
  only the scenes Carbon Mapper processed, not every acquisition; ask Carbon Mapper.
- **Detection limits per scene.** Six scenes carry `cm:pod`: the emission rate detected
  10%, 50% and 90% of the time. The 50% values range from 116 to 355 kg/hr. These are
  Carbon Mapper's numbers for those scenes, not a sourced curve for
  `config/instruments.yaml` yet.
- **Versions are mixed.** Each plume carries the processing version of its rate
  (`emission_version`): v1 402, v3 125, v3a 3, v3b 3, v3c 17, v3d 45, v3e 18. The
  `collection_version_l3` and `collection_version_l4` filters had no effect without a
  token: even a made-up value returned the same 613 rows. Pinning one version therefore
  has to happen when the table is used, and pinning v3e would keep only 18 plumes.

## Token

None was needed for these endpoints (the API spec marks them token-optional). If
`CARBON_MAPPER_API_KEY` is set in `.env`, it is sent as a bearer token. The manifest
records whether a token was used.

## Terms and credit

Non-commercial use only; credit Carbon Mapper; do not share raw data. The exact credit
line and whether derived tables (counts, dates) may be published are still to be
confirmed with data@carbonmapper.org (see `DATA_TERMS.md`).

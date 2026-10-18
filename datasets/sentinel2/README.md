# Sentinel-2 Level-1C

Sentinel-2 is a check on large methane events (about 1 to 2 t/hr and up), not a main
detector. So this folder holds the full scene list but pixels only for a few chosen days.

| File | Contents |
|---|---|
| `scenes.geojson` | Every L1C scene touching the pilot box, 2022-08-10 to 2026-10-17 (2,101 scenes): `scene_id`, `acquired_utc`, `platform`, `relative_orbit`, `mgrs_tile`, `product_uri`, `cloud_cover_pct` (whole tile), outline |
| `crops/index.csv` | One row per crop: site, day, role, trigger, the plume day a reference serves, orbit, tile cloud cover, product, file |
| `crops/<site_id>/<day>_<tile>_<orbit>.tif` | 6 km x 6 km crop at 20 m around the site's reference point, five bands: B02, B03, B08, B11, B12 |
| `pulls/` | Manifests of the catalog searches |

## Which days are cropped

- **Plume days.** A Carbon Mapper or EMIT plume within 3 km of the site's reference point
  and a Sentinel-2 pass the same day with tile cloud cover of 20% or less. There are 7:
  Newby Island 2023-04-04, 2024-04-08, 2025-08-18 and 2026-07-14; Acme Fill 2026-05-18;
  Potrero Hills 2023-08-07 and 2026-05-18. Three other plume days were too cloudy.
- **Reference days.** For each plume day, the three most recent earlier clear days with no
  known plume within 3 days, on the same relative orbit where possible. The published
  Sentinel-2 method (multi-band multi-pass) compares a plume day with a clean reference
  pass of the same site. Sonoma Central and Shoreline have no plume days, so they get the
  three most recent clear days as baselines.

## Reading the crops

Values are the original digital numbers. Reflectance is
`(DN + offset_<band>) / quantification`; both numbers are read from each product's
metadata and written into the file's tags (for current products, offset -1000 and
quantification 10000). B02, B03 and B08 are 10 m bands averaged to 20 m; they feed the
water and cloud screens in `sentinel2/masks.py`. B11 and B12 are the two infrared bands
where methane absorbs.

## Sources

- Scene list: Earth Search STAC (`earth-search.aws.element84.com/v1`, collection
  `sentinel-2-l1c`, product type S2MSI1C). No login.
- Pixels: Google Cloud's public copy of the ESA L1C archive, bucket
  `gcp-public-data-sentinel-2`, read in small windows without a login. The AWS copy is
  requester-pays, and Copernicus Data Space needs an account; neither was needed.

## Detection limit to cite

About 1,000 to 2,000 kg/hr on uniform ground, from "Understanding the potential of
Sentinel-2 for monitoring methane point emissions" (AMT preprint amt-2022-261). This
matches the project's 2 t/hr rule. Check against the published version before citing.

## Terms and credit

Copernicus open data licence. Credit line: "Contains modified Copernicus Sentinel data
[2023–2026]". The `plume_seen_by` column says which catalog flagged a day; check with
Carbon Mapper that naming its plume days this way is allowed before the repository goes
public.

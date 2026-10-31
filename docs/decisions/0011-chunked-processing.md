# 0011: Chunked and out-of-core processing: measured, and where it helps

- **Status:** accepted
- **Date:** 2026-10-31

## Context

"Streaming" in this decision means chunked, out-of-core processing: reading data in pieces so a step is faster
or fits in memory. It does not mean continuous or live monitoring; the tracker stays retrospective.

The pipeline is about to run on a schedule (refresh, datasets build, publish build, push), so it is worth
knowing where its time and memory go before choosing tools. The question was whether Polars (lazy and
streaming engine), DuckDB, PyArrow datasets, xarray with Dask chunks, or windowed cloud-optimised raster
reads (rioxarray, odc-stac, stackstac) would measurably help.

**How it was measured.** On Oct 31, 2026, on the owner's Mac (Apple M5 Pro), on the real data: 5 pilot sites,
outlines from the registry, every pull since Aug 1, 2022. Wall time and peak memory (maximum resident set size)
come from `/usr/bin/time -l`; the split inside a step comes from cProfile. Network figures are single runs on
one home connection and will vary. `mw publish push` was not measured: there is no database connection string
in `.env` yet.

**Where the time and memory go**

| Step | Wall time | Peak memory | Where the time goes |
|---|---|---|---|
| `mw refresh`, all sources | 34.8 s | 504 MB | the Sentinel-2 scene search |
| Sentinel-2 pull only | 30.5 s | 457 MB | 213 catalogue pages of 10 items (2,129 scenes, 23 MB of JSON) |
| EMIT pull only | 5.4 s | 264 MB | 309 scenes, 7 plume complexes |
| Carbon Mapper pull only | 7.6 s | 258 MB | 614 plumes, 210 scenes |
| Rebuild of the interim tables, no pulls | 5.1 s (2.5 s in-process) | 232 MB | imports about 1 s, run manifest 0.7 s, data work under 0.6 s |
| `mw datasets build`, local steps | 4.4 s | 616 MB | census blocks 4.0 s and 461 MB; the boundaries step exits 2 on the current raw layout |
| `mw datasets build --only` emit / sentinel2 / carbonmapper | 1.2 / 1.4 / 1.0 s | 176 / 453 / 174 MB | |
| `mw publish build` | 1.2 s | 170 MB | |
| One Sentinel-2 crop (5 bands, 6 km square) | 84.6 s; 87.5 s repeated | 215 MB | 294 sequential 16 KB range reads (20 MB) for a 650 KB file |
| One EMIT site window (3 layers, cloud-optimised GeoTIFF) | 6.2 s | | bytes fetched not measured |
| Model draws, demo run (zarr) | 0.18 s to open and summarise | 130 MB | 2.1 MB in memory, 2.4 MB on disk |
| `mw --help` (start-up) | 0.27 s warm, 0.88 s cold | 53 MB | |

**How big the tables are.** The largest interim table, the passes, has 2,177 rows. All interim Parquet files
together are 210 KB. A publication holds 2,177 passes, 614 plumes and 51 operator figures. With all 38 screened
landfills and ten years of passes the passes table would be about 40,000 rows, a few MB. Out-of-core engines
earn their place when a table does not fit in memory; these are three to four orders of magnitude short of that.

**Table engines on the real passes table** (group by site and instrument; each engine in its own process;
three runs, the work time is the typical one):

| Engine | Import | Work | Peak memory |
|---|---|---|---|
| pandas 3.0 (current) | 0.51 s | 31 ms | 122 MB |
| Polars 2.1, lazy scan, streaming engine | 0.17 s | 3 ms | 91 MB |
| DuckDB 1.5 | 0.02 s | 2 ms | 54 MB |
| PyArrow dataset | 0.55 s | 2.5 ms | 120 MB |

Every pipeline step already imports pandas and geopandas for geometry, schemas and attribution, so the faster
imports do not add up in practice, and 30 ms of work is lost in a 35 s refresh.

**Network-bound steps**

| Change | Result |
|---|---|
| Sentinel-2 search, page size 10 (current default) | 213 pages, 25.2 s |
| Page size 100 | 22 pages, 6.4 s, same 2,129 items |
| Page size 250 | 9 pages, 4.8 s |
| Page size 1000 | refused by the catalogue ("Internal server error") |
| Page size 100 and only the fields the pipeline uses | 3.4 s; 669 bytes per item instead of 10.8 KB, but the raw pull loses the asset and link records |
| Sentinel-2 crop, GDAL read chunks of 1 MB instead of 16 KB | 50.9 s, but 353 MB fetched instead of 20 MB |
| Sentinel-2 crop, one thread per band | 19.7 s and 21.4 s, 20 MB fetched, pixels identical |
| Both | 25.9 s, 550 MB fetched |

**Raw pull growth.** Every refresh keeps a full new pull, about 31 MB: 23 MB of Sentinel-2 scene records, 5 MB
of Carbon Mapper and 2.4 MB of EMIT. That is about 1.6 GB a year at one refresh a week, 3.2 GB at two and 11 GB
daily. The refresh re-reads every Sentinel-2 pull (0.09 s each; one pull in memory at a time, so memory does not
grow with the count). The scene records compress well: one 23.7 MB file is 1.0 MB gzipped.

## Options considered

1. **Polars, lazy and streaming.** Rejected. No measurable gain at these sizes, a new dependency, and a rewrite
   of code built on pandas, geopandas and pandera.
2. **DuckDB.** Already a declared dependency, though no code uses it yet. Not adopted for the pipeline tables
   for the same reason; it stays available for one-off queries over the CSV and Parquet copies.
3. **PyArrow datasets.** PyArrow already reads and writes every Parquet file under pandas. Partitioned
   datasets have nothing to partition at 210 KB.
4. **xarray with Dask chunks.** Rejected for the model draws: 0.58 s with Dask chunks against 0.18 s read
   eagerly, 30 MB more memory, and Dask is not a dependency. A real fit of 5 sites stores less than the
   10-site demo. The Sentinel-2 crops are 300 by 300 pixels.
5. **Windowed cloud-optimised reads (rioxarray, odc-stac, stackstac).** The pipeline already reads windows,
   not whole files: rasterio reads only the site's square over HTTP range requests, for Sentinel-2 and for
   EMIT. odc-stac and stackstac load cloud-optimised GeoTIFFs listed in a STAC catalogue. The Sentinel-2 L1C
   pixels the method uses are JPEG 2000 files on Google's public mirror, and Earth Search's L1C links point at
   a requester-pays AWS bucket, so neither tool applies without switching to the L2A cloud-optimised files.
   That would change the input to the retrieval, which is a method question for ADR 0004, not a speed one.
   rioxarray wraps the same GDAL reads. For those reasons these were not measured. EMIT windows already come
   from cloud-optimised files at about 6 s each.
6. **Concurrency where the time is network round trips.** Chosen, in two places.

## Decision

- **No out-of-core table engine.** pandas and geopandas stay for every table. No new dependencies, so
  `pyproject.toml` and `uv.lock` do not change.
- **Sentinel-2 search asks for 100 items a page.** The refresh's Sentinel-2 step drops from about 25 s of
  paging to about 6 s with the same items. 100 rather than 250 leaves room under whatever response limit made
  the catalogue refuse 1,000.
- **Keep full scene records in each raw pull.** Trimming fields would be faster still, but a raw pull is the
  record of what the source returned.
- **Sentinel-2 crops read their five bands at the same time,** one thread and one file handle per band. A crop
  takes about 20 s instead of about 85 s, with the same bytes fetched and identical pixels. Larger GDAL read
  chunks are rejected: they fetch 18 to 28 times more data.
- **Both changes land in their own pull request (#37).** Measured with it on the same data: a full refresh takes
  18.6 s instead of 34.8 s (the Sentinel-2 pull 11.5 s instead of 30.5 s), peak memory unchanged at about
  0.5 GB; the same crop takes 21.2 s instead of 84.6 s, with identical pixels, transform and CRS.
- **The scheduled pipeline builds only what a refresh changes** (`--only emit --only sentinel2 --only
  carbonmapper`); census and boundaries are annual and stay manual.

## Consequences

- A scheduled run is bound by the network, not by memory: peak memory stays near 0.5 GB and the tables stay in
  memory.
- Raw pulls grow by about 31 MB a refresh. At two refreshes a week that is about 3.2 GB a year, which this Mac
  holds easily. If it becomes a problem, gzip the Sentinel-2 scene records (23 times smaller) before reaching for
  anything else.
- **Revisit this decision** if any table passes about 1 GB or ten million rows; if the screening tier moves to
  per-pixel data over all 38 sites; if the Sentinel-2 retrieval grows to hundreds of crops per run (then run
  crops in parallel too, and ask ADR 0004 whether L2A cloud-optimised files are acceptable); or if a model run's
  draws stop fitting in memory.
- `mw publish push` still needs a timing once the connection string is in `.env`.

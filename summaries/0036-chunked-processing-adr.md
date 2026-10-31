# PR #36: Where the pipeline spends its time (ADR 0011)

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/36)

## In one sentence

Before the pipeline runs on a schedule, every step was timed on the real data, and the result is
that no tool for processing data in chunks is needed: the time goes to waiting on the internet.

## Why it was needed

The next step is a job that refreshes the data, rebuilds the tables and loads a review copy into the
website's database on its own. Tools that process data in pieces (out of memory, or in chunks) were
proposed to make that faster. Adopting one only makes sense where it measurably helps.

## What it adds

A decision record with the measurements:

- A full refresh of every source takes about 35 seconds and half a gigabyte of memory. 30 seconds of
  that is the search for Sentinel-2 scenes, which fetches 2,129 scene records ten at a time.
- The tables are tiny. The biggest, the satellite passes over the five sites, has 2,177 rows; all the
  working tables together are 210 KB. Faster table engines cut a 31-millisecond query to 3, which
  nobody would notice.
- Cutting one small image around a site from a Sentinel-2 scene takes about 85 seconds, because its
  five colour bands are fetched one after another in 294 small requests.
- The model's stored results are 2 MB and open in a fifth of a second.

The decision: keep the current table code; ask for Sentinel-2 records 100 at a time (search time from
25 to about 6 seconds, same records); fetch the five bands of an image at once (85 to about 20
seconds, identical pixels). Those two changes come in a separate pull request.

## What we learned

- The refresh was spending most of its time on round trips to a catalogue that hands out ten
  records per page by default. It refuses pages of 1,000.
- Each refresh keeps a full new copy of every source, about 31 MB. At two refreshes a week that is
  about 3 GB a year, which is fine; the Sentinel-2 records shrink 23 times when compressed if it
  ever matters.
- Every plume in the current snapshot comes from Carbon Mapper; NASA's own seven EMIT plume
  complexes do not reach it yet. That is outside this decision and is noted for a later change.

## Still to do

The two speedups; timing the database load once the connection string is in place; the scheduled job.

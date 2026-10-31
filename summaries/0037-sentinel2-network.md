# PR #37: Faster Sentinel-2 searches and image crops

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/37)

## In one sentence

The two slow steps found when the pipeline was timed (decision record 0011) now ask the internet
for more at once, which roughly halves a full refresh and makes each Sentinel-2 image crop four
times faster.

## Why it was needed

The pipeline is about to run on a schedule. Timing it showed that nearly all of a refresh was spent
asking a Sentinel-2 catalogue for scene records ten at a time, and that cutting a small image
around a site fetched its five colour bands one after another.

## What it adds

- The scene search asks for 100 records per page. A full refresh of every source now takes about
  19 seconds instead of 35, with the same 2,129 records.
- An image crop fetches its five bands at the same time. One real crop took 21 seconds instead of
  85, and the pixels are identical to the old crop.
- Two tests that run without the internet: one checks the page size, the other builds a crop from
  five small local files and checks the bands come out in the right order with the right values.

## What we learned

The catalogue refuses pages of 1,000 records, so 100 leaves a margin. Reading larger pieces of each
image file was also tried and rejected: it was faster than before but fetched 18 to 28 times more
data.

## Still to do

The scheduled job itself, and timing the load into the website's database once its connection
string is in place.

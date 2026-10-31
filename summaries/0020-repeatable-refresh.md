# PR #20: Add a repeatable refresh that feeds Carbon Mapper data to the model

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/20)

## In one sentence

One command, `mw refresh`, pulls every satellite and aircraft source again and rebuilds the model's input tables. It is safe to run on a schedule, and it is the first time Carbon Mapper's passes and plume rates reach the model.

## Why it was needed

The tracker looks back, but its sources publish late. Carbon Mapper plumes appear about a month after a flight, and older plumes are sometimes reprocessed at a newer version. So the inputs have to be rebuilt every so often, and each rebuild must give the same answer from the same downloads. A refresh also must never lose data when a source is down.

There was also a gap: no step wrote the Carbon Mapper tables the pass-and-detection step reads, so the model would have seen no aircraft or Tanager passes and no emission rates at all.

## What it adds

- **A single refresh command.** It uses the same date window and areas every time, set in the project configuration, from August 2022 up to today. It rebuilds the site list, the table of every pass over each site, the detections with rates, and the site traits. It also writes spreadsheet copies and a record of each run.
- **Carbon Mapper passes and plumes in the model inputs:**
  - Passes come from every processing version Carbon Mapper has published. The 402 older aircraft plumes are only in the oldest version.
  - EMIT passes come only from NASA's own list, so they aren't counted twice.
- **Safe repeats:**
  - Downloads are kept and merged, with each plume at its newest version.
  - A half-finished download is never used.
  - Temporary server errors are retried.
  - An expired Carbon Mapper token is dropped, since the data are open without one.
  - A source that is down is skipped, its earlier downloads are used, and the run reports the failure.

## What we learned

- **Aircraft days were counted several times over.** On a busy day the survey aircraft flew seven lines over Newby Island, each seeing the same 3 to 5 leak points. Adding all of them together gave about 11,800 kg/hr. Plumes in one pass are now added up, and a day's passes are averaged. That gives a median of about 1,700 kg/hr on aircraft days, close to what Tanager and EMIT see on their own passes there (about 1,650 kg/hr).
- **The first full run**, on provisional site outlines:
  - 309 EMIT scenes, 2,123 Sentinel-2 scenes, and 209 Carbon Mapper scenes with 614 plumes.
  - 2,171 passes over the five pilot sites, 1,286 of them usable.
  - 28 days with a plume: 24 at Newby Island and 4 at Potrero Hills.
- **No usable rate for 126 plumes at the sites:**
  - 111 have no published rate;
  - 15 fall on days with no usable pass.
- **The Carbon Mapper token saved locally had expired.** The refresh now carries on without it.

## Still to do

- **Site outlines.** The run used 500 m circles around each site's reference point; real outlines are the next step.
- **Sentinel-2 plume search.** It hasn't been run, so Sentinel-2 passes must stay out of any fit until it has.
- **Schedule the refresh.** It is ready to run on a timer once the first real fit is done.

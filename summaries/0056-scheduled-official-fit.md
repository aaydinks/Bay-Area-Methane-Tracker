# PR #56: Only the official fit in scheduled review copies

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/56)

## In one sentence

The twice-weekly refresh now becomes the reviewers' copy only when it carries the official model
fit and that fit still matches the refreshed data. Otherwise it is loaded as a draft and the run
says what changed.

## Why it was needed

- **Reviewers see the newest review copy.** On November 6 the scheduled run built a copy with no
  estimates, and for a few minutes it pushed aside the copy with the first real estimates (Newby
  Island and Potrero Hills).
- **PR 52 closed half of that.** It carried the newest model fit that passed its checks. But that
  fit was never compared with the refresh. After a new EMIT pass, a copy's passes would have been
  newer than its estimates, with nothing on the page to say so.
- **No usable fit still meant no estimates.** In that case PR 52's copy had none and still went to
  reviewers.

## What it adds

- **The official fit is named in the project settings**, as `publish.official_model_run`. It is
  now `fit-20261107T010105Z`. Changing it is a reviewed change on `main`, so a trial fit can't
  reach reviewers by being the newest.
- **A new step compares that fit with each refresh.** It compares the passes the fit used with
  the refreshed ones, pass by pass, on what the model reads.
  - Only the instruments the fit used count.
  - Sentinel-2 passes, which the fit leaves out until their plume search runs, are counted in the
    run's record but not compared.
  - Against today's data the fit matches: EMIT, Tanager-1 and the aircraft flights are equal, and
    1,301 Sentinel-2 rows are left out.
- **When the fit no longer matches, or none is usable, the copy stays a draft:**
  - It is built without estimates.
  - It is still loaded into the database, so the free plan never sees seven quiet days.
  - It is not shown to reviewers. They keep the copy with estimates.
  - The run stops with a notification that names the passes added or changed and says to fit
    again.

## What we learned

- **The November 6 run went through the installed launchd job.** Its log holds that run's
  output, and launchd counts one run with exit code 0.
- **It ran on a Friday at about 19:53.** That is not one of the job's times (Mondays and
  Thursdays at 08:00), so it was most likely started by hand. Who started it is not known.
- **The checkout had unsaved changes** at the time.

## Still to do

- **The fix reaches the Mac only when the owner's checkout pulls `main`.** Until then the
  installed job runs PR 52's code, which does no comparison.
- **PR 54's migration must be applied to the live database before that pull.** Code from PR 54 on
  cannot load into a database without the new columns.
- **Each new EMIT, Tanager-1 or aircraft pass needs a refit.** After one, every scheduled run
  stops at review until a new fit is checked and named. The site still has no way to show
  estimates from an older fit beside newer passes.

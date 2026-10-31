# PR #25: Dated checks of every type through the before/after test

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/25)

## In one sentence

The before/after test now runs on every kind of dated record at a landfill, not only on operator
repairs, so the website's checks page can show a measured change for inspections and notices too.

## Why it was needed

The records that exist in public documents are mostly Air District inspections and notices under
Rule 8-34, with CARB plume notices alongside them; operator repair logs are still being requested.
The old registry only had room for repairs. The checks page planned for the website lists every
dated record with the change that followed it, with the same 90% range and the same labels for all.

## What it adds

- One registry file, `checks.csv`, in place of `repairs.csv`. Each row has a type (Air District
  inspection, Air District notice, operator repair with its kind, CARB plume notice, other), the
  date and how exact it is, a description in the project's own words, and the source document. An
  official title such as a notice's formal name has its own field, because it may contain words the
  project itself never uses. The rule stands: no row without a source document.
- The same test for every type: twelve-month windows, a fourteen-day gap after the record, at least
  five usable passes on each side, control sites for shifts that hit everyone, a call only at 97.5%
  probability, and the smallest drop the site's own passes could have caught. The outcome table
  gains the type of record and keeps everything else.
- Decision record 0010, which also says that the placebo check applies to all types alike: a change
  that follows a notice is judged by the same standard as one that follows a repair.
- Tests for every type, for the required repair kind, for rejected types, and for the end-to-end
  run on simulated sites (163 fast tests, plus the slow one).

## What we learned

Nothing new about the data. One framing point was worth writing down: an inspection or a notice is
not expected to change emissions by itself, so a result after one is "what followed", never "what
it did". The pages say so.

## Still to do

Enter the records themselves, by hand, as the Air District and operators respond. The publishing
command will carry the type and the official title through to the website.

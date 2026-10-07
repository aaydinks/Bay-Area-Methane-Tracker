# PR #1: Project skeleton and Python environment

**Status:** merged October 3, 2026 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/1)

## In one sentence

Set up the empty repository as a working project, with the tools, settings
and safety rules every later step builds on.

## Why it was needed

The project plan describes a 12-week analysis with many moving parts:
satellite downloads, a statistical model, validation tests and a public
dashboard. Before any of that, the project needed one agreed place for each
piece, a reproducible software setup so results can be rerun exactly, and the
plan's guardrails written into settings rather than left to memory.

## What it adds

- **A reproducible environment.** Anyone can install the exact same software
  versions and rerun every result.
- **A settings folder where uncertain numbers are flagged.** Values such as
  the methane-to-CO2 conversion factors, the dollar value per tonne and each
  satellite's detection limit carry their source and a "confirmed" flag. A
  value still marked unconfirmed makes outputs "provisional".
- **The pipeline's outline.** One command for each step of the plan, from
  pulling data to building the dashboard. Steps not yet built say which week
  of the plan they belong to.
- **Guardrails from the plan, built in:**
  - A wording check that will block "saved", "real-time" or "violation" from
    any published page.
  - A data-terms file stating that the project is non-commercial, as Carbon
    Mapper's free terms require, and that raw downloads are never shared in
    the repository.
- **Automatic checks** that run on every change, plus the project plan itself.

## What we learned

Nothing new about methane yet; this is groundwork. The first automated check
failed on a tooling version name and then on notebook formatting; both were
fixed in the same pull request.

## Still to do

Everything analytical: the model, the data pulls and the tests. Those arrive
in the following pull requests.

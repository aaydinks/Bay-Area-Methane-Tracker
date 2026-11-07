# PR #46: Pass the allow-unconfirmed flag to the fit by name

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/46)

## In one sentence

The command that runs the main model on real data with provisional detection curves stopped
with an error before doing anything; it now runs.

## Why it was needed

The detection curves are sourced but not yet confirmed, so the only way to fit real data is the
provisional option. That option had never worked: the command handed the setting to the model
in a form the model did not accept, and it stopped at once. Nobody noticed because, until the
curves were sourced in PR 45, the fit could not run on real data anyway.

## What it adds

- The provisional option now reaches the model, so `mw model fit --allow-unconfirmed` runs.
- A test that runs the command with the option and checks the setting arrives.

## What we learned

The fault showed up on the first attempt to fit real data. Tests covered the refusal without the
option, but not the run with it.

## Still to do

Nothing for this change. The first recorded fit on real data follows once this is merged.

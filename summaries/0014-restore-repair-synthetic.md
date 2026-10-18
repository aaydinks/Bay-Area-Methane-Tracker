# PR #14: Restore the repair-test dry-run command

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/14)

## In one sentence

Puts back the command that runs the repair test on simulated data, which was lost when the stacked pull requests
were combined on main.

## Why it was needed

After pull requests #12 and #13 landed, every old branch was checked against main. All of their work was on main
except one thing: the `mw validate repair-synthetic` command. The code behind it was still there, but the command
that runs it had been dropped while the branches were merged into each other. Without it, the placebo and power
checks that set the repair call rule (ADR 0006) could not be rerun.

## What it adds

- The command again, with the same settings as before: 40 simulated worlds, 4 pseudo-repairs per world, 15 fits
  per tested drop.
- A test that fails if the command goes missing again.

## What we learned

A merge that reports no conflicts can still drop a change, when one branch removed a line that another branch
added. Comparing each old branch's files with main is what caught it.

## Still to do

Nothing for this change. The old branches can be deleted once this is merged.

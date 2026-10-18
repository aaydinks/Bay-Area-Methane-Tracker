# 0006: Repair call rule

- **Status:** accepted
- **Date:** 2026-10-03

## Context

The repair test reports the control-adjusted log effect
`log(E_after / E_counterfactual)` with a 90% interval and makes a call. The
plan first said to call "drop" or "rise" whenever the 90% interval excludes 0.
Gate 5 requires the placebo false-positive rate to be at most 10%.

A two-sided 90% interval excludes 0 about 10% of the time when nothing changed.
So under that rule, a perfectly calibrated test fails a 10% gate about half the
time.

The first synthetic dry run (`reports/validation/repair-synthetic/repair-synthetic-20261003T232115Z.md`)
showed it:
- 150 placebos, false-positive rate 0.129, Wilson 0.084–0.193, with symmetric
  errors (11 drops, 8 rises).
- All placebos came from one simulated world, so they were correlated. The site
  bootstrap ran from 0.03 to 0.25, and the run could not separate miscalibration
  from noise.

## Options considered

1. Loosen the gate to 15%. Rejected: the 10% gate comes from the project plan,
   and moving a gate after seeing a failure is the wrong direction.
2. Keep the 90% interval and change only what triggers a call. Calls are made at
   posterior probability 0.975 either way (two-sided 95%, nominal 5%).
3. Report 95% intervals everywhere. Rejected: the 90% interval is the
   project-wide convention for every published number.

## Decision

Option 2. `config/project.yaml: repair.call_probability = 0.975`.
- "drop" if P(effect < 0) ≥ 0.975.
- "rise" if P(effect < 0) ≤ 0.025.
- "inconclusive" otherwise.

Every result shows the 90% interval and P(decrease) next to the call. A 90%
interval that excludes 0 next to an "inconclusive" call is then readable.

The synthetic dry run now uses independent simulated worlds (40 × 4 placebos)
and bootstraps over worlds.

Decided in advance: if the rerun is still above 10% under a nominal-5% rule,
the model is miscalibrated. The next step would then be the effect interval's
coverage under the null and the gamma/delta priors, not a looser threshold.

## Consequences

- Power drops. Under the 90% rule the first dry run called a 50% drop in 22% of
  fits and a 75% drop in 59%. The rerun reports the new numbers and the minimum
  detectable effect, which is what makes an "inconclusive" result interpretable.
- Changing the threshold again means rerunning the dry run and, once real
  schedules exist, Gate 5.

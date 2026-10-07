# 0005: Persistence-model priors

- **Status:** proposed (revisit after sponsor review and the first real fits)
- **Date:** 2026-10-03

## Context

The model (docs/PLAN.md section 6) has few overpasses per site, so the
hierarchical priors carry real weight. The priors must cover plausible landfill
magnitudes without piling mass at the extremes. They must also keep the
rate-density width larger than the log-rate grid spacing (about 0.06 in ln q for
96 points between 50 and 20,000 kg/hr).

## Options considered

1. `sigma ~ HalfNormal(1)`, as in the first draft of the plan. It puts real
   mass near zero. That makes the rate density narrower than the grid spacing,
   so the quadrature becomes inaccurate, and the simulator and model disagree for
   those draws.
2. `sigma ~ LogNormal(ln 0.8, 0.4)`. It keeps sigma in roughly [0.37, 1.75]
   (95%), which spans narrow to very wide rate distributions while staying
   well above the grid spacing.

## Decision

Non-centered hierarchy, values in `config/model.yaml`:

| Parameter | Prior |
|---|---|
| alpha_f (logit mean emitting fraction) | Normal(-1, 1.5) |
| tau_f | HalfNormal(1) |
| alpha_mu (mean log rate, ln kg/hr) | Normal(ln 300, 1) |
| tau_mu | HalfNormal(0.75) |
| sigma | LogNormal(ln 0.8, 0.4) |

Prior predictive check (4,000 sites drawn from the prior, synthetic floor of
50 kg/hr):

| Quantity | 2.5% | 10% | 50% | 90% | 97.5% |
|---|---|---|---|---|---|
| E (t/yr, above-floor) | 34 | 118 | 1,056 | 7,090 | 15,583 |
| f | 0.013 | 0.042 | 0.28 | 0.79 | 0.94 |
| Qbar (kg/hr) | 74 | 124 | 487 | 2,062 | 4,275 |

0.1% of draws exceed 50,000 t/yr, and 0.03% fall below 1 t/yr.

## Consequences

- Gate 3 (synthetic recovery) draws its truths from these priors. A change here
  means rerunning Gate 3.
- The real floor `q_min` is still unset. The check must be repeated once it is
  chosen, because E is defined above the floor.

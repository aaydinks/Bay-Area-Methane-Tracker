"""Log-rate quadrature grid (docs/PLAN.md section 6.3).

Integrals over the emission rate q are taken in x = ln q, so no Jacobian is
needed: the rate distribution is a Normal(mu, sigma) density in x, truncated to
the grid range and normalized so that sum(w * h) == 1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class LogRateGrid:
    x: np.ndarray  # ln q at each node
    w: np.ndarray  # trapezoid weights in x

    @classmethod
    def build(cls, q_min: float, q_max: float, n_points: int) -> LogRateGrid:
        if not 0 < q_min < q_max:
            raise ValueError("need 0 < q_min < q_max")
        x = np.linspace(np.log(q_min), np.log(q_max), n_points)
        w = np.full(n_points, x[1] - x[0])
        w[[0, -1]] *= 0.5
        return cls(x=x, w=w)

    @property
    def q(self) -> np.ndarray:
        return np.exp(self.x)

    def integrate(self, values: np.ndarray) -> np.ndarray:
        """Integrate over the last axis of ``values`` (evaluated at the nodes)."""
        return values @ self.w


def rate_density(grid: LogRateGrid, mu: float, sigma: float) -> np.ndarray:
    """Truncated Normal(mu, sigma) density in ln q, normalized on the grid."""
    h = norm.pdf(grid.x, loc=mu, scale=sigma)
    return h / grid.integrate(h)


def mean_rate(grid: LogRateGrid, density: np.ndarray) -> float:
    """Mean emission rate while emitting, E[q | q_min <= q <= q_max], in kg/hr."""
    return float(grid.integrate(grid.q * density))


def truncated_lognormal_mean(mu: float, sigma: float, q_min: float) -> float:
    """Closed form E[q | q >= q_min] for q ~ LogNormal(mu, sigma); no upper bound.

    Used as a unit-test check on the grid integral.
    """
    a = np.log(q_min)
    return float(
        np.exp(mu + sigma**2 / 2)
        * norm.cdf((mu + sigma**2 - a) / sigma)
        / norm.cdf((mu - a) / sigma)
    )

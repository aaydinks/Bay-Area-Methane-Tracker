"""Hand-entered Air District and operator records (PLAN section 5, phase 2f).

Repair dates live in ``data/registry/repairs.csv``; every row cites a source document.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_repairs(path: Path) -> pd.DataFrame:
    raise NotImplementedError("repairs loader + schemas.repairs validation: week 4")

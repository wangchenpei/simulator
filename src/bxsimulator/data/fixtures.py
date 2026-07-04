from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bxsimulator.config import RunConfig
from bxsimulator.data.loader import assert_returns_df
from bxsimulator.data.offline_us_eu import DEFAULT_OUTPUT, load_offline_us_eu_returns, try_refresh_bundled_csv


def load_returns_csv(path: Path) -> pd.DataFrame:
    path = Path(path)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if resolved == DEFAULT_OUTPUT.resolve() or path.name.startswith("us_eu_long_annual"):
        try_refresh_bundled_csv()
        return load_offline_us_eu_returns()
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    return assert_returns_df(df)


def build_synthetic_returns(cfg: RunConfig, seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = cfg.returns.synthetic_years
    years = np.arange(2005, 2005 + n)
    dates = pd.to_datetime([f"{y}-12-31" for y in years])
    re = rng.normal(cfg.returns.synthetic_mean_equity, cfg.returns.synthetic_vol_equity, n)
    rb = rng.normal(cfg.returns.synthetic_mean_bond, cfg.returns.synthetic_vol_bond, n)
    rs = rng.normal(cfg.returns.synthetic_short_mean, 0.005, n)
    df = pd.DataFrame({"r_equity": re, "r_bond": rb, "r_short": rs}, index=dates)
    return assert_returns_df(df)

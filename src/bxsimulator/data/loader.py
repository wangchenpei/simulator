from __future__ import annotations

from typing import Protocol

import pandas as pd


class ReturnsLoader(Protocol):
    """Provides aligned columns: r_equity, r_bond, r_short (simple period returns)."""

    def load(self) -> pd.DataFrame:
        """Index: DatetimeIndex; columns r_equity, r_bond, r_short."""
        ...


def assert_returns_df(df: pd.DataFrame) -> pd.DataFrame:
    required = {"r_equity", "r_bond", "r_short"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"returns frame missing columns: {missing}")
    out = df[list(required)].copy()
    out = out.sort_index()
    return out.astype(float)

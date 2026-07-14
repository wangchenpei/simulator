from __future__ import annotations

import pandas as pd

from bxsimulator.config import RunConfig
from bxsimulator.engine.smooth import StepResult, simulate_period
from bxsimulator.engine.state import PortfolioState


def run_backtest(
    cfg: RunConfig,
    returns: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, PortfolioState]:
    """Iterate each row of returns as one rebalancing period (annual or monthly)."""
    df = returns.copy()
    if start is not None:
        df = df.loc[pd.Timestamp(start) :]
    if end is not None:
        df = df.loc[: pd.Timestamp(end)]
    if df.empty:
        raise ValueError("No returns rows in requested window")

    state = PortfolioState(
        main_equity=cfg.initial_main_value * cfg.equity_weight,
        main_bond=cfg.initial_main_value * cfg.bond_weight,
        reserve=float(cfg.initial_reserve),
    )

    rows: list[dict] = []
    for dt, row in df.iterrows():
        res: StepResult = simulate_period(
            state,
            float(row["r_equity"]),
            float(row["r_bond"]),
            float(row["r_short"]),
            cfg,
            dt,
        )
        state = res.state
        rows.append(
            {
                "date": pd.Timestamp(dt),
                "r_equity": float(row["r_equity"]),
                "r_bond": float(row["r_bond"]),
                "main_equity": res.state.main_equity,
                "main_bond": res.state.main_bond,
                "main_total": res.state.main_total(),
                "reserve": res.state.reserve,
                "total_nav": res.state.total_nav(),
                "main_begin": res.main_begin,
                "main_after_returns": res.main_after_returns,
                "r_main_before_transfer": res.r_main_before_transfer,
                "transfer_to_reserve": res.transfer_to_reserve,
                "transfer_from_reserve": res.transfer_from_reserve,
                "r_short": res.r_short,
            }
        )

    out = pd.DataFrame(rows)
    return out, state


def annual_summary(nav_df: pd.DataFrame) -> pd.DataFrame:
    """Year-over-year total NAV return from simulated series."""
    s = nav_df.set_index("date")["total_nav"].astype(float)
    r = s.pct_change().dropna()
    return pd.DataFrame({"date": r.index, "total_nav_return": r.values})

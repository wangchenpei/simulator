from __future__ import annotations

from pathlib import Path

import pandas as pd

from bxsimulator.config import RunConfig
from bxsimulator.data.fixtures import load_returns_csv
from bxsimulator.engine.backtest import run_backtest
from bxsimulator.engine.smooth import simulate_period
from bxsimulator.engine.state import PortfolioState


def test_simulate_period_constant_above_threshold_moves_to_reserve():
    cfg = RunConfig.from_yaml(
        Path(__file__).resolve().parents[1] / "configs" / "participating.yaml"
    )
    state = PortfolioState(main_equity=600_000.0, main_bond=400_000.0, reserve=0.0)
    re, rb = 0.10, 0.10
    res = simulate_period(state, re, rb, 0.02, cfg, pd.Timestamp("2020-12-31"))
    assert res.transfer_to_reserve > 0
    assert res.state.reserve > 0


def test_run_backtest_csv_smoke():
    cfg_path = Path(__file__).resolve().parents[1] / "configs" / "participating.yaml"
    cfg = RunConfig.from_yaml(cfg_path)
    csv_path = Path(__file__).resolve().parents[1] / "data" / "sample_returns.csv"
    returns = load_returns_csv(csv_path)

    nav, final = run_backtest(cfg, returns)
    assert len(nav) == len(returns)
    assert final.total_nav() > 0

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from bxsimulator.config import RunConfig
from bxsimulator.data.fixtures import load_returns_csv
from bxsimulator.engine.backtest import run_backtest
from bxsimulator.engine.smooth import simulate_period
from bxsimulator.engine.state import PortfolioState


def _flat_cfg(*, threshold: float = 0.065, max_fill: float = 1.0) -> RunConfig:
    cfg = RunConfig.from_yaml(
        Path(__file__).resolve().parents[1] / "configs" / "participating.yaml"
    )
    return replace(cfg, smoothing_threshold=threshold, max_fill_fraction_of_shortfall=max_fill)


def test_simulate_period_constant_above_threshold_moves_to_reserve():
    cfg = _flat_cfg()
    state = PortfolioState(main_equity=600_000.0, main_bond=400_000.0, reserve=0.0)
    re, rb = 0.10, 0.10
    res = simulate_period(state, re, rb, 0.02, cfg, pd.Timestamp("2020-12-31"))
    assert res.transfer_to_reserve > 0
    assert res.state.reserve > 0


def test_pending_main_fill_when_reserve_empty():
    cfg = _flat_cfg()
    state = PortfolioState(main_equity=600_000.0, main_bond=400_000.0, reserve=0.0)
    res = simulate_period(state, -0.10, -0.10, 0.0, cfg, pd.Timestamp("2020-12-31"))
    assert res.transfer_from_reserve == 0.0
    assert res.pending_main_fill == 165_000.0
    assert res.state.pending_main_fill == 165_000.0


def test_surplus_repay_pending_main_before_reserve_deposit():
    cfg = _flat_cfg()
    state = PortfolioState(
        main_equity=540_000.0,
        main_bond=360_000.0,
        reserve=0.0,
        pending_main_fill=165_000.0,
    )
    res = simulate_period(state, 0.20, 0.20, 0.0, cfg, pd.Timestamp("2021-12-31"))
    assert res.transfer_to_reserve == 0.0
    assert res.pending_main_fill == pytest.approx(43_500.0)
    assert res.pending_reserve_deposit == pytest.approx(121_500.0)


def test_bad_year_withdraws_pending_reserve_backlog():
    cfg = _flat_cfg()
    state = PortfolioState(
        main_equity=540_000.0,
        main_bond=360_000.0,
        reserve=200_000.0,
        pending_main_fill=0.0,
        pending_reserve_deposit=80_000.0,
    )
    res = simulate_period(state, -0.10, -0.10, 0.0, cfg, pd.Timestamp("2022-12-31"))
    assert res.transfer_from_reserve == 200_000.0
    assert res.pending_main_fill == 0.0
    assert res.pending_reserve_deposit == pytest.approx(28_500.0)


def test_run_backtest_csv_smoke():
    cfg_path = Path(__file__).resolve().parents[1] / "configs" / "participating.yaml"
    cfg = RunConfig.from_yaml(cfg_path)
    csv_path = Path(__file__).resolve().parents[1] / "data" / "sample_returns.csv"
    returns = load_returns_csv(csv_path)

    nav, final = run_backtest(cfg, returns)
    assert len(nav) == len(returns)
    assert final.total_nav() > 0

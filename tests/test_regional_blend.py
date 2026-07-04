from __future__ import annotations

from pathlib import Path

import pandas as pd

from bxsimulator.config import RunConfig
from bxsimulator.data.regional_blend import blend_regional_returns
from bxsimulator.engine.backtest import run_backtest


def test_regional_blend_us_only():
    df = blend_regional_returns({"US": 1.0}, {"US": 1.0})
    assert len(df) >= 40
    assert set(df.columns) == {"r_equity", "r_bond", "r_short"}


def test_regional_blend_mixed_overlap():
    df = blend_regional_returns({"US": 0.5, "UK": 0.5}, {"US": 1.0})
    assert int(df.index.min().year) == 1985
    assert "r_equity" in df.columns


def test_regional_backtest_smoke():
    cfg = RunConfig.from_yaml(Path(__file__).resolve().parents[1] / "configs" / "unified.yaml")
    returns = blend_regional_returns(cfg.equity_regions, cfg.bond_regions)
    nav, final = run_backtest(cfg, returns, start="2005-01-01", end="2024-12-31")
    assert len(nav) >= 15
    assert final.total_nav() > 0

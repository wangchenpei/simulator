from __future__ import annotations

from pathlib import Path

import pandas as pd

from bxsimulator.config import RunConfig
from bxsimulator.data.fixtures import load_returns_csv
from bxsimulator.data.offline_us_eu import build_us_eu_annual_table, write_us_eu_annual_csv
from bxsimulator.engine.backtest import run_backtest


def test_offline_us_eu_build_matches_bundled_csv():
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "offline" / "raw" / "components_annual.csv"
    built = build_us_eu_annual_table(raw_path=raw)
    assert len(built) == 41
    assert int(built["date"].min().year) == 1985
    assert int(built["date"].max().year) == 2025


def test_offline_us_eu_backtest_smoke(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "rebuilt.csv"
    write_us_eu_annual_csv(out, raw_path=root / "data" / "offline" / "raw" / "components_annual.csv")
    cfg = RunConfig.from_yaml(root / "configs" / "participating_us_eu.yaml")
    returns = load_returns_csv(out)
    nav, final = run_backtest(cfg, returns, start="1990-01-01", end="2025-12-31")
    assert len(nav) == 36
    assert final.total_nav() > 0


def test_bundled_offline_csv_loads():
    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "offline" / "us_eu_long_annual.csv"
    df = load_returns_csv(path)
    assert len(df) == 41
    assert df.index.min() == pd.Timestamp("1985-12-31")

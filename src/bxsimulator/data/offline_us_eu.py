from __future__ import annotations

from pathlib import Path

import pandas as pd

from bxsimulator.data.loader import assert_returns_df
from bxsimulator.paths import project_root

# Bundled raw tables live in the repo; rebuild with `python -m bxsimulator build-offline`.
_ROOT = project_root()
DEFAULT_RAW = _ROOT / "data" / "offline" / "raw" / "components_annual.csv"
DEFAULT_FTSE_PRICE = _ROOT / "data" / "offline" / "raw" / "ftse100_price_annual.csv"
DEFAULT_FTSE_DIV_YIELD = _ROOT / "data" / "offline" / "raw" / "ftse100_div_yield_annual.csv"
DEFAULT_OUTPUT = _ROOT / "data" / "offline" / "us_eu_long_annual.csv"

OFFLINE_NOTES = """
离线欧美长历史包（学习用，无需网络）：
- 美股：Robert Shiller 标普500含分红总回报（年度）
- 英股：FTSE 100 **总回报**（价格指数 + 股息再投资；1985–1999 股息率采用英国市场历史估计，2000+ 来自 FTSE 100 指数平均股息率）
- 债券：Shiller 长期国债总回报近似（年度）
- r_equity = w_us * us_equity + w_eu * eu_equity（默认 50/50，无汇率换算；记账货币仍可在 YAML 中设为 CNY）
- r_short = r_bond - 1.5%（下限 -5%），模拟短久期略低于长债
原始表见 data/offline/raw/components_annual.csv；价格指数与股息率分量见 ftse100_price_annual.csv / ftse100_div_yield_annual.csv。回测时优先从分量表实时合成（bundled CSV 为缓存）。勿在回测 run 时访问任何行情 API。
"""


def _project_root() -> Path:
    return project_root()


def _ftse100_total_return(price: pd.Series, div_yield: pd.Series) -> pd.Series:
    aligned = pd.concat([price, div_yield], axis=1, join="inner")
    aligned.columns = ["price", "yield"]
    return (1.0 + aligned["price"]) * (1.0 + aligned["yield"]) - 1.0


def _apply_ftse100_total_return(df: pd.DataFrame, raw_dir: Path) -> pd.DataFrame:
    price_path = raw_dir / "ftse100_price_annual.csv"
    yield_path = raw_dir / "ftse100_div_yield_annual.csv"
    if not price_path.exists() or not yield_path.exists():
        return df
    price = pd.read_csv(price_path).set_index("year")["price_return"].astype(float)
    div = pd.read_csv(yield_path).set_index("year")["div_yield"].astype(float)
    tr = _ftse100_total_return(price, div)
    out = df.copy()
    out["eu_equity"] = out["year"].map(tr).astype(float)
    if out["eu_equity"].isna().any():
        missing = out.loc[out["eu_equity"].isna(), "year"].tolist()
        raise ValueError(f"Missing FTSE 100 price/yield rows for years: {missing}")
    return out


def load_components_annual(raw_path: Path | None = None) -> pd.DataFrame:
    path = raw_path or DEFAULT_RAW
    if not path.exists():
        raise FileNotFoundError(f"Missing offline raw table: {path}")
    df = pd.read_csv(path)
    required = {"year", "us_equity", "eu_equity", "us_bond"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    df = df.sort_values("year").astype(
        {"year": int, "us_equity": float, "eu_equity": float, "us_bond": float}
    )
    df = _apply_ftse100_total_return(df.reset_index(drop=True), path.parent)
    return df.reset_index(drop=True)


def build_us_eu_annual_table(
    *,
    raw_path: Path | None = None,
    us_weight: float = 0.5,
    eu_weight: float = 0.5,
    start_year: int | None = None,
    end_year: int | None = None,
) -> pd.DataFrame:
    if abs(us_weight + eu_weight - 1.0) > 1e-6:
        raise ValueError(f"us_weight + eu_weight must be 1.0, got {us_weight + eu_weight}")

    raw = load_components_annual(raw_path)
    if start_year is not None:
        raw = raw[raw["year"] >= start_year]
    if end_year is not None:
        raw = raw[raw["year"] <= end_year]
    if raw.empty:
        raise ValueError("No rows after year filter")

    r_equity = raw["us_equity"] * us_weight + raw["eu_equity"] * eu_weight
    r_bond = raw["us_bond"].astype(float)
    r_short = (r_bond - 0.015).clip(lower=-0.05)

    dates = pd.to_datetime([f"{int(y)}-12-31" for y in raw["year"]])
    out = pd.DataFrame(
        {
            "date": dates,
            "r_equity": r_equity.values,
            "r_bond": r_bond.values,
            "r_short": r_short.values,
        }
    )
    out = out.set_index("date")
    return assert_returns_df(out).reset_index()


def write_us_eu_annual_csv(
    output: Path | None = None,
    *,
    raw_path: Path | None = None,
    us_weight: float = 0.5,
    eu_weight: float = 0.5,
    start_year: int | None = None,
    end_year: int | None = None,
) -> Path:
    out_path = output or DEFAULT_OUTPUT
    df = build_us_eu_annual_table(
        raw_path=raw_path,
        us_weight=us_weight,
        eu_weight=eu_weight,
        start_year=start_year,
        end_year=end_year,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, float_format="%.6f")
    return out_path


def load_offline_us_eu_returns() -> pd.DataFrame:
    """Build offline US/EU returns from bundled raw components (always up to date)."""
    df = build_us_eu_annual_table()
    out = df.set_index("date").sort_index()
    return assert_returns_df(out)


def try_refresh_bundled_csv() -> None:
    """Best-effort sync of the bundled CSV cache from raw components."""
    try:
        write_us_eu_annual_csv()
    except OSError:
        pass


def describe_offline_csv(path: Path | None = None) -> pd.DataFrame:
    p = path or DEFAULT_OUTPUT
    df = pd.read_csv(p, parse_dates=["date"])
    if df.empty:
        raise ValueError(f"Empty offline CSV: {p}")
    y0 = int(df["date"].min().year)
    y1 = int(df["date"].max().year)
    return pd.DataFrame(
        [
            {
                "file": str(p),
                "annual_start": y0,
                "annual_end": y1,
                "annual_years": len(df),
                "r_equity_mean": float(df["r_equity"].mean()),
                "r_bond_mean": float(df["r_bond"].mean()),
            }
        ]
    )

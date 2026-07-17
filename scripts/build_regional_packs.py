"""Build independent offline regional annual return CSVs (one-off maintainer script)."""
from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import pandas as pd

from bxsimulator.data.offline_us_eu import load_components_annual

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "offline" / "regions"
OUT.mkdir(parents=True, exist_ok=True)


def fred_annual_levels(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "bxsimulator/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    df = pd.read_csv(io.BytesIO(raw))
    date_col, val_col = df.columns[0], df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    s = df.dropna(subset=[val_col]).set_index(date_col)[val_col].astype(float).sort_index()
    return s.groupby(s.index.year).last()


def year_returns(levels: pd.Series) -> pd.Series:
    return levels.pct_change().dropna()


def bond_total_return_from_yield(yield_pct: pd.Series) -> pd.Series:
    """Par-bond style annual total return from constant-maturity yield (% pa)."""
    y = yield_pct.astype(float) / 100.0
    out = []
    years = list(y.index)
    for i, yr in enumerate(years):
        if i == 0:
            continue
        y0, y1 = float(y.iloc[i - 1]), float(y.iloc[i])
        duration = 7.0
        price_ret = -duration * (y1 - y0)
        coupon = y0
        out.append((yr, coupon + price_ret))
    return pd.Series(dict(out)).sort_index()


def write_series(path: Path, series: pd.Series, *, label: str) -> None:
    df = pd.DataFrame({"year": series.index.astype(int), "r": series.values})
    df.to_csv(path, index=False, float_format="%.6f")
    print(f"{label}: {path.name} {int(df['year'].min())}-{int(df['year'].max())} ({len(df)} rows)")


def main() -> None:
    comp = load_components_annual()
    write_series(OUT / "us_equity.csv", comp.set_index("year")["us_equity"], label="US equity")
    write_series(OUT / "uk_equity.csv", comp.set_index("year")["eu_equity"], label="UK equity")
    write_series(OUT / "us_bond.csv", comp.set_index("year")["us_bond"], label="US bond")

    # UK / CN / JP bonds from FRED 10Y yields (CN uses 3M treasury as short-end proxy)
    uk_y = fred_annual_levels("IRLTLT01GBM156N")
    jp_y = fred_annual_levels("IRLTLT01JPM156N")
    write_series(OUT / "uk_bond.csv", bond_total_return_from_yield(uk_y), label="UK bond")
    write_series(OUT / "jp_bond.csv", bond_total_return_from_yield(jp_y), label="JP bond")
    try:
        cn_y = fred_annual_levels("IRLTLT01CNM156N")
        write_series(OUT / "cn_bond.csv", bond_total_return_from_yield(cn_y), label="CN bond")
    except Exception:
        cn_y = fred_annual_levels("IR3TTS01CNQ156N")
        write_series(OUT / "cn_bond.csv", bond_total_return_from_yield(cn_y), label="CN bond (3M proxy)")

    # Japan equity: OECD Japan share price index
    jp_eq_lv = fred_annual_levels("SPASTT01JPM661N")
    write_series(OUT / "jp_equity.csv", year_returns(jp_eq_lv), label="JP equity")

    # China equity: CSI300 via akshare if available, else OECD China share prices
    cn_eq: pd.Series | None = None
    try:
        import akshare as ak

        raw = ak.index_zh_a_hist(symbol="000300", period="daily", start_date="20050101")
        close = pd.to_numeric(raw["收盘"], errors="coerce")
        close.index = pd.to_datetime(raw["日期"])
        close = close.sort_index()
        ye = close.groupby(close.index.year).last()
        cn_eq = ye.pct_change().dropna()
        cn_eq.index = cn_eq.index.astype(int)
    except Exception as exc:
        print("CSI300 akshare failed, fallback OECD China:", exc)
        cn_lv = fred_annual_levels("SPASTT01CNM661N")
        cn_eq = year_returns(cn_lv)

    write_series(OUT / "cn_equity.csv", cn_eq, label="CN equity")

    # Canada / Germany from OECD share price indices and FRED 10Y yields
    ca_eq_lv = fred_annual_levels("SPASTT01CAM661N")
    de_eq_lv = fred_annual_levels("SPASTT01DEM661N")
    write_series(OUT / "ca_equity.csv", year_returns(ca_eq_lv), label="CA equity")
    write_series(OUT / "de_equity.csv", year_returns(de_eq_lv), label="DE equity")

    ca_y = fred_annual_levels("IRLTLT01CAM156N")
    de_y = fred_annual_levels("IRLTLT01DEM156N")
    write_series(OUT / "ca_bond.csv", bond_total_return_from_yield(ca_y), label="CA bond")
    write_series(OUT / "de_bond.csv", bond_total_return_from_yield(de_y), label="DE bond")


if __name__ == "__main__":
    main()

from __future__ import annotations

import pandas as pd


def fred_series(series_id: str, start: str) -> pd.Series:
    """Load FRED graph CSV (no API key)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    df = pd.read_csv(url)
    cols = [str(c).strip() for c in df.columns]
    df.columns = cols
    date_col = cols[0]
    val_col = cols[1]
    s = pd.Series(df[val_col].astype(float).values, index=pd.to_datetime(df[date_col]))
    s = s.sort_index().tz_localize(None)
    return s.loc[pd.Timestamp(start) :].dropna()


def fred_fx_series(series_id: str, start: str) -> pd.Series:
    """Alias kept for USD/CNY etc."""
    return fred_series(series_id, start)


def fred_index_close(series_id: str, start: str, end: str | None = None) -> pd.Series:
    """Daily index level from FRED graph CSV (e.g. SP500)."""
    s = fred_series(series_id, start)
    if end is not None:
        s = s.loc[: pd.Timestamp(end)]
    if s.empty:
        raise RuntimeError(f"FRED series {series_id} empty for [{start}, {end}]")
    s.name = series_id
    return s.astype(float)


def hkd_cny_from_fred(start: str, usdcny_id: str = "DEXCHUS", usdhkd_id: str = "DEXHKUS") -> pd.Series:
    """HKD/CNY = (CNY per USD) / (HKD per USD)."""
    usdcny = fred_series(usdcny_id, start)
    usdhkd = fred_series(usdhkd_id, start)
    aligned = pd.DataFrame({"usdcny": usdcny, "usdhkd": usdhkd}).sort_index().ffill().dropna()
    s = aligned["usdcny"] / aligned["usdhkd"]
    s.name = "HKDCNY"
    return s.astype(float)

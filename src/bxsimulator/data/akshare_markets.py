from __future__ import annotations

from datetime import date

import pandas as pd

# Eastmoney US tickers often use exchange prefix + symbol.
_US_PREFIX_CANDIDATES = ("105", "106", "107")


def _require_akshare():
    try:
        import akshare as ak  # noqa: F401
    except ImportError as e:
        raise ImportError("Install live extras: pip install -e \".[live]\"  (akshare + yfinance)") from e


def _to_yyyymmdd(d: str | None, default: str) -> str:
    if d is None:
        return default
    return pd.Timestamp(d).strftime("%Y%m%d")


def _pick_close(df: pd.DataFrame) -> pd.Series:
    for col in ("收盘", "close", "Close", "收盘价"):
        if col in df.columns:
            s = df[col].astype(float)
            break
    else:
        raise ValueError(f"No close column in AkShare frame: {list(df.columns)}")

    for dcol in ("日期", "date", "Date"):
        if dcol in df.columns:
            idx = pd.to_datetime(df[dcol])
            break
    else:
        idx = pd.to_datetime(df.iloc[:, 0])

    s.index = idx.tz_localize(None) if getattr(idx, "tz", None) else idx
    return s.sort_index()


def download_us_close(symbol: str, start: str, end: str | None = None) -> pd.Series:
    """US ETF/stock daily close via AkShare (Eastmoney)."""
    _require_akshare()
    import akshare as ak

    ticker = symbol.split(".")[0].upper()
    start_s = _to_yyyymmdd(start, "20000101")
    end_s = _to_yyyymmdd(end, date.today().strftime("%Y%m%d"))
    last_err: Exception | None = None

    for prefix in _US_PREFIX_CANDIDATES:
        code = f"{prefix}.{ticker}"
        try:
            df = ak.stock_us_hist(
                symbol=code,
                period="daily",
                start_date=start_s,
                end_date=end_s,
                adjust="qfq",
            )
            if df is None or df.empty:
                continue
            s = _pick_close(df)
            s.name = symbol
            out = s.loc[pd.Timestamp(start) :]
            if end is not None:
                out = out.loc[: pd.Timestamp(end)]
            if not out.empty:
                return out.astype(float)
        except Exception as e:  # noqa: BLE001
            last_err = e

    msg = f"AkShare US hist empty for {symbol}"
    if last_err is not None:
        msg = f"{msg} ({last_err})"
    raise RuntimeError(msg)


def _sanitize_hk_prices(s: pd.Series, min_price: float = 1.0) -> pd.Series:
    """Drop invalid early rows (e.g. AkShare 2800.HK negative prints)."""
    import numpy as np

    s = s.astype(float).sort_index()
    ok = (s > min_price).values
    if not ok.any():
        return s.dropna()
    first_i = int(np.argmax(ok))
    return s.iloc[first_i:].dropna()


def download_hk_close(symbol: str, start: str, end: str | None = None) -> pd.Series:
    """HK stock/ETF daily close via AkShare."""
    _require_akshare()
    import akshare as ak

    code = symbol.split(".")[0]
    code = code.zfill(5)
    start_s = _to_yyyymmdd(start, "20000101")
    end_s = _to_yyyymmdd(end, date.today().strftime("%Y%m%d"))

    df = ak.stock_hk_hist(
        symbol=code,
        period="daily",
        start_date=start_s,
        end_date=end_s,
        adjust="qfq",
    )
    if df is None or df.empty:
        raise RuntimeError(f"AkShare HK hist empty for {symbol} ({code})")

    s = _pick_close(df)
    s = _sanitize_hk_prices(s)
    s.name = symbol
    out = s.loc[pd.Timestamp(start) :]
    if end is not None:
        out = out.loc[: pd.Timestamp(end)]
    if out.empty:
        raise RuntimeError(f"AkShare HK hist has no rows for {symbol} in [{start}, {end}]")
    return out.astype(float)


def download_akshare_close(symbol: str, start: str, end: str | None = None) -> pd.Series:
    upper = symbol.upper()
    if upper.endswith(".HK"):
        return download_hk_close(symbol, start, end)
    return download_us_close(symbol, start, end)

from __future__ import annotations

import io
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

STOOQ_BASE = "https://stooq.com/q/d/l/"


def yahoo_to_stooq_symbol(symbol: str) -> str | None:
    s = symbol.strip()
    upper = s.upper()
    if upper.startswith("^"):
        return s.lower()
    if upper.endswith("=X"):
        return None
    if upper.endswith(".HK"):
        return f"{s.split('.')[0]}.hk".lower()
    if "." in s and not upper.endswith(".HK"):
        return s.lower()
    return f"{s.lower()}.us"


def _looks_like_csv(text: str) -> bool:
    head = text.lstrip()[:500].lower()
    if "<html" in head or "<!doctype" in head or "encodeuricomponent" in head:
        return False
    first = head.splitlines()[0] if head else ""
    return first.startswith("date") or "date," in first


def download_stooq_close(symbol: str, start: str, end: str | None = None) -> pd.Series:
    stooq_sym = yahoo_to_stooq_symbol(symbol)
    if stooq_sym is None:
        raise ValueError(f"Symbol {symbol} has no Stooq mapping")

    url = f"{STOOQ_BASE}?s={stooq_sym}&i=d"
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/csv,text/plain,*/*",
            "Referer": "https://stooq.com/",
        },
    )
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except URLError as e:
        raise RuntimeError(f"Stooq download failed for {stooq_sym}: {e}") from e

    text = raw.decode("utf-8", errors="replace")
    if not _looks_like_csv(text):
        raise RuntimeError(
            f"Stooq returned non-CSV for {stooq_sym} (blocked or captcha). Try --price-source akshare."
        )

    df = pd.read_csv(io.StringIO(text))
    if df.empty:
        raise RuntimeError(f"Stooq returned empty data for {stooq_sym}")

    date_col = "Date" if "Date" in df.columns else df.columns[0]
    close_col = "Close" if "Close" in df.columns else "close"
    if close_col not in df.columns:
        close_col = df.columns[-2] if len(df.columns) >= 2 else df.columns[-1]

    s = df.set_index(pd.to_datetime(df[date_col]))[close_col].astype(float)
    s.index = s.index.tz_localize(None)
    s = s.sort_index()
    s.name = symbol

    out = s.loc[pd.Timestamp(start) :]
    if end is not None:
        out = out.loc[: pd.Timestamp(end)]
    if out.empty:
        raise RuntimeError(f"Stooq has no rows for {symbol} in [{start}, {end}]")
    return out

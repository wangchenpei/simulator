from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Literal

import pandas as pd

PriceSource = Literal["auto", "akshare", "stooq", "yahoo", "fred"]

DEFAULT_CACHE_DIR = Path("data/cache/prices")
DEFAULT_REQUEST_DELAY = 1.5

FRED_FALLBACK = {
    "SPY": "SP500",
    "^GSPC": "SP500",
    "GSPC": "SP500",
    "BND": "DGS10",
    "IEF": "DGS10",
}

# If primary symbol fails or is shorter, try these (longest history wins in auto mode).
SYMBOL_ALTERNATES: dict[str, list[str]] = {
    "^HSI": ["^HSI", "2800.HK"],
    "SPY": ["SPY"],
}


def _is_index_symbol(symbol: str) -> bool:
    return symbol.strip().startswith("^")


def _cache_path(cache_dir: Path, symbol: str, start: str, end: str | None) -> Path:
    key = f"{symbol}|{start}|{end or ''}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    safe = symbol.replace("/", "_").replace("=", "_").replace("^", "idx")
    return cache_dir / f"{safe}_{digest}.csv"


def _load_cache(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    if df.empty:
        return None
    s = df.set_index("date")["close"].astype(float)
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s


def _load_longest_symbol_cache(cache_dir: Path, symbol: str) -> pd.Series | None:
    safe = symbol.replace("/", "_").replace("=", "_").replace("^", "idx")
    files = sorted(cache_dir.glob(f"{safe}_*.csv"))
    best: pd.Series | None = None
    for path in files:
        s = _load_cache(path)
        if s is None or s.empty:
            continue
        s.name = symbol
        if best is None or s.index.min() < best.index.min():
            best = s
    return best


def _save_cache(path: Path, series: pd.Series) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": series.index, "close": series.astype(float).values}).to_csv(path, index=False)


def _trim_series(s: pd.Series, start: str, end: str | None) -> pd.Series:
    s = s.sort_index()
    out = s.loc[pd.Timestamp(start) :]
    if end is not None:
        out = out.loc[: pd.Timestamp(end)]
    if out.empty:
        raise RuntimeError(f"No rows for {s.name} in [{start}, {end}]")
    out.name = s.name
    return out.astype(float)


def _try_akshare(symbol: str, start: str, end: str | None) -> pd.Series:
    from bxsimulator.data.akshare_markets import download_akshare_close

    return download_akshare_close(symbol, start=start, end=end)


def _try_stooq(symbol: str, start: str, end: str | None) -> pd.Series:
    from bxsimulator.data.stooq import download_stooq_close

    return download_stooq_close(symbol, start=start, end=end)


def _try_fred(symbol: str, start: str, end: str | None) -> pd.Series:
    from bxsimulator.data.fred import fred_index_close

    sym = symbol.upper()
    if sym in ("^GSPC", "GSPC", "SPX", "SPY"):
        s = fred_index_close("SP500", start, end)
        s.name = symbol
        return s
    sid = FRED_FALLBACK.get(sym.split(".")[0], FRED_FALLBACK.get(sym))
    if sid is None:
        sid = FRED_FALLBACK.get(symbol)
    if sid is None:
        raise RuntimeError(f"No FRED fallback mapping for {symbol}")
    s = fred_index_close(sid, start, end)
    s.name = symbol
    return s


def _try_yahoo(
    symbol: str,
    start: str,
    end: str | None,
    request_delay: float,
    max_retries: int,
) -> pd.Series:
    from bxsimulator.data.yahoo import download_adj_close

    last_err: Exception | None = None
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(20 * attempt)
        elif request_delay > 0:
            time.sleep(request_delay)
        try:
            s = download_adj_close(
                symbol,
                start,
                end,
                cache_dir=None,
                use_cache=False,
                request_delay=0,
                max_retries=1,
            )
            s.name = symbol
            return s
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"yahoo: {last_err}")


def _chain_for_symbol(symbol: str, source: PriceSource) -> tuple[str, ...]:
    if source == "akshare":
        return ("akshare",)
    if source == "stooq":
        return ("stooq",)
    if source == "yahoo":
        return ("yahoo",)
    if source == "fred":
        return ("fred",)
    if _is_index_symbol(symbol):
        return ("stooq", "yahoo", "akshare", "fred")
    return ("akshare", "stooq", "fred", "yahoo")


def _try_step(
    symbol: str,
    step: str,
    start: str,
    end: str | None,
    request_delay: float,
    max_retries: int,
) -> pd.Series:
    if step == "akshare":
        return _try_akshare(symbol, start, end)
    if step == "stooq":
        return _try_stooq(symbol, start, end)
    if step == "fred":
        return _try_fred(symbol, start, end)
    if step == "yahoo":
        return _try_yahoo(symbol, start, end, request_delay=0, max_retries=max_retries)
    raise ValueError(step)


def _pick_longest_series(candidates: list[pd.Series]) -> pd.Series | None:
    best: pd.Series | None = None
    for s in candidates:
        if s is None or s.empty:
            continue
        if best is None or s.index.min() < best.index.min() or len(s) > len(best):
            best = s
    return best


def fetch_close_series(
    symbol: str,
    start: str,
    end: str | None = None,
    *,
    source: PriceSource = "auto",
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    max_retries: int = 3,
    pick_longest: bool = True,
) -> pd.Series:
    """Fetch daily close; in auto mode tries alternates/sources and keeps longest history."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cache_file = _cache_path(cache_dir, symbol, start, end) if cache_dir else None

    if use_cache and cache_dir is not None:
        cached = _load_cache(cache_file) if cache_file else None
        if cached is None:
            cached = _load_longest_symbol_cache(cache_dir, symbol)
        if cached is not None and not cached.empty:
            return _trim_series(cached, start, end)

    symbols = list(dict.fromkeys(SYMBOL_ALTERNATES.get(symbol, [symbol])))
    chain = _chain_for_symbol(symbol, source)

    collected: list[pd.Series] = []
    errors: list[str] = []

    for sym in symbols:
        sym_chain = chain
        if sym != symbol and sym.endswith(".HK"):
            sym_chain = ("akshare", "stooq", "yahoo")
        for step in sym_chain:
            if request_delay > 0:
                time.sleep(request_delay)
            try:
                s = _try_step(sym, step, start, end, request_delay, max_retries)
                s.name = symbol
                collected.append(s)
                if source != "auto" or not pick_longest:
                    break
            except Exception as e:  # noqa: BLE001
                errors.append(f"{sym}/{step}: {e}")
        if source != "auto" or not pick_longest:
            if collected:
                break

    series = _pick_longest_series(collected) if pick_longest else (collected[0] if collected else None)

    if series is None or series.empty:
        msg = f"No data for {symbol}"
        if errors:
            msg = f"{msg} ({'; '.join(errors[:6])}{'...' if len(errors) > 6 else ''})"
        raise RuntimeError(msg)

    if use_cache and cache_file is not None:
        _save_cache(cache_file, series)
    return _trim_series(series, start, end)


def fetch_close_batch(
    symbols: list[str],
    start: str,
    end: str | None = None,
    *,
    source: PriceSource = "auto",
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    max_retries: int = 3,
) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for sym in symbols:
        out[sym] = fetch_close_series(
            sym,
            start,
            end,
            source=source,
            cache_dir=cache_dir,
            use_cache=use_cache,
            request_delay=request_delay,
            max_retries=max_retries,
        )
    return out

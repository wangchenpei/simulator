from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

DEFAULT_CACHE_DIR = Path("data/cache/yahoo")
DEFAULT_REQUEST_DELAY = 2.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BASE_SECONDS = 15.0


def _require_yfinance():
    try:
        import yfinance as yf  # noqa: F401
    except ImportError as e:
        raise ImportError("Install live extras: pip install yfinance") from e


def _normalize_yahoo_frame(df: "pd.DataFrame") -> "pd.DataFrame":
    import pandas as pd

    if isinstance(df, pd.Series):
        return df.to_frame(name="Close")
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _cache_path(cache_dir: Path, symbol: str, start: str, end: str | None) -> Path:
    key = f"{symbol}|{start}|{end or ''}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    safe = symbol.replace("/", "_").replace("=", "_")
    return cache_dir / f"{safe}_{digest}.parquet"


def _load_cache(path: Path) -> "pd.Series | None":
    csv_path = path.with_suffix(".csv")
    for p in (path, csv_path):
        if not p.exists():
            continue
        import pandas as pd

        if p.suffix == ".parquet":
            try:
                s = pd.read_parquet(p)["close"]
            except Exception:
                continue
        else:
            df = pd.read_csv(p, parse_dates=["date"])
            s = df.set_index("date")["close"]
        s.index = pd.to_datetime(s.index).tz_localize(None)
        s.name = path.stem.split("_")[0]
        return s.astype(float)
    return None


def _save_cache(path: Path, series: "pd.Series") -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({"close": series.astype(float)})
    try:
        frame.to_parquet(path)
    except Exception:
        frame.reset_index(names="date").to_csv(path.with_suffix(".csv"), index=False)


def _extract_symbol_frame(raw: "pd.DataFrame", symbol: str) -> "pd.DataFrame":
    import pandas as pd

    if not isinstance(raw.columns, pd.MultiIndex):
        return raw

    lv0 = raw.columns.get_level_values(0)
    lv1 = raw.columns.get_level_values(1)
    if symbol in lv0:
        return raw[symbol]
    if symbol in lv1:
        return raw.xs(symbol, axis=1, level=1)
    # Some yfinance builds use (Field, Ticker) with Ticker at level 1.
    for level in range(raw.columns.nlevels):
        if symbol in raw.columns.get_level_values(level):
            return raw.xs(symbol, axis=1, level=level)
    raise RuntimeError(f"No data for {symbol}")


def _series_from_download(raw, symbol: str) -> "pd.Series":
    import pandas as pd

    if isinstance(raw, pd.Series):
        s = raw.astype(float)
    else:
        df = _normalize_yahoo_frame(raw)
        if df.empty:
            raise RuntimeError(f"No data for {symbol}")
        col = "Close" if "Close" in df.columns else df.columns[0]
        s = df[col].astype(float)

    s.index = pd.to_datetime(s.index).tz_localize(None)
    s.name = symbol
    return s


def _download_once(symbol: str, start: str, end: str | None) -> "pd.Series":
    _require_yfinance()
    import yfinance as yf

    # Ticker.history is often more stable than yf.download for single symbols.
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start, end=end, auto_adjust=True)
    if hist is not None and not hist.empty:
        return _series_from_download(hist["Close"], symbol)

    raw = yf.download(
        symbol,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    return _series_from_download(raw, symbol)


def download_adj_close(
    symbol: str,
    start: str,
    end: str | None = None,
    *,
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_base_seconds: float = DEFAULT_RETRY_BASE_SECONDS,
) -> "pd.Series":
    """Download adjusted close with disk cache, delay, and retry on rate limits."""
    cache_file = _cache_path(cache_dir or DEFAULT_CACHE_DIR, symbol, start, end) if cache_dir else None
    if use_cache and cache_file is not None:
        cached = _load_cache(cache_file)
        if cached is not None and not cached.empty:
            return cached

    last_err: Exception | None = None
    for attempt in range(max_retries):
        if attempt > 0:
            wait = retry_base_seconds * (2 ** (attempt - 1))
            time.sleep(wait)
        elif request_delay > 0:
            time.sleep(request_delay)

        try:
            series = _download_once(symbol, start, end)
            if series.empty:
                raise RuntimeError(f"No data for {symbol}")
            if use_cache and cache_file is not None:
                _save_cache(cache_file, series)
            return series
        except Exception as e:  # noqa: BLE001 - retry on any fetch failure
            last_err = e

    msg = f"No data for {symbol}"
    if last_err is not None:
        msg = f"{msg} (last error: {last_err})"
    raise RuntimeError(msg)


def download_adj_close_batch(
    symbols: list[str],
    start: str,
    end: str | None = None,
    *,
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    request_delay: float = DEFAULT_REQUEST_DELAY,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_base_seconds: float = DEFAULT_RETRY_BASE_SECONDS,
) -> dict[str, "pd.Series"]:
    """Download many symbols; use cache per symbol and one batched Yahoo request for misses."""
    import pandas as pd

    out: dict[str, pd.Series] = {}
    missing: list[str] = []

    for sym in symbols:
        cache_file = _cache_path(cache_dir or DEFAULT_CACHE_DIR, sym, start, end) if cache_dir else None
        if use_cache and cache_file is not None:
            cached = _load_cache(cache_file)
            if cached is not None and not cached.empty:
                out[sym] = cached
                continue
        missing.append(sym)

    if not missing:
        return out

    _require_yfinance()
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(max_retries):
        if attempt > 0:
            wait = retry_base_seconds * (2 ** (attempt - 1))
            time.sleep(wait)
        elif request_delay > 0:
            time.sleep(request_delay)

        try:
            raw = yf.download(
                missing if len(missing) > 1 else missing[0],
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=False,
                group_by="column",
            )
            if raw is None or (hasattr(raw, "empty") and raw.empty):
                raise RuntimeError(f"No data for {missing}")

            if len(missing) == 1:
                sym = missing[0]
                series = _series_from_download(raw, sym)
                out[sym] = series
            else:
                for sym in missing:
                    sub = _extract_symbol_frame(raw, sym)
                    col = "Close" if "Close" in sub.columns else sub.columns[0]
                    out[sym] = _series_from_download(sub[col], sym)

            for sym in missing:
                if use_cache and cache_dir is not None:
                    _save_cache(_cache_path(cache_dir, sym, start, end), out[sym])
            return out
        except Exception as e:  # noqa: BLE001
            last_err = e
            # Fall back to one-by-one for partial failures / odd MultiIndex layouts.
            try:
                for sym in missing:
                    if sym not in out:
                        out[sym] = download_adj_close(
                            sym,
                            start,
                            end,
                            cache_dir=cache_dir,
                            use_cache=use_cache,
                            request_delay=request_delay,
                            max_retries=1,
                            retry_base_seconds=retry_base_seconds,
                        )
                return out
            except Exception as inner:
                last_err = inner

    msg = f"No data for {missing}"
    if last_err is not None:
        msg = f"{msg} (last error: {last_err})"
    raise RuntimeError(msg)

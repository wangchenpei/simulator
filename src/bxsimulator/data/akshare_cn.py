from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import pandas as pd


def _require_akshare():
    try:
        import akshare as ak  # noqa: F401
    except ImportError as e:
        raise ImportError('Install live extras: pip install -e ".[live]"  (akshare + yfinance)') from e


def _normalize_index_symbol(symbol: str) -> str:
    sym = symbol.strip().lower()
    if sym in ("000300", "csi300", "hs300", "sh000300", "sz399300"):
        return "000300"
    if sym.isdigit() and len(sym) == 6:
        return sym
    if sym.startswith("sh") or sym.startswith("sz"):
        return sym[2:]
    return sym


def _to_yyyymmdd(d: str | None, default: str) -> str:
    if d is None:
        return default
    import pandas as pd

    return pd.Timestamp(d).strftime("%Y%m%d")


def _slice_by_dates(df: "pd.DataFrame", start: str, end: str | None) -> "pd.DataFrame":
    import pandas as pd

    out = df.sort_index()
    out = out.loc[pd.Timestamp(start) :]
    if end is not None:
        out = out.loc[: pd.Timestamp(end)]
    if out.empty:
        raise RuntimeError(f"No CSI300 rows in [{start}, {end}] after slicing")
    return out


def _frame_from_akshare(df: "pd.DataFrame") -> "pd.DataFrame":
    import pandas as pd

    frame = df.copy()
    date_col = None
    for name in ("日期", "date", "Date"):
        if name in frame.columns:
            date_col = name
            break
    if date_col is None:
        date_col = frame.columns[0]
    frame["date"] = pd.to_datetime(frame[date_col])
    frame = frame.set_index("date").sort_index()
    if "close" not in frame.columns:
        for name in ("收盘", "Close", "close"):
            if name in frame.columns:
                frame["close"] = frame[name].astype(float)
                break
    if "close" not in frame.columns:
        raise ValueError(f"No close column; columns={list(frame.columns)}")
    return frame


def load_csi300_from_csv(path: Path | str) -> "pd.DataFrame":
    """Local daily CSV: columns date,close (or 日期,收盘)."""
    import pandas as pd

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    df = pd.read_csv(p)
    frame = _frame_from_akshare(df)
    return frame


def pick_close_series(df: "pd.DataFrame") -> "pd.Series":
    for name in ("close", "Close", "收盘"):
        if name in df.columns:
            return df[name].astype(float)
    raise ValueError(f"No close-like column found; columns={list(df.columns)}")


def _retry_call(fn: Callable[[], "pd.DataFrame"], label: str, attempts: int = 3) -> "pd.DataFrame":
    last_err: Exception | None = None
    for i in range(attempts):
        if i > 0:
            time.sleep(3 * i)
        try:
            df = fn()
            if df is not None and not df.empty:
                return df
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"{label} failed ({last_err})")


def _fetch_index_zh_a_hist(code: str, start_s: str, end_s: str) -> "pd.DataFrame":
    import akshare as ak

    # Chunk by 3-year windows to reduce Eastmoney disconnects on long ranges.
    import pandas as pd

    start_year = int(start_s[:4])
    end_year = int(end_s[:4])
    parts: list[pd.DataFrame] = []
    y = start_year
    while y <= end_year:
        y2 = min(y + 2, end_year)
        chunk_start = f"{y}0101" if y > start_year else start_s
        chunk_end = f"{y2}1231" if y2 < end_year else end_s

        def _one() -> pd.DataFrame:
            return ak.index_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=chunk_start,
                end_date=chunk_end,
            )

        parts.append(_retry_call(_one, f"index_zh_a_hist {chunk_start}-{chunk_end}", attempts=3))
        y = y2 + 1

    merged = pd.concat(parts, ignore_index=True)
    return merged.drop_duplicates(subset=["日期"] if "日期" in merged.columns else merged.columns[0])


def _fetch_csindex(code: str, start_s: str, end_s: str) -> "pd.DataFrame":
    import akshare as ak

    if hasattr(ak, "stock_zh_index_hist_csindex"):
        return ak.stock_zh_index_hist_csindex(symbol=code, start_date=start_s, end_date=end_s)
    if hasattr(ak, "index_zh_a_hist_csindex"):
        return ak.index_zh_a_hist_csindex(symbol=code, start_date=start_s, end_date=end_s)
    raise RuntimeError("AkShare csindex helpers not available in this version")


def _fetch_em_daily(code: str) -> "pd.DataFrame":
    import akshare as ak

    em_sym = f"sh{code}" if code.startswith("0") else f"sz{code}"
    return ak.stock_zh_index_daily_em(symbol=em_sym)


def _fetch_tx_daily(code: str) -> "pd.DataFrame":
    import akshare as ak

    tx_sym = f"sh{code}" if code.startswith("0") else f"sz{code}"
    if hasattr(ak, "stock_zh_index_daily_tx"):
        return ak.stock_zh_index_daily_tx(symbol=tx_sym)
    raise RuntimeError("stock_zh_index_daily_tx not available")


def load_csi300_daily(
    symbol: str = "000300",
    start: str = "2005-01-01",
    end: str | None = None,
    *,
    cn_csv_path: Path | str | None = None,
) -> "pd.DataFrame":
    """Daily CSI 300: local CSV -> Eastmoney (chunked) -> CSIndex -> EM daily -> Tencent -> Sina."""
    if cn_csv_path is not None:
        frame = load_csi300_from_csv(cn_csv_path)
        return _slice_by_dates(frame, start, end)

    _require_akshare()
    code = _normalize_index_symbol(symbol)
    start_s = _to_yyyymmdd(start, "20050101")
    end_s = _to_yyyymmdd(end, date.today().strftime("%Y%m%d"))
    errors: list[str] = []

    fetchers: list[tuple[str, Callable[[], pd.DataFrame]]] = [
        ("index_zh_a_hist", lambda: _fetch_index_zh_a_hist(code, start_s, end_s)),
        ("csindex", lambda: _fetch_csindex(code, start_s, end_s)),
        ("stock_zh_index_daily_em", lambda: _fetch_em_daily(code)),
        ("stock_zh_index_daily_tx", lambda: _fetch_tx_daily(code)),
    ]

    import akshare as ak

    def _sina() -> "pd.DataFrame":
        sina_sym = f"sh{code}" if code.startswith("0") else f"sz{code}"
        return ak.stock_zh_index_daily(symbol=sina_sym)

    fetchers.append(("stock_zh_index_daily(sina)", _sina))

    for label, fn in fetchers:
        try:
            raw = _retry_call(fn, label, attempts=3)
            frame = _frame_from_akshare(raw)
            return _slice_by_dates(frame, start, end)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{label}: {e}")

    raise RuntimeError(
        "AkShare CSI300 fetch failed. "
        f"({' ; '.join(errors)}). "
        "Workaround: export CSI300 daily CSV (date,close) and pass --cn-csv path/to/csi300.csv"
    )

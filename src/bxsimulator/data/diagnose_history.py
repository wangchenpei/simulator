from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from bxsimulator.config import RunConfig, LiveFetchConfig
from bxsimulator.data.fred import fred_fx_series, fred_index_close, hkd_cny_from_fred
from bxsimulator.data.history_sources import BOND_CANDIDATES, HK_CANDIDATES, US_CANDIDATES
from bxsimulator.data.market_prices import DEFAULT_CACHE_DIR, PriceSource, fetch_close_series
from bxsimulator.data import akshare_cn
from bxsimulator.data.yahoo_akshare import year_end_annual_return_from_prices


def _annual_range(close: pd.Series) -> tuple[int | None, int | None, int]:
    r = year_end_annual_return_from_prices(close)
    if r.empty:
        return None, None, 0
    return int(r.index.min().year), int(r.index.max().year), len(r)


def diagnose_history_coverage(
    cfg: RunConfig,
    start: str = "1990-01-01",
    end: str | None = None,
    *,
    price_source: PriceSource = "auto",
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    cn_csv_path: Path | str | None = None,
) -> pd.DataFrame:
    """Report daily/annual coverage per market and intersection years."""
    lf = cfg.live_fetch
    rows: list[dict] = []

    def add_row(label: str, symbol: str, close: pd.Series | None, err: str | None = None) -> None:
        if close is None or close.empty:
            rows.append(
                {
                    "component": label,
                    "symbol": symbol,
                    "daily_start": None,
                    "daily_end": None,
                    "annual_start": None,
                    "annual_end": None,
                    "annual_years": 0,
                    "error": err or "empty",
                }
            )
            return
        y0, y1, n = _annual_range(close)
        rows.append(
            {
                "component": label,
                "symbol": symbol,
                "daily_start": close.index.min().date().isoformat(),
                "daily_end": close.index.max().date().isoformat(),
                "annual_start": y0,
                "annual_end": y1,
                "annual_years": n,
                "error": "",
            }
        )

    # US
    try:
        us = fetch_close_series(lf.us_symbol, start, end, source=price_source, cache_dir=cache_dir)
        fx = fred_fx_series(lf.fred_fx_usdcny, start)
        aligned = pd.DataFrame({"p": us, "fx": fx}).sort_index().ffill().dropna()
        us_cny = aligned["p"] * aligned["fx"]
        add_row("US (CNY)", lf.us_symbol, us_cny)
    except Exception as e:  # noqa: BLE001
        add_row("US (CNY)", lf.us_symbol, None, str(e))

    # HK
    try:
        hk = fetch_close_series(lf.hk_symbol, start, end, source=price_source, cache_dir=cache_dir)
        hkdcny = hkd_cny_from_fred(start, usdcny_id=lf.fred_fx_usdcny, usdhkd_id=lf.fred_fx_usdhkd)
        aligned = pd.DataFrame({"p": hk, "hkdcny": hkdcny}).sort_index().ffill().dropna()
        hk_cny = aligned["p"] * aligned["hkdcny"]
        add_row("HK (CNY)", lf.hk_symbol, hk_cny)
    except Exception as e:  # noqa: BLE001
        add_row("HK (CNY)", lf.hk_symbol, None, str(e))

    # CN
    try:
        cn_path = cn_csv_path or getattr(lf, "cn_csv_path", None)
        cn_df = akshare_cn.load_csi300_daily(lf.cn_symbol, start=start, end=end, cn_csv_path=cn_path)
        cn_close = akshare_cn.pick_close_series(cn_df)
        add_row("CN (CSI300)", lf.cn_symbol, cn_close)
    except Exception as e:  # noqa: BLE001
        add_row("CN (CSI300)", lf.cn_symbol, None, str(e))

    # Bond
    try:
        bnd = fetch_close_series(lf.bond_symbol, start, end, source=price_source, cache_dir=cache_dir)
        add_row("Bond", lf.bond_symbol, bnd)
    except Exception as e:  # noqa: BLE001
        add_row("Bond", lf.bond_symbol, None, str(e))

    df = pd.DataFrame(rows)

    # Intersection estimate from annual returns
    try:
        series_map: dict[str, pd.Series] = {}
        us = fetch_close_series(lf.us_symbol, start, end, source=price_source, cache_dir=cache_dir)
        fx = fred_fx_series(lf.fred_fx_usdcny, start)
        aligned = pd.DataFrame({"p": us, "fx": fx}).sort_index().ffill().dropna()
        series_map["us"] = year_end_annual_return_from_prices(aligned["p"] * aligned["fx"])
        hk = fetch_close_series(lf.hk_symbol, start, end, source=price_source, cache_dir=cache_dir)
        hkdcny = hkd_cny_from_fred(start, usdcny_id=lf.fred_fx_usdcny, usdhkd_id=lf.fred_fx_usdhkd)
        aligned = pd.DataFrame({"p": hk, "hkdcny": hkdcny}).sort_index().ffill().dropna()
        series_map["hk"] = year_end_annual_return_from_prices(aligned["p"] * aligned["hkdcny"])
        cn_path = cn_csv_path or getattr(lf, "cn_csv_path", None)
        cn_df = akshare_cn.load_csi300_daily(lf.cn_symbol, start=start, end=end, cn_csv_path=cn_path)
        series_map["cn"] = year_end_annual_return_from_prices(akshare_cn.pick_close_series(cn_df))
        bnd = fetch_close_series(lf.bond_symbol, start, end, source=price_source, cache_dir=cache_dir)
        series_map["bond"] = year_end_annual_return_from_prices(bnd)

        joined = pd.DataFrame(series_map).dropna(how="any")
        if not joined.empty:
            df.loc[len(df)] = {
                "component": "INTERSECTION (all)",
                "symbol": "-",
                "daily_start": None,
                "daily_end": None,
                "annual_start": int(joined.index.min().year),
                "annual_end": int(joined.index.max().year),
                "annual_years": len(joined),
                "error": "",
            }
    except Exception as e:  # noqa: BLE001
        df.loc[len(df)] = {
            "component": "INTERSECTION (all)",
            "symbol": "-",
            "daily_start": None,
            "daily_end": None,
            "annual_start": None,
            "annual_end": None,
            "annual_years": 0,
            "error": str(e),
        }

    return df


def pick_longest_symbol(
    candidates: tuple[str, ...],
    start: str,
    end: str | None,
    *,
    price_source: PriceSource,
    cache_dir: Path | None,
) -> tuple[str, pd.Series]:
    best_sym = ""
    best_series: pd.Series | None = None
    best_start: pd.Timestamp | None = None
    last_err: Exception | None = None

    for sym in candidates:
        try:
            s = fetch_close_series(sym, start, end, source=price_source, cache_dir=cache_dir)
            if s.empty:
                continue
            if best_start is None or s.index.min() < best_start:
                best_start = s.index.min()
                best_sym = sym
                best_series = s
        except Exception as e:  # noqa: BLE001
            last_err = e

    if best_series is None or not best_sym:
        raise RuntimeError(f"No candidate in {candidates} ({last_err})")
    return best_sym, best_series


def apply_long_history_preset(cfg: RunConfig, auto_pick: bool = True) -> RunConfig:
    from bxsimulator.data.history_sources import LONG_HISTORY_SYMBOLS

    lf = replace(
        cfg.live_fetch,
        us_symbol=LONG_HISTORY_SYMBOLS["us_symbol"],
        hk_symbol=LONG_HISTORY_SYMBOLS["hk_symbol"],
        cn_symbol=LONG_HISTORY_SYMBOLS["cn_symbol"],
        bond_symbol=LONG_HISTORY_SYMBOLS["bond_symbol"],
    )
    return replace(cfg, live_fetch=lf)


def resolve_auto_symbols(
    cfg: RunConfig,
    start: str,
    end: str | None,
    *,
    price_source: PriceSource,
    cache_dir: Path | None,
) -> LiveFetchConfig:
    us_sym, _ = pick_longest_symbol(US_CANDIDATES, start, end, price_source=price_source, cache_dir=cache_dir)
    hk_sym, _ = pick_longest_symbol(HK_CANDIDATES, start, end, price_source=price_source, cache_dir=cache_dir)
    bond_sym, _ = pick_longest_symbol(BOND_CANDIDATES, start, end, price_source=price_source, cache_dir=cache_dir)
    return replace(
        cfg.live_fetch,
        us_symbol=us_sym,
        hk_symbol=hk_sym,
        bond_symbol=bond_sym,
    )

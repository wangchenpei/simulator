from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from bxsimulator.data import akshare_cn
from bxsimulator.data.fred import fred_fx_series, hkd_cny_from_fred
from bxsimulator.data.market_prices import DEFAULT_CACHE_DIR, PriceSource, fetch_close_batch


def year_end_annual_return_from_prices(close: pd.Series) -> pd.Series:
    """Calendar-year simple return using last available price per year."""
    s = close.sort_index().astype(float)
    s.index = pd.to_datetime(s.index).tz_localize(None)
    ye = s.groupby(s.index.year).last()
    r = ye.pct_change().dropna()
    years = [int(y) for y in r.index]
    r.index = pd.to_datetime([f"{y}-12-31" for y in years])
    return r.astype(float)


def fetch_live_annual_table(
    cfg,
    start: str = "2005-01-01",
    end: str | None = None,
    *,
    price_source: PriceSource = "auto",
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    request_delay: float = 1.5,
    max_retries: int = 3,
    cn_csv_path: Path | str | None = None,
    history_preset: str | None = None,
    auto_symbols: bool = False,
) -> pd.DataFrame:
    """Annual r_equity (CNY), r_bond, r_short for backtest CSV."""
    from bxsimulator.data.diagnose_history import apply_long_history_preset, resolve_auto_symbols

    if history_preset == "long":
        cfg = apply_long_history_preset(cfg, auto_pick=False)
    if auto_symbols:
        cfg = replace(cfg, live_fetch=resolve_auto_symbols(cfg, start, end, price_source=price_source, cache_dir=cache_dir))

    lf = cfg.live_fetch
    regions = cfg.equity_regions

    yahoo_symbols = [lf.us_symbol, lf.hk_symbol, lf.bond_symbol]
    prices = fetch_close_batch(
        yahoo_symbols,
        start=start,
        end=end,
        source=price_source,
        cache_dir=cache_dir,
        use_cache=use_cache,
        request_delay=request_delay,
        max_retries=max_retries,
    )
    us = prices[lf.us_symbol]
    hk = prices[lf.hk_symbol]
    bnd = prices[lf.bond_symbol]

    fx = fred_fx_series(lf.fred_fx_usdcny, start=start)
    usdhkd_id = getattr(lf, "fred_fx_usdhkd", "DEXHKUS")
    hkdcny = hkd_cny_from_fred(start, usdcny_id=lf.fred_fx_usdcny, usdhkd_id=usdhkd_id)

    cn_path = cn_csv_path or getattr(lf, "cn_csv_path", None)
    cn_df = akshare_cn.load_csi300_daily(
        lf.cn_symbol, start=start, end=end, cn_csv_path=cn_path
    )
    cn_close = akshare_cn.pick_close_series(cn_df)

    def cny_value_usd_asset(us_close: pd.Series) -> pd.Series:
        aligned = pd.DataFrame({"p": us_close, "fx": fx}).sort_index().ffill().dropna(how="any")
        return (aligned["p"] * aligned["fx"]).astype(float)

    def cny_value_hkd_asset(hk_close: pd.Series) -> pd.Series:
        aligned = pd.DataFrame({"p": hk_close, "hkdcny": hkdcny}).sort_index().ffill().dropna(how="any")
        return (aligned["p"] * aligned["hkdcny"]).astype(float)

    r_us = year_end_annual_return_from_prices(cny_value_usd_asset(us))
    r_hk = year_end_annual_return_from_prices(cny_value_hkd_asset(hk))
    r_cn = year_end_annual_return_from_prices(cn_close)

    joined = pd.DataFrame({"us": r_us, "hk": r_hk, "cn": r_cn}).dropna(how="any")
    wu = float(regions.get("US", 0.0))
    wh = float(regions.get("HK", 0.0))
    wc = float(regions.get("CN", 0.0))
    joined["r_equity"] = joined["us"] * wu + joined["hk"] * wh + joined["cn"] * wc

    r_bond = year_end_annual_return_from_prices(bnd)
    r_short = r_bond.copy()

    out = pd.DataFrame(index=joined.index)
    out["r_equity"] = joined["r_equity"]
    out["r_bond"] = r_bond.reindex(out.index)
    out["r_short"] = r_short.reindex(out.index)
    out = out.dropna(how="any").sort_index()
    out.insert(0, "date", out.index)
    return out

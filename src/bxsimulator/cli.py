from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bxsimulator.config import RunConfig
from bxsimulator.data.fixtures import build_synthetic_returns, load_returns_csv
from bxsimulator.data.diagnose_history import diagnose_history_coverage
from bxsimulator.data.history_sources import LONG_HISTORY_SYMBOLS, PRESET_NOTES
from bxsimulator.data.offline_us_eu import OFFLINE_NOTES, describe_offline_csv, write_us_eu_annual_csv
from bxsimulator.data.yahoo_akshare import fetch_live_annual_table
from bxsimulator.engine.backtest import annual_summary, run_backtest
from bxsimulator.export.excel import export_excel


def _cmd_run(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config)
    cfg = RunConfig.from_yaml(cfg_path)

    source = args.source or cfg.returns.source
    if source == "csv":
        csv_path = Path(args.csv) if args.csv else cfg.resolved_returns_csv(cfg_path)
        if csv_path is None:
            print("CSV source requires --csv or returns.csv_path in config", file=sys.stderr)
            return 2
        returns = load_returns_csv(csv_path)
    elif source == "synthetic":
        returns = build_synthetic_returns(cfg, seed=args.seed)
    else:
        print(f"Unsupported --source {source!r} for run (use csv or synthetic)", file=sys.stderr)
        return 2

    nav, _ = run_backtest(cfg, returns, start=args.start, end=args.end)
    ann = annual_summary(nav)

    if args.export:
        export_excel(args.export, cfg, nav, annual_summary=ann)

    print(f"Backtest periods: {len(nav)}  ({nav['date'].min().date()} → {nav['date'].max().date()})")
    print(nav.tail())
    if args.export:
        print(f"Wrote Excel: {args.export}")
    return 0


def _cmd_fetch_live(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config)
    cfg = RunConfig.from_yaml(cfg_path)
    cache_dir = None if args.no_cache else Path(args.cache_dir)
    cn_csv = Path(args.cn_csv) if getattr(args, "cn_csv", None) else None
    try:
        df = fetch_live_annual_table(
            cfg,
            start=args.start,
            end=args.end,
            price_source=args.price_source,
            cache_dir=cache_dir,
            use_cache=not args.no_cache,
            request_delay=args.request_delay,
            max_retries=args.max_retries,
            cn_csv_path=cn_csv,
            history_preset=getattr(args, "preset", None),
            auto_symbols=getattr(args, "auto_symbols", False),
        )
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:
        print(f"fetch-live failed: {e}", file=sys.stderr)
        print(
            "Tip: use --price-source akshare (Eastmoney, best in CN). "
            "Stooq/Yahoo may block or rate-limit. Cache: data/cache/prices/.",
            file=sys.stderr,
        )
        return 1
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(df.tail())
    print(f"Wrote CSV: {out}")
    return 0


def _cmd_build_offline(args: argparse.Namespace) -> int:
    out = write_us_eu_annual_csv(
        Path(args.output),
        raw_path=Path(args.raw) if args.raw else None,
        us_weight=args.us_weight,
        eu_weight=args.eu_weight,
        start_year=args.start_year,
        end_year=args.end_year,
    )
    info = describe_offline_csv(out)
    print(OFFLINE_NOTES.strip())
    print()
    print(info.to_string(index=False))
    print(f"\nWrote CSV: {out}")
    return 0


def _cmd_describe_offline(args: argparse.Namespace) -> int:
    path = Path(args.csv)
    info = describe_offline_csv(path)
    print(OFFLINE_NOTES.strip())
    print()
    print(info.to_string(index=False))
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    from bxsimulator.web import main as web_main

    extra = [a for a in getattr(args, "streamlit_args", []) if a != "--"]
    return web_main(extra)


def _cmd_diagnose_history(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config)
    cfg = RunConfig.from_yaml(cfg_path)
    if args.preset == "long":
        from bxsimulator.data.diagnose_history import apply_long_history_preset

        cfg = apply_long_history_preset(cfg)
    cache_dir = None if args.no_cache else Path(args.cache_dir)
    cn_csv = Path(args.cn_csv) if args.cn_csv else None
    try:
        df = diagnose_history_coverage(
            cfg,
            start=args.start,
            end=args.end,
            price_source=args.price_source,
            cache_dir=cache_dir,
            cn_csv_path=cn_csv,
        )
    except Exception as e:
        print(f"diagnose-history failed: {e}", file=sys.stderr)
        return 1
    if args.preset == "long":
        print(PRESET_NOTES.strip())
        print("Long-history preset symbols:", LONG_HISTORY_SYMBOLS)
        print()
    print(df.to_string(index=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="bxsimulator")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run backtest from CSV or synthetic returns")
    r.add_argument("--config", required=True, help="Path to YAML config")
    r.add_argument("--source", choices=["csv", "synthetic"], default=None)
    r.add_argument("--csv", default=None, help="Override CSV path when source=csv")
    r.add_argument("--seed", type=int, default=None, help="RNG seed for synthetic")
    r.add_argument("--start", default=None, help="Inclusive start date YYYY-MM-DD")
    r.add_argument("--end", default=None, help="Inclusive end date YYYY-MM-DD")
    r.add_argument("--export", default=None, help="Output .xlsx path")

    f = sub.add_parser("fetch-live", help="Download Yahoo+AkShare+FRED and write annual CSV")
    f.add_argument("--config", required=True)
    f.add_argument("--output", required=True, help="Output CSV path")
    f.add_argument("--start", default="2005-01-01")
    f.add_argument("--end", default=None)
    f.add_argument(
        "--cn-csv",
        default=None,
        help="Local CSI300 daily CSV (columns date,close) if AkShare CN index fails",
    )
    f.add_argument("--cache-dir", default="data/cache/prices", help="Price cache directory")
    f.add_argument("--no-cache", action="store_true", help="Do not read/write price cache")
    f.add_argument(
        "--price-source",
        choices=["auto", "akshare", "stooq", "yahoo", "fred"],
        default="auto",
        help="Price source: auto=AkShare then Stooq/FRED/Yahoo (default)",
    )
    f.add_argument(
        "--request-delay",
        type=float,
        default=2.0,
        help="Seconds to wait between price downloads (default 2)",
    )
    f.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Retry count when Yahoo rate-limits or returns empty",
    )
    f.add_argument(
        "--preset",
        choices=["long"],
        default=None,
        help="Use long-history symbol preset (SPY, ^HSI, IEF, 000300)",
    )
    f.add_argument(
        "--auto-symbols",
        action="store_true",
        help="Auto-pick longest available US/HK/bond symbols from candidate lists",
    )

    b = sub.add_parser(
        "build-offline",
        help="Build US/EU offline annual CSV from bundled raw data (no network)",
    )
    b.add_argument(
        "--output",
        default="data/offline/us_eu_long_annual.csv",
        help="Output annual returns CSV",
    )
    b.add_argument(
        "--raw",
        default=None,
        help="Override raw components CSV (default: data/offline/raw/components_annual.csv)",
    )
    b.add_argument("--us-weight", type=float, default=0.5, help="US equity weight in r_equity")
    b.add_argument("--eu-weight", type=float, default=0.5, help="EU equity weight in r_equity")
    b.add_argument("--start-year", type=int, default=None, help="First calendar year to include")
    b.add_argument("--end-year", type=int, default=None, help="Last calendar year to include")

    o = sub.add_parser("describe-offline", help="Show coverage of bundled offline annual CSV")
    o.add_argument(
        "--csv",
        default="data/offline/us_eu_long_annual.csv",
        help="Offline annual CSV path",
    )

    u = sub.add_parser("ui", help="Launch Streamlit web UI (works from any directory)")
    u.add_argument(
        "streamlit_args",
        nargs=argparse.REMAINDER,
        help="Extra args passed to streamlit run (prefix with -- if needed)",
    )

    d = sub.add_parser("diagnose-history", help="Show per-market history coverage and intersection")
    d.add_argument("--config", required=True)
    d.add_argument("--start", default="1990-01-01")
    d.add_argument("--end", default=None)
    d.add_argument("--cn-csv", default=None)
    d.add_argument("--cache-dir", default="data/cache/prices")
    d.add_argument("--no-cache", action="store_true")
    d.add_argument("--price-source", choices=["auto", "akshare", "stooq", "yahoo", "fred"], default="auto")
    d.add_argument("--preset", choices=["long"], default=None)

    args = p.parse_args(argv)
    if args.cmd == "run":
        return _cmd_run(args)
    if args.cmd == "fetch-live":
        return _cmd_fetch_live(args)
    if args.cmd == "build-offline":
        return _cmd_build_offline(args)
    if args.cmd == "describe-offline":
        return _cmd_describe_offline(args)
    if args.cmd == "ui":
        return _cmd_ui(args)
    if args.cmd == "diagnose-history":
        return _cmd_diagnose_history(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

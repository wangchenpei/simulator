from __future__ import annotations

from pathlib import Path

import pandas as pd

from bxsimulator.data.loader import assert_returns_df
from bxsimulator.paths import project_root

REGIONS_DIR = project_root() / "data" / "offline" / "regions"

EQUITY_REGIONS: dict[str, dict[str, str]] = {
    "US": {"label": "美国·标普500", "file": "us_equity.csv"},
    "UK": {"label": "英国·FTSE100", "file": "uk_equity.csv"},
    "CN": {"label": "中国·沪深300", "file": "cn_equity.csv"},
    "JP": {"label": "日本·日经225", "file": "jp_equity.csv"},
}

BOND_REGIONS: dict[str, dict[str, str]] = {
    "US": {"label": "美国·长期国债", "file": "us_bond.csv"},
    "UK": {"label": "英国·10年期国债", "file": "uk_bond.csv"},
    "CN": {"label": "中国·10年期国债", "file": "cn_bond.csv"},
    "JP": {"label": "日本·10年期国债", "file": "jp_bond.csv"},
}

SHORT_BOND_SPREAD = 0.015
SHORT_BOND_FLOOR = -0.05


def _load_region_series(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    if "year" not in df.columns or "r" not in df.columns:
        raise ValueError(f"{path} must have columns year,r")
    return df.set_index("year")["r"].astype(float).sort_index()


def load_all_region_series(regions_dir: Path | None = None) -> dict[str, pd.Series]:
    base = regions_dir or REGIONS_DIR
    out: dict[str, pd.Series] = {}
    for key, meta in EQUITY_REGIONS.items():
        path = base / meta["file"]
        if not path.exists():
            raise FileNotFoundError(f"Missing regional pack: {path}")
        out[f"equity:{key}"] = _load_region_series(path)
    for key, meta in BOND_REGIONS.items():
        path = base / meta["file"]
        if not path.exists():
            raise FileNotFoundError(f"Missing regional pack: {path}")
        out[f"bond:{key}"] = _load_region_series(path)
    return out


def _active_weights(weights: dict[str, float]) -> dict[str, float]:
    active = {k: float(v) for k, v in weights.items() if float(v) > 1e-9}
    if not active:
        raise ValueError("At least one region weight must be > 0")
    total = sum(active.values())
    return {k: v / total for k, v in active.items()}


def _blend(active: dict[str, float], series_map: dict[str, pd.Series]) -> pd.Series:
    keys = list(active.keys())
    frames = pd.concat({k: series_map[k] for k in keys}, axis=1)
    frames = frames.dropna(how="any")
    if frames.empty:
        raise ValueError("No overlapping years for selected regions")
    w = pd.Series(active)
    blended = frames.mul(w, axis=1).sum(axis=1)
    blended.index = blended.index.astype(int)
    return blended.sort_index()


def blend_regional_returns(
    equity_weights: dict[str, float],
    bond_weights: dict[str, float],
    *,
    regions_dir: Path | None = None,
    short_spread: float = SHORT_BOND_SPREAD,
) -> pd.DataFrame:
    all_series = load_all_region_series(regions_dir)
    eq_map = {k: all_series[f"equity:{k}"] for k in EQUITY_REGIONS}
    bd_map = {k: all_series[f"bond:{k}"] for k in BOND_REGIONS}

    eq_w = _active_weights(equity_weights)
    bd_w = _active_weights(bond_weights)

    r_equity = _blend(eq_w, eq_map)
    r_bond = _blend(bd_w, bd_map)

    aligned = pd.concat([r_equity.rename("r_equity"), r_bond.rename("r_bond")], axis=1).dropna(how="any")
    if aligned.empty:
        raise ValueError("Equity and bond blends have no overlapping years")

    aligned["r_short"] = (aligned["r_bond"] - short_spread).clip(lower=SHORT_BOND_FLOOR)
    dates = pd.to_datetime([f"{int(y)}-12-31" for y in aligned.index])
    out = aligned.set_index(dates).sort_index()
    return assert_returns_df(out)


def describe_regional_coverage(regions_dir: Path | None = None) -> pd.DataFrame:
    base = regions_dir or REGIONS_DIR
    rows = []
    for kind, catalog in (("equity", EQUITY_REGIONS), ("bond", BOND_REGIONS)):
        for key, meta in catalog.items():
            path = base / meta["file"]
            if not path.exists():
                continue
            s = _load_region_series(path)
            rows.append(
                {
                    "kind": kind,
                    "region": key,
                    "label": meta["label"],
                    "start": int(s.index.min()),
                    "end": int(s.index.max()),
                    "years": len(s),
                }
            )
    return pd.DataFrame(rows)

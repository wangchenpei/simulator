from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from bxsimulator import profiles


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class LiveFetchConfig:
    us_symbol: str = "SPY"
    hk_symbol: str = "2800.HK"
    cn_symbol: str = "000300"
    bond_symbol: str = "BND"
    fred_fx_usdcny: str = "DEXCHUS"
    fred_fx_usdhkd: str = "DEXHKUS"
    cn_csv_path: str | None = None


@dataclass
class ReturnsConfig:
    source: Literal["csv", "synthetic", "yahoo_akshare", "regional"] = "csv"
    csv_path: str | None = None
    synthetic_years: int = 20
    synthetic_vol_equity: float = 0.18
    synthetic_vol_bond: float = 0.06
    synthetic_mean_equity: float = 0.07
    synthetic_mean_bond: float = 0.03
    synthetic_short_mean: float = 0.025


@dataclass
class RunConfig:
    product_id: str
    label: str = ""
    accounting_currency: str = "CNY"

    equity_weight: float = 0.60
    bond_weight: float = 0.40
    equity_min: float = 0.45
    equity_max: float = 0.75
    bond_min: float = 0.25
    bond_max: float = 0.55

    smoothing_threshold: float = 0.065
    max_fill_fraction_of_shortfall: float = 1.0

    rebalance_frequency: Literal["annual", "monthly"] = "annual"

    initial_main_value: float = 1_000_000.0
    initial_reserve: float = 0.0

    returns: ReturnsConfig = field(default_factory=ReturnsConfig)
    equity_regions: dict[str, float] = field(
        default_factory=lambda: {"US": 0.4, "HK": 0.3, "CN": 0.3}
    )
    bond_regions: dict[str, float] = field(
        default_factory=lambda: {"US": 1.0}
    )
    live_fetch: LiveFetchConfig = field(default_factory=LiveFetchConfig)

    @staticmethod
    def _defaults_for_product(product_id: str) -> dict[str, float]:
        if product_id == "participating":
            return profiles.PARTICIPATING_DEFAULTS
        if product_id == "ci_annuity":
            return profiles.CI_ANNUITY_DEFAULTS
        return {}

    @classmethod
    def from_yaml(cls, path: Path | str) -> RunConfig:
        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        pid = str(raw.get("product_id") or "participating")
        merged = _deep_merge(dict(cls._defaults_for_product(pid)), raw)

        returns_raw = merged.get("returns") or {}
        live_raw = merged.get("live_fetch") or {}
        regions = merged.get("equity_regions") or {"US": 1 / 3, "HK": 1 / 3, "CN": 1 / 3}
        bond_regions = merged.get("bond_regions") or {"US": 1.0}

        rc = cls(
            product_id=pid,
            label=str(merged.get("label") or pid),
            accounting_currency=str(merged.get("accounting_currency") or "CNY"),
            equity_weight=float(merged["equity_weight"]),
            bond_weight=float(merged["bond_weight"]),
            equity_min=float(merged["equity_min"]),
            equity_max=float(merged["equity_max"]),
            bond_min=float(merged["bond_min"]),
            bond_max=float(merged["bond_max"]),
            smoothing_threshold=float(merged["smoothing_threshold"]),
            max_fill_fraction_of_shortfall=float(
                merged.get("max_fill_fraction_of_shortfall", 1.0)
            ),
            rebalance_frequency=merged.get("rebalance_frequency", "annual"),
            initial_main_value=float(merged.get("initial_main_value", 1_000_000.0)),
            initial_reserve=float(merged.get("initial_reserve", 0.0)),
            returns=ReturnsConfig(
                source=returns_raw.get("source", "csv"),
                csv_path=returns_raw.get("csv_path"),
                synthetic_years=int(returns_raw.get("synthetic_years", 20)),
                synthetic_vol_equity=float(returns_raw.get("synthetic_vol_equity", 0.18)),
                synthetic_vol_bond=float(returns_raw.get("synthetic_vol_bond", 0.06)),
                synthetic_mean_equity=float(returns_raw.get("synthetic_mean_equity", 0.07)),
                synthetic_mean_bond=float(returns_raw.get("synthetic_mean_bond", 0.03)),
                synthetic_short_mean=float(returns_raw.get("synthetic_short_mean", 0.025)),
            ),
            equity_regions={str(k): float(v) for k, v in regions.items()},
            bond_regions={str(k): float(v) for k, v in bond_regions.items()},
            live_fetch=LiveFetchConfig(
                us_symbol=str(live_raw.get("us_symbol", "SPY")),
                hk_symbol=str(live_raw.get("hk_symbol", "2800.HK")),
                cn_symbol=str(live_raw.get("cn_symbol", "000300")),
                bond_symbol=str(live_raw.get("bond_symbol", "BND")),
                fred_fx_usdcny=str(live_raw.get("fred_fx_usdcny", "DEXCHUS")),
                fred_fx_usdhkd=str(live_raw.get("fred_fx_usdhkd", "DEXHKUS")),
                cn_csv_path=live_raw.get("cn_csv_path"),
            ),
        )
        rc.validate()
        return rc

    def validate(self) -> None:
        ew, bw = self.equity_weight, self.bond_weight
        if abs(ew + bw - 1.0) > 1e-9:
            raise ValueError(f"equity_weight + bond_weight must be 1.0, got {ew + bw}")
        if not (self.equity_min <= ew <= self.equity_max):
            raise ValueError(
                f"equity_weight {ew} not in [{self.equity_min}, {self.equity_max}]"
            )
        if not (self.bond_min <= bw <= self.bond_max):
            raise ValueError(f"bond_weight {bw} not in [{self.bond_min}, {self.bond_max}]")
        if self.smoothing_threshold < 0 or self.smoothing_threshold > 1:
            raise ValueError("smoothing_threshold should be in [0, 1]")
        if not (0 < self.max_fill_fraction_of_shortfall <= 1.0):
            raise ValueError("max_fill_fraction_of_shortfall must be in (0, 1]")
        if self.rebalance_frequency not in ("annual", "monthly"):
            raise ValueError("rebalance_frequency must be annual or monthly")
        total = sum(self.equity_regions.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"equity_regions weights must sum to 1, got {total}")
        btotal = sum(self.bond_regions.values())
        if abs(btotal - 1.0) > 1e-6:
            raise ValueError(f"bond_regions weights must sum to 1, got {btotal}")

    def resolved_returns_csv(self, config_path: Path | None) -> Path | None:
        if self.returns.source != "csv" or not self.returns.csv_path:
            return None
        p = Path(self.returns.csv_path)
        if p.is_absolute():
            return p
        if config_path is None:
            return p.resolve()
        cfg_dir = Path(config_path).parent
        candidates = [cfg_dir / p, cfg_dir.parent / p]
        for c in candidates:
            if c.exists():
                return c.resolve()
        return (cfg_dir / p).resolve()

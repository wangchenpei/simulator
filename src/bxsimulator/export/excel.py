from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from bxsimulator.config import RunConfig
from bxsimulator.display_format import round_dataframe, round_value


def export_excel(
    path: Path | str,
    cfg: RunConfig,
    nav_series: pd.DataFrame,
    transfers: pd.DataFrame | None = None,
    annual_summary: pd.DataFrame | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _write_excel_sheets(writer, cfg, nav_series, transfers, annual_summary)


def export_excel_bytes(
    cfg: RunConfig,
    nav_series: pd.DataFrame,
    transfers: pd.DataFrame | None = None,
    annual_summary: pd.DataFrame | None = None,
) -> bytes:
    import io

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _write_excel_sheets(writer, cfg, nav_series, transfers, annual_summary)
    return buf.getvalue()


def _write_excel_sheets(
    writer: pd.ExcelWriter,
    cfg: RunConfig,
    nav_series: pd.DataFrame,
    transfers: pd.DataFrame | None,
    annual_summary: pd.DataFrame | None,
) -> None:
    meta_rows = _config_to_meta_rows(cfg)
    meta_df = pd.DataFrame(meta_rows, columns=["key", "value"])

    cfg_dict = asdict(cfg)
    meta_json = pd.DataFrame({"config_json": [json.dumps(cfg_dict, ensure_ascii=False, indent=2)]})

    nav_out = round_dataframe(nav_series)
    if transfers is None:
        transfers = nav_series[
            [
                "date",
                "transfer_to_reserve",
                "transfer_from_reserve",
                "r_main_before_transfer",
                "r_short",
            ]
        ].copy()
    transfers_out = round_dataframe(transfers)
    annual_out = round_dataframe(annual_summary) if annual_summary is not None else None

    meta_df.to_excel(writer, sheet_name="Meta", index=False)
    meta_json.to_excel(writer, sheet_name="ConfigJSON", index=False)
    nav_out.to_excel(writer, sheet_name="NavSeries", index=False)
    transfers_out.to_excel(writer, sheet_name="Transfers", index=False)
    if annual_out is not None and not annual_out.empty:
        annual_out.to_excel(writer, sheet_name="AnnualSummary", index=False)


def _config_to_meta_rows(cfg: RunConfig) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = [
        ("product_id", cfg.product_id),
        ("label", cfg.label),
        ("accounting_currency", cfg.accounting_currency),
        ("equity_weight", round_value(cfg.equity_weight)),
        ("bond_weight", round_value(cfg.bond_weight)),
        ("smoothing_threshold", round_value(cfg.smoothing_threshold)),
        ("max_fill_fraction_of_shortfall", round_value(cfg.max_fill_fraction_of_shortfall)),
        ("rebalance_frequency", cfg.rebalance_frequency),
        ("initial_main_value", round_value(cfg.initial_main_value)),
        ("initial_reserve", round_value(cfg.initial_reserve)),
    ]
    for k, v in cfg.equity_regions.items():
        rows.append((f"equity_regions.{k}", round_value(v)))
    for k, v in cfg.bond_regions.items():
        rows.append((f"bond_regions.{k}", round_value(v)))
    return rows

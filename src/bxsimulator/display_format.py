from __future__ import annotations

import pandas as pd

DISPLAY_DECIMALS = 2

_RATE_COLUMNS = frozenset(
    {
        "r_main_before_transfer",
        "r_short",
        "r_equity",
        "r_bond",
        "total_nav_return",
    }
)

NAV_TABLE_COLUMNS: tuple[str, ...] = (
    "date",
    "r_equity",
    "r_bond",
    "r_short",
    "main_begin",
    "main_after_returns",
    "r_main_before_transfer",
    "transfer_to_reserve",
    "transfer_from_reserve",
    "pending_main_fill",
    "pending_reserve_deposit",
    "main_equity",
    "main_bond",
    "main_total",
    "reserve",
    "total_nav",
)

NAV_COLUMN_LABELS_ZH: dict[str, str] = {
    "date": "期末日期",
    "r_equity": "股票收益率",
    "r_bond": "债券收益率",
    "r_short": "短债收益率",
    "main_begin": "期初主账户",
    "main_after_returns": "收益后主账户",
    "r_main_before_transfer": "平滑前收益率",
    "transfer_to_reserve": "转入平滑池",
    "transfer_from_reserve": "平滑池回补",
    "pending_main_fill": "待补主账户",
    "pending_reserve_deposit": "待入平滑池",
    "main_equity": "主账户股票",
    "main_bond": "主账户债券",
    "main_total": "主账户合计",
    "reserve": "固定账户",
    "total_nav": "总净值",
}

NAV_COLUMN_DESCRIPTIONS_ZH: dict[str, str] = {
    "date": "该期期末时点（每年一行）",
    "r_equity": "主账户股票组合本期市场收益率（小数，0.08=8%）",
    "r_bond": "主账户债券组合本期市场收益率（小数，0.05=5%）",
    "r_short": "固定账户计息收益率（=债券收益率−1.5%，下限−5%）",
    "main_begin": "本期期初主账户市值（股票+债券）",
    "main_after_returns": "资产收益后、平滑划转前的主账户市值",
    "r_main_before_transfer": "平滑前主账户收益率（相对期初主账户）",
    "transfer_to_reserve": "收益超阈值时从主账户转入固定账户的金额",
    "transfer_from_reserve": "收益低于阈值时从固定账户回补主账户的金额",
    "pending_main_fill": "因平滑池资金不足而结转、待后续补入主账户的金额",
    "pending_reserve_deposit": "因优先补回主账户而结转、待后续划入平滑池的金额",
    "main_equity": "期末主账户股票仓位（平滑并再平衡后）",
    "main_bond": "期末主账户债券仓位（平滑并再平衡后）",
    "main_total": "期末主账户合计",
    "reserve": "期末固定账户（平滑池）余额",
    "total_nav": "期末总净值（主账户+固定账户）",
}


def fmt_amount(value: float) -> str:
    return f"{max(0.0, float(value)):,.{DISPLAY_DECIMALS}f}"


def fmt_number(value: float) -> str:
    return f"{float(value):,.{DISPLAY_DECIMALS}f}"


def fmt_rate(value: float) -> str:
    return f"{float(value):.{DISPLAY_DECIMALS}%}"


def round_value(value: float, *, decimals: int = DISPLAY_DECIMALS) -> float:
    return round(float(value), decimals)


def round_dataframe(df: pd.DataFrame, *, decimals: int = DISPLAY_DECIMALS) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].round(decimals)
    return out


def reorder_nav_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in NAV_TABLE_COLUMNS if c in df.columns]
    extra = [c for c in df.columns if c not in cols]
    return df[cols + extra]


def prepare_nav_table_export(df: pd.DataFrame) -> pd.DataFrame:
    out = reorder_nav_columns(df)
    out = round_dataframe(out)
    if "date" in out.columns:
        out = out.copy()
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def build_nav_export_table(df: pd.DataFrame) -> pd.DataFrame:
    """Chinese headers, one description row, then numeric data."""
    data = prepare_nav_table_export(df)
    labels = {c: NAV_COLUMN_LABELS_ZH.get(c, c) for c in data.columns}
    desc_row = {labels[c]: NAV_COLUMN_DESCRIPTIONS_ZH.get(c, "") for c in data.columns}
    renamed = data.rename(columns=labels)
    return pd.concat([pd.DataFrame([desc_row]), renamed], ignore_index=True)


def format_nav_table_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """On-screen detail table: Chinese headers + description row + formatted values."""
    ordered = reorder_nav_columns(df)
    formatted = format_table_for_display(ordered)
    labels = {c: NAV_COLUMN_LABELS_ZH.get(c, c) for c in ordered.columns}
    formatted = formatted.rename(columns=labels)
    desc_row = {labels[c]: NAV_COLUMN_DESCRIPTIONS_ZH.get(c, "") for c in ordered.columns}
    return pd.concat([pd.DataFrame([desc_row]), formatted], ignore_index=True)


def format_table_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Format a dataframe for on-screen tables (all numbers to 2 decimal places)."""
    show = df.copy()
    if "date" in show.columns:
        show["date"] = pd.to_datetime(show["date"]).dt.strftime("%Y-%m-%d")
    for col in show.columns:
        if col in _RATE_COLUMNS:
            show[col] = show[col].map(fmt_rate)
        elif pd.api.types.is_numeric_dtype(show[col]):
            show[col] = show[col].map(fmt_number)
    return show

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

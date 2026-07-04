from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bxsimulator.data.regional_blend import BOND_REGIONS, EQUITY_REGIONS, load_all_region_series
from bxsimulator.display_format import DISPLAY_DECIMALS, fmt_rate

_REGION_COLORS: dict[str, str] = {
    "US": "#2874a6",
    "UK": "#c2783a",
    "CN": "#c0392b",
    "JP": "#3d8b7a",
}

_LEGEND_LAYOUT = dict(
    orientation="h",
    yanchor="bottom",
    y=1.02,
    x=0,
    itemclick="toggle",
    itemdoubleclick="toggleothers",
)


def _nav_years(nav: pd.DataFrame) -> list[int]:
    return [int(pd.Timestamp(d).year) for d in nav["date"]]


def compute_ideal_nav(
    nav: pd.DataFrame,
    *,
    threshold: float,
    initial_total: float,
) -> pd.Series:
    """Total NAV if it compounded at the smoothing threshold each period."""
    values = [
        float(initial_total) * (1.0 + float(threshold)) ** (i + 1)
        for i in range(len(nav))
    ]
    return pd.Series(values, index=nav.index)


def _load_regional_index_overlays(
    nav: pd.DataFrame,
    catalog: dict[str, dict[str, str]],
    *,
    series_prefix: str,
) -> dict[str, tuple[str, pd.Series]]:
    """Cumulative regional index (base 100) aligned to each nav row."""
    all_series = load_all_region_series()
    years = _nav_years(nav)
    out: dict[str, tuple[str, pd.Series]] = {}
    for code, meta in catalog.items():
        s = all_series[f"{series_prefix}:{code}"]
        level = 100.0
        values: list[float] = []
        for i, year in enumerate(years):
            if i > 0 and year in s.index:
                level *= 1.0 + float(s.loc[year])
            values.append(level if year in s.index else float("nan"))
        out[code] = (meta["label"], pd.Series(values, index=nav.index))
    return out


def _load_regional_return_overlays(
    nav: pd.DataFrame,
    catalog: dict[str, dict[str, str]],
    *,
    series_prefix: str,
) -> dict[str, tuple[str, pd.Series]]:
    """Annual regional returns aligned to each nav row."""
    all_series = load_all_region_series()
    years = _nav_years(nav)
    out: dict[str, tuple[str, pd.Series]] = {}
    for code, meta in catalog.items():
        s = all_series[f"{series_prefix}:{code}"]
        values = [float(s.loc[y]) if y in s.index else float("nan") for y in years]
        out[code] = (meta["label"], pd.Series(values, index=nav.index))
    return out


def load_equity_index_overlays(nav: pd.DataFrame) -> dict[str, tuple[str, pd.Series]]:
    return _load_regional_index_overlays(nav, EQUITY_REGIONS, series_prefix="equity")


def load_bond_index_overlays(nav: pd.DataFrame) -> dict[str, tuple[str, pd.Series]]:
    return _load_regional_index_overlays(nav, BOND_REGIONS, series_prefix="bond")


def load_equity_return_overlays(nav: pd.DataFrame) -> dict[str, tuple[str, pd.Series]]:
    return _load_regional_return_overlays(nav, EQUITY_REGIONS, series_prefix="equity")


def load_bond_return_overlays(nav: pd.DataFrame) -> dict[str, tuple[str, pd.Series]]:
    return _load_regional_return_overlays(nav, BOND_REGIONS, series_prefix="bond")


def render_regional_overlay_toggles() -> tuple[dict[str, bool], dict[str, bool]]:
    st.caption("勾选后在图表上叠加各区域股票 / 债券走势")
    eq_cols = st.columns(len(EQUITY_REGIONS))
    show_equity: dict[str, bool] = {}
    for col, (code, meta) in zip(eq_cols, EQUITY_REGIONS.items()):
        with col:
            show_equity[code] = st.checkbox(
                meta["label"],
                value=False,
                key=f"bx_overlay_eq_{code}",
            )
    bd_cols = st.columns(len(BOND_REGIONS))
    show_bond: dict[str, bool] = {}
    for col, (code, meta) in zip(bd_cols, BOND_REGIONS.items()):
        with col:
            show_bond[code] = st.checkbox(
                meta["label"],
                value=False,
                key=f"bx_overlay_bd_{code}",
            )
    return show_equity, show_bond


def _add_regional_overlay_traces(
    fig: go.Figure,
    *,
    dates: pd.Series,
    overlays: dict[str, tuple[str, pd.Series]],
    show: dict[str, bool],
    secondary_y: bool,
    mode: str,
    line_dash: str,
    name_suffix: str = "",
) -> bool:
    added = False
    for code, (label, series) in overlays.items():
        if not show.get(code, False):
            continue
        name = f"{label}{name_suffix}" if name_suffix else label
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=series.tolist(),
                name=name,
                mode=mode,
                line=dict(color=_REGION_COLORS.get(code, "#888"), width=1.8, dash=line_dash),
                connectgaps=False,
            ),
            secondary_y=secondary_y,
        )
        added = True
    return added


def chart_nav(
    nav: pd.DataFrame,
    *,
    threshold: float | None = None,
    initial_total: float | None = None,
    equity_overlays: dict[str, tuple[str, pd.Series]] | None = None,
    bond_overlays: dict[str, tuple[str, pd.Series]] | None = None,
    show_equity: dict[str, bool] | None = None,
    show_bond: dict[str, bool] | None = None,
) -> go.Figure:
    df = nav.copy()
    df["date"] = pd.to_datetime(df["date"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["total_nav"], name="总净值", line=dict(width=2)),
        secondary_y=False,
    )
    if threshold is not None and initial_total is not None:
        ideal = compute_ideal_nav(df, threshold=threshold, initial_total=initial_total)
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=ideal.tolist(),
                name=f"理想净值（年化 {fmt_rate(threshold)}）",
                mode="lines",
                line=dict(width=2, dash="dash", color="#e67e22"),
            ),
            secondary_y=False,
        )
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["main_total"], name="主账户"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["reserve"], name="固定账户（平滑池）"),
        secondary_y=False,
    )
    if equity_overlays and show_equity:
        _add_regional_overlay_traces(
            fig,
            dates=df["date"],
            overlays=equity_overlays,
            show=show_equity,
            secondary_y=True,
            mode="lines+markers",
            line_dash="dot",
        )
    if bond_overlays and show_bond:
        _add_regional_overlay_traces(
            fig,
            dates=df["date"],
            overlays=bond_overlays,
            show=show_bond,
            secondary_y=True,
            mode="lines+markers",
            line_dash="dash",
        )
    fig.update_layout(
        title="账户净值走势",
        xaxis_title="日期",
        hovermode="x unified",
        legend=_LEGEND_LAYOUT,
    )
    fig.update_yaxes(title_text="金额", tickformat=",.2f", secondary_y=False)
    fig.update_yaxes(
        title_text="股票 / 债券指数（期初=100）",
        tickformat=",.2f",
        secondary_y=True,
    )
    return fig


def chart_transfers(nav: pd.DataFrame) -> go.Figure:
    df = nav.copy()
    df["date"] = pd.to_datetime(df["date"])
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["transfer_to_reserve"],
            name="转入固定账户",
            marker_color="#2ca02c",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=-df["transfer_from_reserve"],
            name="从固定账户回补",
            marker_color="#d62728",
        )
    )
    fig.update_layout(
        title="平滑池划转（年度）",
        xaxis_title="日期",
        yaxis_title="金额",
        barmode="relative",
    )
    fig.update_yaxes(tickformat=",.2f")
    return fig


def chart_returns(
    nav: pd.DataFrame,
    threshold: float,
    *,
    equity_overlays: dict[str, tuple[str, pd.Series]] | None = None,
    bond_overlays: dict[str, tuple[str, pd.Series]] | None = None,
    show_equity: dict[str, bool] | None = None,
    show_bond: dict[str, bool] | None = None,
) -> go.Figure:
    df = nav.copy()
    df["date"] = pd.to_datetime(df["date"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["r_main_before_transfer"],
            name="主账户收益率（平滑前）",
            mode="lines+markers",
        ),
        secondary_y=False,
    )
    fig.add_hline(
        y=threshold,
        line_dash="dash",
        line_color="orange",
        annotation_text=f"阈值 {fmt_rate(threshold)}",
    )
    if "total_nav" in df.columns:
        ann = df[["date", "total_nav"]].copy()
        ann["ret"] = ann["total_nav"].pct_change()
        fig.add_trace(
            go.Bar(x=ann["date"], y=ann["ret"], name="总净值环比", opacity=0.35),
            secondary_y=True,
        )
    overlay_added = False
    if equity_overlays and show_equity:
        overlay_added |= _add_regional_overlay_traces(
            fig,
            dates=df["date"],
            overlays=equity_overlays,
            show=show_equity,
            secondary_y=True,
            mode="lines+markers",
            line_dash="dot",
            name_suffix=" 股票",
        )
    if bond_overlays and show_bond:
        overlay_added |= _add_regional_overlay_traces(
            fig,
            dates=df["date"],
            overlays=bond_overlays,
            show=show_bond,
            secondary_y=True,
            mode="lines+markers",
            line_dash="dash",
            name_suffix=" 债券",
        )
    fig.update_layout(title="收益率 vs 平滑阈值", legend=_LEGEND_LAYOUT)
    fig.update_yaxes(title_text="主账户收益率", tickformat=f".{DISPLAY_DECIMALS}%", secondary_y=False)
    secondary_title = "环比 / 股票·债券年度收益" if overlay_added else "环比"
    fig.update_yaxes(title_text=secondary_title, tickformat=f".{DISPLAY_DECIMALS}%", secondary_y=True)
    return fig

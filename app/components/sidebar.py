from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

from bxsimulator.config import RunConfig
from bxsimulator.display_format import fmt_amount, fmt_number
from bxsimulator.data.regional_blend import (
    BOND_REGIONS,
    EQUITY_REGIONS,
    blend_regional_returns,
    describe_regional_coverage,
)

from bxsimulator.paths import project_root

CONFIG_YAML = project_root() / "configs" / "unified.yaml"


def _format_money(n: float) -> str:
    return fmt_amount(n)


def _parse_money(s: str) -> float:
    cleaned = str(s).replace(",", "").replace(" ", "").strip()
    if not cleaned:
        raise ValueError("empty amount")
    return float(cleaned)


_MONEY_INPUT_VERSION = "v7"


def _money_input(label: str, *, default: float, state_key: str) -> float:
    full_key = f"money_{state_key}_{_MONEY_INPUT_VERSION}"
    fmt_default = _format_money(default)

    if full_key not in st.session_state:
        st.session_state[full_key] = fmt_default
    else:
        try:
            st.session_state[full_key] = _format_money(_parse_money(st.session_state[full_key]))
        except ValueError:
            st.session_state[full_key] = fmt_default

    def _normalize() -> None:
        try:
            n = _parse_money(st.session_state[full_key])
            if n < 0:
                n = 0.0
            st.session_state[full_key] = _format_money(n)
        except ValueError:
            st.session_state[full_key] = fmt_default

    st.text_input(
        label,
        key=full_key,
        on_change=_normalize,
        help="文本框，可含千分位逗号，例如 1,000,000.00",
    )
    try:
        return _parse_money(st.session_state[full_key])
    except ValueError:
        return float(default)


_WEIGHT_TOTAL_TOLERANCE = 0.01


def _pct_weights_from_raw(raw: dict[str, float]) -> dict[str, float]:
    return {k: float(v) / 100.0 for k, v in raw.items()}


def _validate_pct_weights(raw: dict[str, float]) -> tuple[bool, float, str | None]:
    total = sum(float(v) for v in raw.values())
    if sum(1 for v in raw.values() if float(v) > 0) == 0:
        return False, total, "至少一个区域权重要大于 0"
    if abs(total - 100.0) > _WEIGHT_TOTAL_TOLERANCE:
        return False, total, f"区域权重合计须为 100.00%，当前为 {fmt_number(total)}%"
    return True, total, None


def _region_weight_inputs(
    catalog: dict[str, dict[str, str]],
    defaults: dict[str, float],
    *,
    key_prefix: str,
) -> tuple[dict[str, float], bool]:
    cols = st.columns(2, gap="small")
    raw: dict[str, float] = {}
    items = list(catalog.items())
    for i, (code, meta) in enumerate(items):
        col = cols[i % 2]
        pct_default = float(defaults.get(code, 0.0)) * 100.0
        wkey = f"{key_prefix}_{code}"
        with col:
            if wkey not in st.session_state:
                st.session_state[wkey] = pct_default
            raw[code] = float(
                st.number_input(
                    meta["label"],
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key=wkey,
                )
            )
    ok, total, message = _validate_pct_weights(raw)
    if ok:
        st.caption("合计 100.00%")
    else:
        st.error(message or f"区域权重合计须为 100.00%，当前为 {fmt_number(total)}%")
    return _pct_weights_from_raw(raw), ok


# Border colors aligned with theme primary (#1f4e79) and chart palette.
_SIDEBAR_BLOCK_BORDERS: dict[str, tuple[str, str]] = {
    "参数配置": ("sidebar_block_params", "#1f4e79"),
    "区域股票权重": ("sidebar_block_equity", "#2874a6"),
    "区域债券权重": ("sidebar_block_bond", "#3d8b7a"),
    "初始资金": ("sidebar_block_capital", "#5b6b8c"),
    "回测区间": ("sidebar_block_range", "#c2783a"),
}


def inject_sidebar_block_styles() -> None:
    """Inject colored borders and compact spacing for sidebar blocks."""
    rules = []
    for _, (key, color) in _SIDEBAR_BLOCK_BORDERS.items():
        block_rule = f"border: 2px solid {color} !important;"
        rules.append(
            f"""
            section[data-testid="stSidebar"] [data-testid="stVerticalBlock"].st-key-{key} {{
                {block_rule}
            }}
            section[data-testid="stSidebar"] .element-container:has(#bx-anchor-{key})
                + .element-container [data-testid="stVerticalBlock"] {{
                {block_rule}
            }}
            """
        )
    rules.append(
        """
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding-top: 0.75rem !important;
            padding-bottom: 0.75rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.42rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.55rem 0.6rem 0.58rem !important;
            margin-bottom: 0.45rem !important;
        }
        section[data-testid="stSidebar"] .element-container {
            margin-bottom: 0.18rem !important;
        }
        section[data-testid="stSidebar"] .bx-sidebar-block-title {
            font-size: 0.95rem;
            font-weight: 650;
            line-height: 1.35;
            margin: 0 0 0.55rem 0;
            padding-bottom: 0.1rem;
            color: #1a2433;
        }
        section[data-testid="stSidebar"] .element-container:has(.bx-sidebar-block-title) {
            margin-bottom: 0.35rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            margin-top: 0.05rem !important;
            margin-bottom: 0.12rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            font-size: 0.78rem !important;
            line-height: 1.25 !important;
            margin: 0 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
            font-size: 0.84rem !important;
            margin-bottom: 0.18rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
        section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
            min-height: 1.65rem !important;
            padding-top: 0.15rem !important;
            padding-bottom: 0.15rem !important;
            font-size: 0.84rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stNumberInputStepDown"],
        section[data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] {
            min-height: 1.65rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSlider"] {
            padding-top: 0.18rem !important;
            padding-bottom: 0.22rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSlider"] [data-testid="stThumbValue"] {
            font-size: 0.75rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stCheckbox"] {
            min-height: 1.5rem !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stDateInput"] {
            padding-top: 0.05rem !important;
            padding-bottom: 0.1rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
            min-height: 1.55rem !important;
            font-size: 0.82rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
            font-size: 0.82rem !important;
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {
            gap: 0.2rem !important;
        }
        section[data-testid="stSidebar"] button[kind="primary"] {
            min-height: 2rem !important;
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
            margin-top: 0.15rem !important;
        }
        """
    )
    st.markdown(f"<style>{''.join(rules)}</style>", unsafe_allow_html=True)


@contextmanager
def _sidebar_block(title: str):
    block_key, _ = _SIDEBAR_BLOCK_BORDERS[title]
    st.markdown(
        f'<div id="bx-anchor-{block_key}" aria-hidden="true" style="display:none"></div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True, key=block_key):
        st.markdown(f'<p class="bx-sidebar-block-title">{title}</p>', unsafe_allow_html=True)
        yield


def build_config_from_ui(
    equity_pct: float,
    threshold_pct: float,
    initial_main: float,
    initial_reserve: float,
    max_fill_pct: float,
    equity_regions: dict[str, float],
    bond_regions: dict[str, float],
) -> RunConfig:
    cfg = RunConfig.from_yaml(CONFIG_YAML)
    bond_pct = 100.0 - equity_pct
    cfg = replace(
        cfg,
        equity_weight=equity_pct / 100.0,
        bond_weight=bond_pct / 100.0,
        equity_min=0.0,
        equity_max=1.0,
        bond_min=0.0,
        bond_max=1.0,
        smoothing_threshold=threshold_pct / 100.0,
        initial_main_value=float(initial_main),
        initial_reserve=float(initial_reserve),
        max_fill_fraction_of_shortfall=max_fill_pct / 100.0,
        equity_regions=equity_regions,
        bond_regions=bond_regions,
    )
    cfg.validate()
    return cfg


def load_returns_from_ui(
    equity_regions: dict[str, float],
    bond_regions: dict[str, float],
) -> pd.DataFrame:
    return blend_regional_returns(equity_regions, bond_regions)


def _param_with_slider(
    label: str,
    *,
    state_key: str,
    min_value: float,
    max_value: float,
    default: float,
    number_step: float,
    slider_step: float = 0.1,
    help: str | None = None,
) -> float:
    """Number input (+/− on the right, like regional weights) plus a drag slider below."""
    slider_key = f"{state_key}_slider"
    if state_key not in st.session_state:
        st.session_state[state_key] = default
    if slider_key not in st.session_state:
        st.session_state[slider_key] = default

    def _sync_from_number() -> None:
        st.session_state[slider_key] = st.session_state[state_key]

    def _sync_from_slider() -> None:
        st.session_state[state_key] = st.session_state[slider_key]

    st.number_input(
        label,
        min_value=min_value,
        max_value=max_value,
        step=number_step,
        key=state_key,
        help=help,
        on_change=_sync_from_number,
    )
    st.slider(
        label,
        min_value=min_value,
        max_value=max_value,
        step=slider_step,
        key=slider_key,
        label_visibility="collapsed",
        on_change=_sync_from_slider,
    )
    return float(st.session_state[state_key])


def _returns_date_bounds(
    equity_regions: dict[str, float],
    bond_regions: dict[str, float],
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    try:
        df = blend_regional_returns(equity_regions, bond_regions)
        if df.empty:
            return None, None
        return pd.Timestamp(df.index.min()), pd.Timestamp(df.index.max())
    except Exception:
        return None, None


def render_sidebar() -> dict:
    defaults = RunConfig.from_yaml(CONFIG_YAML)
    inject_sidebar_block_styles()

    with _sidebar_block("参数配置"):
        threshold_pct = _param_with_slider(
            "平滑阈值 (%)",
            state_key="bx_threshold_pct",
            min_value=0.0,
            max_value=100.0,
            default=float(defaults.smoothing_threshold * 100),
            number_step=0.5,
            slider_step=0.1,
            help="主账户年度收益低于该阈值时从固定账户补入；高于该阈值时划入固定账户。",
        )
        equity_pct = int(
            _param_with_slider(
                "股票权重 (%)",
                state_key="bx_equity_pct",
                min_value=0.0,
                max_value=100.0,
                default=float(int(defaults.equity_weight * 100)),
                number_step=1.0,
                slider_step=1.0,
            )
        )
        st.caption(f"债券权重：{fmt_number(100 - equity_pct)}%")

    with _sidebar_block("区域股票权重"):
        equity_regions, equity_weights_ok = _region_weight_inputs(
            EQUITY_REGIONS,
            defaults.equity_regions,
            key_prefix="eq",
        )
        with st.expander("各区域数据覆盖范围"):
            st.dataframe(describe_regional_coverage(), hide_index=True, use_container_width=True)

    with _sidebar_block("区域债券权重"):
        bond_regions, bond_weights_ok = _region_weight_inputs(
            BOND_REGIONS,
            defaults.bond_regions,
            key_prefix="bd",
        )

    with _sidebar_block("初始资金"):
        cap_main, cap_reserve = st.columns(2, gap="small")
        with cap_main:
            initial_main = _money_input(
                "期初主账户",
                default=float(defaults.initial_main_value),
                state_key="initial_main_amount",
            )
        with cap_reserve:
            initial_reserve = _money_input(
                "期初固定账户",
                default=float(defaults.initial_reserve),
                state_key="initial_reserve_amount",
            )
        max_fill_pct = st.slider(
            "缺口最大填补比例 (%)",
            1,
            100,
            int(defaults.max_fill_fraction_of_shortfall * 100),
        )

    region_weights_ok = equity_weights_ok and bond_weights_ok

    with _sidebar_block("回测区间"):
        if region_weights_ok:
            data_min, data_max = _returns_date_bounds(equity_regions, bond_regions)
        else:
            data_min, data_max = None, None
        if data_min is not None and data_max is not None:
            st.caption(
                f"可用 {data_min.date()} → {data_max.date()}（{data_max.year - data_min.year + 1} 年）"
            )
        use_filter = st.checkbox("限制起止日期", value=True)
        start_date = end_date = None
        if use_filter:
            default_start = data_min.date() if data_min is not None else pd.Timestamp("2010-01-01").date()
            default_end = data_max.date() if data_max is not None else pd.Timestamp("2024-12-31").date()
            picker_min = data_min.date() if data_min is not None else pd.Timestamp("1980-01-01").date()
            picker_max = data_max.date() if data_max is not None else pd.Timestamp("2030-12-31").date()
            date_start_col, date_end_col = st.columns(2, gap="small")
            with date_start_col:
                start_date = st.date_input(
                    "开始日期",
                    value=default_start,
                    min_value=picker_min,
                    max_value=picker_max,
                )
            with date_end_col:
                end_date = st.date_input(
                    "结束日期",
                    value=default_end,
                    min_value=picker_min,
                    max_value=picker_max,
                )
        run_clicked = st.button(
            "运行回测",
            type="primary",
            use_container_width=True,
            disabled=not region_weights_ok,
        )

    return {
        "equity_pct": equity_pct,
        "threshold_pct": threshold_pct,
        "initial_main": initial_main,
        "initial_reserve": initial_reserve,
        "max_fill_pct": max_fill_pct,
        "equity_regions": equity_regions,
        "bond_regions": bond_regions,
        "region_weights_ok": region_weights_ok,
        "start_date": start_date,
        "end_date": end_date,
        "use_filter": use_filter,
        "run_clicked": run_clicked,
    }

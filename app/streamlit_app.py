from __future__ import annotations

import sys
from pathlib import Path

import importlib
import pandas as pd
import streamlit as st

# Ensure project root + src package are importable (Streamlit Cloud / local).
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(SRC), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


BACKTEST_ENGINE_ID = "benchmark-path-v1"


def _ensure_bxsimulator_from_src() -> None:
    """Drop cached bxsimulator modules not loaded from this repo's src/."""
    if not (SRC / "bxsimulator").is_dir():
        return
    src_marker = str(SRC).replace("\\", "/")
    for name in list(sys.modules):
        if name != "bxsimulator" and not name.startswith("bxsimulator."):
            continue
        mod = sys.modules.get(name)
        mod_file = getattr(mod, "__file__", None) or ""
        if mod_file and src_marker not in mod_file.replace("\\", "/"):
            del sys.modules[name]


def _reload_engine_modules() -> None:
    """Pick up engine changes during Streamlit hot-reload (editable install cache)."""
    _ensure_bxsimulator_from_src()
    import bxsimulator.engine.state as state_mod
    import bxsimulator.engine.smooth as smooth_mod
    import bxsimulator.engine.backtest as backtest_mod

    importlib.reload(state_mod)
    importlib.reload(smooth_mod)
    importlib.reload(backtest_mod)


_reload_engine_modules()

from app.components.brand_header import render_brand_header  # noqa: E402
from app.components.charts import (
    chart_nav,
    chart_returns,
    chart_transfers,
    load_bond_index_overlays,
    load_bond_return_overlays,
    load_equity_index_overlays,
    load_equity_return_overlays,
    render_regional_overlay_toggles,
)  # noqa: E402
import app.components.sidebar as _sidebar_module
importlib.reload(_sidebar_module)
from app.components.sidebar import (
    build_config_from_ui,
    load_returns_from_ui,
    render_sidebar,
)  # noqa: E402
from bxsimulator.config import RunConfig
from bxsimulator.display_format import fmt_amount, format_nav_table_for_display
from bxsimulator.engine.backtest import run_backtest
from bxsimulator.engine.state import PortfolioState
from bxsimulator.export.excel import export_nav_table_csv_bytes, export_nav_table_excel_bytes


def _nav_export_stem(nav: pd.DataFrame) -> str:
    dates = pd.to_datetime(nav["date"])
    return f"bxsim_detail_{dates.min():%Y%m%d}_{dates.max():%Y%m%d}"


def _run_backtest_from_ui(ui: dict) -> tuple[RunConfig, pd.DataFrame, PortfolioState]:
    cfg = build_config_from_ui(
        equity_pct=ui["equity_pct"],
        threshold_pct=ui["threshold_pct"],
        initial_main=ui["initial_main"],
        initial_reserve=ui["initial_reserve"],
        max_fill_pct=ui["max_fill_pct"],
        equity_regions=ui["equity_regions"],
        bond_regions=ui["bond_regions"],
    )
    returns = load_returns_from_ui(ui["equity_regions"], ui["bond_regions"])
    start = str(ui["start_date"]) if ui["use_filter"] and ui["start_date"] else None
    end = str(ui["end_date"]) if ui["use_filter"] and ui["end_date"] else None
    nav, final = run_backtest(cfg, returns, start=start, end=end)
    return cfg, nav, final


def _render_results(cfg: RunConfig, nav: pd.DataFrame, final: PortfolioState) -> None:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("期末总净值", fmt_amount(final.total_nav()))
    m2.metric("主账户", fmt_amount(final.main_total()))
    m3.metric("固定账户", fmt_amount(final.reserve))
    m4.metric("回测期数", len(nav))
    if "benchmark_main_end" not in nav.columns:
        st.warning("当前结果为旧版引擎缓存，请重新点击 **运行回测**。")
    else:
        st.caption(f"平滑引擎：{BACKTEST_ENGINE_ID}（明细表含「基准主账户」列）")

    show_equity, show_bond = render_regional_overlay_toggles()
    equity_index = load_equity_index_overlays(nav)
    bond_index = load_bond_index_overlays(nav)
    equity_returns = load_equity_return_overlays(nav)
    bond_returns = load_bond_return_overlays(nav)

    tab1, tab2, tab3, tab4 = st.tabs(["净值", "平滑划转", "收益率", "明细表"])

    with tab1:
        st.plotly_chart(
            chart_nav(
                nav,
                threshold=cfg.smoothing_threshold,
                initial_total=cfg.initial_main_value + cfg.initial_reserve,
                equity_overlays=equity_index,
                bond_overlays=bond_index,
                show_equity=show_equity,
                show_bond=show_bond,
            ),
            use_container_width=True,
        )
    with tab2:
        st.plotly_chart(chart_transfers(nav), use_container_width=True)
    with tab3:
        st.plotly_chart(
            chart_returns(
                nav,
                cfg.smoothing_threshold,
                equity_overlays=equity_returns,
                bond_overlays=bond_returns,
                show_equity=show_equity,
                show_bond=show_bond,
            ),
            use_container_width=True,
        )
    with tab4:
        export_stem = _nav_export_stem(nav)
        dl_xlsx, dl_csv, _ = st.columns([1, 1, 4])
        with dl_xlsx:
            st.download_button(
                "导出 Excel",
                data=export_nav_table_excel_bytes(nav),
                file_name=f"{export_stem}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with dl_csv:
            st.download_button(
                "导出 CSV",
                data=export_nav_table_csv_bytes(nav),
                file_name=f"{export_stem}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.dataframe(format_nav_table_for_display(nav), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(
        page_title="分红产品投资仿真器 · Alpha Wang",
        page_icon="chart",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    render_brand_header("分红产品投资仿真器")

    if st.session_state.get("backtest_engine_id") != BACKTEST_ENGINE_ID:
        st.session_state.pop("backtest_result", None)
        st.session_state["backtest_engine_id"] = BACKTEST_ENGINE_ID

    with st.sidebar:
        ui = render_sidebar()

    if ui["run_clicked"]:
        if not ui.get("region_weights_ok", False):
            st.error("区域股票/债券权重合计须为 100.00% 后才能运行回测。")
            return
        try:
            cfg, nav, final = _run_backtest_from_ui(ui)
            st.session_state["backtest_result"] = {
                "cfg": cfg,
                "nav": nav,
                "final": final,
            }
        except Exception as e:
            st.error(f"回测失败：{e}")
            return

    result = st.session_state.get("backtest_result")
    if result is None:
        st.info("在左侧配置参数，点击 **运行回测** 查看图表。")
        st.markdown(
            """
**快速开始**
1. 设置 **平滑阈值 (%)** 与 **主账户股债比例**
2. 在 **区域股票/债券权重** 中勾选参与区域并配置权重（合计 100%）
3. 点击 **运行回测**
            """
        )
        return

    _render_results(result["cfg"], result["nav"], result["final"])


main()

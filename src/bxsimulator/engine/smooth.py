from __future__ import annotations

from dataclasses import dataclass

from bxsimulator.config import RunConfig
from bxsimulator.engine.state import PortfolioState


@dataclass
class StepResult:
    state: PortfolioState
    period_end: object
    main_begin: float
    main_after_returns: float
    r_main_before_transfer: float
    transfer_to_reserve: float
    transfer_from_reserve: float
    r_short: float
    pending_main_fill: float
    benchmark_main_end: float


def _inject_reserve_to_main(
    eq1: float,
    bd1: float,
    amount: float,
    cfg: RunConfig,
) -> tuple[float, float]:
    if amount <= 0.0:
        return eq1, bd1
    mt = eq1 + bd1
    if mt > 0.0:
        eq1 += amount * (eq1 / mt)
        bd1 += amount * (bd1 / mt)
    else:
        eq1 += amount * cfg.equity_weight
        bd1 += amount * cfg.bond_weight
    return eq1, bd1


def _skim_main_to_reserve(
    eq1: float,
    bd1: float,
    main_after: float,
    amount: float,
    res1: float,
) -> tuple[float, float, float]:
    if amount <= 0.0 or main_after <= 0.0:
        return eq1, bd1, res1
    scale = max(0.0, (main_after - amount) / main_after)
    eq1 *= scale
    bd1 *= scale
    res1 += amount
    return eq1, bd1, res1


def simulate_period(
    state: PortfolioState,
    r_equity: float,
    r_bond: float,
    r_short: float,
    cfg: RunConfig,
    period_end,
) -> StepResult:
    eq0, bd0, res0 = state.main_equity, state.main_bond, state.reserve
    pending_m = float(state.pending_main_fill)
    benchmark_begin = float(state.benchmark_main)
    main_begin = eq0 + bd0
    if main_begin <= 0:
        raise ValueError("main_begin must be positive")

    eq1 = eq0 * (1.0 + r_equity)
    bd1 = bd0 * (1.0 + r_bond)
    main_after = eq1 + bd1

    res1 = res0 * (1.0 + r_short)

    r_main = (main_after - main_begin) / main_begin
    th = cfg.smoothing_threshold
    max_fill = cfg.max_fill_fraction_of_shortfall
    benchmark_end = benchmark_begin * (1.0 + th)

    shortfall_vs_benchmark = max(0.0, benchmark_end - main_after)
    surplus_vs_benchmark = max(0.0, main_after - benchmark_end)

    transfer_to_reserve = 0.0
    transfer_from_reserve = 0.0

    if shortfall_vs_benchmark > 0.0:
        gross_need = shortfall_vs_benchmark * max_fill + pending_m
        transfer_from_reserve = min(res1, gross_need)
        pending_m = gross_need - transfer_from_reserve
        res1 -= transfer_from_reserve
        eq1, bd1 = _inject_reserve_to_main(eq1, bd1, transfer_from_reserve, cfg)
    elif surplus_vs_benchmark > 0.0:
        repay = min(pending_m, surplus_vs_benchmark)
        pending_m -= repay
        transfer_to_reserve = surplus_vs_benchmark - repay
        eq1, bd1, res1 = _skim_main_to_reserve(
            eq1, bd1, main_after, transfer_to_reserve, res1
        )

    main_total = eq1 + bd1
    ew, bw = cfg.equity_weight, cfg.bond_weight
    eq2 = main_total * ew
    bd2 = main_total * bw

    new_state = PortfolioState(
        main_equity=eq2,
        main_bond=bd2,
        reserve=res1,
        benchmark_main=benchmark_end,
        pending_main_fill=float(pending_m),
    )
    return StepResult(
        state=new_state,
        period_end=period_end,
        main_begin=main_begin,
        main_after_returns=float(main_after),
        r_main_before_transfer=float(r_main),
        transfer_to_reserve=float(transfer_to_reserve),
        transfer_from_reserve=float(transfer_from_reserve),
        r_short=float(r_short),
        pending_main_fill=float(pending_m),
        benchmark_main_end=float(benchmark_end),
    )

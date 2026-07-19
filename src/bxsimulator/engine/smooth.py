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
    pending_reserve_deposit: float


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
    pending_r = float(state.pending_reserve_deposit)
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

    year_to_main = main_begin * max(0.0, th - r_main) * max_fill
    year_to_reserve = main_begin * max(0.0, r_main - th)

    transfer_to_reserve = 0.0
    transfer_from_reserve = 0.0

    if year_to_main > 0.0:
        gross_need = year_to_main + pending_m + pending_r
        transfer_from_reserve = min(res1, gross_need)
        remaining = transfer_from_reserve

        alloc_year = min(remaining, year_to_main)
        remaining -= alloc_year
        alloc_pending_m = min(remaining, pending_m)
        remaining -= alloc_pending_m
        alloc_pending_r = min(remaining, pending_r)

        pending_m = pending_m - alloc_pending_m + (year_to_main - alloc_year)
        pending_r = pending_r - alloc_pending_r
        res1 -= transfer_from_reserve
        eq1, bd1 = _inject_reserve_to_main(eq1, bd1, transfer_from_reserve, cfg)

    elif year_to_reserve > 0.0:
        repay_main = min(pending_m, year_to_reserve)
        pending_m -= repay_main
        skim = year_to_reserve - repay_main
        transfer_to_reserve = skim
        pending_r += repay_main
        if skim > 0.0:
            cleared = min(pending_r, skim)
            pending_r -= cleared
        eq1, bd1, res1 = _skim_main_to_reserve(eq1, bd1, main_after, transfer_to_reserve, res1)

    main_total = eq1 + bd1
    ew, bw = cfg.equity_weight, cfg.bond_weight
    eq2 = main_total * ew
    bd2 = main_total * bw

    new_state = PortfolioState(
        main_equity=eq2,
        main_bond=bd2,
        reserve=res1,
        pending_main_fill=float(pending_m),
        pending_reserve_deposit=float(pending_r),
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
        pending_reserve_deposit=float(pending_r),
    )

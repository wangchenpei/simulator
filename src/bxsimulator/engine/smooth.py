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


def simulate_period(
    state: PortfolioState,
    r_equity: float,
    r_bond: float,
    r_short: float,
    cfg: RunConfig,
    period_end,
) -> StepResult:
    eq0, bd0, res0 = state.main_equity, state.main_bond, state.reserve
    main_begin = eq0 + bd0
    if main_begin <= 0:
        raise ValueError("main_begin must be positive")

    eq1 = eq0 * (1.0 + r_equity)
    bd1 = bd0 * (1.0 + r_bond)
    main_after = eq1 + bd1

    res1 = res0 * (1.0 + r_short)

    r_main = (main_after - main_begin) / main_begin
    th = cfg.smoothing_threshold

    transfer_to_reserve = main_begin * max(0.0, r_main - th)
    shortfall = main_begin * max(0.0, th - r_main) * cfg.max_fill_fraction_of_shortfall
    transfer_from_reserve = min(res1, shortfall)

    if transfer_to_reserve > 0.0 and main_after > 0.0:
        scale = max(0.0, (main_after - transfer_to_reserve) / main_after)
        eq1 *= scale
        bd1 *= scale
        res1 += transfer_to_reserve

    if transfer_from_reserve > 0.0:
        res1 -= transfer_from_reserve
        mt = eq1 + bd1
        if mt > 0.0:
            eq1 += transfer_from_reserve * (eq1 / mt)
            bd1 += transfer_from_reserve * (bd1 / mt)
        else:
            eq1 += transfer_from_reserve * cfg.equity_weight
            bd1 += transfer_from_reserve * cfg.bond_weight

    main_total = eq1 + bd1
    ew, bw = cfg.equity_weight, cfg.bond_weight
    eq2 = main_total * ew
    bd2 = main_total * bw

    new_state = PortfolioState(main_equity=eq2, main_bond=bd2, reserve=res1)
    return StepResult(
        state=new_state,
        period_end=period_end,
        main_begin=main_begin,
        main_after_returns=float(main_after),
        r_main_before_transfer=float(r_main),
        transfer_to_reserve=float(transfer_to_reserve),
        transfer_from_reserve=float(transfer_from_reserve),
        r_short=float(r_short),
    )

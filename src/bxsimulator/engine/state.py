from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PortfolioState:
    main_equity: float
    main_bond: float
    reserve: float
    benchmark_main: float
    pending_main_fill: float = 0.0

    def main_total(self) -> float:
        return float(self.main_equity + self.main_bond)

    def total_nav(self) -> float:
        return float(self.main_equity + self.main_bond + self.reserve)

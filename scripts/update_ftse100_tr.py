"""Rebuild FTSE 100 total-return eu_equity in components_annual.csv."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from bxsimulator.data.offline_us_eu import _ftse100_total_return

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "offline" / "raw"
COMPONENTS = RAW / "components_annual.csv"
PRICE_OUT = RAW / "ftse100_price_annual.csv"
DIV_YIELD = RAW / "ftse100_div_yield_annual.csv"


def main() -> None:
    comp = pd.read_csv(COMPONENTS)
    if not PRICE_OUT.exists():
        comp[["year", "eu_equity"]].rename(columns={"eu_equity": "price_return"}).to_csv(
            PRICE_OUT, index=False, float_format="%.4f"
        )
        print(f"Created price archive: {PRICE_OUT}")

    price = pd.read_csv(PRICE_OUT).set_index("year")["price_return"]
    div = pd.read_csv(DIV_YIELD).set_index("year")["div_yield"]
    tr = _ftse100_total_return(price, div)

    comp["eu_equity"] = comp["year"].map(tr).astype(float)
    comp.to_csv(COMPONENTS, index=False, float_format="%.4f")

    print(f"Updated TR eu_equity in: {COMPONENTS}")
    for y in (1985, 2000, 2020, 2024, 2025):
        print(f"  {y}: price={price.loc[y]:.4f} tr={tr.loc[y]:.4f}")


if __name__ == "__main__":
    main()

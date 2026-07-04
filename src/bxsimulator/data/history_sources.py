from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HistoryPreset = Literal["default", "long"]

# Recommended longest reliable combo for this project (CN limits equity bundle to ~2005+).
LONG_HISTORY_SYMBOLS = {
    "us_symbol": "SPY",       # AkShare 东财美股 ETF；2005+ 与缓存一致
    "hk_symbol": "^HSI",      # 恒生指数（Stooq/Yahoo）；避免 2800.HK 早期异常价
    "cn_symbol": "000300",    # 沪深300指数；官方约 2005-04 起
    "bond_symbol": "IEF",     # 7-10年美债 ETF；通常远早于 BND 的 AkShare 覆盖
}

# Auto-pick order when --auto-symbols is used (first successful longest history wins).
US_CANDIDATES = ("SPY", "^GSPC")
HK_CANDIDATES = ("^HSI", "2800.HK", "03033.HK")
BOND_CANDIDATES = ("IEF", "AGG", "TLT", "BND", "SHY")

PRESET_NOTES = """
最长可用区间（经验组合，实际以 diagnose-history 输出为准）：
- A股 沪深300：约 2005 年起（指数发布限制，硬上限）
- 美股 SPY：约 2005+（AkShare）；^GSPC 指数可更早但需 Stooq/Yahoo
- 港股 ^HSI：约 1980 年代起（指数）；优于 2800.HK ETF 的早期脏数据
- 债券 IEF/AGG：约 2002–2003 起；BND 在 AkShare 往往仅 2018+
合成年度表起始年 ≈ max(各序列首个可算年度收益年) 的交集，通常约 2006–2007（CN+债券对齐后）。
"""

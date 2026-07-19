# BX 双产品投资平滑模拟器

统一回测内核 + 两套产品配置（**分红储蓄**：默认股 60% / 债 40%，平滑阈值 **6.5%**；**重疾+年金**：默认股 25% / 债 75%，平滑阈值 **4.5%**），支持导出多工作表 Excel。

## 收益与划转口径（年度步进）

1. **期初**：记录主账户合计 `main_begin = equity + bond`，固定账户 `reserve_begin`。
2. **主账户资产收益**：`equity *= (1 + r_equity)`，`bond *= (1 + r_bond)`（本期 `r_*` 来自数据层，可为年度收益率）。
3. **固定账户短债计息**：`reserve *= (1 + r_short)`（先对期初 reserve 计息；与主账户同一时期）。
4. **平滑前主账户收益率**：`r_main = (main_after - main_begin) / main_begin`，其中 `main_after` 为步骤 2 之后、划转之前的主账户合计。
5. **划转**（含跨年结转）：
   - 先按阈值计算本期主账户应**回补**或**划入平滑池**的金额。
   - 若 `r_main < threshold`：从平滑池回补 `min(池余额, 本期应回补 + 待补主账户 + 待入平滑池)`；不足部分记入 **待补主账户**。
   - 若 `r_main > threshold`：超出阈值部分优先冲减 **待补主账户**（留在主账户、不划入平滑池）；剩余部分划入平滑池，并冲减 **待入平滑池**；为补回主账户而暂未划入平滑池的部分记入 **待入平滑池**。
6. **再平衡**：将主账户股、债调回配置中的目标 `equity_weight` / `bond_weight`（固定账户**不参与**股债比例分母）。

阈值与权重在 YAML 中配置；股权重必须在产品允许的 `[equity_min, equity_max]` 内，且 `equity_weight + bond_weight == 1`。

## 安装

```bash
cd "C:\N-21AJPF46TWSF-Data\chenwang\Desktop\my cursor\BX\Simulator"
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

可选行情依赖（接入 Yahoo / AkShare）：

```bash
pip install -e ".[live]"
```

## 可视化网页（本地 Streamlit）

```bash
pip install -e ".[ui]"
bxsim-web
```

`bxsim-web` 会定位项目里的 `app/streamlit_app.py`，**在任意当前目录**都可启动。等价命令：

```bash
python -m bxsimulator ui
streamlit run app/streamlit_app.py   # 仍需在项目根目录下
```

浏览器打开提示的地址（默认 `http://localhost:8501`）。左侧配置产品、股债比例、平滑阈值与数据 CSV，点击 **运行回测** 查看 Plotly 图表，并可下载 Excel。

**说明（MVP）**：网页版使用内置离线区域数据包，无需外网行情 API。

**线上部署（给同事用）**：见 [DEPLOY.md](DEPLOY.md)（Streamlit Cloud / Docker / Render / 内网服务器）。

## 运行（CLI）

**CSV 历史收益率（无网络，推荐学习用）**

```bash
python -m bxsimulator run --config configs\participating_us_eu.yaml --export out_us_eu.xlsx
python -m bxsimulator describe-offline
```

### 区域离线数据包（美 / 英 / 中 / 日）

`data/offline/regions/` 下 8 个独立 CSV（`year,r`）。Web 界面选 **区域离线包（自定义配比）** 可分别设置股票与债券的区域权重。

| 文件 | 含义 |
|------|------|
| `us_equity.csv` | 美国·标普500 |
| `uk_equity.csv` | 英国·FTSE100 |
| `cn_equity.csv` | 中国·沪深300（2005 起） |
| `jp_equity.csv` | 日本·日经225 |
| `us_bond.csv` | 美国·长期国债 |
| `uk_bond.csv` / `jp_bond.csv` | 英 / 日 10Y 国债总回报近似 |
| `cn_bond.csv` | 中国·10年期国债 |

维护脚本：`python scripts/build_regional_packs.py`（需网络）。

内置 **`data/offline/us_eu_long_annual.csv`**：欧美 50/50 预设（1985–2025），可在「预设合成文件（旧）」中使用。

```bash
python -m bxsimulator run --config configs\participating.yaml --export out_participating.xlsx
```

默认 `returns.csv_path` 相对于 `configs` 目录解析（示例为 `../data/sample_returns.csv`）。

**合成数据（演示）**

```bash
python -m bxsimulator run --config configs\ci_annuity.yaml --source synthetic --seed 42 --export out_ci.xlsx
```

**拉取 Yahoo + AkShare 合成年度收益（需安装 live 依赖与网络）**

```bash
pip install -e ".[live]"
python -m bxsimulator fetch-live --config configs\participating.yaml --output data\live_annual.csv --price-source akshare
python -m bxsimulator run --config configs\participating.yaml --source csv --csv data\live_annual.csv --export out_live.xlsx
```

默认 `--price-source auto`：**AkShare（东财）→ Stooq → FRED → Yahoo**。国内网络建议直接用 `--price-source akshare`。汇率仍用 FRED；A 股用 AkShare 沪深300。

若 A 股指数接口不稳定，可自备沪深300日线 CSV（列 `date,close`），例如：

```bash
python -m bxsimulator fetch-live --config configs\participating.yaml --output data\live_participating.csv --price-source akshare --cn-csv data\csi300_daily.csv
```

### 最长历史组合（推荐）

| 市场 | 代码 | 说明 |
|------|------|------|
| 美股 | **SPY** | AkShare 东财；约 2005+ |
| 港股 | **^HSI** | 恒生指数（Stooq/Yahoo）；避免 2800.HK 早期异常价 |
| A股 | **000300** | 沪深300；约 **2005-04** 起（硬上限） |
| 债券 | **IEF** | 7–10年美债 ETF；**勿用 BND**（AkShare 常仅 2018+） |

**1. 诊断各市场覆盖：**

```bash
python -m bxsimulator diagnose-history --config configs\participating_long.yaml --preset long --start 1990-01-01
```

**2. 拉最长年度 CSV（建议清 BND 旧缓存或 `--no-cache` 首次）：**

```bash
python -m bxsimulator fetch-live --config configs\participating_long.yaml --preset long --output data\live_participating_long.csv --start 2005-01-01 --price-source auto --request-delay 2
```

预期合成后约 **2006–2007 年起** 有年度行（首年 `pct_change` 会少一行），直到最新年；具体以 `diagnose-history` 的 `INTERSECTION` 为准。

## 数据文件格式（CSV）

列：`date,r_equity,r_bond,r_short`（`date` 为期末日期；收益为小数，如 `0.08` 表示 8%）。年度回测时每行代表一个年度区间收益。

## 项目结构

- `app/`：Streamlit 可视化界面
- `configs/`：示例产品配置
- `src/bxsimulator/`：配置、数据加载、引擎、Excel 导出、CLI
- `data/sample_returns.csv`：示例年度收益（6 年演示）
- `data/offline/us_eu_long_annual.csv`：欧美离线长历史（41 年，无需网络；由 `components_annual.csv` 自动生成）

## 说明

- 本工具为**研究/教育用抽象模型**，不等于任何保险公司实际分红基金或账户处理。
- 多市场汇率与交易日对齐在 `fetch-live` 中做**简化**处理：各区域以当地货币计价资产收益，再按**年末即期汇率**换算到记账货币（默认 CNY）后合成加权股票收益；债券侧使用单一代理序列。详见 `data/yahoo_akshare.py`。
- **再平衡频率**：引擎按收益表**每一行**执行一次完整步进（年表即年度，月表即月度）。配置项 `rebalance_frequency` 用于约束/文档，当前不改变步进逻辑；若需严格「仅年末再平衡」，请提供仅含年末行的收益表。

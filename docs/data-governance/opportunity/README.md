# 红利机会值（A股）· 模块说明

> 2026-10-08：本模块已由独立的 `红利机会值/` 文件夹**并入主站统一管理**（不再有独立页面 / iframe / 独立目录）。
> 本文档替代原 `红利机会值/README.md`。

中证红利（000922.CSI）加减仓打分。机会值 0–100，**50 = 中性值**；越高越适合加仓，越低越该谨慎。
适用周期：未来 6–12 个月的方向判断，不预测涨跌幅度。方法细节见同目录 `方法说明.md`。

## 文件位置（并入后）

| 路径 | 内容 | 谁来改 |
|---|---|---|
| `opportunity_engine.py`（仓库根） | 计算引擎（Python，依赖 pandas、openpyxl） | Claude（研究、改算法） |
| `opportunity_config.json`（仓库根） | 输入路径、窗口、映射区间、权重 | Claude（研究、改参数） |
| `inputs/opportunity/`（本地，不入库） | Wind 导出的原始数据（`data_add.xlsx`、`中国_国债到期收益率_10年.csv`、可选 `wind_daily.csv`） | 用户 |
| `data/curation/opportunity_observe.json` | 观察指标（不计分，手工维护最新值） | 用户 |
| `data/opportunity.json` | 页面数据（JSON，供页面 fetch） | 由引擎生成，**不要手改** |
| `data/opportunity_history_monthly.csv` | 2018 年以来每月末的机会值与四项机会分 | 由引擎生成 |
| `index.html` → `#subOpportunity` | 页面 DOM（已内联进主站） | 网页 Agent |
| `opportunity-page.js` | 页面渲染 / 图表逻辑（IIFE，挂在 `window.OpportunityPage`） | 网页 Agent |
| `docs/data-governance/opportunity/` | 本说明 + 方法说明 + 输入说明 + prompts | — |

## 分工

- **算法与研究**：改 `opportunity_engine.py` / `opportunity_config.json` / `方法说明.md`。
- **网页与部署**：改 `index.html` 的 `#subOpportunity`、`opportunity-page.js`；**不改引擎算法与 data 里的数字**。
- **数据更新**：见下。

## 更新数据（已纳入周更）

1. 从 Wind 重新导出两个文件，覆盖 `inputs/opportunity/` 下的同名文件（格式见 `输入数据说明.md`）：
   - `data_add.xlsx`（「收盘价+成交额+换手率」「市盈率+市净率」两个 sheet）
   - `中国_国债到期收益率_10年.csv`
2. 运行：`python3 opportunity_engine.py`（终端打印「✅ 数据截至 …，机会值 …」即成功；`data/` 下两个文件被覆盖）。
3. 周更流水线（`auto_sync_deploy.sh`）已接入本引擎：周更档会先跑引擎再跑 `check_data.py`；输入缺失或引擎失败时**跳过并保留上一版 `data/`**，不影响其他数据与部署。
4. 观察指标（`data/curation/opportunity_observe.json`）仍手工维护，不参与计算。

## 路由

- 站内入口：「红利指数」下拉 → 红利机会值（A股），路由 `#/index/opportunity`（桌面 + 手机端 + 详情页导航均已加入口）。
- 兼容旧地址：`/dividend-opportunity` 与 `/红利机会值/` 均 302 跳转到 `/#/index/opportunity`（见 `_redirects`）。

## 当前版本

- 方法版本：v4（2026-10-07）
- 数据截至：2026-09-30；机会值 41.7（显示 42），中性区间 · 持有

## 尚未完成

- **Wind MCP 自动取数**：`输入数据说明.md` 里描述的 `fetch_opportunity_inputs.py`（用万得 MCP 复刻手工导出，产出 `inputs/opportunity/wind_daily.csv`）**尚未实现**，当前仍依赖用户手工导出 xlsx/csv。实现与否、何时接入周更，见 `prompts/给网页Agent的Wind取数提示词.md`（需用户确认后再做）。

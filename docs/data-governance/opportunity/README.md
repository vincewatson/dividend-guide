# 红利机会值（A股）· 模块说明

> 2026-10-08：本模块已由独立的 `红利机会值/` 文件夹**并入主站统一管理**（不再有独立页面 / iframe / 独立目录）。
> 本文档替代原 `红利机会值/README.md`。

中证红利（000922.CSI）加减仓打分。机会值 0–100，**50 = 中性值**；越高越适合加仓，越低越该谨慎。
适用周期：未来 6–12 个月的方向判断，不预测涨跌幅度。方法细节见同目录 `方法说明.md`。

## 文件位置（并入后）

| 路径 | 内容 | 谁来改 |
|---|---|---|
| `opportunity_engine.py`（仓库根） | 计算引擎（Python，依赖 pandas） | Claude（研究、改算法） |
| `opportunity_central.py`（仓库根） | 输入层：读中央库导出 + 本地增量 | Claude |
| `fetch_opportunity_inputs.py`（仓库根） | Wind MCP 增量取数 + 写回中央库 | Claude |
| `opportunity_config.json`（仓库根） | 中央库路径、窗口、映射区间、权重 | Claude（研究、改参数） |
| `inputs/opportunity/`（本地，不入库） | 只放 Wind MCP 增量缓存 `increments.csv` 与写回队列 `.cache/`（脚本自动维护，**不再放手工导出**） | 脚本 |
| `data/curation/opportunity_observe.json` | 观察指标（不计分，手工维护最新值） | 用户 |
| `data/opportunity.json` | 页面数据（JSON，供页面 fetch） | 由引擎生成，**不要手改** |
| `data/opportunity_history_monthly.csv` | 2018 年以来每月末的机会值与四项机会分 | 由引擎生成 |
| `index.html` → `#subOpportunity` | 页面 DOM（已内联进主站） | 网页 Agent |
| `opportunity-page.js` | 页面渲染 / 图表逻辑（IIFE，挂在 `window.OpportunityPage`） | 网页 Agent |
| `docs/data-governance/opportunity/` | 本说明 + 方法说明 + prompts | — |

## 分工

- **算法与研究**：改 `opportunity_engine.py` / `opportunity_config.json` / `方法说明.md`。
- **网页与部署**：改 `index.html` 的 `#subOpportunity`、`opportunity-page.js`；**不改引擎算法与 data 里的数字**。
- **数据更新**：见下。

## 更新数据（已纳入日更，2026-10-08 起改为中央库 + Wind MCP）

日更档（`auto_sync_deploy.sh`）自动完成，不需要手工导出：

1. `fetch_opportunity_inputs.py`：看中央库导出（`../../data_center/exports/dividend/`）+ 本地增量已覆盖到哪天，把「从覆盖日 → A股最新交易日」之间缺的交易日**一次补齐**（不是只取最后一天），只对缺口调用 Wind MCP（全部经 `wind_client`；无缺口 0 次，有缺口约 4–6 次），结果写 `inputs/opportunity/increments.csv`（不入库、不部署），并经 `data_center/pipelines/submit.py` 写回中央库（用中央库 MCP 安装的 `~/.local/share/data_center/venv` Python；写回失败的留在 `inputs/opportunity/.cache/central_queue/`，下次再交）。
   - 000922 股息率直接复用站点日更 `sync_div_history` 写入的 `data/indexData.json`，通常不另调 Wind。
   - 只补近 120 天缺口；更早的历史以中央库为准，不用 Wind 回补。
   - 因此中途漏跑一两天，下次日更会自动把缺的交易日一起补上。
   - 手动：`--plan`（只看缺口和计划调用数）、`--probe`（每类调 1 次看返回）、`--selftest`（模拟 Wind，0 次调用）、`--no-submit`。
2. `opportunity_engine.py`：只读 **中央库 + 本地增量**（`opportunity_central.py`）。中央库不完整时直接报错，不读任何手工导出。
3. 取数 / 引擎失败 → 保留上一版 `data/opportunity.json`，不阻断其它数据与部署。
4. 观察指标（`data/curation/opportunity_observe.json`）仍手工维护，不参与计算。

## 路由

- 站内入口：「红利指数」下拉 → 红利机会值（A股），路由 `#/index/opportunity`（桌面 + 手机端 + 详情页导航均已加入口）。
- 兼容旧地址：`/dividend-opportunity` 与 `/红利机会值/` 均 302 跳转到 `/#/index/opportunity`（见 `_redirects`）。

## 当前版本

- 方法版本：v4（2026-10-07）
- 数据截至：2026-10-08；机会值 39.4（显示 39），本地已算出，待下次数据更新部署上线（线上仍为 2026-09-30 / 41.7）

## 已退出手工导出（2026-10-08）

- 中央库新导出 `exports/dividend/opportunity-inputs.json` 已落地；只读中央库复算 = 41.7（截至 09-30），与手工导出一致。
- 首次真实取数（TRAE 代跑）：`--probe` 6 条序列都取到数，正式运行补到 2026-10-08，机会值 39.4，共 11 次 Wind。
- 写回中央库：首次因 TRAE 终端环境变量干扰未找到 duckdb，10-08 增量由 Claude 经 MCP 代交；脚本已修（清理 PYTHONHOME/PYTHONPATH、自动从 Claude/TRAE 的 MCP 配置找 Python），复测可用。
- 引擎已去掉 Excel/CSV 回退；`compare_opportunity_inputs.py`、`输入数据说明.md`、旧 Wind 取数提示词归档到 `archive/opportunity-manual-inputs-20261008/`。
- 用户研究文件夹里的原始导出（`Watson/Projects/红利择时信号(claude)/data/`）保留备查，网站不再读取。

## 中央库入库进度（2026-10-08，Claude）

目标：引擎改从中央库（data_center）读历史 + Wind MCP 取增量，最终删掉 `inputs/opportunity/` 的手工导出依赖。

| 引擎输入 | 中央库位置 | 状态 |
|---|---|---|
| 000922.CSI 收盘点位 | `quote.index_daily` · close | ✅ 已入库（2010-01-04 起，10-08 build） |
| 000922.CSI 股息率(近12个月) | `quote.index_daily` · dividend_yield | ✅ 已入库（与库里 2023 年起已有值逐日 0 差异；两个来源并存，读取时按日期去重） |
| 10年期国债到期收益率 | `rates.value` · 序列「10年期国债到期收益率」 | ✅ 已入库（series_id red94e9，2008-07 起） |
| H00922.CSI 全收益收盘 | `quote.index_daily` · close | ✅ 已入库（2010-01-04 起） |
| 881001.WI 万得全A 股息率 | `quote.index_daily` · dividend_yield | ✅ 已入库（2010-01-04 起） |
| 000922.CSI 换手率 | `quote.index_daily` · turnover_rate | ✅ 已入库（2010-01-04 起） |

- 同批顺带提交：000922 成交额、PE(TTM)、PB(LF)；000151.SH / 932305.CSI 股息率。
- 转换脚本与待提交文件不在本仓库，在用户的研究文件夹 `Watson/Projects/红利择时信号(claude)/中央库提交/`（见其中 README）。
- 2026-10-08 18:49 Windows build 已接收这 3 批。剩余 3 项到位后，下一步是：引擎增加「从中央库读」的输入源，再写 Wind MCP 增量取数（取到后 submit_data 写回）。
- **2026-10-08 复算验证**：只用中央库数据（同日多来源时优先 `submission:dividend-guide`）重建引擎输入、跑 `opportunity_engine.py`，得到机会值 41.7，与现网一致；历史对比、打分参考完全一致；448 个周度点最大偏差 0.1（四舍五入）。**中央库已能完整替代 `inputs/opportunity/` 的手工导出。**

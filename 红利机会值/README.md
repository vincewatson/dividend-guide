# 红利机会值（A股）

中证红利（000922.CSI）加减仓打分。机会值 0–100，**50 = 常态**；越高越适合加仓，越低越该谨慎。
适用周期：未来 6–12 个月的方向判断，不预测涨跌幅度。

## 目录

| 路径 | 内容 | 谁来改 |
|---|---|---|
| `index.html` | 展示页（纯静态，只读 `data/opportunity.js`，不写死任何数字） | 网页 Agent（样式 / 嵌入） |
| `data/opportunity.json` | 页面数据（JSON，供其他程序读取） | 由引擎生成，**不要手改** |
| `data/opportunity.js` | 同一份数据，包成 `window.DIVIDEND_OPPORTUNITY`，本地双击 `index.html` 也能打开 | 由引擎生成，**不要手改** |
| `data/opportunity_history_monthly.csv` | 2018 年以来每月末的机会值与四项机会分 | 由引擎生成 |
| `engine/opportunity_engine.py` | 计算引擎（Python，依赖 pandas、openpyxl） | Claude（研究、改算法） |
| `engine/config.json` | 输入文件路径、窗口、映射区间、权重 | Claude（研究、改参数） |
| `inputs/` | Wind 导出的原始数据 + 观察指标（手工维护） | 用户 |
| `docs/方法说明.md` | 指标定义、权重、回测结论、已知局限 | Claude |
| `prompts/` | 给网页 Agent 的接入提示词、给 Claude 的研究续作提示词 | — |

## 分工

- **算法与研究**：在 Claude 里做（读 `prompts/给Claude的研究续作提示词.md`）。改动只落在 `engine/` 和 `docs/`。
- **网页与部署**：网页 Agent 只负责把 `index.html` 接入站点、部署；**不改 `engine/` 里的算法和 `data/` 里的数字**。
- **数据更新**：见下。

## 更新数据（每周一次即可）

1. 从 Wind 重新导出两个文件，覆盖 `inputs/` 下的同名文件（格式说明见 `inputs/README.md`）：
   - `data_add.xlsx`（需要其中的「收盘价+成交额+换手率」「市盈率+市净率」两个 sheet）
   - `中国_国债到期收益率_10年.csv`
2. 运行：`python3 红利机会值/engine/opportunity_engine.py`
3. 终端打印「✅ 数据截至 …，机会值 …」即成功；`data/` 下三个文件被覆盖。
4. 按站点原有流程部署。

> 观察指标（剪刀差、流动性、ETF 资金等）目前在 `inputs/observe.json` 里手工维护，不参与计算。

## 当前版本

- 方法版本：v4（2026-10-07）
- 数据截至：2026-09-30；机会值 41.7（显示 42），中性 · 持有
- 首版 `data/` 由 Claude 会话直接计算；之后以引擎输出为准。

## 接入状态（2026-10-08）

- 已接入食息指南站点：**「红利指数」下拉 → 红利机会值（A股）**，路由 `#/index/opportunity`（桌面 + 手机端 + 详情页导航均已加入口）；英文别名 `/dividend-opportunity` → `/红利机会值/`。
- 页面以 **iframe** 嵌入站内框架（子页用 `?embed=1` 隐藏自带顶栏、`postMessage` 汇报高度）。
- 部署范围：仅 `index.html` + `data/` 上线；`inputs/`、`engine/`、`prompts/`、`docs/` 已加入 `deploy_cloudflare.sh` 排除清单。

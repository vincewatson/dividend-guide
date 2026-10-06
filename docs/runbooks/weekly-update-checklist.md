# 每周更新操作手册（runbook）

> 来源：《网站更新与数据管理对照文档》（2026-08-22 拆分；原件归档为 `docs/_archived_网站更新与数据管理对照文档.md`）**规范篇**「更新后必查清单（部署前）」+ **附录 B**（B1–B4 定期更新内容总清单）。
---

> 本文档内容迁移自《网站更新与数据管理对照文档》（2026-08-22 docs 重组）。
> 当前唯一权威规范以 `reference/` 与 `data-governance/` 下的文件为准；`changelog/` 只是历史记录，不代表当前状态。

## 一、更新后必查清单（部署前）


1. `python3 check_data.py` 全部 ✅（部署硬门槛）
2. 首页「数据更新于」为最新交易日（curl 线上确认）
3. 红利指数浏览器：dailyChange 日期为最新交易日
4. 余额宝（首页 + 各详情页图例）2 位小数
5. 详情页：图表可交互（hover/滑块/select），footer 全宽跟随滚动、与卡片 16px 间距、hint 气泡完整
6. 月月分红 divDate 覆盖率达标（fund ≥20、etf ≥14、cnEtf ≥50）；且月月名单**无超期成员**（最近分红 ≥ 上月初，超期者已由步骤 14 自动剔除）、**行结构完整**（check_data 7c）；**新增**成员已由编号外步骤 `sync_new_monthly` 自动补入（全市场近 1 年分红 ≥ 11 的指数产品，A 类去重）
7. 线上 index.html 与本地一致（md5 对比）或 curl 关键数据抽查
8. 股息率口径抽查：etfData/fundData 任抽 2-3 只详情，yield=跟踪指数股息率（与指数浏览器一致）；**无负值/无 15%+ 极端值**
9. 简称 N 前缀：全站无残留「N」开头简称（grep "N红利\|N.*ETF"）
10. 浏览器验证需**强刷**（?t=时间戳），避免 CDN/浏览器缓存看到旧数据（08-16 曾误判 3.43% 未修复）

---

## 二、定期更新内容总清单（附录 B）


## B1. 每周六 15:00「食息指南网站数据更新」定时任务（21 步流水线）

> 编号自 2026-09-19 起统一为**连续 1..20**；**2026-09-26 起新增步骤 13（sync_new_reits），顺延为连续 1..21**，与 `data-governance/update-mechanism.md`「标准流程（21 步）」、`auto_sync_deploy.sh` 保持一致。步骤 1–2 为任务准备（由任务层完成），步骤 3–21 为脚本流水线（`auto_sync_deploy.sh` 从步骤 3 开始打印）。
>
> **预检（preflight，2026-10-04 新增；不计入 21 步编号）**：流水线开头自动执行 `python3 preflight.py`——判断今天 A股/港股是否开盘、各数据域是否已是最新交易日、建议跑/跳过哪些步骤，并给出耗时粗估。默认只报告；按其建议跳过：`SKIP_STEPS="5 6 7 8 9 10 16" bash auto_sync_deploy.sh` 或 `PREFLIGHT_AUTO=1 bash auto_sync_deploy.sh`。交易日历见根目录 `market_calendar.json`（每年官方发布次年安排后更新一次）。

| 步骤 | 脚本 | 更新内容 |
|------|------|---------|
| 1 | （任务准备）| 修订文档：读 docs/README.md 索引 → 更新 `reference/` 或 `data-governance/` 对应文件 |
| 2 | （任务准备）| 确认任务逻辑：核对定时任务 / `auto_sync_deploy.sh` / `update-mechanism.md` 三者步骤数·顺序·脚本清单一致 |
| 3 | （语法预检）| 全部 .py 语法检查（防 // 注释类错误）|
| 3.5 | **sync_lifecycle**（编号外）| **生命周期体检（「出」机制）**：① **港交所红利ETF** 用**中央数据库**的「港交所上市ETF」全量名单（`data/curation/_hk_etf_universe.json`，451 只，与策略魔方同源）比对，不在名单=退市（文件缺失则退回 aastocks）；② **境内红利ETF/REITs/货币基金** 用 Wind「基金到期日」**≤ 今天**=已结束（REIT 未来到期日不误杀；约 28 天节流）。命中写入 `data/curation/_retired.json`，`build_lists` 重建时剔除（2026-10-06）|
| 4 | build_lists(1) | **从 `data/curation/*.json` 重建**（assetData/indexData/cnEtf/hkEtf/etf/fund/moneyFund/reits；2026-10-06 P2 起不再读 Excel）|
| 5 | sync_div_history + fix_laggard | 指数股息率日频补最新交易日（57 指数）|
| 6 | sync_daily_change | 每日涨跌幅 + **本年涨跌幅 yrChange**（Wind 实时）|
| 7 | sync_money_fund | 货基头部实时 7 日年化 |
| 8 | sync_yuebao_history | 余额宝日频历史（动态 180 天）|
| 9 | sync_asset_macro | 宏观资产历史（LPR/国债/存款/预定利率/同业存单 931059/租金率保留）|
| 10 | sync_reits_daily | REITs 日频增量（产权/特许中位数）|
| 11 | build_lists(2) | 重建（assetData 取最新 divHistory；来源 = `data/curation/*.json`）|
| 12 | sync_new_etf | 新 ETF/新指数自动发现（近 30 天红利类）|
| 13 | sync_new_reits | 新 REITs 自动发现（全部已上市公募 REITs：508xxx.SH / 180xxx.SZ）|
| — | **sync_new_monthly** | **【编号外】月月名单自动补入**：全市场检索「近 1 年分红次数 ≥ 11」的指数产品（A 类去重），自动补入 etfData/fundData（位于 step 13 后、step 14 前；2026-10-06 起；`--dry-run` 可先只读核对）|
| 14 | sync_fund_divdate | 恢复最近分红日期（fund/etf/cnEtf）+ **月月名单剔除超期成员**（最近分红早于「上一个月」者移出 etfData/fundData；2026-10-06）|
| **15** | **sync_wind_fields** | **字段级 Wind 化：fundCount / ETF 成立·上市·费率·规模·份额·持有人·分红次数 / 月月分红全字段 / 股息率=指数股息率 / N 前缀摘除** |
| 16 | sync_daily | 食息资讯日报（只读 digest-db.json → data/dailyData.json + dailyTagColors.json；原 sync_weekly 已归档 archive/weekly-feed-2026-09/）|
| 17 | backup_db | 离线备份 |
| 18 | check_data（硬门槛）| 验证含附录 A 问题点抽查，全部 ✅ 才可部署 |
| 19 | embed_data | 刷新 index.html 内嵌兜底数组（9 个）|
| 20 | （部署）| 部署到 Cloudflare Pages |
| 21 | （线上验证）| curl 线上「数据更新于」为最新交易日 |

## B2. 季度（4/7/10/12 月下旬）：重点50城租金率 SOP（见 `runbooks/quarterly-rent-sop.md`）
每季度从中指云报告更新「重点50城租金率」季度时点值（最新 2023Q1 起 14 点），assetData 列表值由用户提供。

## B3. 不定期（用户指令）：
- 月月分红清单变更：**新增**成员已**自动化**——编号外步骤 `sync_new_monthly`（全市场检索近 1 年分红次数 ≥ 11 的指数产品，A 类去重，自动补入 etfData/fundData；2026-10-06 起）；**移出**已停止月月分红的成员亦**自动化**——步骤 14 `sync_fund_divdate.prune_stale_monthly`：最近一次分红早于「上一个月」（如 10 月运行要求 ≥ 9/1）即移出 etfData/fundData（2026-10-06；Excel 仍会带回，若恢复月月分红则自动回归）
- 港交所 ETF 互联互通/跟踪指数修订（对话告知 AI，登记 `manual-overrides.md`）
- 租金率列表新值

## B4. 每日若手动同步（非周末）：跑 B1 的步骤 5–10 + 14 + 15 即可（增量安全）。动手前先跑 `python3 preflight.py`，确认当天是否为交易日、哪些域确需更新（假期里多数日频域无新点，可直接跳过）。

# 数据更新流程重构方案（2026-10-06 定稿 · 待实施）

> 版本：v1 · 更新：2026-10-06 · 提出：Watson（问题）/ Claude（方案）· 实施：TRAE
> 本文件是重构期间的**唯一目标规范**。实施完成后，把“现行规则”并入 `update-mechanism.md`，本文件改为“已归档·仅备查”。

## 一、要解决的三个问题

| 问题 | 现象 | 根因 |
|---|---|---|
| 1. 太慢 | 一次更新 ≥ 1 小时；网站只有六七张列表 | 每次都把所有步骤跑一遍；名单重建两次；新品发现、生命周期体检、分红日期这类“周/月级”任务每次都跑；十几个脚本各自串行查 Wind |
| 2. Wind 额度不够 | 每天 2000 次上限，白天做过开发后例行更新跑不完 | 没有统一的调用计数和预算；跑到一半额度用光，脚本中途失败 |
| 3. 数据乱 | 不知道哪些重跑了、哪些是旧值；改名会被回退 | “先整表重建、再逐步打补丁”：第 4、11 步重建覆盖，第 14、15 步再把被覆盖的字段补回来；失败时有的文件更新了、有的没有，也没有记录 |

## 二、目标（验收标准）

1. **例行更新（每个交易日）≤ 10 分钟，Wind 调用 ≤ 300 次**；没有新交易日时 **0 次调用、1 分钟内结束**。
2. **每周维护 ≤ 30 分钟，Wind 调用 ≤ 800 次**。
3. **额度不够时不失败**：按优先级做到哪算哪，没做完的记下来，下次优先补；已更新的部分照常部署。
4. **每次运行都留一份清楚的报告**：每个数据项“已更新到哪天 / 本次跳过（已是最新）/ 待补（额度不足）/ 失败（保留旧值）”，以及 Wind 用了多少次。
5. **任何字段都不会被更旧的值覆盖**（包括改名、人工修订）。

## 三、设计

### 1. 三档频率（不再每次全跑）

| 档位 | 什么时候跑 | 内容 |
|---|---|---|
| **日更**（默认） | 有新交易日时 | 指数股息率最新值、每日涨跌幅、货基 7 日年化、余额宝、REITs 日频收益率、产品行情、食息资讯、检查、部署 |
| **周更** | 每周一次（如周末），或手动 `--weekly` | 规模/份额/费率等字段刷新、分红日期、新 ETF/新 REITs/新港股 ETF/月月分红名单自动发现、生命周期体检、宏观资产 |
| **月更/按需** | 每月一次或手动 `--full` | 指数基础信息（挂钩产品数等）、历史回补、档案类字段全量核对 |

`preflight.py` 决定这次跑哪一档、跑哪些步骤：没有新交易日的数据项直接跳过（不调用 Wind）。

### 2. 统一的 Wind 调用客户端 + 每日预算（最关键）

- 新建 `wind_client.py`，**所有脚本只通过它调用 Wind**（删掉各脚本里各自复制的 `call_wind`）。
- 每次调用写入当日计数 `.wind_usage/YYYY-MM-DD.json`（按脚本/步骤分别计数）；**跨脚本、跨运行、跨开发任务共用同一个计数**——白天开发用掉的次数也算在内。
- 预算：日更默认 300、周更 800（环境变量可调）；离当日 2000 上限还剩不到 200 次时，只跑最高优先级的数据项。
- 返回“额度用尽”时：**立刻停止所有后续 Wind 调用**（不重试、不换措辞再试），把没做完的数据项写入 `.wind_pending.json`；下次运行**先补 pending**。
- 重试只针对限流类瞬时错误，并且**计入预算**；多措辞兜底的每一次尝试也计入。

### 3. 一次重建、之后只做“合并”（解决数据乱）

- 名单只在开头从 `data/curation/` **构建一次**（去掉第 11 步“第二次重建”）。
- 之后所有取数步骤都**合并写入**：只覆盖本次确实取到的字段，并同时写该字段的日期（`xxxDate`）；**取到的值日期比现有的旧，就不覆盖**。
- 这样就不再需要第 14 步“恢复被覆盖的分红日期”这类补救步骤。
- 改名、人工修订一律改 `data/curation/`（见 `known-issues`），构建时以 curation 为准，Wind 不得覆盖 curation 里标注为人工修订的字段。

### 4. 增量与批量

- 每个数据项都按“本地最新日期 → 最近交易日”只取缺口（交易日以中央数据库 `ref.trade_calendar` 为准，`market_calendar.json` 兜底）。
- 能批量就批量：一次查询多个代码（在“单次 ≤ 7 个字段、≤ 约 100 行”的限制内尽量放满）；时间序列按代码批量取，不逐只取。
- **能不用 Wind 的不用**：中央数据库里已有的、或指数公司官网能直接拿到的（如中证、国证指数的收盘、估值），先查中央数据库，查不到再用 Wind。

### 5. 运行报告

每次运行结束输出 `logs/update-YYYYMMDD-HHMM.md`（也在终端末尾打印摘要）：

| 数据项 | 档位 | 结果 | 数据日期 | Wind 次数 | 耗时 |
|---|---|---|---|---|---|
| 指数股息率 | 日更 | 已更新 | 2026-10-09 | 12 | 40s |
| 新 REITs 发现 | 周更 | 本次不跑 | — | 0 | 0 |
| 货基 7 日年化 | 日更 | 待补（额度不足） | 2026-10-08（旧） | 0 | 0 |

## 四、实施顺序（每阶段独立可验收）

1. **阶段 0：先测量（不改逻辑）** —— 加上 `wind_client.py` 计数，跑一次完整更新，产出“每一步的 Wind 次数 + 耗时”表，写进本文件附录。后面的优化以这张表为准。
2. **阶段 1：预算 + 断点续跑** —— 所有脚本改走 `wind_client.py`；额度用尽优雅停止、记录 pending、已完成部分照常部署。
3. **阶段 2：三档频率** —— `preflight.py` 输出档位与步骤清单，`auto_sync_deploy.sh` 按档位执行；周/月级步骤移出日更。
4. **阶段 3：一次构建 + 合并写入** —— 去掉第二次重建与“恢复”类步骤，所有字段带日期、旧不覆盖新。
5. **阶段 4：减少调用** —— 按阶段 0 的表从调用最多的步骤开始做批量化、改用中央数据库或官网数据。
6. **收尾**：步骤重新连续编号；更新 `update-mechanism.md`、`weekly-update-checklist.md`、项目规则；本文件归档。

每个阶段完成后：`check_data.py` 全部通过；与改造前的 `data/*.json` 对比，除日期更新外不应有意外差异；在本文件附录记一行“阶段 N 完成：耗时 / Wind 次数 前→后”。

## 附录：测量与进展记录

### 阶段 0（只测量、不改逻辑）

**状态：计数层已就绪；已实跑一次测量（2026-10-07 00:19–00:33，`SX_NO_DEPLOY=1` 只跑数据不部署）。⚠️ 流水线在**步骤 18（check_data）中止**——**非** Wind 额度中断（共 **1004** 次 < 2000）。**

- **2026-10-06**：新建 `wind_client.py`（统一 Wind 客户端）；15 个脚本的 **18 处** Wind 调用**全部改走** `wind_client.run(...)`（透传 `subprocess.run`，逻辑/措辞/重试/并发**零改动**）；`auto_sync_deploy.sh` 的 `run_py` 注入 `SX_WIND_STEP=<label>`，计数写 `.wind_usage/YYYY-MM-DD.json`（与 `.run_timings.jsonl` 的 label 对齐）。
- **2026-10-07 00:19–00:33 实测**：全新一日额度（从 0 起），逐 step 计数正常。**中止原因**：步骤 18 `check_data` 报 **9 项未通过**，全部为「跨市场日期口径」——当日 **A股假期休市（A股最近交易日 09-30）、港股开市（10-07）**，而 check_data 的「全覆盖（允许滞后≤2天）」以**合并最新交易日 2026-10-07** 要求全部序列，故 A股系（09-30，滞后 7 天）被判滞后。**属既有判据的节假日问题，与本次重构无关**（无任何 schema/类型错误；`divHistory 最新日期: 2026-10-07` 等 HK 系为 ✅）。

#### 每步 Wind 调用次数 + 耗时（2026-10-07 实测 · `SX_NO_DEPLOY=1`）

| 步骤 | 脚本（label） | Wind 次数 | 耗时(s) |
|---|---|---|---|
| 3.5（编号外） | sync_lifecycle.py | 227 | 65 |
| 4 | build_lists.py（第一次） | 0 | 5 |
| 5 | sync_div_history.py | 87 | 171 |
| 5 | fix_laggard_indexes.py | 42 | 10 |
| 6 | sync_daily_change.py | 37 | 215 |
| 7 | sync_money_fund.py | 1 | 5 |
| 8 | sync_yuebao_history.py | 18 | 45 |
| 9 | sync_asset_macro.py | 13 | 10 |
| 10 | sync_reits_daily.py | 89 | 30 |
| 11 | build_lists.py（第二次） | 0 | 5 |
| 12 | sync_new_etf.py | 1 | 5 |
| 编号外 | sync_new_hk_etf.py --add | 0 | 5 |
| 13 | sync_new_reits.py | 99 | 130 |
| 编号外 | sync_new_monthly.py | 3 | 10 |
| 编号外 | sync_product_quotes.py | 17 | 15 |
| 14 | sync_fund_divdate.py all --force | 315 | 95 |
| 15 | sync_wind_fields.py all | 55 | 40 |
| 16 | sync_daily.py | 0 | 5 |
| 17 | backup_db.py | 0 | 5 |
| 18 | check_data.py | 0 | 5 |
| **合计** | | **1004** | **876 ≈ 14.6 min** |
| 19 | embed_data.py | 0 | 未执行（步骤 18 中止） |
| 20 | 部署 deploy_cloudflare | — | 本次跳过（SX_NO_DEPLOY=1） |
| 21 | 线上验证 | — | 本次跳过（SX_NO_DEPLOY=1） |

> **口径**：**Wind 次数**来自 `.wind_usage/2026-10-07.json`；**耗时**来自 `.run_timings.jsonl`（wall-clock，各步 `run_py` 实测）。`.wind_usage` 的 `sec` 是**单次调用耗时累加**（并发下远大于 wall-clock，如 lifecycle 382s vs 65s），故未采用。语法预检 / preflight 非 `run_py`，未计入。
>
> **结论（阶段 0 用途）**：现状 ≈ **14.6 分钟 / 1004 次调用**，远高于目标（日更 ≤10min、≤300 次）。**调用最多**：fund_divdate 315、lifecycle 227、new_reits 99、reits_daily 89、div_history 87 → 即阶段 4「减少调用」的优先对象；**耗时最多**：daily_change 215s、div_history 171s、new_reits 130s。

#### 阶段 0 结果分析与后续安排（2026-10-07，Claude）

**结论**：一次完整更新约 1000 次调用，所以一天跑两次再加上开发测试就会碰到 2000 的上限；耗时 14.6 分钟（不含部署）。约 64% 的调用花在“很少变化、不必每天查”的数据上。

| 步骤 | 次数 | 归档建议 | 理由 |
|---|---|---|---|
| sync_fund_divdate all --force | 315 | **周更**；日更只查“预计近期分红”的基金 | 分红日期很少变，`--force` 每次全量重查 |
| sync_lifecycle | 227 | **周更** | 成立/清盘状态很少变 |
| sync_new_reits | 99 | **周更** | 新 REITs 发现 |
| sync_new_monthly / sync_new_etf / new_hk_etf | 4 | 周更 | 新产品发现 |
| build_lists（第二次） | 0 | **删除**（阶段 3） | |
| fix_laggard_indexes | 42 | div_history 改增量后删除 | 补救步骤 |
| sync_reits_daily | 89 | 日更，**批量化**（多代码一次） | |
| sync_div_history | 87 / 171s | 日更，只取缺口 | |
| sync_daily_change | 37 / 215s | 日更，查清为什么慢（等待/串行） | 次数少、耗时最长 |
| 其余日更步骤 | ~105 | 日更 | |

仅按上表移出周更步骤：日更约 **360 次 / 约 9 分钟**；再做 reits_daily 批量化、删除 fix_laggard，即可达到 ≤300 次的目标。

**顺序调整**：阶段 1（预算+断点续跑）与阶段 2（三档频率）合并做，收益最大；阶段 3、4 随后。

**check_data 节假日问题**（阶段 0 中止原因）：改为**按市场分别判断**“最新交易日”——A股系序列对照 A股日历、港股系对照港股日历（中央数据库 `ref.trade_calendar` 的 cn/hk，或 `market_calendar.json`），不再用合并后的最新日期。修好后阶段 0 视为验收通过，不需要再补测。

### 阶段完成记录

- ✅ **阶段 0：通过**（2026-10-07）。`check_data.py` 已改为**按市场分别判断「最新交易日」**：A股系序列对照 A股日历、港股系对照港股日历（来源 `market_calendar.json`，与 preflight 同源）；仅当**落后**（早于）本市场最新交易日 >2 天才判滞后（领先不判）；若某指数「行情（dailyDate）仍新、仅股息率源滞后」则豁免其股息率滞后。原「合并最新日期」在跨市场假期（A股休市、港股开市）误判的问题已消除。

- ✅ **阶段 1：预算 + 断点续跑**（2026-10-07）：
  - `wind_client.py` 新增**按档位的每日预算**（日更 `SX_WIND_BUDGET` 默认 **300**、周更 **800**）：当日该档位调用数 ≥ 预算即**拒绝**后续调用（返回 rc=3 的合成结果），调用方按既有「保留旧值」路径**安全降级、不失败**；同时把当前步骤记入 `.wind_pending.json`。
  - `auto_sync_deploy.sh`：流水线开头读取 pending → **本次先补**（无论档位都先跑），读后清空（若再触预算会重新写入）。
  - `check_data.py`：对「待补步骤」产出的数据项**豁免新鲜度校验**（额度不足不失败；`check(..., step_label=...)`）。
  - 新增 `SX_NO_DEPLOY=1`（只跑数据、不部署，供测量/演练）。

- ✅ **阶段 2：三档频率（先落「日更 / 周更」两档）**（2026-10-07）：
  - `preflight.py` 增 `--weekly` / `--mode`，输出本次档位与步骤清单；`--emit-skip` 仅日更生效。
  - **移至周更**：分红日期 `sync_fund_divdate`(14)、生命周期 `sync_lifecycle`、新 REITs `sync_new_reits`(13)、新 ETF `sync_new_etf`(12) 与港 ETF `sync_new_hk_etf`、月月发现 `sync_new_monthly`。周更=**仅周级步骤**；日更=其余日频步骤（另 17/18/19 备份·校验·内嵌两档都跑）。
  - `auto_sync_deploy.sh` 加 `--weekly` 档位门控（`step_on`/`label_on`），编号外步骤同受控；`SX_WIND_MODE` 透传 `wind_client`。
  - **关键依赖修复**：`build_lists.py` 重建会清空 `divDate`（原靠紧随其后的 `sync_fund_divdate` 恢复）；该步移至周更后，遂让 `build_lists` 重建时**保留旧 `divDate`**（旧不覆盖新），使日更不再依赖它（已无 Wind 验证：重建日志出现「保留旧的分红日期 divDate N 条」，`check_data` ✅）。

- 🔧 **阶段 3：一次构建 + 合并写入**（2026-10-07 · **代码完成，待实跑验收**）：
  - `build_lists.py` **只跑一次**（原第 4、11 步的两次 → 合并为一次，置于原第 11 步位置）：确保 assetData 取到当日最新 divHistory，其后 new_*/fund_divdate/wind_fields 再更新。
  - `build_lists` 重建**合并写入**：保留旧 `divDate`/`size`（`divHistory`/`dailyChange`/`yrChange` 本就保留）——旧值不覆盖新值。
  - 取数步骤加**日期守卫（旧不覆盖新）**：`sync_daily_change`（本次 `dailyDate` 早于现有则不写）、`sync_money_fund`（`yieldDate` 早于现有则不写）。序列类步骤（div_history/yuebao/asset_macro/reits_daily/productQuotes）本就是「只补缺口/追加」。

- 🔧 **阶段 4：日更提速（目标 ≤5 分钟）**（2026-10-07 · **代码完成，待实跑验收**）：
  - **`sync_div_history` 按市场补缺口**：目标日按各指数所属市场日历（A 股对 A 股、港股对港股）——**A 股休市时 A 股指数不再被当作「滞后」反复重查**（原目标只跳周末、不跳节假日，假期内白查数百次）。`fill_laggards` 同步按市场目标。
  - **删除 `fix_laggard_indexes.py`**（其逻辑早已并入 `sync_div_history.fill_laggards`；流水线第 5 步只留 div_history）。
  - **`sync_daily_change` 提速**：慢因 = ①每交易日全量重拉（新交易日必要）；②**批量失败后逐只单查且每次失败 `sleep 6s`×3**（长超时放大）；③慢在「等待」而非串行——正常路径已是 **12 只/批、6 并发**。改：重试等待 `SX_DC_RETRY_SLEEP` 默认 **2s**；批量失败**先对半拆批重试**再逐只兜底；并**按市场跳过**已到最新交易日的指数（如 A 股休市时跳过 A 股指数）。
  - **收盘时间（2026-10-07 追加）**：新增共享模块 **`trade_calendar.py`**（交易日历单一真实来源）——**A 股 15:30 / 港股 16:30 前，「今天」不算最新交易日，取上一交易日**；`sync_div_history` / `sync_daily_change` / `preflight` / `check_data` 统一引用（此前各自实现、且未计收盘时间）。
  - **部署排除（2026-10-07 追加）**：`deploy_cloudflare.sh` 的 rsync 增 `--exclude='/.*' --exclude='/logs'`，防止运行报告与 Wind 用量等隐藏文件/日志被部署到线上。

- 🔧 **运行报告（每次运行生成）**（2026-10-07 · 代码完成）：`auto_sync_deploy.sh` 末尾 `make_run_report.py` 汇总 `.run_report.jsonl`（每步结果/原因）+ `.run_timings.jsonl`（耗时）+ `.wind_usage`（本次增量）+ `.wind_pending.json` → **`logs/update-YYYYMMDD-HHMM.md`**。报告逐项写明「已更新 / 本次不跑（原因）/ 失败」、Wind 次数与耗时。

**两次实跑（2026-10-07，`SX_NO_DEPLOY=1`；同一日额度紧张，`SX_FORCE_RUN=1` 越过整跑闸）**

| 档位 | Wind 次数 | 耗时 | 预算 | check_data |
|---|---|---|---|---|
| **日更** | **232** | **≈567s（9.5 min）** | ≤300 ✅ | ✅ ※ |
| **周更** | **644** | **577s（9.6 min）** | ≤800 ✅ | ✅ |

> ※ **日更首跑** 的 `check_data` 未过（仅 2 项：`etfData`/`fundData` 的 `divDate` 覆盖）——根因是 `build_lists` 重建清空 `divDate`，而恢复它的 `sync_fund_divdate` 已移至周更。定位后已修（`build_lists` 重建保留旧 `divDate`），并**无 Wind 复验**：`python3 build_lists.py` + `check_data` → **✅ 全部通过**。**周更 run** 的 `check_data` 直接 **✅**（其 `fund_divdate` 亦恢复了 divDate）。

日更分步（2026-10-07 实测）：

| 步骤 | 脚本 | Wind | 耗时(s) |
|---|---|---|---|
| 4 | build_lists（第一次） | 0 | 5 |
| 5 | sync_div_history.py | 87 | 76 |
| 5 | fix_laggard_indexes.py | 41 | 240 |
| 6 | sync_daily_change.py | 37 | 176 |
| 11 | build_lists（第二次） | 0 | 5 |
| 编号外 | sync_product_quotes.py | 12 | 10 |
| 15 | sync_wind_fields.py all | 55 | 40 |
| 16 | sync_daily.py | 0 | 5 |
| 17 | backup_db.py | 0 | 5 |
| 18 | check_data.py | 0 | 5 |
| **合计** | | **232** | **≈567** |

周更分步（2026-10-07 实测）：

| 步骤 | 脚本 | Wind | 耗时(s) |
|---|---|---|---|
| 编号外 | sync_lifecycle.py | 227 | 65 |
| 12 | sync_new_etf.py | 1 | 5 |
| 编号外 | sync_new_hk_etf.py --add | 0 | 5 |
| 13 | sync_new_reits.py | 96 | 196 |
| 编号外 | sync_new_monthly.py | 3 | 10 |
| 14 | sync_fund_divdate.py all --force | 317 | 280 |
| 17 | backup_db.py | 0 | 6 |
| 18 | check_data.py | 0 | 5 |
| 19 | embed_data.py | 0 | 5 |
| **合计** | | **644** | **577** |

> 口径：Wind 次数按「本次运行 − 上次运行」的 `.wind_usage` 增量（`.wind_usage` 跨运行累计；本日增量与 `by_mode` 的 daily/weekly 一致）。耗时取自 `.run_timings.jsonl`（日更的中断未落总表，取自其运行日志逐步耗时）。当日实测总用量 1880/2000（含前次阶段 0 测量 1004）。
>
> **结论**：两档次数均达预算目标（日更 232≤300、周更 644≤800）；日更 ≈9.5min 逼近 10min 目标上限——主要因当日 **A股休市、港股开市**，`div_history`/`fix_laggard` 需为港股补数且较慢（fix_laggard 240s 已属异常，与港股假期补数有关）。下一步（阶段 3：一次构建+合并写入；阶段 4：减少调用）优先项：`fund_divdate`(317)、`lifecycle`(227)、`new_reits`(96)、`fix_laggard`(41/240s)。

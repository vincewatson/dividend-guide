# 数据更新机制（data-governance）

> 来源：《网站更新与数据管理对照文档》（2026-08-22 拆分；原件归档为 `docs/_archived_网站更新与数据管理对照文档.md`）**流程篇**「三条铁律」「标准流程」「新 ETF / 新指数自动发现规则」「数据更新机制」。
---

> 本文档内容迁移自《网站更新与数据管理对照文档》（2026-08-22 docs 重组）。
> 当前唯一权威规范以 `reference/` 与 `data-governance/` 下的文件为准；`changelog/` 只是历史记录，不代表当前状态。

## 三条铁律（所有数据更新必须遵守）

1. **写回绝不删除旧数据**：拉取失败/跳过/无新增 → 一律保留旧值。删除是显式操作且仅在全量成功替换时发生。
2. **历史序列起点必须早于所有图表数据起点**：yuebaoHistory 起点 ≤ divHistory 起点（差额 180 天余量）；前端对早于起点的日期返回 null（无数据不画，禁止假填充）。
3. **部署前 check_data.py 必须全部 ✅**：含数据覆盖范围检查（起点/最新日期/条数）；脚本改动后必须语法预检（流水线步骤 3）。

### 跨市场日历（2026-09-26 新增）
站点同时覆盖 **A股与港股**指数，两市场交易日历可不同（如 A股中秋休市、港股照常开市），此时「最新交易日」**分市场**——港股指数领先 A股/REITs/余额宝 1 天属正常，非数据滞后。
- `check_data.py` 的 `divHistory 全覆盖` / `dailyChange 全覆盖` / `reitsDaily 全覆盖` **一律按「允许滞后 ≤2 天」容差**判定（**禁止**用单一 `latest ==` 判等），各指数/REITs 以各自市场的最新交易日推进。
- `sync_daily_change.py` 对 Wind 截面缺失的指数（「最新交易日」返回 `0` / 涨跌幅为空）自动**单只重查 + K 线兜底**；解析前校验日期为 8 位数字，**绝不写入畸形日期**。
- 交易日历以根目录 `market_calendar.json` 为准（CN/HK 各年『工作日休市』清单；周末由脚本自动排除），`preflight.py` 据此计算各市场「最近交易日」；每年官方发布次年休市安排后更新该文件（沪深北交易所公告 / 港交所通告）。

## 标准流程（21 步：步骤 1–2 任务准备 + 步骤 3–21 脚本流水线）

> 编号自 2026-09-19 起统一为**连续 1..20**（原 `0`/`0.1`/`6.5`/`7.5` 与 `0a/0b/0c` 已废除）；**2026-09-26 起新增步骤 13（sync_new_reits 新 REITs 自动发现），编号顺延为连续 1..21**（原 13–20 步整体 +1）。`auto_sync_deploy.sh` 从**步骤 3** 开始打印（步骤 1–2 由任务层在上游完成）。

1 修订文档（读 docs/README.md 索引 → 更新 `reference/` 或 `data-governance/`，冲突以用户最新指令为准）→ 2 确认任务逻辑（核对「食息指南网站数据更新」定时任务 / `auto_sync_deploy.sh` / 本文件三者步骤数·顺序·脚本清单一致）→ 3 脚本语法预检（全部 .py）→ 4 build_lists(1) → 5 div_history+fix_laggard → 6 daily_change → 7 money_fund → 8 yuebao_history → 9 asset_macro → 10 **sync_reits_daily（REITs 日频增量，asset_macro 不覆盖 REITs）** → 11 build_lists(2)（assetData 取最新）→ 12 **sync_new_etf（新 ETF/新指数自动发现）** → 13 **sync_new_reits（新 REITs 自动发现，2026-09-26 起）** → **（2026-10-06 起）步骤 13 之后插入一个编号外步骤 `sync_new_monthly`（月月分红名单自动补入：全市场「近 1 年分红次数 ≥ 11」的指数产品，A 类去重）** → 14 fund_divdate（恢复 divDate + 月月名单剔除超期成员）→ 15 **sync_wind_fields（字段级 Wind 化：fundCount/ETF 字段/月月分红字段/股息率口径/N 前缀检查，2026-08-16 起）** → 16 **sync_daily（食息资讯日报；只读 digest-db.json；2026-09-20 起取代原 weekly）** → 17 backup → 18 **check_data（硬门槛）** → 19 embed → 20 部署 → 21 线上验证。（**2026-10-05 起**在步骤 12 之后插入一个**编号外**步骤 `sync_product_quotes`（产品行情快照入库），不计入 1..21；详见下方「产品行情快照库 productQuotes」。**2026-10-06 起**在步骤 13 之后插入编号外步骤 `sync_new_monthly`，详见「月月分红名单『自动补入 + 自动移出』规则」。）

> **更新前体检（preflight，2026-10-04 新增；不计入 21 步编号）**：`python3 preflight.py` 读取交易日历（根目录 `market_calendar.json`）与本地各 JSON 最新日期，判断 **A股/港股今天是否开盘、各数据域是否已覆盖到最新交易日、建议跑/跳过哪些步骤**，并给出耗时粗估。`auto_sync_deploy.sh` 在步骤 3 前自动执行并打印；按建议跳过：`SKIP_STEPS="5 6 7 8 9 10 16" bash auto_sync_deploy.sh` 或 `PREFLIGHT_AUTO=1 bash auto_sync_deploy.sh`（保守：仅跳过纯 Wind 日频 5–10 + 资讯 16，`build_lists`/校验/部署一律保留）。目的：假期/休市日不空跑全量（如国庆 A股多日休市，多数日频域无新点，可省去一半步骤）。

## 更新频次总表（数据 → 来源 → 脚本 → 频次）

> 「要更新什么、多久一次、由谁触发」一表看全。步骤号对应上节「标准流程」；「每次」= 每次执行流水线都刷新（至少覆盖最新交易日）。

| 更新对象（文件 · 字段）| 数据来源 | 更新脚本 | 频次 | 触发 / 步骤 |
|---|---|---|---|---|
| indexData · divHistory | Wind 指数股息率（日频）| sync_div_history + fix_laggard_indexes | **每次**（增量补最新交易日）| 步骤 5 |
| indexData · dailyChange / yrChange | Wind 涨跌幅 | sync_daily_change | **每次** | 步骤 6 |
| productQuotes · 产品行情快照（当日涨跌幅/今年以来回报）| Wind `fund_data.get_fund_price_indicators` | sync_product_quotes | **每次**（按日期【追加】，同日仅补空值、绝不覆盖旧值）| 「月月名单自动补入」之后（**编号外**步骤）|
| moneyFundData · 头部 7 日年化 | Wind 实时 | sync_money_fund | **每次** | 步骤 7 |
| yuebaoHistory | Wind 日频 | sync_yuebao_history | **每次**（动态 180 天）| 步骤 8 |
| assetHistory · 宏观序列（LPR/存款/国债/预定利率/存单）| Wind EDB（国债=Wind 债券发行记录）| sync_asset_macro | **每次** | 步骤 9 |
| assetHistory · REITs 两类日频 | Wind 日频中位数 | sync_reits_daily | **每次**（增量；**2026-09-26 起覆盖 reitsData.json 全量**，分组由 projectType 推导）| 步骤 10 |
| cnEtfData / hkEtfData / etfData / fundData / moneyFundData / reitsData / assetData | **`data/curation/*.json` 清单 + 标注**（2026-10-06 excel-exit P2 起；原用户 Excel 快照已弃用）| build_lists（跑两次）| **每周**（`data/curation/` 变更时才变化）| 步骤 4 / 11（「出」由编号外 `sync_lifecycle.py` → `_retired.json` 负责）|
| cnEtfData · 新 ETF、indexData · 新指数 | Wind 自动发现 | sync_new_etf | **每次**（检索近 30 天）| 步骤 12 |
| reitsData · 新 REITs + 空字段补齐 | Wind 自动发现 / 补齐 | sync_new_reits | **每次**（全量检索已上市 REITs；并为字段为空的 REITs 补 分红次数·年化派息率·累计/年化派息额·收盘价，取不到留空不写 0；2026-09-26 起）| 步骤 13 |
| divDate（fund / etf / cnEtf）**＋ 月月名单剔除超期成员** | Wind 最近分红 | sync_fund_divdate | **每次**（全量重拉；顺带把最近分红早于「上一个月」的 etfData/fundData 成员移出，2026-10-06）| 步骤 14 |
| ETF 成立/上市/费率/规模/份额/持有人/分红次数、fundCount、N 前缀、**fundData 分红金额补空白** | Wind | sync_wind_fields | **每次** | 步骤 15 |
| dailyData / dailyTagColors | `digest-db.json`（生成端）| sync_daily | **每次**（数据源每日更新）| 步骤 16 |
| assetHistory · 重点50城租金率 | 中指研究院季度报告 | 用户手动给值 + sync_asset_macro **保留** | **季度**（4/7/10/12 月下旬）| B2（`runbooks/quarterly-rent-sop.md`）|
| 月月分红清单**新增**成员（etfData/fundData）| Wind 全市场检索`search_funds`（近 1 年分红次数 ≥ 11；A 类去重；限指数产品）| **sync_new_monthly** | **每次** | 步骤 13 之后（**编号外**）|
| 港交所互联互通·跟踪指数 / 租金率列表值 | 用户业务判断 | 手动 | **不定期** | B3 |
| 月月分红清单**移出**已停止月月分红的成员 | 自动（最近分红 < 上月初）| sync_fund_divdate（步骤 14）| **每次** | 步骤 14 |

**说明**：
- **「每次」类**脚本均**增量 + 失败不破坏**（拉不到就保留旧值），可在任意时点安全重跑。
- **「每周」**指每周六 15:00 定时任务跑一次完整流水线（21 步）；清单/标注类只有在 `data/curation/` 变更时数值才变化。
- **「季度 / 不定期」**由用户在对应节点手动提供，脚本侧一律「保留现有值不覆盖」。

### 产品行情快照库 productQuotes（2026-10-05 确立·日期标签 + 只追加不覆盖）

**用户约定（原话）**：每次取特定日期的行情，下次更新**不要把之前的数据冲毁掉**——每次取完数据要**给数据打上日期标签**，数据库才能越来越丰富。

- **文件**：`data/productQuotes.json`（结构 `{schema, note, updatedAt, quotes:{ <code>: [ {date, dailyChange, yrChange, source}, ... ] }}`，每码按日期**升序**）。
- **两条铁律**：① **只追加不覆盖**——新交易日**追加**一条快照，历史快照永久保留；**同一天**再次写入时**只补空值（null→有值），绝不改写已有非空值**。② **产品绝不跨取跟踪指数**——产品回报已扣费且含分红，与指数口径不同；缺数据**从 Wind 补**，取不到写 `null`（前端显「—」，**不臆造、不借用挂钩指数**）。
- **来源**：Wind `fund_data.get_fund_price_indicators`（`indexes=最新交易日,涨跌幅,年初至今涨跌幅`）；12 只/批、失败重试 4 次 + 单只回退；日期须 8 位数字，**绝不写入畸形日期**。
- **独立于重建**：`productQuotes.json` **不在** `build_lists.py` 的整表重建清单内 → 每周重建产品列表**不会**冲掉行情快照（这也是把它做成独立文件、而非写回产品字段的原因）。
- **前端读取**：`/data/productQuotes.json` 运行时加载 → `productQuoteLatest`（各产品**最新日期**快照）；`embed_data.py` 额外内嵌 `productQuoteLatest` 作离线兜底。详情页「当日涨跌幅 / 今年以来回报」只读它。
- **脚本**：`sync_product_quotes.py`（`--dry-run` 只打印不写、`--codes a,b` 调试单批）；已挂到 `auto_sync_deploy.sh`（**「月月名单自动补入」之后**、**编号外**、失败不阻断）。⚠️ 位置 **2026-10-06 由「步骤 12 后」后移**至此 —— 使当轮「月月名单自动补入」的新产品**同轮即可取到行情快照**（否则新加产品要等下一周才有「当日涨跌幅/今年以来回报」）。

## 新 ETF / 新指数自动发现规则（2026-08-15 固化）

**这是"列表页变化"的官方机制——判断新产品不再依赖用户 Excel：**

1. **新 ETF 发现**：Wind `search_funds` 检索近 30 天成立的红利类 ETF（名称含 红利/高股息/股东回报/央企回报）→ 对照 cnEtfData.json → 新标的自动补入（含跟踪指数/管理人/费率/规模/成立/上市日）。
2. **新指数纳入**：新 ETF 的跟踪指数若在 indexData.json 匹配不到 → 该指数为新指数，自动补入指数浏览器（基础信息 + 2023 年以来股息率历史 divHistory）。
3. **联动**：build_lists.py 重建 cnEtfData 时保留 Wind 自动补充的标的（不删 curation 清单外条目）；auto_sync_deploy.sh 在第二次 build_lists（步骤 11）后挂载 sync_new_etf.py（步骤 12）。
4. 示例：159083 嘉实中证红利低波动100ETF（08-05 成立/08-13 上市）按此规则补入；其跟踪指数 930955.CSI 已在浏览器，不重复添加。

## 新 REITs 自动发现规则（2026-09-26 固化）

**REITs 列表补全的官方机制**（参照新 ETF 规则，脚本 `sync_new_reits.py`）：

1. **新 REITs 发现**：Wind `search_funds` 检索**全部已上市公募 REITs**（代码 508xxx.SH / 180xxx.SZ）→ 对照 `reitsData.json` → 新标的自动补入。核心字段（名称 / 资产类型 / 上市日 / 项目类型＝产权类·特许经营权类）取自 Wind **基金级档案** `get_fund_info`（须用「含项目类型列」的表，排除底层资产明细表）。
2. **留空不填 0**：新标的的明细字段（分红次数 totalDiv、年化派息率 annualDiv、累计/年化派息额、yield/yieldNum、volatility、prevClose…）本次取不到 → **数值型写 `null`、字符串型写 `''`（不写 0）**，待后续人工/其它脚本补齐。
3. **联动**：`build_lists.py` 重建 reitsData 时保留 Wind 自动补充的标的（不删 curation 清单外条目）；`auto_sync_deploy.sh` 在 sync_new_etf（步骤 12）后挂载 `sync_new_reits.py`（步骤 13）。
4. **代码范围**：Wind 若返回 181xxx.SZ 等范围外 REITs（如 181001.SZ 创金合信北京国资公司REIT），脚本会识别并**单独打印、不自动纳入**（需人工确认后放开 `ALLOWED_PREFIX`）。
5. **先跑 --dry-run**：`python3 sync_new_reits.py --dry-run` 只打印不写入，核对无误后再正式运行。
6. **日频覆盖 + 空字段补齐（2026-09-26）**：`sync_reits_daily.py` 的日频覆盖以 `reitsData.json` **全量**为准（分组由 `projectType` 推导，新标的从上市日做基线拉取、之后增量）；`sync_new_reits.py` 会对**字段为空**的 REITs 用 Wind 补齐 累计分红次数 / 年化分红次数 / 单位累计分红 / 单位年化分红 / 年化派息率 / 前收盘价——**只补空值、绝不覆盖；取不到继续留空、不写 0**。`build_lists.py` 已加 reitsData 非 Excel 行保留（同 cnEtfData），避免 Excel 重建清掉自动发现标的。

## 月月分红名单「自动补入 + 自动移出」规则（2026-10-06 固化）

**这是「月月分红」两个板块（ETF 月月分红 `etfData` / 指数基金月月分红 `fundData`）成员进出的官方机制**（脚本 `sync_new_monthly.py` + `sync_fund_divdate.prune_stale_monthly`；用户 2026-10-06 确认）：

1. **进入（自动补入）** —— 用户口径 **「≥11 次 / 全市场口径 / 直接自动加」**：
   - **范围**：Wind `search_funds` **全市场**检索（不预设「红利主题」白名单）。
   - **阈值**：Wind「近 1 年分红次数」**≥ 11 次**。
   - **份额去重**：同一产品的多个份额类别（A/C/E/I/Y）**只保留 A 类**（无 A 类则保留检出的一个）。
   - **限指数产品**：仅纳入 ETF（Wind 代码 .SH/.SZ）与指数基金（Wind 返回「跟踪指数代码」）；主动管理产品（超短债、量化选股等无跟踪指数者）**不纳入** —— 名单两板块固有语义为「ETF / 指数基金 月月分红」。
   - **写入**：ETF → `etfData.json`；场外 → `fundData.json`；`code` 一律 `base + '.OF'`。仅写身份/结构字段，数值与跟踪指数规范名由步骤 15 `sync_wind_fields` 补齐，`divDate` 由步骤 14 刷新。
   - **无人工确认**（用户 2026-10-06：「直接自动加吧，不要人工确认了」）；`python3 sync_new_monthly.py --dry-run` 可先只读核对。
   - **首轮落地（2026-10-06）**：补入 `021583.OF 中欧中证港股通央企红利指数A`、`022325.OF 长城中证港股通高股息投资指数A`、`021375.OF 中欧中证红利低波动100指数A`（fundData 25 → 28）；同轮排除 `012773.OF 嘉实超短债A`、`021814.OF 华泰柏瑞红利量化选股A`（非指数产品）。
2. **调出（自动移出）**：`sync_fund_divdate.prune_stale_monthly`（步骤 14）—— 最近一次分红**早于「上一个月」**（如 2026-10 运行要求 ≥ 2026-09-01）即移出 etfData/fundData；`divDate` 为空者不动（防误删）。curation 清单仍在，若恢复月月分红则自动回归。
3. **防回退**：`build_lists.py` 重建 etfData/fundData 时**保留 curation 清单外的行**（新增表外行护栏，2026-10-06）—— 否则每周整表重建会冲掉自动补入成员；`check_data.py` 第 7b（无超期成员）/ 7c（行结构完整）为部署硬门槛。
4. **顺序不可调**：`sync_new_monthly` 必须在 step 11 `build_lists(2)` **之后**（产物是表外行，靠护栏保留）、step 14 之前（同轮紧接刷 divDate 并做连续性剔除）。
5. **金额字段补空白（2026-10-06）**：自动补入的场外基金**不在 curation 清单内**，其 `annualDivAmt`/`monthlyDivAmt`/`divTotalAmt` 由步骤 15 `sync_wind_fields` **仅在为空/0 时**用 Wind「最新单位年度分红」「最新年度分红总额（亿元）」补齐（**清单行已有值 → 不动**）；口径 `monthlyDivAmt = 年度单位分红 ÷ 年度分红次数(annualDiv)`。此前缺失表现为「有最近分红日、但月均分红 = 0」。

## 数据更新机制

### 增量优先（2026-08-04 确立）
1. **增量优先**：已有数据只补"最后日期之后"的新段，旧数据保留，绝不重复全量（sync_div_history 增量、asset_macro 只刷新最新、yuebao 只补新段）。
2. **强制全量例外**：数据源口径变更/结构升级/数据损坏才允许 `SX_FULL_REFRESH=1` 全量重拉，执行前说明理由。
3. **已有数据不动**：前端已正常显示的字段，同步以"保留 + 补新"为默认。
4. **拉取前先读现有 JSON** 确定增量起点。
5. **失败不破坏**：拉取失败保留旧数据（不 pop）。

### 防回退机制（在线口径取代清单旧值）
- **divDate**：build_lists 之后必须重跑 `sync_fund_divdate.py all --force`。
- **余额宝 7 日年化**：build_asset_data 从 moneyFundData（含 yieldDate）覆盖；sync_money_fund 必须早于 build_lists(2)。
- **国债**：`BOND_OVERRIDE` 从 assetHistory（Wind 债券发行记录的储蓄国债票面利率）取最新，清单储蓄国债旧值不覆盖。
- **REITs 两类**：build_lists 特判从 assetHistory 最新日频中位数覆盖。
- **红利指数**：yield/date 从 divHistory 最新值覆盖（build_lists 跑两次的顺序约束）。
- 通用原则：任何"清单旧口径 vs 在线新口径"冲突字段，加 `XXX_OVERRIDE` 优先在线。

### 重建型写入的「保留白名单 + 表外行护栏」（2026-09-27 审计固化；2026-10-06 excel-exit P2 更新）
`build_lists.py` 对 8 个文件（`assetData/indexData/cnEtfData/hkEtfData/etfData/fundData/moneyFundData/reitsData`）是**整表重建**（从 `data/curation/` 清单 + 标注 builder 重新生成），因此任何「先前脚本/人工写入、但不属于 curation 清单」的内容都必须显式保留，否则每周被冲掉。既有护栏：

- **表外行（不在 curation 清单里的条目）**：`cnEtfData`（新 ETF）、`reitsData`（新 REITs）、`indexData`（新指数，2026-09-27 补；`trackOnly` 详情页补充指数，2026-10-06 补）、`hkEtfData`（人工补充的港股 ETF，如主动管理ETF `3555.HK`，2026-10-05 补）、`assetData`（手工补加资产，如「红利低波」，2026-10-06 补，见 `EXTRA_ASSETS`）、`etfData`/`fundData`（月月名单自动补入的成员，2026-10-06 补，见 `sync_new_monthly.py`）→ 重建后按 code 追加保留。
- **字段级**：
  - `indexData`：`divHistory`/`dailyChange`/`dailyDate`/`yrChange` + `MANUAL_FIELDS`（publisher/listedDate/weight/weightExtra/yield/yieldNum/components/market/currency/fullReturn）+ `AUTHORITATIVE_MANUAL`。
  - `moneyFundData`：**有 `yieldDate` 即整组保留 Wind 实时值**（`yield7d/yield7dNum/dailyWan/yieldDate`，2026-09-27 修复——此前只保日期、值被清单覆盖）。
    - `hkEtfData`：人工补充字段 `active`（主动管理ETF 标记）/`shares`/`sharesUnit` 旧值非空则保留（curation 清单无此列，2026-10-05）。
  - 规模类（cnEtf/hkEtf 的 `size`、etf/fund 的 `fundSize`、moneyFund 的 `size`）：旧文件 `sizeDate` 比 curation 清单快照新 → 保留 Wind 值与日期。
- **「重建 → 重放」顺序（不可调整）**：`etfData/fundData/cnEtfData/hkEtfData` 的 Wind 字段依赖 step 15 `sync_wind_fields`、`divDate` 依赖 step 14 `sync_fund_divdate`；`reitsData.shortName`（扩位简称）依赖 step 13 `sync_new_reits`——均在 step 11 的第二次 `build_lists` 之后。
- **手工修订通道（2026-09-27 用户约定；2026-10-06 excel-exit P1/P2 升级）**：手工修订**在对话里告知 AI**，由 AI 落到 `data/*.json` 并登记到 `manual-overrides.md` 台账，同时确保该项能扛住 rebuild（落到 `MANUAL_FIELDS` / `AUTHORITATIVE_MANUAL` / 专用护栏）。**不要直接改最终 JSON 了事**（非白名单字段会被下轮重建覆盖）。**「标注」类现统一来源 = `data/curation/*.json`**（指数详情页/加权附加条件/调整周期/调整生效日、港ETF详情页/互联互通、港股红利税系数、每月千元投入、博客内容标签/相关指数）；P1 后 `build_lists.py`/`sync_blog.py` **只读 curation、不再读飞书表/标注 Excel**；**清单**亦于 P2 改读 curation（`build_lists.py` 已不读任何 xlsx）—— 至此彻底脱离 Excel（见 `excel-exit-plan.md`）。
- **新增 Wind 自动字段时的检查清单**：① 写入方在 step 11 之前还是之后？② 之前 → 必须在 `build_lists` 加保留护栏或在 step 11 之后重放；③ 之后 → 确认该文件不被后续步骤重建。

### 清单「出」机制 · 停用名单 `_retired.json`（2026-10-06 新增）
- **范围**：境内红利ETF / 港交所红利ETF / REITs / 货币基金 四类清单。
- **港交所红利ETF 的判据 = 中央数据库「港交所上市 ETF」全量名单**（与「策略魔方」同源）：名单冻结在 `data/curation/_hk_etf_universe.json`（451 只，由**会话内 MCP** 从中央库 `fund.product` 导出：`SELECT security_id FROM fund.product WHERE sec_type='ETF' AND security_id LIKE '%.HK'`）；标的**不在**该名单 ⇒ 退市/终止 ⇒ 停用。该文件缺失时**自动退回**抓 aastocks 港股 ETF 列表（`default.aspx`，全量代码内嵌 HTML，实测约 450 个）作后备；两路失败则跳过，绝不误判。
- **其余三类（境内红利ETF/REITs/货币基金）的判据 = Wind「基金到期日」≤ 今天** ⇒ 已结束 ⇒ 移出。⚠️ **不可**按「非空即出」——公募 REITs 运作中也有**未来**的「到期日」（成立日 + 合约存续期，实测 `180101.SZ`=2071-06-07、`508000.SH`=2056-06-07），按「非空」判定会**误杀全部 REITs**。约 28 天节流（`SX_LIFECYCLE_DAYS`）。
- **实现**：编号外步骤 `sync_lifecycle.py`（置于**步骤 3 之后、步骤 4 之前**）；命中即写入 `data/curation/_retired.json`；`build_lists.py` 重建时**在全部「表外行护栏」之后**统一剔除该名单的 code（确保停用标的不会被重新并入）。**历史数据不删**，仅移出展示清单；**删条目即恢复**。
- **说明**：港交所ETF 之所以不走 Wind，是因为 Wind 未返回其「到期日」（仅「存续期」）——故改用 aastocks 列表比对。

### 本地数据库与离线保障
1. `data/*.json` = 本地数据库（断源后继续可用）。
2. `backup_db.py`：每次同步后快照 + `offline-db-<日期>.json` 离线归档 + 保留 30 天 + `--check` 校验；恢复 = 快照拷回 data/。
3. `embed_data.py`：刷新 index.html 内嵌数组（9 个，indexData 内嵌去 divHistory），data/*.json 加载失败时兜底；替换前备份、替换后 node 语法验证失败回滚。
4. 脚本类文件用 `cat heredoc` 或先备份再重写（坚果云写保护）；JSON 写入临时文件 + os.replace。

### 用户上传区 data/user/（2026-10-06 excel-exit P3 后已清空）
- 原用户上传 Excel 放 `data/user/`、由 `find_snapshot` 取最新 —— **P2 起已无脚本读取**（`find_snapshot` 已删除）；**P3（2026-10-06）起 xlsx 已移入 `archive/excel-baseline-20261006/`（不入库），`data/user/` 随之清空**。
- 数值字段由 AI 用 Wind MCP 更新到最新；产品/指数**清单 + 标注**由 `data/curation/*.json` 提供（`sync_new_etf` 等 Wind 自动发现为补充）。
- （历史流程）放文件 → 检查字段映射 → 跑流水线 → 备份/embed/部署。

### 目录结构规范
运行必需留根目录（index.html/package.json/auto_sync_deploy.sh/**deploy_cloudflare.sh**/**preflight.py**/**market_calendar.json**/**functions/**（Pages Functions）/**\_redirects**/**\_headers**/api/studio/blog/data/sync_*.py/**build_lists.py**/backup_db.py/embed_data.py/extract_digests.js）；数据 JSON 在 data/；**原用户 Excel 已归档 `archive/excel-baseline-*/`（不入库）**；备份产物进 backup/；历史演示进 archive/；勿删脚本间互相引用（archive/weekly-feed-2026-09/ 内的 extract_digests.js 被 sync_weekly.py 引用，属归档件；现行日报链路为 sync_daily.py）。

### 部署（2026-10-03 起：Cloudflare Pages，取代 Vercel）

> 用户要求：项目改部署到 **Cloudflare Pages**，绑定自有域名 **divlab.net**；**不再同步到 Vercel**。

- **平台**：Cloudflare Pages（直传 Direct Upload，非 Git 集成——本仓库 git 与工作目录已脱节，仍沿用「本地同步 → 直传」模式）。
- **命令**：`bash deploy_cloudflare.sh`（`auto_sync_deploy.sh` 第 20 步已改为调用它；原 Vercel 直传逻辑已移除）。
- **凭据**（脚本开头校验，均放项目外文件，勿写入仓库）：
  - `~/.config/dividend-guide/cloudflare-token`（一行 API token；需权限 `Account → Cloudflare Pages → Edit`、`Zone → DNS → Edit`（divlab.net））
  - `~/.config/dividend-guide/cloudflare-account`（一行 Account ID）
  - 亦可用环境变量 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`
- **Pages 特定文件**（替代原 `vercel.json`）：
  - `functions/api/studio/*.js`：4 个接口（auth/list/save/delete）由 Vercel Serverless (`module.exports=async(req,res)`) 改写为 Pages Functions (`export async function onRequest(context)`)；`save/delete` 的 `node:https`+`Buffer` 改为 `fetch`+UTF-8 安全 base64；`list` 由读文件系统改为经 `env.ASSETS` 读取静态 `blog/posts.json`。**需在 Pages 项目设置环境变量 `STUDIO_PASSWORD`、`GITHUB_PAT`。**
  - `_redirects`：`/studio` → `/studio/index.html`（hash 路由 SPA 无需兜底 rewrite）。
  - `_headers`：HTML 不缓存、`/blog/*` 与 `/data/*` 协商缓存（与 Vercel 版一致）。
- **域名**（2026-10-03 已绑定并上线）：Pages 项目 `dividend-guide` 新增自定义域 **`divlab.net`** 与 **`www.divlab.net`**；DNS 托管在同一 Cloudflare 账户，两条 **CNAME → `dividend-guide-5km.pages.dev`（proxied）**（根域走 CNAME 扁平化）。线上实测 `https://divlab.net/`（200）、`http → https`（301）、`https://www.divlab.net/`（200）。
- **收尾**：Cloudflare 上线验证通过后，**已删除 `vercel.json` / `.vercelignore`**（2026-10-03）；Vercel 侧项目 `dividend-guide`（`prj_ci9SSB1opXOx8912PjiqMauOiaQ8`）不再接收部署，可按需在 Vercel 面板归档/删除。
- **环境变量（2026-10-03 已配置）**：Pages 项目 `dividend-guide` 的 **Production 与 Preview** 均已设 `STUDIO_PASSWORD`（plain_text，值为后台登录口令）与 `GITHUB_PAT`（secret_text；为**细粒度 token**，仅授权 `vincewatson/dividend-guide` 一个仓库、权限 `Contents: Read and write` + `Metadata: Read-only`、无到期日）。配置后需**重新部署**一次才被 Functions 读取。线上实测：`POST /api/studio/auth`（正确口令）返回 `token`、（错误口令）`密码错误`；`/api/studio/list`（带 token）`{posts:[]}`、无 token `未授权`。⚠️ 口令/PAT 值不写入仓库，仅存于 Cloudflare Pages 环境变量与 `~/.config/dividend-guide/`。

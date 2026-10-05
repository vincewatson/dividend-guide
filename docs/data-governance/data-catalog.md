# 数据目录（data-governance）

> 来源：《网站更新与数据管理对照文档》（2026-08-22 拆分；原件归档为 `docs/_archived_网站更新与数据管理对照文档.md`）**流程篇**「数据矩阵」「数据文件清单」「数据来源明细」「数据源优先级」；「规范数据库（Wind Excel 快照）表头结构」「指数币种变体归并」「口径模糊 / 数据重复问题的标准处理范式」为 2026-09-20 新增。
---

> 本文档内容迁移自《网站更新与数据管理对照文档》（2026-08-22 docs 重组）。
> 当前唯一权威规范以 `reference/` 与 `data-governance/` 下的文件为准；`changelog/` 只是历史记录，不代表当前状态。

## 数据矩阵（文件 → 来源 → 脚本 → 保护）

| 数据文件 | 数据源 | 更新脚本 | 覆盖范围规则 | 写回保护 |
|----------|--------|----------|--------------|----------|
| indexData.json（divHistory）| Wind 指数股息率日频 | sync_div_history.py + fix_laggard | 增量补到最新交易日（2023-01 起全量）；fix_laggard 单查补缺口（**日频查询 + 合并**，2026-09-13 修订）| **绝不删除**（跳过做占位 + 写回兜底）|
| indexData.json（dailyChange）| Wind 涨跌幅 | sync_daily_change.py | 每日最新交易日 | 仅更新两字段；**存小数**（-0.0204=-2.04%）|
| productQuotes.json（产品行情快照）| Wind `fund_data.get_fund_price_indicators` | **sync_product_quotes.py** | 各 ETF/基金【按日期追加】快照（当日涨跌幅 / 今年以来回报）；新交易日追加、同日仅补空值 | **只追加不覆盖**（历史永久保留）；**独立文件**，不受 sync_excel 整表重建；缺数据写 `null`（前端「—」）；**绝不跨取跟踪指数**（2026-10-05）|
| indexData.json（新指数）| Wind（自动发现）| sync_new_etf.py | 新 ETF 跟踪指数缺失时补入 | 自动纳入，含 divHistory |
| cnEtfData/hkEtf/etf/fundData | Excel 快照 | sync_excel.py | 快照全量重建 | divHistory/dailyChange/divDate/yieldDate 保护；**cnEtf 保留 Wind 自动发现标的**；**hkEtf 保留表外标的 + `active`/`shares` 字段（2026-10-05，如主动管理ETF 3555.HK）** |
| cnEtfData（新 ETF）| Wind（自动发现）| sync_new_etf.py | 近 30 天成立红利类 ETF 自动补入 | 与 Excel 重建合并去重 |
| reitsData.json（新 REITs）| Wind（自动发现）| sync_new_reits.py | 全部已上市公募 REITs（508xxx.SH / 180xxx.SZ）对照补入；明细字段本次取不到**留空不填 0**（数值 null / 字符串 ''）| 与 Excel 重建合并去重（sync_excel 保留 Wind 自动发现标的，2026-09-26 起）|
| divDate | Wind 最近分红 | sync_fund_divdate.py | 全量重拉 | 无数据保留原值；**必须在 sync_excel 之后**；措辞**多路兜底**（最近分红情况→最近分红发放日期→基金分红 分红发放日）|
| moneyFundData（yield7d/yieldDate）| Wind 实时 | sync_money_fund.py | 最新交易日 | 重建时保留 yieldDate；**必须早于 sync_excel(2)** |
| yuebaoHistory.json | Wind 日频 | sync_yuebao_history.py | **动态：divHistory 最早日期向前 180 天** | 每段重试 3 次 + 写回前与现有文件**合并**兜底（2026-09-13 加固，防瞬时失败丢段）|
| assetHistory.json | Wind EDB + 中指季度报告 | sync_asset_macro.py + sync_reits_daily.py | 各序列全量；REITs 两类为**日频增量**；重点50城租金率为**中指季度时点序列**（用户/季度报告更新，asset_macro 保留现有值）| safe_fetch：拉取空保留旧值；asset_macro 不覆盖 REITs 与重点50城租金率 |
| reitsDaily.json | Wind REITs 日频原始缓存（58 只逐只）| sync_reits_daily.py | **增量缓存**（每只续补新段 → 汇总两类中位数 → 写 assetHistory）| 纯缓存，可从 Wind 重建；断点续传落盘处 |
| dailyData.json | digest-db.json（坚果云同步，稳定机器接口）| sync_daily.py | 最新一期前置 | 独立 |
| dailyTagColors.json | digest-db.json → meta.tagColors | sync_daily.py | 10 标签浅底/深字配色，前端直接复用 | 独立 |
| blogData.json（博客 · 子弹列车文章目录）| **用户提供**（`user_upload/公众号历史文章(20240123-20260919).xlsx`：发表日期 / 标题 / 文章链接 / 所属栏目）+ **标注表** `user_upload/博客文章标注表*.xlsx`（取最新一份；内容标签 / 相关指数，按 url 合并）+ 兜底 `data/blogAnnotations.json` | **手动**（`sync_blog.py`：xlsx + 标注表合并 + 按链接去重 + 空格规范）| 目标 = 公众号历史文章全量目录（当前 **289 篇**，含付费 **2** 篇；已标注内容标签 **114** 篇 / 相关指数 **86** 篇，其余留空待补；相关指数为 Wind 指数简称，前端按站点 `indexData` 匹配，命中者标蓝并可跳转其指数代码）| 独立（不参与自动流水线）|
| etfData/fundData/cnEtfData/hkEtf/indexData（Wind 化字段）| Wind get_fund_financials / get_index_fundamentals | **sync_wind_fields.py** | 步骤 15，在 sync_excel(2)（步骤 11）之后（不被覆盖）| **fundCount/yrChange/divDate/yield=指数股息率 均保护**；N 前缀摘除不恢复（fix_n_prefix + sync_excel 保护）|

## 数据文件清单（data/）

| 文件 | 当前数量 | 生成脚本 | 主来源 | 更新方式 |
|------|---------|---------|--------|---------|
| indexData.json | 49 指数 | sync_excel.py + sync_new_etf | ②+① 混合 | 流水线 |
| cnEtfData.json | 93 ETF | sync_excel.py + sync_new_etf + sync_fund_divdate | ② Wind 快照（divDate/新 ETF 由 ③）| 流水线 |
| hkEtfData.json | 13 | sync_excel.py（表外行保留）| ① 用户表优先；人工补充（3555.HK 主动管理ETF，2026-10-05）| 流水线 |
| etfData.json | 15 | sync_excel.py + sync_fund_divdate | ② Wind 快照 | 流水线 |
| fundData.json | 26 | sync_excel.py + sync_fund_divdate | ② Wind 快照 | 流水线 |
| moneyFundData.json | 43 | sync_excel.py + sync_money_fund | ② Wind 快照 | 流水线 |
| reitsData.json | 58（新上市自动补入）| sync_excel.py + sync_new_reits | ② Wind 快照（新 REITs 由 ③ 自动发现）| 流水线 |
| assetData.json | 16 | sync_excel.py | ① 用户表（总表）| 流水线 |
| （Wind 化字段）| — | **sync_wind_fields.py** | Wind get_fund_financials / get_index_fundamentals | 周流水线 步骤 15 |
| assetHistory.json | 12 序列 | sync_asset_macro.py + sync_reits_daily.py | ③ Wind MCP（REITs 日频独立脚本；重点50城租金率=中指季度报告）| 流水线 |
| reitsDaily.json | 58 只日频缓存 | sync_reits_daily.py | ③ Wind MCP | 流水线（缓存，可重建）|
| yuebaoHistory.json | 1022 条 | sync_yuebao_history.py | ③ Wind MCP | 流水线 |
| productQuotes.json | 135 产品 / 135 条快照（逐日累积）| **sync_product_quotes.py** | ③ Wind MCP（`get_fund_price_indicators`）| 流水线（步骤 12 后·编号外；只追加不覆盖）|
| dailyData.json | 期数随 digest-db.json 累积 | sync_daily.py | digest-db.json | 流水线 |
| dailyTagColors.json | 10 标签 | sync_daily.py | digest-db.json → meta.tagColors | 流水线 |
| blogData.json | 289 篇 | sync_blog.py（手动）| 用户提供（`user_upload/公众号历史文章*.xlsx`）+ 标注表 `user_upload/博客文章标注表*.xlsx`（兜底 `data/blogAnnotations.json`）| 手动（随用户补充而更新）|
| backup/ + index.html 内嵌 | — | backup_db.py / embed_data.py | 本地 | 同步后自动 |

## 数据来源明细（按数据域）

### 红利指数（indexData.json）
- ① 用户手动（受保护，不更新）：`publisher/listedDate/weight/weightExtra/components/market/currency/fullReturn/adjustCycle/adjustDate`。
- ③ Wind：`yield/yieldNum`（divHistory 最新值覆盖）、`divHistory`（日频，2023-01 起，只补不删）、`dailyChange/dailyDate`（独立脚本，存小数）。
- 新指数：sync_new_etf 自动补入（基础信息 + divHistory）。

### A股红利ETF（cnEtfData.json）
- 基本信息（名称/管理人/费率/跟踪指数/上市日）：② Wind 快照「境内红利ETF」；**新 ETF 由 sync_new_etf 用 ③ Wind 自动补入**。
- `name`（ETF 简称）：**唯一口径 = Wind「基金扩位场内简称」**（快照列名即「ETF扩位场内简称」；新 ETF 由 `sync_new_etf.fetch_ext_short_names()` 取该字段覆盖 `search_funds` 的证券简称）——2026-09-20 用户要求，详见「规范数据库（Wind Excel 快照）表头结构」。
- `divDate`：③ Wind（sync_fund_divdate.py，**多措辞兜底**：`{code} 最近分红情况` → `{code} 最近分红发放日期` → `{code} 基金分红 分红发放日`，首个返回「基金红利发放日」者即用；2026-09-13 起「最近分红情况」为主），Wind 查不到留空 `—`。
- `divCount/size/shares/holders`：② 快照；空值 `—`。

### 港交所红利ETF（hkEtfData.json）
- `connect/trackCode/trackName`：① 用户手动（修订 Wind 缺失）；`divDate` 港股 Wind 不支持，保留 Excel 值；其余 ② 快照。

### 月月分红 ETF/场外基金（etfData/fundData.json）

**股息率口径（2026-08-16 用户确认）**：`yield/yieldNum` = **跟踪指数股息率**（trackCode → indexData.yieldNum 映射；trackCode 不在 49 指数时由 `_extend_yield_map` 从 Wind 查指数股息率兜底）；Wind「近12月分红收益率」（ETF 实际派息口径，≠指数股息率）另存 `divYieldNum` 备用，**禁止写入 yield**。
- 全部字段：② 快照「月月可分红ETF/月月可分红（场外）」。
- `name`（ETF 简称）：**统一 = Wind「基金扩位场内简称」**（快照「月月可分红ETF」表头 2026-09-20 由「ETF简称」更名为「ETF扩位场内简称」；取值本就是扩位简称，实测 15/15 与 Wind 一致）。**场外基金表「月月可分红（场外）」无场内概念，`fundData.name` 仍是基金简称，不受此规则约束**。
- `divDate`：③ Wind（sync_fund_divdate，**多措辞兜底**，2026-09-13 起「最近分红情况」为主）。
- `taxRate`（港股红利税系数）：① 用户（名称智能识别 0.8/1.0）。

### 首页食息资产（assetData.json + assetHistory.json）
| 资产 | 列表快照来源 | 历史曲线来源 |
|------|-------------|-------------|
| 红利类（中证红利等 5 个）| ② Wind（divHistory 最新覆盖）| ③ Wind MCP |
| 5年期LPR | ① 用户（央行）| ③ Wind EDB |
| REITs 两类 | **③ Wind 日频中位数**（assetHistory 覆盖，Excel 不覆盖）| ③ Wind MCP（日频）|
| 重点50城租金率 | ① 用户（**中指研究院 50城租金房价比**，2026-08-15 确认权威；用户手动提供列表值）| ① 中指季度报告（**季度时点序列 2023Q1 起 14 点**，08-16 接入；每季度从中指云报告更新）；中原 6 城均值→备用 key「重点城市租金率(中原6城均值)」|
| 预定利率研究值 | ① 用户（保协）| ③ Wind EDB + 官方发布覆盖 |
| 3/5年期储蓄国债 | ② Wind（**储蓄国债票面利率**，Wind 债券发行记录周频采样）| ③ Wind bond_data |
| 整存整取 1/3年期 | ① 用户（工行官网核对）| ③ Wind EDB |
| 中证同业存单AAA | ② Wind | ③ Wind EDB |
| 天弘余额宝 | ② Wind（快照）+ ③ 实时覆盖 | ④ iFind 日频（Wind 限流）|

### 货币基金 / REITs / 食息资讯（日报）
- 货币基金（moneyFundData）：② 快照「货币基金」+ sync_money_fund ③ 实时更新头部（含 yieldDate）。
- REITs（reitsData）：② 快照「REITs（产权类）/REITs（经营权类）」58 只。
- 食息资讯（dailyData）：**只读 `digest-db.json`**（坚果云同步目录内的稳定机器接口，schema 见同目录 `DATA-SCHEMA.md`）→ sync_daily.py 提取。
  - 产出 `dailyData.json`（= `db["digests"]` 按期倒序，item 含 `id/tags/time/source/text/url`）与
    `dailyTagColors.json`（= `db["meta"]["tagColors"]`，前端运行时覆盖内嵌兜底，实现「配色复用」）。
  - **不解析** `yield-guide-daily-digest.html`（它只是同一份数据的视图，结构随改版变动；不一致时以 JSON 为准）；
    **不执行** `yield-guide-daily-digest-skill.md` 的采集流程（那是 Windows 生成端的事，消费方只读）。
  - 原**周报**线路（`dividend-guide-weekly-digest.html` → sync_weekly.py → weeklyData.json）已于 2026-09-20 退役，
    完整实现归档在 `archive/weekly-feed-2026-09/`（可回滚，未删除）。

## 规范数据库（Wind Excel 快照）表头结构（2026-09-20 统一）

> **规范数据库 = `data/user/食息指南(EXCEL-Wind)-*.xlsx`（主表）与 `data/user/食息指南PRO(EXCEL-Wind)-*.xlsx`（PRO 表）**，由用户从 Wind 导出。
> `sync_excel.py` 用 `pd.read_excel(header=None)` **按列下标取值**，故列顺序是硬约束：**改表头文字不影响解析，但增删/移动列必须同步改脚本下标**。
> ⚠️ 这是一条**只能靠人记住**的隐性契约（挪列忘改代码会静默错位）；解方（改为**按表头名称取值**）已立项为中期改进项，见 `docs/backlog.md` B-1。

### ETF 简称的唯一口径

**站内所有 ETF 的简称（JSON `name` 字段）统一使用 Wind 的「基金扩位场内简称」。**
Wind 对同一只 ETF 提供三个简称，**只用第三个**：

| # | Wind 字段 | 说明 | 站点是否使用 |
|---|-----------|------|--------------|
| 1 | 基金简称 / 证券简称 | 如「嘉实中证红利低波动100ETF」 | ❌ 不用 |
| 2 | 场内简称 | 交易所短简称 | ❌ 不用 |
| 3 | **基金扩位场内简称** | 如「红利低波100ETF嘉实」 | ✅ **唯一口径** |

覆盖范围：`cnEtfData.json`（93 只）、`etfData.json`（15 只）。
**例外**：`hkEtfData.json`（港交所 ETF）——Wind 的「基金扩位场内简称」**对港股返回空字符串**（该字段仅 A 股适用），故保留 `name` = 场内简称（= 证券简称），表头沿用「ETF简称」。
**不受约束**：`fundData.json`（月月可分红场外，非 ETF）、`moneyFundData.json`（货币基金）仍为「基金简称」。

### 各工作表简称列表头

| 快照 | 工作表 | 列下标 | 简称列表头 | 取值口径 |
|------|--------|--------|-----------|----------|
| PRO 表 | 境内红利ETF | r[1] | **ETF扩位场内简称** | Wind 基金扩位场内简称 |
| 主表 | 月月可分红ETF | r[1] | **ETF扩位场内简称**（2026-09-20 由「ETF简称」更名） | Wind 基金扩位场内简称（取值原本就是） |
| PRO 表 | 港交所红利ETF | r[1] | ETF简称（例外保留） | 港交所场内简称（Wind 无扩位字段） |
| 主表 | 月月可分红（场外） | r[1] | 基金简称（不改） | 场外基金，无场内概念 |
| 主表 | 货币基金 | r[1] | 基金简称（不改） | 货币基金，非 ETF |
| PRO 表 | 境内红利指数 | r[1] | 指数名称 | 指数简称 |

### 「境内红利ETF」完整表头（19 列，顺序即脚本下标）

```
ETF代码 | ETF扩位场内简称 | 跟踪指数代码 | 跟踪指数名称 | 基金管理人 | 成立日期 | 上市日期 | 管理费率 |
最近分红日期 | 年度分红次数(2026) | 场内流通份额(亿份) | 持有人户数(2025,万) | ETF联接基金持有比例(2025) |
管理规模(最新,亿元) | 管理规模(2025,亿元) | 管理规模(2024,亿元) | 管理规模(2023,亿元) |
管理规模(2022,亿元) | 管理规模(2021,亿元)
```

### 防回退要点

- 修改 JSON 简称后，**必须同时更新规范数据库对应单元格**，否则下次 `sync_excel.py`（每周步骤 4/11）会按旧值重建并回退。
- 新 ETF（`sync_new_etf.py` 自动发现）不走 Excel，其简称由 `fetch_ext_short_names()` 从 Wind 取「基金扩位场内简称」，已内置，无需人工干预。

## 数据源优先级

**优先使用万得（Wind）数据，不得已才取其他数据源。**

| 优先级 | 数据源 | 用途 |
|--------|--------|------|
| ① 首选 | Wind（快照 Excel + Wind MCP）| 所有基础数据、股息率历史、宏观资产、货币基金、指数/ETF/REITs 快照 |
| ② 备选 | iFind（EDB/基金端）| Wind 配额不足/超限时（国债中债收益率、余额宝日频历史）|
| ③ 备选 | 东财 mx-ds-mcp | 行情/板块补充 |
| ④ 权威 | 用户手动（对话告知 AI → 登记 `manual-overrides.md`；官方发布）| 指数公司、加权方式、发布日期、存款利率、LPR 等 |

**执行要求**：Wind 优先；Wind `QUOTA_ERROR` 才切 iFind/东财并记录"本次用 X 源替代"；已用其他源补的数据，Wind 配额可用时优先 Wind 重拉核对（`SX_FULL_REFRESH=1`）；用户表字段永远优先不被覆盖。

**已知替代（2026-08-05 确认）**：国债 3/5 年期 Wind EDB 无权限（S0059746）→ 保留 iFind；余额宝 Wind get_fund_kline 限流严重 → iFind 日频 1311 条保留；标普A股红利100 各源均无股息率 → 维持 `—`。

## 指数币种变体归并（2026-09-20）

**规则：同一指数的港币版 / 人民币版在站内只保留一条 —— 取「基准版」，不并列。**

用户原话（2026-09-20）：「关于港币版取数的问题，直接取人民币版就行了。这也是数据治理的一方面 …… 一旦出现了港币版，就不要再单独列出来，这样显得很傻。」

### 为什么要规范
Wind 对港股通 / 香港类指数通常**同时发布港币版与人民币版两条**，**代码不同、股息率数值完全相同**（2026-09-20 逐日比对一致）。不归并的话：同一指数在站内出现两条，且 ETF 的 `trackCode` 分裂到两个代码上 —— 表现就是同一页面里有的行显示「港股通高股息(HKD)」、有的显示「港股通高股息CNY」。

### 基准版判定（可核验，不靠猜）
1. Wind 全称里写**「人民币」**的那一版 = **变体**（折算派生版），另一版为基准版；
2. 若没有带「人民币」的版本，则带**「港币 / (港币)」**的那一版 = 变体。

### 已核验的变体对
| 变体版 | 基准版 | 站内处理（截至 2026-09-20）|
|---|---|---|
| `SPAHLVHP.SPI` 标普港股通低波红利指数(港币) | **`SPAHLVCP.SPI` 标普港股通低波红利指数** | ✅ **已启用归并** —— 6 只 ETF 全部指向基准版（含新收录的 `158039.OF`）|
| `930915.CSI` 港股通高股息CNY | `930914.CSI` 港股通高股息(HKD) | ⏸ **保持现状（用户 2026-09-20 确认，不迁移）** —— 站内 9 处用 930914、2 处用 930915 |
| `930840.CSI` 港股通高息精选CNY | `930839.CSI` 港股通高息精选 | ⏸ 保持现状（变体版未出现于站内）|
| `930793.CSI` HK银行(CNY) | `930792.CSI` HK银行(HKD) | ⏸ 保持现状（变体版未出现于站内）|

### 实现与防回退（单一事实来源）
| 位置 | 作用 |
|---|---|
| `index_variants.py` | **映射表 `VARIANT_TO_BASE` + `BASE_NAME` + `normalize()`**，全站唯一来源；改口径只改这里 |
| `sync_excel.py` | 所有 builder 产出后**统一归并**（置于「按跟踪指数股息率校正」之前，保证取到的是基准版股息率）|
| `sync_new_etf.py` | 补入新 ETF 前**归并**跟踪指数，避免港币版进入数据 |
| `check_data.py` 第 17 项 | 硬校验：站内任何 `trackCode` 都不得是变体代码 |

**注意**：归并会改变展示名（去掉「(港币)」），而主题 / 市场筛选由 `trackName` 推导（`cnEtfThemeOf` / `cnEtfMarketOf`）；归并前后命中结果一致（2026-09-20 实测：`标普港股通低波红利指数` 仍归「红利低波」主题 +「港股」市场）。

### 已确认：其余变体对保持现状（2026-09-20）
用户 2026-09-20 明确：标普那一组已归并，**其余变体对保持现状、不做迁移**。以下仅作记录、不作处理：
- `930914.CSI`(HKD) / `930915.CSI`(CNY)：`cnEtfData` 7 只 + `etfData` 3 处 + `fundData` 2 处引用 `930914.CSI`；`513530.OF`（`cnEtfData`/`etfData`）与 `018387.OF`（`fundData`）引用 `930915.CSI`；`indexData` 只有 `930914.CSI`。属"同指数分裂两版"，但两版数值完全相同，**不影响线上数值**。
- `930840.CSI` / `930793.CSI`：站内均未出现变体版，无需处理。
- **映射表不含以上三组** —— `index_variants.py` 的 `VARIANT_TO_BASE` 只启用标普一组。
  将来若要统一，把对应键加进该映射表（一行）即可，`check_data.py` 第 17 项会自动覆盖新启用的变体代码。
  参考：按「基准版判定」规则，930914 那组的基准版应为 `930914.CSI`（把 2 处 930915 归并过去，改动最小）；若届时要求"一律人民币版"，则需迁移 `indexData` 代码 + 9 处引用 + 规范数据库 5 张表。

## 口径模糊 / 数据重复问题的标准处理范式（2026-09-20 确立）

> 起因：「指数币种变体归并」这一节处理得非常规范，用户要求把它**沉淀为通用原则**，今后遇到任何"同一对象出现两条、口径说不清、不知道听谁的"问题，一律照此执行，**不要每次重新讨论判断标准**。

**四步范式（缺一不可）**：

1. **可核验的判定规则**——用一条**可查证、不靠主观**的规则决定取舍，代替"看着办"。
   - 正例：币种变体取"Wind 全称里写『人民币』的那版为变体，否则带『港币/(港币)』的为变体"——规则可由任何人按同一份 Wind 数据独立复现。
   - 反例：❌「哪个看起来更准就留哪个」「我印象中应该是 A」——不可核验，不可继承。
2. **单一事实来源（Single Source of Truth）**——把规则与映射落到**一个文件、一处定义**，全站只引用它、不各自实现。
   - 正例：`index_variants.py` 的 `VARIANT_TO_BASE` / `normalize()`；改口径只改这里。
3. **自动化硬校验（防回退）**——在 `check_data.py` 加一项断言，把"规则"变成**部署硬门槛**，任何人手滑回退都会当场失败。
   - 正例：`check_data.py` 第 17 项「站内任何 `trackCode` 都不得是变体代码」。
4. **明确记录"故意不处理"的部分**——把**经确认后维持现状**的例外写进文档（连同理由与将来如何启用），避免后人误以为遗漏而反复"顺手修一刀"。
   - 正例：本节前述「已确认：其余变体对保持现状」——写明 930914/930915 等同指数分裂但数值相同、不影响线上，且注明"将来要统一，把键加进映射表一行即可"。

**沿用清单（已有实例）**：指数币种变体归并（`index_variants.py` + `check_data` 第 17 项）、ETF 简称唯一口径（`data-catalog`「规范数据库表头结构」+ `sync_new_etf.fetch_ext_short_names`）、每日资讯【】符号（生成端规范 + `sync_daily.strip_marks` + `check_data` 第 16 项）。


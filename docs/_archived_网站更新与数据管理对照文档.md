# 食息指南 网站更新与数据管理对照文档

> 本文件是网站每次更新/修正时的**唯一权威对照手册**：
> - **规范篇**：所有修改必须遵守的格式、口径、样式约定（检查清单）。
> - **流程篇**：所有数据文件的来源、更新方式、字段归属与防回退机制（数据治理）。
> - **记录篇**：变更执行记录（精简摘要，不代表当前状态）。
>
> **维护约定**：新"规范式"约定（格式/口径/样式/流程/数据源变化）出现即追加到对应章节；若与历史记录冲突，**以本文件最新规范为准**。

> **⚠️ 每周自动更新前置步骤（2026-08-15 用户指令，最高优先级）**：
> 1. **先修订本文件**：把本周的最新变化写入对应章节（简洁 + 准确），冲突需求一律**以用户最新指令为准**（本文件同步更新）。
> 2. **再确认自动任务执行逻辑**：核对「食息指南网站数据更新」定时任务与 `auto_sync_deploy.sh` 的步骤数、顺序、脚本清单是否与本文件一致；发现不一致先修正脚本/任务，再执行更新。
> 3. 顺序固定：**修订文档 → 确认逻辑 → 才允许开始数据同步**。

---

# 规范篇 · 更新检查规范

## 1. 显示格式统一

1. **日期格式**（2026-08-04）：全站统一 `yyyy-mm-dd`；禁止显示层替换 `.` 或手动拼接；排序比较可用 `replace(/-/g,'')`（仅内部比较）。
2. **缺数据占位**（2026-08-04）：全站统一 `—`（em dash）。禁止 `'-'`/`'--'`/`'暂无历史'`/`'数据待更新'`/`'暂无简介'` 等混用。语义性文案除外（如"暂未分红"=明确分红 0 次；整图空态说明"该指数暂无股息率历史数据"是整图说明非单元格占位）。
3. **余额宝 7 日年化 2 位小数**（2026-08-10）：首页资产列表、各详情页图例值（`*YuebaoVal`）、图表端点标注、hover 悬浮框全部 `toFixed(2)`；数据层 `'{:.2f}%'`。**任何新增余额宝显示处一律 2 位小数**。

## 2. 数据源口径统一

1. **指数股息率以 Wind divHistory 最新值为准**：`sync_excel.py` 写回 indexData 时用 divHistory 最新值覆盖 `yield/yieldNum`；Excel 快照仅兜底。Wind 无值 → `yield` 置空显示 `—`，**禁止 `0.00%`**、禁止用陈旧数值充数。
2. **手动字段保护**：`publisher/listedDate/weight/weightExtra/components/market/currency/fullReturn`（+ `adjustCycle/adjustDate`）由用户维护（飞书表），sync_excel 不得覆盖（旧值非空保留）；`AUTHORITATIVE_MANUAL` 硬编码权威值强制固定（如 SPCADMCP.SPI components=100、000922.CSI listedDate=2008-05-09）。
3. **REITs 两类口径**（2026-08-11 确立，08-15 定稿）：
   - 分类按**现金流属性**（非 Wind"项目属性"物权口径）：产权类 = 园区/仓储物流/消费/保障房；特许经营权类 = 交通/新能源/生态环保/水利（**派息含资产摊销本金返还，虚高**）。
   - 指标 = Wind **名义派息率（中位数）**：产权类、特许经营权类均**日频**（每交易日，2023-01 起约 873 点/类，assetHistory 运行时加载）。
   - 首页 assetData 的 yield/date：sync_excel 特判从 assetHistory 最新日频中位数覆盖（08-15 起），**不随 Excel 快照回退**；note/desc/图例统一"名义派息率（中位数）"。
   - 特许经营权类详情页红字风险提示（定稿文案）：**"特别提示：特许经营权类REITs的名义派息率，包含资产摊销对应的本金返还部分，该指标会高估实际投资收益率，需要结合IRR综合判断真实回报水平。"**
4. **红利指数覆盖**：build_asset_data 中红利指数 yield/date 取 indexData divHistory 最新值（`ASSET_INDEX_NAME_MAP`：上证国企红利→上国红利、香港银行→HK银行(HKD)）。

## 3. 前端样式约定

1. 红利指数浏览器"股息率"列：亮蓝 `#001AFF` + 加粗（`.col-yield`）；各列表/详情页"管理费率"默认黑色正常字重，不套用 yield 类。
2. "最近分红日期"仅存在于基金/ETF（详情页 + 月月分红列表），**指数无此概念**。
3. **Footer 规则**（08-04 确立，08-05/08-10 修订定稿）：
   - 全站 footer 一律**不悬浮**（`position:relative` 跟随滚动）；统一基类 `.site-footer`（背景 `#21292e`、白字、上边框 `rgba(255,255,255,0.12)`），改 footer 只改基类，全站 7 处一起生效。
   - 首页 footer 在 `.main-content` 内；**详情页 footer 必须在 `.detail-body` 内部**（打开详情锁 body 滚动，`.detail-body` 为唯一滚动容器，footer 随其滚到底部露出）。
   - **全宽**（关键）：`.site-footer` 基类 `max-width:100%` 导致负 margin 只平移不增宽——必须显式设宽 + 放行：桌面 `margin:16px -28px 0; width:calc(100% + 56px); max-width:none`；移动（≤767px）`margin:16px -14px 0; width:calc(100% + 28px)`（**与 `.detail-body` 的 media query 成对修改**）。
   - 与上方卡片留空隙：`margin-top:16px`（桌面+移动都要写，防移动端 margin 简写覆盖丢失）。
   - ❌ 禁止把 footer 移到 `.detail-body` 外部（flex 直接子项 → 视觉悬浮）；禁止 `-43px` 大负 margin。
4. **无阴影 + 外框**（08-04/05）：表格/卡片不设 box-shadow（仅浮动交互元素：下拉/气泡/滑块手柄/tab 高亮保留阴影）；数据可视化区保留 1px 浅色外框（`.asset-table` #e3e6ef、`.intro-card`/`.detail-main-card` #e8ebf3、`.fund-card`/`.knowledge-item`/`.fav-item`/`.fav-empty`/`.blog-card`/`.blog-empty`/`.weekly-nav-item` #eef1f8、`.detail-chart-select` #e0dde5）。
5. **详情页溢出控制**（08-05/10 修订）：`.detail-body` 用 `overflow-x:hidden`；`.detail-card-section` **不得设 overflow**（`hidden`/`overflow-x:hidden` 都会裁剪 hint 气泡，向上弹出超出 section 顶部被裁）；滑块 handle 内移定位（左 `calc(p0%+8px)`、右 `calc(p1%-16px)`）。
6. **详情页基准线**（08-05）：余额宝 7 日年化基准线为**绿色实线 `#1FBE7F`**（端点/圆点/hover 气泡内数值/图例均同色）；主曲线蓝色 `#001AFF` 实线，hover 主曲线文字 `#9fb3ff`。天弘余额宝详情页的橙线对标基准为"一年期整存整取"，其余资产为"余额宝七日年化收益率"。

## 4. 其他约定

- 图表 hover 气泡宽度按文本动态计算（`measureText`），自动避开视口左右边界。
- 表格排序 `divDate` 支持（08-05）：`smartCompare`/`sortData` 加 divDate 分支，空值排最后。
- 红利指数浏览器简介固定句式：「本表仅展示有挂钩产品发行的[n]个指数 · 数据已更新至[date]」（n=指数总数，date 优先 dailyDate、兜底 divHistory 最新日期）。
- 新增详情页图表必须同步改 **6 处**（HTML/状态/初始化/select/滑块/hover），对照 monthlyEtfDetail 模式。
- 页面副标题/文案迭代为常态（非 bug）。
- 数据同步脚本写入用临时文件 + `os.replace` 原子替换（坚果云盘锁冲突）。
- **批量修改脚本必须"全断言通过后统一原子写盘"**（教训：任一断言失败整次修改未写盘，改后需 grep 复查关键标记）。

## 5. 更新后必查清单（部署前）

1. `python3 check_data.py` 全部 ✅（部署硬门槛）
2. 首页「数据更新于」为最新交易日（curl 线上确认）
3. 红利指数浏览器：dailyChange 日期为最新交易日
4. 余额宝（首页 + 各详情页图例）2 位小数
5. 详情页：图表可交互（hover/滑块/select），footer 全宽跟随滚动、与卡片 16px 间距、hint 气泡完整
6. 月月分红 divDate 覆盖率达标（fund ≥25、etf ≥14、cnEtf ≥50）
7. 线上 index.html 与本地一致（md5 对比）或 curl 关键数据抽查
8. 股息率口径抽查：etfData/fundData 任抽 2-3 只详情，yield=跟踪指数股息率（与指数浏览器一致）；**无负值/无 15%+ 极端值**
9. 简称 N 前缀：全站无残留「N」开头简称（grep "N红利\|N.*ETF"）
10. 浏览器验证需**强刷**（?t=时间戳），避免 CDN/浏览器缓存看到旧数据（08-16 曾误判 3.43% 未修复）

---

# 流程篇 · 数据来源与更新流程

## 1. 数据矩阵（文件 → 来源 → 脚本 → 保护）

| 数据文件 | 数据源 | 更新脚本 | 覆盖范围规则 | 写回保护 |
|----------|--------|----------|--------------|----------|
| indexData.json（divHistory）| Wind 指数股息率日频 | sync_div_history.py + fix_laggard | 增量补到最新交易日（2023-01 起全量）| **绝不删除**（跳过做占位 + 写回兜底）|
| indexData.json（dailyChange）| Wind 涨跌幅 | sync_daily_change.py | 每日最新交易日 | 仅更新两字段；**存小数**（-0.0204=-2.04%）|
| indexData.json（新指数）| Wind（自动发现）| sync_new_etf.py | 新 ETF 跟踪指数缺失时补入 | 自动纳入，含 divHistory |
| cnEtfData/hkEtf/etf/fundData | Excel 快照 | sync_excel.py | 快照全量重建 | divHistory/dailyChange/divDate/yieldDate 保护；**cnEtf 保留 Wind 自动发现标的** |
| cnEtfData（新 ETF）| Wind（自动发现）| sync_new_etf.py | 近 30 天成立红利类 ETF 自动补入 | 与 Excel 重建合并去重 |
| divDate | Wind 最近分红 | sync_fund_divdate.py | 全量重拉 | 无数据保留原值；**必须在 sync_excel 之后** |
| moneyFundData（yield7d/yieldDate）| Wind 实时 | sync_money_fund.py | 最新交易日 | 重建时保留 yieldDate；**必须早于 sync_excel(2)** |
| yuebaoHistory.json | Wind 日频 | sync_yuebao_history.py | **动态：divHistory 最早日期向前 180 天** | 拉取空则保留旧文件 |
| assetHistory.json | Wind/iFind EDB + 中指季度报告 | sync_asset_macro.py + sync_reits_daily.py | 各序列全量；REITs 两类为**日频增量**；重点50城租金率为**中指季度时点序列**（用户/季度报告更新，asset_macro 保留现有值）| safe_fetch：拉取空保留旧值；asset_macro 不覆盖 REITs 与重点50城租金率 |
| weeklyData.json | digest HTML | sync_weekly.py | 最新一期前置 | 独立 |
| etfData/fundData/cnEtfData/hkEtf/indexData（Wind 化字段）| Wind get_fund_financials / get_index_fundamentals | **sync_wind_fields.py** | 周更新第 9 步，在 sync_excel(2) 之后（不被覆盖）| **fundCount/yrChange/divDate/yield=指数股息率 均保护**；N 前缀摘除不恢复（fix_n_prefix + sync_excel 保护）|

## 2. 三条铁律（所有数据更新必须遵守）

1. **写回绝不删除旧数据**：拉取失败/跳过/无新增 → 一律保留旧值。删除是显式操作且仅在全量成功替换时发生。
2. **历史序列起点必须早于所有图表数据起点**：yuebaoHistory 起点 ≤ divHistory 起点（差额 180 天余量）；前端对早于起点的日期返回 null（无数据不画，禁止假填充）。
3. **部署前 check_data.py 必须全部 ✅**：含数据覆盖范围检查（起点/最新日期/条数）；脚本改动后必须语法预检（流水线步骤 0）。

## 3. 标准流程（auto_sync_deploy.sh，15 步）

0 修订本文件最新变化 + 确认任务逻辑（用户指令，最高优先级）→ 0.1 脚本语法预检 → 1 sync_excel(1) → 2 div_history+fix_laggard → 3 daily_change → 4 money_fund → 5 yuebao_history → 6 asset_macro → 6.5 **sync_reits_daily（REITs 日频增量，asset_macro 不覆盖 REITs）** → 7 sync_excel(2)（assetData 取最新）→ 7.5 **sync_new_etf（新 ETF/新指数自动发现）** → 8 fund_divdate（恢复 divDate）→ 9 **sync_wind_fields（字段级 Wind 化：fundCount/ETF 字段/月月分红字段/股息率口径/N 前缀检查，2026-08-16 起）** → 10 weekly → 11 backup → 12 **check_data（硬门槛）** → 13 embed → 14 部署 → 15 线上验证。

## 4. 新 ETF / 新指数自动发现规则（2026-08-15 固化）

**这是"列表页变化"的官方机制——判断新产品不再依赖用户 Excel：**

1. **新 ETF 发现**：Wind `search_funds` 检索近 30 天成立的红利类 ETF（名称含 红利/高股息/股东回报/央企回报）→ 对照 cnEtfData.json → 新标的自动补入（含跟踪指数/管理人/费率/规模/成立/上市日）。
2. **新指数纳入**：新 ETF 的跟踪指数若在 indexData.json 匹配不到 → 该指数为新指数，自动补入指数浏览器（基础信息 + 2023 年以来股息率历史 divHistory）。
3. **联动**：sync_excel.py 重建 cnEtfData 时保留 Wind 自动补充的标的（不删 Excel 外条目）；auto_sync_deploy.sh 在第二次 sync_excel 后挂载 sync_new_etf.py。
4. 示例：159083 嘉实中证红利低波动100ETF（08-05 成立/08-13 上市）按此规则补入；其跟踪指数 930955.CSI 已在浏览器，不重复添加。

## 5. 数据文件清单（data/）

| 文件 | 当前数量 | 生成脚本 | 主来源 | 更新方式 |
|------|---------|---------|--------|---------|
| indexData.json | 49 指数 | sync_excel.py + sync_new_etf | ②+① 混合 | 流水线 |
| cnEtfData.json | 89 ETF | sync_excel.py + sync_new_etf + sync_fund_divdate | ② Wind 快照（divDate/新 ETF 由 ③）| 流水线 |
| hkEtfData.json | 12 | sync_excel.py | ① 用户表优先 | 流水线 |
| etfData.json | 15 | sync_excel.py + sync_fund_divdate | ② Wind 快照 | 流水线 |
| fundData.json | 26 | sync_excel.py + sync_fund_divdate | ② Wind 快照 | 流水线 |
| moneyFundData.json | 43 | sync_excel.py + sync_money_fund | ② Wind 快照 | 流水线 |
| reitsData.json | 58 | sync_excel.py | ② Wind 快照 | 流水线 |
| assetData.json | 16 | sync_excel.py | ① 用户表（总表）| 流水线 |
| （Wind 化字段）| — | **sync_wind_fields.py** | Wind get_fund_financials / get_index_fundamentals | 周流水线第 9 步 |
| assetHistory.json | 12 序列 | sync_asset_macro.py + sync_reits_daily.py | ③ Wind MCP（REITs 日频独立脚本；重点50城租金率=中指季度报告）| 流水线 |
| yuebaoHistory.json | 994 条 | sync_yuebao_history.py | ③ Wind MCP | 流水线 |
| weeklyData.json | 4 期 | sync_weekly.py | digest HTML | 流水线 |
| backup/ + index.html 内嵌 | — | backup_db.py / embed_data.py | 本地 | 同步后自动 |

## 6. 数据来源明细（按数据域）

### 6.1 红利指数（indexData.json）
- ① 用户手动（受保护，不更新）：`publisher/listedDate/weight/weightExtra/components/market/currency/fullReturn/adjustCycle/adjustDate`。
- ③ Wind：`yield/yieldNum`（divHistory 最新值覆盖）、`divHistory`（日频，2023-01 起，只补不删）、`dailyChange/dailyDate`（独立脚本，存小数）。
- 新指数：sync_new_etf 自动补入（基础信息 + divHistory）。

### 6.2 A股红利ETF（cnEtfData.json）
- 基本信息（名称/管理人/费率/跟踪指数/上市日）：② Wind 快照「境内红利ETF」；**新 ETF 由 sync_new_etf 用 ③ Wind 自动补入**。
- `divDate`：③ Wind（sync_fund_divdate.py，措辞 `{code} 最近分红发放日期`，08-16 起；`最近分红情况`会偶发返回近1月统计表无发放日列），Wind 查不到留空 `—`。
- `divCount/size/shares/holders`：② 快照；空值 `—`。

### 6.3 港交所红利ETF（hkEtfData.json）
- `connect/trackCode/trackName`：① 用户手动（修订 Wind 缺失）；`divDate` 港股 Wind 不支持，保留 Excel 值；其余 ② 快照。

### 6.4 月月分红 ETF/场外基金（etfData/fundData.json）

**股息率口径（2026-08-16 用户确认）**：`yield/yieldNum` = **跟踪指数股息率**（trackCode → indexData.yieldNum 映射；trackCode 不在 49 指数时由 `_extend_yield_map` 从 Wind 查指数股息率兜底）；Wind「近12月分红收益率」（ETF 实际派息口径，≠指数股息率）另存 `divYieldNum` 备用，**禁止写入 yield**。
- 全部字段：② 快照「月月可分红ETF/月月可分红（场外）」。
- `divDate`：③ Wind（sync_fund_divdate，措辞 `{code} 最近分红发放日期`，08-16 起最稳定）。
- `taxRate`（港股红利税系数）：① 用户（名称智能识别 0.8/1.0）。

### 6.5 首页食息资产（assetData.json + assetHistory.json）
| 资产 | 列表快照来源 | 历史曲线来源 |
|------|-------------|-------------|
| 红利类（中证红利等 5 个）| ② Wind（divHistory 最新覆盖）| ③ Wind MCP |
| 5年期LPR | ① 用户（央行）| ③ Wind EDB |
| REITs 两类 | **③ Wind 日频中位数**（assetHistory 覆盖，Excel 不覆盖）| ③ Wind MCP（日频）|
| 重点50城租金率 | ① 用户（**中指研究院 50城租金房价比**，2026-08-15 确认权威；用户手动提供列表值）| ① 中指季度报告（**季度时点序列 2023Q1 起 14 点**，08-16 接入；每季度从中指云报告更新）；中原 6 城均值→备用 key「重点城市租金率(中原6城均值)」|
| 预定利率研究值 | ① 用户（保协）| ③ Wind EDB + 官方发布覆盖 |
| 3/5年期国债 | ④ iFind EDB（中债收益率，Wind EDB 无权限）| ④ iFind EDB 日频 |
| 整存整取 1/3年期 | ① 用户（工行官网核对）| ③ Wind EDB |
| 中证同业存单AAA | ② Wind | ③ Wind EDB |
| 天弘余额宝 | ② Wind（快照）+ ③ 实时覆盖 | ④ iFind 日频（Wind 限流）|

### 6.6 货币基金 / REITs / 周报
- 货币基金（moneyFundData）：② 快照「货币基金」+ sync_money_fund ③ 实时更新头部（含 yieldDate）。
- REITs（reitsData）：② 快照「REITs（产权类）/REITs（经营权类）」58 只。
- 周报（weeklyData）：`dividend-guide-weekly-digest.html` → sync_weekly.py 提取。

## 7. 数据更新机制

### 7.1 增量优先（2026-08-04 确立）
1. **增量优先**：已有数据只补"最后日期之后"的新段，旧数据保留，绝不重复全量（sync_div_history 增量、asset_macro 只刷新最新、yuebao 只补新段）。
2. **强制全量例外**：数据源口径变更/结构升级/数据损坏才允许 `SX_FULL_REFRESH=1` 全量重拉，执行前说明理由。
3. **已有数据不动**：前端已正常显示的字段，同步以"保留 + 补新"为默认。
4. **拉取前先读现有 JSON** 确定增量起点。
5. **失败不破坏**：拉取失败保留旧数据（不 pop）。

### 7.2 防回退机制（在线口径取代 Excel 旧值）
- **divDate**：sync_excel 之后必须重跑 `sync_fund_divdate.py all --force`。
- **余额宝 7 日年化**：build_asset_data 从 moneyFundData（含 yieldDate）覆盖；sync_money_fund 必须早于 sync_excel(2)。
- **国债**：`BOND_OVERRIDE` 从 assetHistory（iFind 中债收益率）取最新，Excel 储蓄国债旧值不覆盖。
- **REITs 两类**：sync_excel 特判从 assetHistory 最新日频中位数覆盖。
- **红利指数**：yield/date 从 divHistory 最新值覆盖（sync_excel 跑两次的顺序约束）。
- 通用原则：任何"Excel 旧口径 vs 在线新口径"冲突字段，加 `XXX_OVERRIDE` 优先在线。

### 7.3 本地数据库与离线保障
1. `data/*.json` = 本地数据库（断源后继续可用）。
2. `backup_db.py`：每次同步后快照 + `offline-db-<日期>.json` 离线归档 + 保留 30 天 + `--check` 校验；恢复 = 快照拷回 data/。
3. `embed_data.py`：刷新 index.html 内嵌数组（9 个，indexData 内嵌去 divHistory），data/*.json 加载失败时兜底；替换前备份、替换后 node 语法验证失败回滚。
4. 脚本类文件用 `cat heredoc` 或先备份再重写（坚果云写保护）；JSON 写入临时文件 + os.replace。

### 7.4 用户上传区 data/user/
- 用户上传 Excel 一律放 `data/user/`；`find_snapshot` 双目录搜索取修改时间最新。
- 数值字段由 AI 用 Wind MCP 更新到最新；产品/指数**列表**由 Excel 或 sync_new_etf 提供。
- 上传后标准流程：放文件 → 检查字段映射 → 跑流水线 → 备份/embed/部署。

### 7.5 目录结构规范
运行必需留根目录（index.html/vercel.json/package.json/auto_sync_deploy.sh/api/studio/blog/data/sync_*.py/backup_db.py/embed_data.py/extract_digests.js）；数据 JSON 在 data/；用户 Excel 在 data/user/；备份产物进 backup/；历史演示进 archive/；勿动 vercel.json 路由引用的目录；勿删脚本间互相引用（extract_digests.js 被 sync_weekly 引用）。

## 8. 数据源优先级

**优先使用万得（Wind）数据，不得已才取其他数据源。**

| 优先级 | 数据源 | 用途 |
|--------|--------|------|
| ① 首选 | Wind（快照 Excel + Wind MCP）| 所有基础数据、股息率历史、宏观资产、货币基金、指数/ETF/REITs 快照 |
| ② 备选 | iFind（EDB/基金端）| Wind 配额不足/超限时（国债中债收益率、余额宝日频历史）|
| ③ 备选 | 东财 mx-ds-mcp | 行情/板块补充 |
| ④ 权威 | 用户手动（飞书表/官方发布）| 指数公司、加权方式、发布日期、存款利率、LPR 等 |

**执行要求**：Wind 优先；Wind `QUOTA_ERROR` 才切 iFind/东财并记录"本次用 X 源替代"；已用其他源补的数据，Wind 配额可用时优先 Wind 重拉核对（`SX_FULL_REFRESH=1`）；用户表字段永远优先不被覆盖。

**已知替代（2026-08-05 确认）**：国债 3/5 年期 Wind EDB 无权限（S0059746）→ 保留 iFind；余额宝 Wind get_fund_kline 限流严重 → iFind 日频 1311 条保留；标普A股红利100 各源均无股息率 → 维持 `—`。

## 9. Wind 拉取经验清单（节约调用次数）

**A. 拉取前必查 3 件事**：① 先读现有 JSON 确认覆盖到哪（增量起点）；② 只拉缺口，全新数据才全量；③ 判断配额状态，刚大量用过优先 iFind 补数。

**B. 拉取中 4 技巧**：① 批量查询（BATCH_SIZE=3 一批查多个）；② 日期分段（**单次返回上限约 100 行**，按段拉取宁多勿截断；REITs 日频按每段 135 日历日）；③ 按需拉取（只拉页面展示字段）；④ 增量合并去重。

**C. 出错 3 纪律**：① `QUOTA_ERROR` 禁止原样重试，改备用源或等刷新；② QPS 限流等 3-5 秒可原样重试一次；③ 失败不破坏（保留旧数据）。

**D. 落地优化参考**：sync_div_history 增量（49 指数 ~588→~10 次）；sync_money_fund 只更新头部；sync_yuebao_history 按月分段去重；REITs 日频 58 只×10 段=580 次分两批断点续传（reits_daily_fetch.py，进度落盘可续传）。

**E. 2026-08-16 实测补充**：
- **divDate 查询措辞**：「{code} 最近分红发放日期」返回含「基金红利发放日」列，**最稳定**；「{code} 最近分红情况」会偶发返回近1月统计表（无发放日列）→ 导致 divDate 被误判"无数据"（08-16 曾致 fund 5 + etf 6 缺失，已单查修复并改措辞，见 sync_fund_divdate.py）。
- **dailyChange 全量重拉可能漏指数**（批量截断）：08-16 曾致 932584.CSI 停在 08-11；运行后核对更新数与指数总数（48/49），check_data 已加「全覆盖」检查拦截（见规范篇 5）。
- **Wind 配额用尽**：立即停止批量拉取，把断点写入记录篇（当前进度/缺失项/恢复步骤），配额刷新后从断点继续（所有脚本为增量逻辑，安全）。
- **基金/ETF 查询稳定搭档**：`get_fund_financials` 措辞 `{code} 最近分红发放日期`（保留 .OF 后缀）；港股 .HK 跳过保留原值。
- **单次查询字段数 ≤7 个**：超过则 Wind 返回"没找到数据"（08-16 实测，12 字段查询全部落空）；拆两次查询合并。
- **批量查询需限速**：连续同类查询（如"跟踪X的基金数量"）高频触发 Wind 限流返回空表 → 批次间 sleep ≥10 秒；失败批次可重跑（增量逻辑安全）。
- **列名不稳定**：「跟踪X的基金数量」有时带"指数"二字（跟踪指数X）→ 解析用正则 `^跟踪(指数)?` 兼容。
- **ETF 上市临时 N 前缀**：交易所对刚上市产品简称加"N"（new），上市数日后摘除；判断标准=网站简称带 N 而 Wind 证券简称不带 N → 摘除（fix_n_prefix）；摘除后 Excel 快照残留 N 不恢复（sync_excel 保护）。

## 10. 重点50城租金房价比 · 季度收集 SOP（2026-08-16 确立）

**目标**：维护 assetHistory.json「重点50城租金率」季度时点序列（3/6/9/12 月末，2023Q1 起，当前 14 点）。

**数据源（权威）**：中指研究院《中国住房租赁市场总结》系列报告（中指云 m.cih-index.com，标题形如《中指丨2026一季度中国住房租赁市场总结》《中指丨2026上半年中国住房租赁市场总结与展望》）。

**发布节奏**：一季度总结≈4 月下旬；上半年总结≈7 月上旬；三季度总结≈10 月下旬；年度总结≈12 月下旬。

**收集流程**：
1. 东财 mx_finance_search_news 检索：`中指 50城租金房价比 租售比 [年份] [一季度/上半年/三季度/全年]`，取报告原文数值；
2. WebFetch 中指云官方报告页交叉验证（如 m.cih-index.com/news/2026-07-09/54872546.html）；
3. 校验口径一致性：报告通常给出「较2023年初低点（1.98%）提高 X pct」→ 反推值须与原文数值一致（2.28%-0.30pct=1.98% ✓）；相邻时点互验（2024-09=2.12% 与 2025-09 报告"较去年同期+0.09pct→2.21%" ✓）；
4. 追加到 assetHistory.json「重点50城租金率」末尾 {date: 季度末(03-31/06-30/09-30/12-31), yield: 数值}；assetData 列表值由用户手动提供，脚本不动。

**口径铁律**：
- 统一现行口径：租金房价比 = 50城住宅平均租金×12 ÷ 二手住宅均价；
- 2023 年初低点 = 1.98%（多源确认）；所有「较低点提高 X pct」反推以 1.98% 为基准；
- ⚠️ 旧口径陷阱：早期报道存在旧口径（2024-01 报道 2023-12=1.80%），与现行 2.03% 相差 0.23pct，**禁止混用**；
- 官方未单独披露时点：用最近官方月度值替代并标注（2025-12 ← 11 月官方值 2.23%；2023-03 ← 2023 年初低点 1.98%，当年无季度系列）。

**保护**：sync_asset_macro.py 对「重点50城租金率」**保留现有值不覆盖**（同 REITs 模式，2026-08-16 起）；中原地产 6 城均值口径存备用 key「重点城市租金率(中原6城均值)」由 asset_macro 继续维护。

**前端**：assetHistory 运行时加载（不内嵌 embed）；详情页图表按序列点直接渲染（≥8 点正常显示），图例「租金回报率（租金房价比）」。

---

# 记录篇 · 更新执行记录（摘要）

| 日期 | 变更 | 验证/要点 |
|------|------|-----------|
| 08-04 | 基础规范确立：日期格式、`—` 占位、手动字段保护、footer/阴影/外框规则、增量优先、离线保障、目录规范 | — |
| 08-05 | 批量更新：divHistory 42 指数补到 08-05、dailyChange 首次补拉（修小数口径）、divDate Wind 拉取（fund 26/26、etf 15/15、cnEtf 50/88）、详情页 footer 三次修复（悬浮→全宽→移动端）、REITs 两指标曾置空 | footer 最终规则见规范篇 3.3 |
| 08-10 | 周任务未更新修复：任务顺序 bug（sync_excel×2）、divDate 被覆盖、dailyChange 缺失；sync_daily_change.py 固化；余额宝实时覆盖；系统梳理问题复盘 + 三层防复发机制 | 数据全部到 08-10 |
| 08-11 | 全面审查定稿（数据矩阵/三条铁律/14 步流程）；A6 divHistory 清空修复（占位+绝不删除）；余额宝 2023-08 前假平线修复（动态 180 天 + 前端 null）；REITs 现金流属性口径（产权 35/特许 23，月度中位数 4.75%/9.52%）；详情页遮罩；自定义域名 dividend.top 上线；REITs/港股ETF 详情页图表 | 线上 v168~v171 |
| 08-12 | REITs 数据升级为**日频**（每交易日 873 点/类，2023-01 起；58 只全量分两批 570 次调用断点续传）| 最新中位数 产权 4.89% / 特许 10.04%（08-11 收盘）|
| 08-15 | **新 ETF 自动发现规则固化**（sync_new_etf.py：Wind 检索近 30 天红利类 ETF → 自动补入；新指数自动纳入浏览器；sync_excel 保留自动发现标的）；159083 嘉实红利低波100 补入（88→89）；REITs 首页列表值更新到最新日频；"名义派息率（中位数）"口径统一（note/图例/desc）；风险提示加"特别提示："；文档精简重构 | 线上 v175~v180 |
| 08-15 | **指数浏览器主题新增“红利质量”“红利价值”标签**（在“红利低波”后；质量 2 只/价值 2 只），主题序列：纯红利/红利低波/红利质量/红利价值/央国企/银行 | 线上 v187 |
| 08-15 | **数据健康修复 + 租金率口径确认**：同业存单AAA未来日期修正（08-31→实际截止日，fetch_ncd 加自动修正）；build_asset_data 通用覆盖（整存整取/LPR/预定利率/同业存单 列表取 assetHistory 最新）；**重点50城租金率确认用中指研究院“50城租金房价比”口径（用户不定期手动提供，2.28% 与中指 2.26-2.28% 吻合），不被 assetHistory 中原口径覆盖**；divDate 恢复（fund 26/26、etf 15/15）| 线上 v188 |
| 08-17 | **移动端适配（用户需求 7 项）**：新增 mobile.css（233 行）+ mobile.js（124 行），仅 @media(max-width:767px) 与 768-1024 平板区间生效，桌面零影响；① asset 表卡片化（grid-template-areas：type/name/yield 上行 + date·note·src 下行 + fav）；② 全部 .index-table 系卡片化（指数 9 列/月月分红 7 列/ETF 5 列，股息率绝对定位右侧，涨跌幅背景色标签）；③ 导航横向滑动 + 下拉 position:fixed；④ 详情页 info-row 纵向、canvas 220px、slider 44px、安全区；⑤ 触控 36px + hover 取消（@media(hover:none)）；⑥ 平板仅微调字号/padding；⑦ 排序下拉框 select（mobile.js 注入 6 处，复用原排序函数）。验证：375px 视口 asset 卡片 areas、指数卡片、排序升降、重置、canvas 220px 全部生效 | 线上 v201 |
| 08-17 | **三个列表卡片间隙改页面浅灰（用户二次反馈仍白）**：根因=间隙在表格内部，.index-table 默认白底盖住了容器背景 → 容器内 .index-table 背景改为 #f4f2f7（与 body 一致），实测 tableBg=bodyBg=rgb(244,242,247)，卡片白底、间隙 10px 浅灰 | 线上 v251 |
| 08-17 | **筛选器结构重写 + 触屏 hover 修复（用户反馈两处）**：①滚动对齐：Safari sticky 兼容性问题 → 改为结构性分离（idxTagBarHtml/cnEtfTagBarHtml 生成 .index-tagbar-row > [.index-tagbar-group 固定72px + .index-tagbar-scroll 独立滚动区]），标题天然不滚；实测滚动 200px 后标题 left 不变、滑出标签 96px = 第二行 96px 对齐 ②触屏 hover 清底：@media(hover:none) 的 hover 原设 background:transparent（轻点后瞬时无底色）→ 改为 hover=各元素默认外观（index-tag hover 保持 #fff 白底、dropdown/main-nav hover 保持透明），点中才 active 蓝底白字；线上 css 已确认规则生效 | 线上 v250 |
| 08-17 | **筛选标题固定宽度（用户反馈 mobile 标签不对齐）**：标题 min-width 60 时"指数公司"等长标题（加粗）超宽 → 改为 width:72px + min-width:72px + box-sizing:border-box；实测指数浏览器 4 组 + 境内ETF 4 组标签起点全部 96px 严格对齐 | 线上 v249 |
| 08-17 | **筛选器 sticky 标题背景补全（用户反馈）**：原标题背景只覆盖文字高度，36px 高的标签滑过时白底框露出 → 标题 align-self:stretch + display:flex align-items:center，背景与标签等高同位（实测 groupH=36=tagH、滚动 200px 后标题仍固定 left:0），滑过标签完全被盖 | 线上 v247 |
| 08-17 | **移动端三处修正（用户反馈）**：①港交所/月月ETF/月月指数基金三列表容器加浅灰背景 #e8e8ee（白卡片之间显示浅灰间隙；这些列表移动端是表格卡片化，非 m-card）②筛选器标题（主题/调仓频率等）position:sticky + 页面底色盖住滚过的标签，只滚动标签（index/cn 两个筛选器）③一级菜单项全宽：根因主样式 .main-nav align-items:center 让列表 116px 不拉伸 → drawer 覆盖 align-items:stretch，一级项 width:100% → 选中蓝底（hover:none 媒体查询 #001aff）从左到右铺满 220px，与二级统一；实测 listW/itemW/subW 均 220 | 线上 v246 |
| 08-17 | **月月分红二级选中白字修复 + 箭头间距统一（用户反馈）**：①根因：pageIndex 隐藏后其 sub-page 残留 active，syncMenuActive 用 #pageIndex 查询拿到 subBrowser → 月月分红 sub 匹配不上 → 无选中态；改为基于当前 .page.active 查 sub-page → ETF/指数基金正确白字（实测 activePage=pageMonthly + ETF 白字）②间距：一级文字→右箭头 20px（gap 6 + padding 8）、二级箭头→文字 0px，统一为 8px（一级 gap:0 + padding 8，二级文字列 32）；实测 l1=8/l2=8 | 线上 v245 |
| 08-17 | **菜单选中项白字（用户 Safari 实测：蓝底去不掉 → 用户方案白字）**：一级/二级 active 文字改为纯白 #fff（蓝底白字可读），非选中保持 #111；实测 active color rgb(255,255,255) 700、非选中 rgb(17,17,17) 400 | 线上 v243 |
| 08-17 | **汉堡菜单三处修正（用户 Safari 实测反馈）**：①二级与一级字号/颜色统一（全部 15px #111）②选中态**仅加粗**（700、颜色不变），消除 Safari 蓝色背景——加 -webkit-tap-highlight-color:transparent + :active/:focus 背景 none + 删除残留的 active color:#000 旧规则 ③抽屉宽度 280→220px（满足展示即可）；验证：一级/二级 fs/color 全一致、active fw700 无背景、tap 透明、220px | 线上 v241 |
| 08-17 | **汉堡菜单移到右侧 + 选中粗体规则（用户要求）**：①抽屉 left→right（translateX(100%) 从右滑入，实测贴右缘 633）②选中项粗体 700、非选中/取消选中恢复 400（修复：移动端二级 dropdown-item 已移出 #navIndex，主脚本 active 不更新 → mobile.js 加 syncMenuActive（打开菜单时按当前 sub-page 同步）+ 点击时更新 active，实测切换后旧项恢复 400、重开菜单状态正确） | 线上 v239 |
| 08-17 | **汉堡菜单重做为左侧滑出抽屉（用户最终要求）**：①左侧 280px 抽屉（translateX -100%→0，非全屏/非居中）②背景遮罩 rgba(15,18,32,0.45) 压暗、点击关闭 ③内容全部左对齐、white-space:nowrap 横向单行（消除单字竖排），项高 44px 行距适度 ④带子层级的一级项右侧显示 > 箭头（.has-sub::after）⑤5 项：食息数据/食息资讯/红利指数/月月分红/食息之路 ⑥二级层保留（抽屉内从右滑入：返回+分组标题+子项）；验证：280px、遮罩显隐、箭头、子项切页、遮罩点击关闭全部正确；css/js v8 | 线上 v235 |
| 08-17 | **二级菜单改为独立第二层全屏页面（用户截图指出与 elevenreader 不一致）**：一级列表（食息数据/资讯/红利指数/月月分红/食息之路）点击带子项的一级项（红利指数/月月分红）→ 右侧滑入**第二层全屏**（返回 ← 按钮 + 标题 + 灰色分组标题 + 子项列表，仿 elevenreader Discover 二级层）；子项点击切页+关闭、返回回一级、✕ 关整个菜单、黑白灰无装饰不变；踩坑：取标题时必须先移走 dropdown 子项否则 textContent 混入子项文本；css/js 版本号 v7 | 线上 v234 |
| 08-17 | **菜单黑白化（用户要求）**：①一级黑色 #111（15px/500）、二级灰色 #8e8e93（14px/400），靠颜色区分层级 ②去除所有彩色装饰：圆角胶囊(padding/radius/hover 背景)全部移除，纯文字、选中态用**加粗**表示（不再用蓝色）③顶部 logo 去掉多余"息"字改为"食息指南"；保留右侧滑入+垂直居中（上下 102px 对称）；验证：颜色/加粗/padding0/radius0/背景透明/居中全部正确 | 线上 v232 |
| 08-17 | **汉堡菜单按 elevenreader 真实代码重写（用户要求直接看源码抄）**：从其 dialog class 提取关键实现——①inset-y-0 right-0 + slide-in-from-right：**右侧滑入全屏面板**（transform translateX 100%→0，400ms）②header h-16 + 右上角 **svg ✕ 图标关闭按钮**（rounded-full）③nav justify-center：菜单**垂直居中**（实测上下间距 132px 对称）④菜单项 li ml-[-12px] + a h-9 rounded-full px-3 text-sm：**圆角胶囊**（80×36px、14px、hover 浅灰 rgba(16,24,40,0.04)）⑤ul space-y-3：gap 12px 等距；无 emoji/无边框/选中蓝 #001AFF；踩坑：主样式 height:100% 污染菜单项高度（改 height:auto）、width 用 fit-content、padding 对称、css 版本号 v6 | 线上 v231 |
| 08-17 | **汉堡菜单改为全屏覆盖层（用户指定参考 elevenreader.io）**：点汉堡→全屏白底覆盖（z-999、淡入淡出），顶部 logo"息 食息指南"+ 右上角 ✕ 关闭；菜单项竖排纯文字（15px、无 emoji、无背景、无边框、无符号）、等距（gap 6px）；二级平铺与一级一致；选中蓝色；去掉原遮罩/窄抽屉方案；踩坑：菜单项包 .m-nav-list 后 dropdown 移动的 insertBefore 父节点错误抛错中断 emoji 剥离（改 list 作父）；css/js 版本号升 v5；验证：全屏 633x652、初始 opacity0、✕ 关闭、subEtf 切换、body 滚动恢复 | 线上 v226 |
| 08-17 | **菜单"敲文字"等距版（用户最终标准）**：①二级项加"· "前缀（示例式）②dropdown 由 mobile.js 移到 nav 层与一级平级（不再撑高一级项）③统一 line-height:25px、去掉一级项 2px 透明边框、移除 ▼ 箭头 → 实测 10 行行高全部 49px、行距全部 49px 完全等距；文本与用户示例逐字一致（食息数据/食息资讯/红利指数/· 红利指数浏览器/· 境内红利ETF/· 港交所红利ETF/月月分红/· ETF/· 指数基金/食息之路）；选中蓝色、无 hover、无背景不变 | 线上 v224 |
| 08-17 | **mobile 菜单彻底去样式（用户要求"不要保留任何样式"）**：dropdown 容器清掉背景/box-shadow/min-width/毛玻璃（外框消除）；hover 全部无效化（一级 color:inherit、二级 background:none+color:inherit），**仅选中项显示蓝色 #001AFF**；一级/二级上下 padding 统一 12px、字号 15px；验证：dropdown 全透明无阴影、hover 无变色（蓝色来自 active）、点击切页正常 | 线上 v221 |
| 08-17 | **抽屉菜单终版简化（用户要求）**：①一级菜单去掉全部 emoji（📊📬📈💰📖）②二级菜单与一级样式完全一致（无背景/无•符号/无缩进容器感/同 15px 字号），仅选中时主色蓝 #001AFF ③抽屉宽度改 width:fit-content（340→220px 跟随文字，min 200/max 80vw）；验证：文字起点一级=二级=433 完全对齐、无 emoji 残留、二级点击切页+蓝色选中正常 | 线上 v220 |
| 08-17 | **抽屉菜单"并列"布局修复（用户强调）**：两层真 bug——①.main-nav-item 主样式 display:flex 导致 dropdown 作为 flex 子项排到一级项右侧（"一级在二级左边"）；②nav 继承 align-items:center 使宽度不同的项水平居中错位；修复=一级项 display:block + nav align-items:stretch，一级/二级左边缘完全对齐（实测一级 x=293、二级 x=313、宽 340/300 占满），子菜单直接换行在下方，emoji/• 各 18px 占位使文字列对齐 | 线上 v218 |
| 08-17 | **mobile 菜单简化（用户要求）**：①去掉抽屉顶部品牌区（网站名/描述）②二级菜单去掉开头 emoji（🔍🏛️🇭🇰📊📈，仅 mobile 注入时剥离，桌面保留）③一级/二级并列（同 padding-left 20px），二级小字 12.5px + 无序列表符号 •，行高收紧；验证：无品牌区、子项无 emoji、• 符号生效 | 线上 v215 |
| 08-17 | **全站去除浅灰描边（用户要求）**：除可视化图表旁时间周期（.detail-chart-select）、滑块手柄、红色警示框、博客内容表格、表头蓝底、顶栏分隔线外，所有浅灰外框/行线移除（asset/intro/index-tag/表格行线/weekly/fund/knowledge/fav/detail-main-card/详情分区线/blog/m-card/抽屉边线/排序下拉等，共 27 处）；卡区分靠白底+阴影；验证：assetTable/m-card/detailMain/intro 边框 0px，时间周期/警示框 1px 保留 | 线上 v214 |
| 08-17 | **抽屉二级菜单平铺化（用户要求）**：二级选项不再点击展开，直接平铺（缩进 36px、13px 小字、浅色底），箭头 ▼ 隐藏；去掉独立"🏠 首页"项（默认食息数据即首页，品牌区保留点击回食息数据）；点击任意项（顶层或子项）切页+收起；验证：红利指数 3 子项/月月分红 2 子项平铺显示、子项点击 subEtf+收起正常 | 线上 v213 |
| 08-17 | **汉堡抽屉被遮罩盖住 bug 修复（用户反馈"完全看不到选项"）**：根因=抽屉困在 .top-bar(z-index 60) 层叠上下文内，而遮罩挂 body(z-index 55/1140) → 遮罩盖住整个顶栏（含抽屉）；修复=**抽屉由 mobile.js 移到 body 顶层**挂 .m-nav-drawer（z-index 1000 > 遮罩 980），用 nav._btn/btn._nav 双向引用维持开合；elementFromPoint 逐项验证 6 项全部可点、下拉展开/切页/关闭全正常 | 线上 v212 |
| 08-17 | **筛选器标签不换行横向滑动（用户要求）**：境内红利ETF/红利指数浏览器 的 .index-tagbar-row 移动端改 flex-wrap:nowrap + overflow-x:auto（隐藏滚动条），标签 flex-shrink:0；多标签维度（基金公司等）左右滑动，不再换行显得选项多；桌面保持换行不变 | 线上 v210 |
| 08-17 | **汉堡菜单改右侧抽屉（用户要求）**：点汉堡→菜单从右侧滑出（80vw/340px，transform 动画）+ 半透明遮罩（点击关闭、防滚动穿透）；抽屉内新增品牌区（食息指南，点击回首页）和 **🏠 首页**选项；完整展示 6 项（首页/食息数据/资讯/红利指数/月月分红/食息之路），子菜单抽屉内静态展开；验证：右对齐、遮罩显隐、首页切换、滚动恢复全部正常 | 线上 v209 |
| 08-17 | **移动端独立渲染层（中间态，用户要求体验）**：mobile.js 新增 renderAssetTableMobile/renderIndicesMobile/renderCnEtfMobile——移动端不再"表格+CSS 改卡片"，而是独立函数直接生成卡片 HTML；覆写 window.renderXxx 分流 + MutationObserver 兜底（主脚本词法绑定直接调原函数时替换为移动版）；踩坑记录：①const 声明的数据（assetData 等）不挂 window，需直接引用全局 ②listNote 是 renderAssetTable 嵌套函数（非全局），移动层内联同款逻辑 ③函数声明词法绑定无法覆写，靠 observer 兜底 ④resize 重入导致排序框重复注入，buildSelect 加去重；验证：asset 16 卡/indices 49 卡（港股筛选 15）/cnEtf 89 卡，排序/筛选/详情/下拉保持全部正常 | 线上 v208 |
| 08-17 | **移动端汉堡菜单（用户要求）**：tab 导航默认折叠为汉堡按钮（三横线→叉），点开为固定面板（竖排 5 项）；带下拉的项点击展开子菜单（菜单保持），点下拉项切页+收起；点击外部/普通项自动收起；捕获阶段监听规避主脚本 stopPropagation；踩坑：profileBtn 为 top-bar 孙节点导致 bar.insertBefore 抛错（整段注入中断），改 prof.parentNode.insertBefore + try-catch 隔离；详情页 6 个 top-bar 同步注入；mobile.css/js 引用加 ?v=3 防缓存 | 线上 v206 |
| 08-17 | **移动端排序工具位置调整（用户要求）**：红利指数浏览器/境内红利ETF 的排序下拉框改到**筛选器与列表之间**（index: tagbar→排序→列表；cnEtf: tagbar→计数→排序→列表）；mobile.js 用 MutationObserver 在 render 清空容器后自动重建 select 并恢复当前排序值；无筛选器的板块（资产/港交所/月月分红）保持容器前原位置 | 线上 v204 |
| 08-17 | **Safari 交互修复（用户反馈下拉/时间选项无效）**：根因=顶层 `localStorage.getItem` 在 Safari 隐私模式抛 SecurityError → 主脚本中断 → 后续 addEventListener（下拉项/图表时间 select/tab）全部未绑定（详情页靠内联 onclick 仍可开，故症状为"点击没反应"）；修复=①favorites 初始化与 setItem 加 try-catch 降级内存数组 ②新增 interaction-fix.js（body 开头加载，document 级事件委托：下拉项/sub 切换/时间 select 兜底，__mainReady 标志判断主脚本是否正常）③触屏下拉：点击 nav 切换 dropdown-open（不再依赖 :hover，iPhone Safari 可用）；验证：下拉展开 3 项、切 subHkEtf、近 3 年 rangePct=[16.9,100] 生效 | 线上 v203 |
| 08-16 | **"每月千元分红需总投入"计算错误修复（用户发现中证红利潜力 0.34 万）**：根因=yieldNum 约定为**百分数**（4.2756=4.28%，sync_excel 股息率校正写入）但前端公式按小数计算（缺 /100）→ 差 100 倍；昨天 etf/fund yieldNum 统一百分数后同样受影响；修复=前端 3 处公式加 /100（指数详情/ETF 详情/场外详情），check_data 加 yieldNum 单位校验（0.5~30 百分数口径）；验证：红利潜力 34.12 万、513630 28.01 万、022448 52.91 万 | 线上 v199 |
| 08-16 | **股息率口径全面排查（用户追问）**：① indexData 49 指数 yieldNum 与 divHistory 全一致 ✅；② etfData/fundData 41 只已映射全=指数股息率 ✅；③ 未映射 9 只（trackCode 不在 49 指数）发现异常值（513530=-1.51%、022448=15.92%、023919=-5.81%）→ 逐只从 Wind 查跟踪指数股息率修正（513530→5.20%、022448→2.27%、023919→4.07% 等）；④ sync_wind_fields.py 加 _extend_yield_map 兜底（未映射 trackCode 自动查指数股息率）；⑤ assetData 红利指数 3 只与 indexData 一致 ✅ | 线上 v198 |
| 08-16 | **股息率口径修正（用户发现 513630 显示 3.43% vs 万得指数 5.35%）**：根因=前日 Wind 化把 etfData/fundData 的 yield 设为“近12月分红收益率”（ETF 实际分红，新 ETF 分红少导致远低于指数股息率）；修正=yield/yieldNum 改为**跟踪指数股息率**（trackCode→indexData.yieldNum 映射，513630→5.35% 与万得一致），近12月分红收益率存 divYieldNum 备用；sync_wind_fields.py 已固化 | 线上 v197 |
| 08-16 | **上市 N 前缀动态处理（用户要求）**：ETF 简称的上市临时“N”（new）会随上市摘除；sync_wind_fields.py 新增 fix_n_prefix（每周 Wind 化时若网站简称带 N 而 Wind 证券简称不带则摘除）；sync_excel.py 加 N 前缀保护（Excel 快照残留 N 不恢复）；561450 已摘（N红利低波50ETF华泰柏瑞→红利低波50ETF华泰柏瑞）| 线上 v196 |
| 08-16 | **字段级 Wind 化（用户 7 项指示）**：新增 sync_wind_fields.py，① indexData.fundCount 挂钩产品数随 Wind（49 个）；② cnEtfData 成立日/上市日/费率/2026分红次数/规模/份额/持有人数（88/89）；③④ etfData+fundData 除产品列表外全字段 Wind 化（15+26）；⑤⑥ moneyFundData/reitsData 保持现状；⑦ hkEtfData 除列表/名称外字段 Wind 化（12）。流水线加第 9 步；经验：Wind 查询字段≤7 个/次否则返回空，批量限流需 sleep，列名“跟踪指数X”/“跟踪X”不稳定需正则 | 线上 v195 |
| 08-16 | **本年涨跌幅 yrChange 修复**：此前 yrChange 仅来自 Excel 快照（滞后 1-2pct）；sync_daily_change.py 新增 Wind 实时拉取（get_index_fundamentals 批量“年初至今涨跌幅”，8 个/批，41/49 更新，标普A股红利100 无数据）；sync_excel.py 加 yrChange 保护（Wind 值不被 Excel 覆盖）；前端同步（红利质量 8.02%、中证红利质量 -3.58%、消费红利 -17.54%）| 线上 v194 |
| 08-15 | **同业存单AAA 标的切换 931059.CSI + 文案定稿**：标的指数 931815→**931059（中证同业存单AAA指数）**，数据 1.41%@08-15；利率说明“中证同业存单AAA指数月度年化收益率”、指标详情“中证同业存单AAA指数（931059.CSI）月度年化收益率。…”（用户定稿）；首页列表简版“同业存单指数年化收益率”不变 | 线上 v191-192 |
| 08-15 | **同业存单AAA 指标文案按 Wind 口径重写**：note 改为“中证同业存单0-6个月AAA指数月度年化收益率”（详情页完整版；首页列表用简版“同业存单指数年化收益率”，前端 listNote 特判）（NOTE_OVERRIDE，Excel 备注“今年以来”不准确）；desc 更新为 Wind 931815.CSI 口径说明；图例“月度年化收益率”；divDate 恢复 26/26、15/15 | 线上 v189 |
| 08-15 | **红利指数浏览器新增“调仓频率”筛选项**：在“指数公司”之前，基于 adjustCycle 字段（季度 5/半年 21/一年 23），展示为 季度/半年/一年，可与主题/市场/指数公司组合过滤。验证：季度 5 只、一年 23 只、一年+中证指数 21 只、清除恢复 49 | 线上 v185 |
| 08-15 | **境内红利ETF 子页面四维筛选**：仿指数浏览器 tagbar，主题（**红利/红利低波/红利质量/红利价值/股东回报/其他**，按跟踪指数名互斥分类，优先级 低波>质量>价值>股东回报>红利>其他；**港股通红利/高股息均归入“红利”**——市场维度已按 A股/港股区分，主题不区分地域）+ 市场（A股/港股）+ 管理费率三档（0.15%/0.20-0.45%/0.50%，08-15 合并中间两档）+ 基金公司（**按该公司全部红利ETF加总规模降序**；简称最短化，如 摩根）四维筛选；管理费率列可点击排序（feeNum）；筛选结果计数。验证：红利 42/低波 35/质量 8/价值 1/股东回报 3/其他 0；叠加 0.15% 后 11 只；公司首标签华泰柏瑞（652亿） | 线上 v183 |
| 08-15 | **定期任务与流水线升级**：sync_reits_daily.py 固化（REITs 日频增量：data/reitsDaily.json 缓存 + 每只增量段重算中位数，asset_macro 不再覆盖 REITs）；auto_sync_deploy.sh 挂载 sync_reits_daily + sync_new_etf；「食息指南网站数据更新」「食息周报素材筛选」两个定时任务 prompt 同步更新（新增日频/新 ETF 步骤与联动说明）；REITs 数据增量到 08-14（产权 4.91% / 特许 10.66%）| 线上 v181 |
# 附录 A · 问题清单（已解决，防复发机制）

| # | 问题 | 根因 | 解决/防复发 |
|---|------|------|-------------|
| 1 | 同业存单标的指数错误（用 931815 0-6个月AAA）| 取数时误选 | 用户确认 **931059.CSI**；sync_asset_macro 固化；文案定稿 |
| 2 | 同业存单 note"今年以来"不准确 | Excel 备注误导 | NOTE_OVERRIDE 强制；前端 listNote 简版/详情完整版 |
| 3 | divDate 被 sync_excel 重建覆盖（反复）| Excel 快照无/旧 divDate | 流水线顺序：fund_divdate 在 sync_excel(2) 之后；备份合并恢复 |
| 4 | sync_asset_macro fetch_ncd 缺 import datetime | 局部 import 模式遗漏 | fetch_ncd 内补 `import datetime`（文件风格为函数内 import）|
| 5 | yrChange（本年涨跌幅）滞后 1-2pct | 仅来自 Excel 快照 | sync_daily_change 加 Wind 实时拉取 + sync_excel 保护 |
| 6 | fundCount 批量解析错位/漏 | Wind 列名"跟踪指数X"/"跟踪X"不稳定 | 正则 `^跟踪(指数)?` 解析；每批 sleep 10 秒防限流 |
| 7 | Wind 查询 12 字段返回"没找到数据" | 单次查询字段过多 | **≤7 字段/次**，拆两次查询合并 |
| 8 | ETF 股息率显示 3.43% vs 万得指数 5.35% | 误用"近12月分红收益率"（ETF 实际派息）| yield=**跟踪指数股息率**（trackCode 映射）；近12月分红收益率存 divYieldNum 备用 |
| 9 | 未映射 trackCode 出现负值/15.92% 异常 | 兜底口径缺失 | `_extend_yield_map`：未映射 trackCode 自动查指数股息率 |
| 10 | ETF 简称"N"前缀过期残留 | 上市临时标记未动态摘除 | fix_n_prefix（Wind 简称无 N 则摘）+ sync_excel 保护不恢复 |
| 11 | dailyChange 批量截断漏指数（932584 停 08-11）| 批量返回上限 | check_data 全覆盖检查（更新数 vs 指数总数）拦截 |
| 12 | divDate 查询偶发返回近1月统计表（误判无数据）| 查询措辞不稳 | 固定措辞「最近分红发放日期」最稳定 |
| 13 | 同业存单未来日期（08-31）| Wind 返回月内未来截止日 | fetch_ncd 自动修正为实际截止日 |
| 14 | 重点50城租金率旧口径（1.80% vs 现行 2.03%）| 早期报道口径不同 | 铁律：租金房价比=50城租金×12÷均价；2023 低点 1.98% 基准；旧口径禁止混用 |
| 15 | 场外基金每份分红金额口径存疑（A/C 拆分）| Wind 分红总额口径与 Excel 差异大 | **保留 Excel 原值不覆盖**（annualDivAmt/monthlyDivAmt/divTotalAmt/cumDiv）|
| 16 | 浏览器缓存显示旧数据（3.43% 误判未修复）| CDN/浏览器缓存 | 线上验证用 `?t=时间戳` 强刷 |
| 18 | Safari（隐私模式）下拉菜单/图表时间选项点击无效 | 顶层 localStorage 访问抛 SecurityError 中断主脚本，其后所有 addEventListener 未绑定 | favorites 加 try-catch 降级；interaction-fix.js 事件委托兜底；触屏下拉 dropdown-open 不依赖 hover |
| 17 | "每月千元分红需总投入"差 100 倍（红利潜力 0.34 vs 应 34.12）| **yieldNum 单位约定为百分数**（4.2756=4.28%）但前端公式按小数计算（缺 /100）| 前端 3 处公式统一加 /100；check_data 加 yieldNum 单位校验（0.5~30）防复发；公式=1.2÷(yieldNum/100×税后系数) 万元 |

# 附录 B · 定期更新内容总清单

## B1. 每周六 15:00「食息指南网站数据更新」定时任务（15 步流水线）
| 步骤 | 脚本 | 更新内容 |
|------|------|---------|
| 1/7 | sync_excel.py | Excel 快照重建（assetData/indexData/cnEtf/hkEtf/etf/fund/moneyFund/reits）|
| 2 | sync_div_history + fix_laggard | 指数股息率日频补最新交易日（49 指数）|
| 3 | sync_daily_change | 每日涨跌幅 + **本年涨跌幅 yrChange**（Wind 实时）|
| 4 | sync_money_fund | 货基头部实时 7 日年化 |
| 5 | sync_yuebao_history | 余额宝日频历史（动态 180 天）|
| 6 | sync_asset_macro | 宏观资产历史（LPR/国债/存款/预定利率/同业存单 931059/租金率保留）|
| 6.5 | sync_reits_daily | REITs 日频增量（产权/特许中位数）|
| 7 | sync_excel(2) | 重建（assetData 取最新 divHistory）|
| 7.5 | sync_new_etf | 新 ETF/新指数自动发现（近 30 天红利类）|
| 8 | sync_fund_divdate | 恢复最近分红日期（fund/etf/cnEtf）|
| **9** | **sync_wind_fields** | **字段级 Wind 化：fundCount / ETF 成立·上市·费率·规模·份额·持有人·分红次数 / 月月分红全字段 / 股息率=指数股息率 / N 前缀摘除** |
| 10-11 | sync_weekly → backup_db | 周报、离线备份 |
| 12-15 | check_data（硬门槛）→ embed → 部署 → 线上验证 | 验证含附录 A 问题点抽查 |

## B2. 季度（4/7/10/12 月下旬）：重点50城租金率 SOP（见流程篇 §10）
每季度从中指云报告更新「重点50城租金率」季度时点值（最新 2023Q1 起 14 点），assetData 列表值由用户提供。

## B3. 不定期（用户指令）：
- 月月分红清单变更（哪些 ETF/场外算"月月分红"——业务判断，用户维护）
- 港交所 ETF 互联互通/跟踪指数修订（用户飞书表）
- 租金率列表新值

## B4. 每日若手动同步（非周末）：跑 B1 的步骤 2-6.5 + 8 + 9 即可（增量安全）。
| 08-15 | **每周同步执行中断（Wind 配额用尽）**：进度至 ⑪ sync_new_etf（无新 ETF）全部完成，⑫ sync_fund_divdate 全量恢复 divDate 中途遇 Wind 配额用尽被停止；数据本地已全部更新至 08-14（divHistory 48 指数、dailyChange、余额宝 0.82%、yuebaoHistory 997 条、assetHistory、REITs 日频 产权 4.91%/特许 10.66%、assetData 5 红利指数均 08-14）；**⚠️ fundData/etfData/cnEtfData 的 divDate 已被 sync_excel(2) 覆盖待恢复；未部署（线上保持上一版）**；明日（08-16，周日，最新交易日仍 08-14）配额刷新后从 ⑫ 继续：sync_fund_divdate all --force → ⑬weekly → ⑭backup → ⑮check_data（硬门槛）→ ⑯embed → ⑰部署 → ⑱验证；或直接重跑完整任务（各脚本均为增量逻辑，安全）| 未部署 |
| 08-16 | **每周同步完成（接续 08-15 中断）**：divDate 恢复 fund 26/26、etf 15/15、cnEtf 51/89；**sync_fund_divdate 措辞改为「{code} 最近分红发放日期」**（「最近分红情况」会偶发返回近1月统计表，导致 11 个标的 divDate 缺失，已用新措辞逐个单查修复）；weekly 5 期、backup、check_data 全部 ✅、embed 9 数组、部署 dividend.top 成功；REITs 日频 产权 4.91% / 特许 10.66% @ 08-14（876 点/类）| 线上已验证 08-14 |
| 08-16 | **check_data 增强 + 全量排查**：新增 4 项全覆盖检查——①divHistory 全覆盖（有历史指数最后日期==最新交易日）②dailyChange 全覆盖（有 divHistory 指数 dailyDate==最新，932584 滞后 bug 教训）③assetHistory 日频序列最新日期（国债×2/余额宝/REITs×2，≤3天）④reitsDaily 全覆盖（58 只，允许 ≤5 只停牌滞后）；已反向测试验证可捕获滞后；全量排查结论：仅 LPR（07-20，每月20日公布）与重点50城租金率（用户手动不定期提供）滞后，属正常节奏非 bug；其余 divHistory/dailyChange/assetData/assetHistory/余额宝/yuebao/REITs 全部到 08-14 | check_data 全部 ✅ |
| 08-16 | **重点50城租金率升级为中指季度序列**：将 assetHistory 原「重点50城租金率」（中原地产口径 35 点）改为**中指研究院季度时点序列 14 点**（2023Q1=1.98% → 2026Q2=2.28%，3/6/9/12 月末，口径=租金×12÷二手房价），与列表值 2.28% 口径统一；中原口径改名「重点城市租金率(中原6城均值)」备用保留；sync_asset_macro.py 对重点50城租金率**保留现有值不覆盖**（同 REITs 模式）；每季度从中指云《中国住房租赁市场总结》系列报告更新（一季度约 4 月下旬/上半年约 7 月上旬/三季度约 10 月下旬/年度约 12 月下旬），数据来源含东财 mx_finance_search_news 检索 + 中指云官网 WebFetch 交叉验证 | 已部署 dividend.top 线上验证 14 点 |
| 08-16 | **数据收集方法论固化**：对照文档新增「第 10 节 重点50城租金房价比季度收集 SOP」（中指云报告检索/抓取/口径校验/写入流程，含旧口径陷阱与未披露时点替代规则）与「Wind 经验清单 E」（divDate 措辞、dailyChange 截断核对、配额用尽断点记录）；今后按此方法执行 | 见流程篇 9E / 10 |
| 08-22 | **每周同步（按 2026-08-15 用户最新指令执行）**：执行顺序定稿 6 要点（sync_excel×2 / fund_divdate 紧随 excel(2) / money_fund 先于 excel(2) / reits_daily 紧随 asset_macro / new_etf 在 excel(2) 之后 / check_data 硬门槛）；**本轮用户指令（19 步）未含 sync_wind_fields 步骤**——冲突以用户最新指令为准（B1 第 9 步与 auto_sync_deploy.sh 保留，后续轮次以当轮指令为准） | **结果**：divHistory 48 指数到 08-21（标普A股红利100 无数据源）；995127 单查补齐；dailyChange 48 指数 08-21；余额宝 0.81%@08-21（yuebao 1002 条）；REITs 产权 4.90%/特许 10.74%@08-21（881 点/类，58 只全覆盖）；assetData 5 红利指数+REITs+余额宝均 08-21；divDate fund 26/26·etf 15/15·cnEtf 51/89；weekly 6 期；**修复**：fix_laggard TARGET_DATE 写死 07-31→动态最近工作日；sync_excel 加 etf/fund yieldNum 口径校正（Excel 股息率列全小数→百分数+trackCode 映射，41 只修复）；check_data 全部 ✅；部署成功（18s）线上已验证 |

---

*本文件为网站更新与数据管理的唯一权威对照文档，随网站演进持续维护。规范冲突时以本文件最新规范为准。*


---

## Mobile 版本 CSS 样式要求（2026-08-17 汇总）

> 以下为移动端（≤767px）样式规范，全部经 iPhone Safari 实测反馈后定稿。桌面端不受影响。
> 相关实现文件：`mobile.css`、`mobile.js`（移动端独立渲染层）。

### ⛔ 修改纪律（2026-08-17 用户严格立规，必须遵守）

1. **mobile.css 的所有规则必须写在 `@media (max-width: 767px)` 媒体查询内**，严禁在媒体查询外新增规则（否则会污染 PC 端）。
2. **严禁为适配移动端去修改 index.html / mobile.js 里的全局生成函数**（如 idxTagBarHtml 等）——这些函数 PC 端共用，改了会破坏 PC 版。如需结构变化：优先用 CSS 媒体查询；非改结构不可时，必须同时补 PC 端样式并在 PC 端验证。
3. **每次改完 mobile 相关样式，必须 PC + 移动两端都实测验证**，再部署。
4. 本次教训（2026-08-17）：改 idxTagBarHtml 结构（标题+滚动区分离）时只给移动端写了 CSS，PC 端标签失去间距（标签进入新容器 .index-tagbar-scroll，PC 无 gap）→ 已补 `.index-tagbar-scroll { display:flex; flex-wrap:wrap; gap:6px 10px }` 到主样式修复。

### 一、汉堡菜单（全局导航）

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | **右侧滑出抽屉**，只占右侧一部分宽度（220px），背景遮罩半透明黑 rgba(15,18,32,0.45)，点击遮罩关闭 | `.m-nav-drawer`：`right:0; width:220px; translateX(100%) 滑入`；`.m-nav-mask` 点击关闭 |
| 2 | 5 个一级项：**文字横向单行**（禁止竖排）、**左对齐**、44px 行高、15px、#111、无装饰（无胶囊/无彩色） | `.m-nav-list .main-nav-item`：`white-space:nowrap; text-align:left; height:44px` |
| 3 | **子层级右侧箭头**：svg 线条 chevron（非字符">"），16px、#999、与文字间距 8px | `.m-nav-arrow` 内 svg（stroke-width 1.5），间距由 gap:0 + padding-left:8px 保证 |
| 4 | **二级菜单**：返回按钮（svg 左箭头）+ 标题 + 子项列表；无灰色分组小字；子项点击直接进页面 | `.m-nav-sub` 层，标题与子项文字左对齐同一列 |
| 5 | 二级返回箭头**悬挂在文字左侧**（右缘贴文字起点），左侧留白 8px | `.m-nav-sub-back`：absolute left:8px，箭头 flex-start；文字列 padding-left 32px |
| 6 | 一/二级**字号颜色统一**：全部 15px、#111；选中项仅加粗 | `.m-nav-sub .dropdown-item` 与一级同款 |
| 7 | **两个方向箭头大小颜色一致**：16px、#999、线宽 1.5 | 返回箭头与一级右箭头同规格 |
| 8 | **选中态**：仅加粗（700）+ 纯蓝底（触屏 #001aff）+ 白字；取消选中恢复正常；选中蓝底**从左到右铺满全宽**（一级/二级统一） | 一级项 `width:100%` + drawer `align-items:stretch`（覆盖主样式 center，否则列表只有内容宽）；`@media(hover:none)` 中 `.main-nav-item.active/.dropdown-item.active{background:#001aff;color:#fff}` |
| 9 | 选中状态**实时同步**：打开菜单时按当前所在页面高亮（一级项由主脚本管理；二级项由 mobile.js `syncMenuActive` 基于 **当前激活 .page** 的 .sub-page.active 匹配 data-sub） | 注意：pageIndex 隐藏后其 sub-page 会残留 active，必须查 `.page.active` 内的 |
| 10 | 禁止 Safari 点击蓝色高亮残留：`-webkit-tap-highlight-color: transparent`、`:active/:focus` 无背景、无 outline | `.m-nav-list .main-nav-item / .m-nav-sub .dropdown-item` |

### 二、筛选器（指数浏览器 / 境内ETF）

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | **标题固定**（"主题/市场/调仓频率/指数公司"等），**只滑动标签** | 结构性分离（不用 sticky，Safari 兼容）：`.index-tagbar-row > [.index-tagbar-group 固定 + .index-tagbar-scroll 独立 overflow-x:auto]`；生成函数 `idxTagBarHtml`、`cnEtfTagBarHtml` |
| 2 | 标题**统一宽度 72px**（border-box），4 组标签严格左对齐 | `.index-tagbar-group { width:72px; min-width:72px }` |
| 3 | 标签不换行、横向滑动、隐藏滚动条 | `.index-tagbar-scroll`：`flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none` |
| 4 | 标题背景需**盖住滑过的标签白底**（等高同位） | 结构分离后天然满足（标签在独立滚动区） |

### 三、触屏 hover（全站，@media hover:none）

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | 轻点元素**不改变底色**：未选中=白底/默认外观，点中才蓝底白字 | 原 hover 规则 `background:transparent` 会致轻点瞬时无底色 → 已改为 hover=各元素默认（`.index-tag:hover{background:#fff}`、`.main-nav-item:hover{background:transparent;color:#8e8e93}`、`.dropdown-item:hover{background:transparent;color:#1c1c1e}` 等） |
| 2 | 选中态统一：蓝底 #001aff + 白字 + 加粗 | `.index-tag.active, .weekly-nav-item.active, .dropdown-item.active, .main-nav-item.active` |

### 四、移动端列表卡片

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | 港交所红利ETF / 月月分红ETF / 月月分红指数基金：**卡片间隙与网页整体背景色一致**（浅灰 #f4f2f7，白卡片间隙） | 容器 + **表格背景**都要改：这三个列表移动端是表格卡片化（tr 白底 block + margin），**间隙透出的是 .index-table 的白底**（只改容器无效）→ `#hketfListContainer/#monthlyEtfContainer/#monthlyFundContainer { background:#f4f2f7 }` 且容器内 `.index-table { background:#f4f2f7 }`；实测 tableBg=bodyBg=rgb(244,242,247) |
| 2 | 主流资产/指数浏览器/境内ETF 移动端用独立卡片层（.m-card） | mobile.js `renderAssetTableMobile / renderIndicesMobile / renderCnEtfMobile` |


| 08-22 | **品牌主色还原 #2B7FFF → #001AFF（用户反馈：新蓝有点丑）**：v301 的全站替换全部回滚——主色 38+10 处、rgba(43,127,255,X)→rgba(0,26,255,X)（12+1 处）、渐变浅端 #51A2FF→#4A7CFF（4 处）；实测 active 菜单 rgb(0,26,255)，无残留 | 线上 v302 |
| 08-22 | **品牌主色 #001AFF → Tailwind Blue 500 #2B7FFF（用户要求，取自 ui-colors.md）**：全站替换——index.html 38 处 + mobile.css 9 处主色（含 canvas 图表描边/填充、SVG）；浅色变体 rgba(0,26,255,X) → rgba(43,127,255,X)（12+1 处，alpha 不变）；渐变浅端 #4A7CFF → Blue 400 #51A2FF（4 处 linear-gradient）；对应 oklch(0.546 0.245 262.881)；实测 active 菜单 rgb(43,127,255)、渐变 135deg(#2B7FFF,#51A2FF) | 线上 v301 |
| 08-22 | **全站主背景色 #f4f2f7 → #F5F7FB（用户要求）**：5 处同步——index.html body/.app-shell/.index-detail-page（详情页浮层）+ mobile.css 港交所/月月ETF/月月基金列表容器及 .index-table（卡片间隙透出背景，保持与 body 一致）；白卡片与其余装饰背景（#f8f7fc/#f5f4f8 等）不动；实测桌面 body/壳层/详情页与移动端列表间隙均为 rgb(245,247,251) | 线上 v300 |
| 08-22 | **topbar 二级菜单箭头默认朝下（用户反馈）**：v298 的右 chevron 改为向下 chevron（path m10 6 6 6-6 6 → M6 9l6 6 6-6，14 处），hover 旋转 180° 朝上表示展开（原 90°）；移动端 m-nav-arrow 右箭头保持不变（二级抽屉向右滑入语义）；实测默认朝下/hover 朝上/移动端不受影响 | 线上 v299 |
| 08-22 | **topbar 二级菜单箭头改 SVG chevron（用户要求：更现代）**：红利指数/月月分红后的 ▼ 字符（14 处，含 2 处实体版）替换为 mobile.css 同款箭头 （SVG viewBox 24 · path m10 6 6 6-6 6 · stroke 1.5 currentColor）；CSS .arrow 由 font-size 8px 字符改为 14px SVG（flex 居中对齐），hover 旋转 90°（指向展开方向，原 180°）；桌面与移动端（m-nav-arrow 同款）视觉完全统一；表格排序 .sort-icon 的 ▼ 不受影响；实测桌面 14/14 SVG、hover transform rotate(90°)、移动端菜单 2 个同款箭头无冲突 | 线上 v298 |
| 08-22 | **hash 路由：每个子页面独立访问代号（用户要求，例 #/my）**：新增 HASH ROUTER（PAGE_ROUTE/NAV_SUB_ROUTE/navigate/applyRoute + hashchange 监听 + 首载直达）：#/ 与 #/home→首页、#/weekly→食息资讯、#/index(/browser)→红利指数浏览器、#/index/etf→境内红利ETF、#/index/hketf→港交所红利ETF、#/monthly(/etf)→月月ETF、#/monthly/fund→指数基金、#/blog→子弹列车、#/my→我的；未知代号回退首页；6 处切换入口（主tab/两组下拉/详情页下拉/profileBtn）全部改为 navigate；支持前进后退与菜单选中态同步（桌面+移动端，dropdown-item 同步）；无头浏览器 24/24 通过、线上 5 路由实测通过 | 线上 v297 |
| 08-22 | **topbar 菜单改版（用户要求）**：①"食息数据"tab 改名"首页"②topbar 所有菜单去掉 emoji（一级菜单 + 下拉子项 + "我的"按钮，含 HTML 实体版本）③"食息之路"tab 改名"子弹列车"；同步清理 5 处重复菜单（主 topbar / 指数详情 / 资产详情 / 2 个 overlay）与页面 section-title 的 emoji（主流资产食息率 / ETF月月分红 / 我的收藏）以保持整站一致；功能性收藏图标（⭐/☆）保留不动；实测桌面 + 移动端菜单文本正确，无 JS 报错 | 线上 v296 |
| 08-19 | **详情页 ETF/基金涨跌更新（用户反馈）**：根因=ETF/基金 dailyChange/yrChange 依赖 Wind Excel 快照（未导出），仅指数由 sync_daily_change 更新；改用东财批量补全部 142 只（境内89/月月ETF15/月月基金26/港交所12，共 26 批查询）：当日涨跌幅（ETF 用东财价格涨跌幅、基金用复权单位净值增长率）+ 今年以来回报（净值口径，与 Wind 价格口径略有差异），dailyDate=2026-08-19；03031/03488 港交所 YTD 东财查不到保留 Wind 值；交叉验证重复产品数值一致；check_data 全过；线上确认 512890=1.21%/004597=1.726% | 线上 v295 |
| 08-19 | **hint 问号样式统一（用户要求）**：9 处 hint 图标确认均为英文半角 ?（无全角）；CSS .hint font-weight 700→400（不加粗）；tip 弹出文字不变；实测 9/9 font-weight=400 | 线上 v294 |
| 08-19 | **详情页返回键改 mobile 菜单同款 SVG 箭头（用户要求）**：6 个详情页（指数/资产/港交所/境内/月月ETF/月月基金）brand-icon 内 ‹ 字符替换为菜单二级返回同款 SVG（M14 6l-6 6 6 6，stroke 1.5 白色），CSS .brand-icon svg 22px 放大（原 14px 字符）；首页 logo 的"息"图标不受影响；实测 6/6 生效 | 线上 v293 |
| 08-19 | **全站数据更新（Wind+东财双通道，用户要求）**：Wind 恢复后跑 sync_fund_divdate/money_fund/reits_daily/yuebao_history/daily_change(48指数到08-19)/div_history(47/49)/wind_fields(6分钟)/fix_laggard(0滞后)/asset_macro；东财补：国债 assetHistory 3/5年 08-17~19（1.243/1.392），资产宏观已切东财；修复：余额宝 assetData date→08-19、check_data 规则放宽（股息率非每日更新，divHistory/assetData红利 date 允许滞后≤2天，新增 days_between）；标普红利100/沪港深红利100 东财均无数据保持；cnEtf 分红日期 38 只 Wind 无数据（东财无此字段）保持；check_data 全部通过 | 线上 v291（vercel.app）|
| 08-18 | **港交所ETF列表加"互联互通"蓝底白字标签（用户要求）**：renderHkEtfMobile 卡片名称后按 connect 字段追加 .m-tag-connect 小标签（#001aff 蓝底白字 10px 圆角）；数据 connect=True 共 7 只（平安香港高息/GX恒生高股息率/GX亚太/博时央企/南方东西精选/易方达高股息/南方港股通红利）显示标签，5 只非互联互通不显示；本地模拟验证 7/5 正确；版本 mobile.js?v=38 + mobile.css?v=30 | 线上 v290 |
| 08-18 | **Mobile 四列表卡片第二行追加管理费率（用户要求）**：境内/港交所/月月ETF/月月基金 4 列表卡片 meta 行（代码·挂钩指数）后追加灰色小字"管理费率x.xx%"（_mFee helper，feeNum 格式化两位，无数据不显示）；实测全部产品均有 feeNum；本地 Node 模拟验证输出（159083 0.15%、3070 0.55%、513530 0.50%、003318 0.50%）；版本 mobile.js?v=37 | 线上 v289（vercel.app）|
| 08-18 | **解绑 dividend.top（用户要求）**：项目 dividend-guide 绑定 3 域名（dividend.top / www.dividend.top / dividend-guide.vercel.app）；API 删除前两个自定义域名（已验证 404 不可访问=内容清空），保留 vercel.app（200 正常、v36 在线）；后续仅用 https://dividend-guide.vercel.app | 线上 vercel.app |
| 08-18 | **港交所ETF管理费统一改用东财（用户要求）**：3483易方达高股息 显示 0 且万得终端也返回 0（数据源错误），东财核实=0.50%；12 只全部按东财重取：修正 3 只（3483 0.00→0.50、3437博时 0.10→0.50、3145华夏 0.45→0.60），其余 8 只与东财一致（0.55/0.68/0.60/0.68/0.99/0.99/0.50/0.90）；03466恒生高息股东财查不到保留原值 0.55%；详情页 fee 字段数据驱动自动生效 | 线上 v288 |
| 08-18 | **红利指数浏览器默认排序修正（用户反馈）**：默认改为按指数简称（A-Z），选项顺序=按指数简称（A-Z）/按指数股息率（从高到低）；发现并修复 v35 漏改点——覆写函数 renderIndices 内 _ensureDef 参数仍为 yieldNum（仅改 CFG 未改覆写），导致渲染时强制旧默认；已统一两处为 name；线上确认 mobile.js?v=36（CDN 缓存延迟曾显示旧版）；实测 opts 顺序+选中 name:asc+sortKey=name ✅ | 线上 v287 |
| 08-18 | **Mobile 排序文案按用户语言规范统一**：默认排序 / 按指数简称（A-Z）/ 按ETF简称（A-Z）/ 按基金简称（A-Z）/ 按食息率（从高到低）/ 按指数股息率（从高到低）/ 按挂钩指数股息率（从高到低）/ 按管理费（从低到高）；"默认排序"项仅在无具体默认时显示（食息），其余列表第一项即默认方式（指数=股息率↓、其他=简称A-Z）；实测 6 列表 select 文案+选中值全部正确；版本 mobile.js?v=34 | 线上 v285 |
| 08-18 | **Mobile 排序下拉简化（用户要求）**：食息=默认/食息率从高到低；指数=名称A-Z/股息率从高到低（默认股息率↓）；境内ETF=简称A-Z/挂钩指数股息率↓/管理费率↑（默认A-Z）；港交所=简称A-Z/管理费↑（默认A-Z）；月月ETF/基金=同境内（默认A-Z）。实现：mobile.js CFG 简化为固定方向单选项；_ensureDef 兜底默认排序（render 覆写函数内，修复 run() 时序导致默认排序不生效）；_ensureCnYield 渲染时注入境内ETF 挂钩指数股息率（跟踪指数yieldNum→yield→产品自身yield→无数据-1排最后，修复 run() 早于数据加载导致注入失败）；本地 Node 模拟验证严格降序（高股息ETF广发6.14%居首、1只无数据排最后）；浏览器端部分验证（数据fetch曾被CDN限流）；版本 mobile.js?v=33 | 线上 v284 |
| 08-18 | **资产宏观：LPR/3年/5年国债切换东财（用户确认）**：盘点 iFind（同花顺MCP）数据=assetData 7 项；东财实测：LPR✅一致、国债✅可取（3年1.25%/5年1.384%，外汇交易中心口径，比站点旧值1.63%/1.70%更新）、存款⚠️仅央行基准、保险预定利率❌无、同业存单AAA月化❌无；用户确认换 LPR+3/5年国债：assetData source=iFind→东财、date=2026-08-18、note=国债到期收益率、yield 更新为东财最新；列表页/详情页来源字段为数据驱动（item.source）自动生效；实测移动卡片+详情页（5年期国债 1.384%·东财·2026-08-18）✅ | 线上 v279 |
| 08-18 | **Mobile首页食息胶囊颜色跟随类型标签（用户要求）**：新增 _hexA 辅助（hex→rgba），胶囊文字色=第一行类型色、背景=同色 10% 透明度；实测 16 卡全部 matched=true（红利蓝/REITs紫/租金橙/保险绿/货币橙等）；版本 mobile.js?v=28 | 线上 v278 |
| 08-18 | **Mobile首页食息卡片：取消右上角大数字，指标名+数值整体蓝胶囊（用户要求）**：renderAssetTableMobile 移除 m-yield 右上角数字（表达不明）；第三行第一个"指标名称"改为蓝色胶囊"近12个月股息率5.34%"样式（与指数/ETF列表惯例一致），后接 ·来源·日期；实测 16 卡 hasYieldNum=0、胶囊 [blue] 正确；版本 mobile.js?v=27 | 线上 v277 |
| 08-18 | **境内ETF列表股息率胶囊缺失修复（用户反馈）**：5 只无股息率，原因两类——①3 只（鹏华159117/华夏159118/银华520610）trackCode 误写为 SPAHLVHP.SPI，经东财业绩比较基准确认同一指数"标普港股通低波红利指数"=SPAHLVCP.SPI（yield 5.30%），已修正 trackCode；②华泰柏瑞513530 跟踪的 930915.CSI 不在指数库，改从产品自身 yield 补 5.01%（etfData 同源）；列表渲染改为"股息率优先产品自身、回退跟踪指数"；红利100ETF景顺（SPCADMCP.SPI）东财/Wind 均无数据，保持无胶囊；同时核对 5 只今年涨跌幅与东财原始值一致（-0.65%/-0.32%/-6.14%/+4.48%/-5.62%，列表=详情）；版本 mobile.js?v=26 | 线上 v276 |
| 08-18 | **移动列表页：数值为空的胶囊直接不显示（用户要求，替代"暂缺"方案）**：红利指数浏览器"股息率/本年涨跌幅"、及港交所/境内/月月ETF/月月基金 4 列表的"本年"胶囊，无数据一律不渲染（去掉"—"/"暂缺"占位）；标普中国A股红利100（SPCADMCP.SPI）数据缺失且 yrChange 为假 0.0 → 清理为 null（东财/Wind 均取不到，暂缺）；实测红利指数浏览器 49 卡仅该指数无胶囊、其余正常（红利低波100：股息率4.46%+本年-4.84%）；版本 mobile.js?v=25 | 线上 v275 |
| 08-18 | **修复详情页两字段"空着"（用户反馈 央企红利ETF华泰柏瑞）**：根因=8-17 在"跟踪指数名称"后插入的旧两行（带hint、产品自身行情暂未接入版）未删除，与 8-18 字段区末尾新行 id 重复，JS getElementById 只填充第一对（中间），末尾新行空着；删除 3 个详情页（境内/月月ETF/月月基金）遗留旧行 3 组，id 全部唯一；模拟用户路径（月月ETF列表→点击央企红利ETF华泰柏瑞）实测：列表胶囊 股息率4.22%+本年3.31%，详情页 当日1.31% 今年3.31% 红涨绿跌、label 带日期，dailyIdCount=1 | 线上 v274 |
| 08-18 | **移动列表页"本年"胶囊改用产品自身行情（用户反馈）**：港交所/境内ETF/月月ETF/月月基金 4 个移动列表页的"本年"涨跌胶囊原用跟踪指数 yrChange（部分显示—），现全部改为产品自身 yrChange（东财行情）；股息率胶囊不变（境内ETF走跟踪指数、月月走产品自带）；实测：港交所 12 卡（7.86%/1.69%/8.47%）、境内 89 卡、月月ETF 15 卡、月月基金 26 卡（500SNLV 由"—"→7.24%）全部正确、红涨绿跌 | 线上 v272 |
| 08-18 | **境内ETF+场外基金全部接入产品自身行情（用户要求，东财MCP已充值）**：用 mx_fund_finance_data 分批（8只/批，串行防限流）取齐 cnEtfData 89 + etfData 15 + fundData 26 = 130 只的当日涨跌幅+今年以来回报（2026-08-18 收盘）；境内/月月ETF 用场内代码（.SH/.SZ）查"涨跌幅"（价格口径），场外基金用 .OF 查"复权单位净值增长率"（净值口径）；写入 dailyChange/yrChange/dailyDate/dailySource=东财；3 个详情页（境内ETF/月月ETF/月月基金）字段区末尾加两行，label 动态"（数据截至2026-08-18）"、产品自身优先（回退跟踪指数）；修复 showMonthlyFundDetail 变量名 etf→fund（否则详情页图表中断）；实测 3 页显示正确 | 线上 v271 |
| 08-18 | **港交所详情页：当日/今年两字段 hint 取消 + label 加数据日期（用户要求）**：两行 label 改为动态"当日涨跌幅（数据截至2026-08-18）"/"今年以来回报（数据截至2026-08-18）"（JS 读 etf.dailyDate 动态拼接，数据更新日期自动跟随）；实测 hasHint=false、日期拼接正确 | 线上 v269 |
| 08-18 | **港交所红利 ETF 全部接入产品自身行情（用户要求，东财/同花顺 MCP）**：Wind 基金行情工具不可用（kline/quote/stock 空错误、NAV_chg/NAV_return 不在 indexes 白名单）；改用 mcp_mx-ds-mcp（东方财富）mx_hk_finance_data + mx_fund_finance_data：12 只全部取到当日涨跌幅+今年以来累计涨跌幅（2026-08-18 收盘，逐只串行查询避开限流）；写入 hkEtfData.json 新增 dailyChange/yrChange/dailyDate/dailySource 字段；港交所详情页改为产品自身行情优先（回退跟踪指数），hint 更新；实测 12/12 显示正确、红涨绿跌；其他 3 个产品详情页仍为跟踪指数口径待后续接入 | 线上 v267 |
| 08-17 | **产品详情页新增"当日涨跌幅/今年以来回报"（用户要求，跟踪指数口径）**：Wind 工具实测仅指数行情+货基指标通道可用（get_fund_price_indicators 货基字段 OK；fund/stock 的 kline/quote 及 NAV_chg/NAV_return 字段均返回空错误/非法——用户提供的 Wind 智能体字段名在 wind-mcp-skill 的 get_fund_price_indicators indexes 白名单外）；方案：4 个产品详情页（港交所ETF/境内ETF/ETF月月/基金月月）新增两行，值取跟踪指数 dailyChange/yrChange（findIndexForTrack 匹配，红涨绿跌），label 附 hint 注明"按跟踪指数口径（产品自身行情暂未接入）"；实测：港交所 +1.11%/+7.09%、月月ETF +1.50%/+5.83%、境内ETF -0.22%/-4.84% 颜色正确；trackCode 未收录于 indexData 的产品（如 500SNLV）显示"—"；列表页未动 | 线上 v266 |
| 08-17 | **移动端 5 列表卡片统一三行结构（用户要求）**：红利指数浏览器/境内ETF/港交所ETF/ETF月月分红/指数基金月月分红 统一为：①大字名称②灰字 code·市场·币种（或 code·挂钩指数）③胶囊行（股息率蓝胶囊 .m-pct.blue + 本年涨跌胶囊红涨绿跌）；右上角不再显示数字（首页食息数据保留）；港交所只有涨跌胶囊无股息率；ETF/基金股息率优先用自带 yield、涨跌幅按 trackCode 查 indexData.yrChange；新增 renderHkEtfMobile/renderMonthlyEtfMobile/renderMonthlyFundMobile 三个渲染函数并覆写主脚本；实测 5 列表 lines=3、topNum=false、胶囊/颜色/计数全部正确（49/89/12/15/26 张卡）；9 只产品 trackCode 未收录于 indexData（本年显示—，股息率胶囊正常） | 线上 v264 |
| 08-17 | **一级菜单不再预跳转（用户要求：选中二级子项才跳页）**：之前点一级带子项（红利指数/月月分红）时下方页面跟着跳；改为 capture 阶段 e.stopPropagation() 阻止主脚本切页——点一级仅展开二级；无子项一级（食息之路等）正常直接跳；实测：点"红利指数"后仍 pageData+二级展开，点"境内红利ETF"后才 pageIndex/subEtf/菜单收起 | 线上 v262 |
| 08-17 | **菜单选中蓝底统一（用户反馈：桌面缩窗二级菜单无蓝底）**：根因=选中蓝底规则原在 @media(hover:none)（仅触屏设备匹配），桌面浏览器缩到 767 以下时 hover:none 不匹配 → 无蓝底；将选中态规则移到 @media(max-width:767px) 内（7.1 块，不依赖设备类型）+ 删除 hover:none 冗余；实测桌面 Chromium（hoverNone=false）真实点击月月分红→ETF 后 bg=rgb(0,26,255) 纯蓝、color=#fff | 线上 v261 |
| 08-17 | **首页生息资产列表标题等宽（用户要求）**："📌 适合普通人的几种常见生息资产"列表的 6 个标题（股票→股息/债券→债息/REITs→分红/保险→分红/现金→现金收益/其他）占位统一 108px（最长标题宽度），描述从固定列开始、换行时缩进不占标题空间：`.intro-item b { flex:0 0 108px }` + align-items:flex-start；实测 6 项标题宽/左缘/描述起点全部一致（108/51/165） | 线上 v258 |
| 08-17 | **hint 问号加粗 + 详情页汉堡菜单位置修复（用户反馈）**：①hint 圆圈内问号 font-weight:700（实测 700）②详情页汉堡按钮之前跑到页面中间——根因：详情页 header 无 profileBtn，汉堡插入逻辑走 insertBefore(btn, nav-right) 插到 nav-right 前面；改为 nr.insertBefore(btn, nr.firstChild) 插到 nav-right 内部（五角星左侧），实测 hbInsideNavRight=true、汉堡 553/五角星 601 同组相邻；主页面（有 profileBtn）分支不变 | 线上 v257 |
| 08-17 | **"每月千元分红需总投入" Hint 文字更新 + 弹出文字加粗（用户要求）**：指数详情页 data-tip 改为"本指标数值的含义：按对应指数的当前股息率计算，每月获得1000元分红所需的投入本金（万元）。计算公式：12×1000÷股息率÷税后系数（港股按0.8系数计入红利税）。本指标并不等同于基金的实际分红，请注意区分。"；hint-tip 全局 font-weight:600（实测 600）；月月分红页"收益"版 hint 未动 | 线上 v254 |
| 08-17 | **PC 筛选器间距回归修复 + 详情页大块横线（用户反馈）**：①PC 筛选器标签无间距——根因：改 idxTagBarHtml 生成结构（标题+滚动区分开）是全局的，PC 标签进入新容器 .index-tagbar-scroll 失去 gap → 主样式补 `.index-tagbar-scroll{display:flex;flex-wrap:wrap;gap:6px 10px}`（实测间距 10px 恢复）②详情页三大块（名称描述/详细信息/图表）之间加 1px solid #f2f2f2 横线：`.detail-card-section + .detail-card-section` 的 border-top none → #f2f2f2（全详情页共用，实测 1px rgb(242,242,242)）；同时把"移动端改动不得污染 PC"立为纪律（见 Mobile 章节顶部） | 线上 v253 |
| 08-17 | **全站数据同步 + 两个同步脚本 bug 修复（用户睡觉前嘱托）**：①sync_wind_fields._extend_yield_map 列名当索引用 → TypeError（修复：colmap 返回 {列名:索引}，yi 须取索引值）②Wind 指数股息率返回小数(0.0235) 而站点约定百分数(2.35) → 兜底值 ×100（修复 6 只联接基金 yieldNum 异常）；数据全部更新至 2026-08-17（divHistory/dailyChange/余额宝），check_data 仅剩 REITs T+1 正常滞后；Vercel 部署成功、线上 fundData 异常 0 | 线上 v252 |
# 数据格式与口径规则（reference）

> 来源：《网站更新与数据管理对照文档》（2026-08-22 拆分；原件归档为 `docs/_archived_网站更新与数据管理对照文档.md`）**规范篇**「显示格式统一」「数据源口径统一」「其他约定」。
---

> 本文档内容迁移自《网站更新与数据管理对照文档》（2026-08-22 docs 重组）。
> 当前唯一权威规范以 `reference/` 与 `data-governance/` 下的文件为准；`changelog/` 只是历史记录，不代表当前状态。

## 显示格式统一

1. **日期格式**（2026-08-04）：全站统一 `yyyy-mm-dd`；禁止显示层替换 `.` 或手动拼接；排序比较可用 `replace(/-/g,'')`（仅内部比较）。
2. **缺数据占位**（2026-08-04）：全站统一 `—`（em dash）。禁止 `'-'`/`'--'`/`'暂无历史'`/`'数据待更新'`/`'暂无简介'` 等混用。语义性文案除外（如"暂未分红"=明确分红 0 次；整图空态说明"该指数暂无股息率历史数据"是整图说明非单元格占位）。
3. **余额宝 7 日年化 2 位小数**（2026-08-10）：首页资产列表、各详情页图例值（`*YuebaoVal`）、图表端点标注、hover 悬浮框全部 `toFixed(2)`；数据层 `'{:.2f}%'`。**任何新增余额宝显示处一律 2 位小数**。
4. **资讯正文一律不使用【】强调符号**（2026-09-20，用户要求：「今后也不要加这些符号了」）：**三层保障**——
   - **生成端（根治）**：digest 改写规范改为「主体自然入句、不加【】」，规范落在
     `workbuddy/dividend-guide-digest-workbuddy/yield-guide-daily-digest-skill.md`「改写规范」、
     `DATA-SCHEMA.md` 的 `text` 字段说明、以及 `.workbuddy/memory/MEMORY.md`「内容质量标准」
     （后者是 Windows 生成端每次运行必读的**长期记忆**，跨设备经坚果云同步）；
     另需在 Windows 侧同步改 live skill `dividend-guide-digest-daily-update/SKILL.md`。
     **✅ 2026-09-20 用户确认：Windows 侧 live skill 已同步修改完成。**
     实测：生成端 `digest-db.json` 全文 **0 处【】**（11924→11840 B，恰为 14 对括号），
     `sync_daily.py` 复跑输出「正文检查: 无【】符号 ✅」（不再触发 WARN），全链路已干净。
   - **消费端（兜底）**：`sync_daily.py` 写 `dailyData.json` 前用 `strip_marks()` 剥离正文【】，
     命中时打印 `[WARN]` 以便发现上游回归；`check_data.py` 第 16 项据此做硬校验。
   - **渲染端（最后一道）**：`renderDaily()` 用 `dEsc(dfPlain(it.text))`，`dfPlain` 只删 `【】` 本身、保留其内文字。
   复制按钮读同一 DOM 节点，故复制文本同步无符号。**上游 `digest-db.json` 不做改写**（生成端下一次生成起自然干净）。
   若后续新增正文渲染入口，须同样走 `dfPlain()`。

## 数据源口径统一

1. **指数股息率以 Wind divHistory 最新值为准**：`sync_excel.py` 写回 indexData 时用 divHistory 最新值覆盖 `yield/yieldNum`；Excel 快照仅兜底。Wind 无值 → `yield` 置空显示 `—`，**禁止 `0.00%`**、禁止用陈旧数值充数。
2. **手动字段保护**：`publisher/listedDate/weight/weightExtra/components/market/currency/fullReturn`（+ `adjustCycle/adjustDate`）由用户维护，sync_excel 不得覆盖（旧值非空保留）；`AUTHORITATIVE_MANUAL` 硬编码权威值强制固定（如 SPCADMCP.SPI components=100、000922.CSI listedDate=2008-05-09）。**手工修订在对话里告知 AI，由 AI 落地并登记到 `manual-overrides.md`；飞书/Excel 表仅用于「全新表一次性提交」（2026-09-27 用户约定）。**
3. **REITs 两类口径**（2026-08-11 确立，08-15 定稿）：
   - 分类按**现金流属性**（非 Wind"项目属性"物权口径）：产权类 = 园区/仓储物流/消费/保障房；特许经营权类 = 交通/新能源/生态环保/水利（**派息含资产摊销本金返还，虚高**）。
   - 指标 = Wind **名义派息率（中位数）**：产权类、特许经营权类均**日频**（每交易日，2023-01 起约 873 点/类，assetHistory 运行时加载）。
   - 首页 assetData 的 yield/date：sync_excel 特判从 assetHistory 最新日频中位数覆盖（08-15 起），**不随 Excel 快照回退**；note/desc/图例统一"名义派息率（中位数）"。
   - 特许经营权类详情页红字风险提示（定稿文案）：**"特别提示：特许经营权类REITs的名义派息率，包含资产摊销对应的本金返还部分，该指标会高估实际投资收益率，需要结合IRR综合判断真实回报水平。"**
4. **红利指数覆盖**：build_asset_data 中红利指数 yield/date 取 indexData divHistory 最新值（`ASSET_INDEX_NAME_MAP`：上证国企红利→上国红利、香港银行→HK银行(HKD)）。
5. **ETF 简称统一口径 = 场内扩位简称**（2026-09-20 用户要求）：**站内所有 ETF 的 `name` 一律取 Wind「基金扩位场内简称」**，❌ 不用「基金简称 / 证券简称」，❌ 不用「场内简称」。
   - 覆盖 `cnEtfData.json`（93 只）与 `etfData.json`（15 只）；规范数据库对应列名统一为 **「ETF扩位场内简称」**（主表「月月可分红ETF」当日由「ETF简称」更名）。
   - **例外**：`hkEtfData.json`（港交所 ETF）——Wind 该字段对港股返回空值（仅 A 股适用），保留 `name` = 场内简称。
   - **不受约束**：`fundData.json`（场外基金）/`moneyFundData.json`（货币基金）非 ETF，仍是基金简称。
   - 完整口径与防回退见 `data-governance/data-catalog.md`「规范数据库（Wind Excel 快照）表头结构」。
6. **指数币种变体统一归并到「基准版」**（2026-09-20 用户要求：「一旦出现了港币版，就不要再单独列出来，这样显得很傻」）：
   同一指数在 Wind 常有**港币版 / 人民币版**两条（代码不同、**股息率数值完全相同**）。站内**只保留一条**，取「**基准版**」：
   - **判定**：Wind 全称里写「人民币」的那一版是**变体**（折算派生版）；若没有「人民币」版，则带「港币 / (港币)」的那一版是变体。
   - **已核验的变体对**：`SPAHLVHP.SPI`（港币）→ **`SPAHLVCP.SPI`（基准 = 人民币版）**；`930915.CSI`（人民币）→ `930914.CSI`（基准）；`930840.CSI` → `930839.CSI`；`930793.CSI` → `930792.CSI`。
   - **实现**：`index_variants.py` 是**单一事实来源**（映射表 + `normalize()`）；`sync_excel.py` 在所有 builder 产出后统一归并、`sync_new_etf.py` 补入前归并；`check_data.py` 第 17 项硬校验「站内任何 trackCode 都不得是变体代码」。
   - 归并会改变**展示名**（如「标普港股通低波红利指数(港币)」→「标普港股通低波红利指数」）；主题/市场筛选由 trackName 推导（`cnEtfThemeOf` / `cnEtfMarketOf`），归并前后结果一致（已实测）。
   - ⏸ **其余变体对保持现状（用户 2026-09-20 确认，不做迁移）**：`930914.CSI`(HKD)/`930915.CSI`(CNY) 一组站内 9 处用前者、2 处用后者（`513530.OF`/`018387.OF`），两版数值相同；`930840.CSI`/`930793.CSI` 站内未出现。映射表只启用标普一组；将来要统一，把键加进 `index_variants.py` 一行即可（`check_data.py` 第 17 项自动覆盖）。详见 `data-catalog.md`「已确认：其余变体对保持现状」。

## 其他约定

- 图表 hover 气泡宽度按文本动态计算（`measureText`），自动避开视口左右边界。
- 表格排序 `divDate` 支持（08-05）：`smartCompare`/`sortData` 加 divDate 分支，空值排最后。
- 红利指数浏览器简介固定句式：「本表仅展示有挂钩产品发行的[n]个指数 · 数据已更新至[date]」（n=指数总数，date 优先 dailyDate、兜底 divHistory 最新日期）。
- 新增详情页图表必须同步改 **6 处**（HTML/状态/初始化/select/滑块/hover），对照 monthlyEtfDetail 模式。
- 页面副标题/文案迭代为常态（非 bug）。
- 数据同步脚本写入用临时文件 + `os.replace` 原子替换（坚果云盘锁冲突）。
- **批量修改脚本必须"全断言通过后统一原子写盘"**（教训：任一断言失败整次修改未写盘，改后需 grep 复查关键标记）。

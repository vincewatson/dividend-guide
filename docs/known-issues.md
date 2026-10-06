# 已知问题与防复发（known-issues）

> 来源：《网站更新与数据管理对照文档》（2026-08-22 拆分；原件归档为 `docs/_archived_网站更新与数据管理对照文档.md`）**附录 A · 问题清单（已解决，防复发机制）**。
---

> 本文档内容迁移自《网站更新与数据管理对照文档》（2026-08-22 docs 重组）。
> 当前唯一权威规范以 `reference/` 与 `data-governance/` 下的文件为准；`changelog/` 只是历史记录，不代表当前状态。

| # | 问题 | 根因 | 解决/防复发 |
|---|------|------|-------------|
| 1 | 同业存单标的指数错误（用 931815 0-6个月AAA）| 取数时误选 | 用户确认 **931059.CSI**；sync_asset_macro 固化；文案定稿 |
| 2 | 同业存单 note"今年以来"不准确 | Excel 备注误导 | NOTE_OVERRIDE 强制；前端 listNote 简版/详情完整版 |
| 3 | divDate 被 build_lists 重建覆盖（反复）| Excel 快照无/旧 divDate | 流水线顺序：fund_divdate 在 build_lists(2) 之后；备份合并恢复 |
| 4 | sync_asset_macro fetch_ncd 缺 import datetime | 局部 import 模式遗漏 | fetch_ncd 内补 `import datetime`（文件风格为函数内 import）|
| 5 | yrChange（本年涨跌幅）滞后 1-2pct | 仅来自 Excel 快照 | sync_daily_change 加 Wind 实时拉取 + build_lists 保护 |
| 6 | fundCount 批量解析错位/漏 | Wind 列名"跟踪指数X"/"跟踪X"不稳定 | 正则 `^跟踪(指数)?` 解析；每批 sleep 10 秒防限流 |
| 7 | Wind 查询 12 字段返回"没找到数据" | 单次查询字段过多 | **≤7 字段/次**，拆两次查询合并 |
| 8 | ETF 股息率显示 3.43% vs 万得指数 5.35% | 误用"近12月分红收益率"（ETF 实际派息）| yield=**跟踪指数股息率**（trackCode 映射）；近12月分红收益率存 divYieldNum 备用 |
| 9 | 未映射 trackCode 出现负值/15.92% 异常 | 兜底口径缺失 | `_extend_yield_map`：未映射 trackCode 自动查指数股息率 |
| 10 | ETF 简称"N"前缀过期残留 | 上市临时标记未动态摘除 | fix_n_prefix（Wind 简称无 N 则摘）+ build_lists 保护不恢复 |
| 11 | dailyChange 批量截断漏指数（932584 停 08-11）| 批量返回上限 | check_data 全覆盖检查（更新数 vs 指数总数）拦截 |
| 12 | divDate 查询措辞失效（误判"无数据"，覆盖率骤降）| 查询措辞随 Wind 语义漂移，**不存在永久最稳的单一措辞** | **多措辞依次兜底**（最近分红情况 → 最近分红发放日期 → 基金分红 分红发放日），首个返回「基金红利发放日」者即用（sync_fund_divdate.py）；验收看覆盖率（fund≥25/26、etf≥14/15、cnEtf≥50）。2026-09-13 复测：「最近分红情况」有效、「最近分红发放日期」失效（旧结论反转）|
| 13 | 同业存单未来日期（08-31）| Wind 返回月内未来截止日 | fetch_ncd 自动修正为实际截止日 |
| 14 | 重点50城租金率旧口径（1.80% vs 现行 2.03%）| 早期报道口径不同 | 铁律：租金房价比=50城租金×12÷均价；2023 低点 1.98% 基准；旧口径禁止混用 |
| 15 | 场外基金每份分红金额口径存疑（A/C 拆分）| Wind 分红总额口径与 Excel 差异大 | **保留 Excel 原值不覆盖**（annualDivAmt/monthlyDivAmt/divTotalAmt/cumDiv）|
| 16 | 浏览器缓存显示旧数据（3.43% 误判未修复）| CDN/浏览器缓存 | 线上验证用 `?t=时间戳` 强刷 |
| 17 | "每月千元分红需总投入"差 100 倍（红利潜力 0.34 vs 应 34.12）| **yieldNum 单位约定为百分数**（4.2756=4.28%）但前端公式按小数计算（缺 /100）| 前端 3 处公式统一加 /100；check_data 加 yieldNum 单位校验（0.5~30）防复发；公式=1.2÷(yieldNum/100×税后系数) 万元 |
| 18 | Safari（隐私模式）下拉菜单/图表时间选项点击无效 | 顶层 localStorage 访问抛 SecurityError 中断主脚本，其后所有 addEventListener 未绑定 | favorites 加 try-catch 降级；interaction-fix.js 事件委托兜底；触屏下拉 dropdown-open 不依赖 hover |
| 19 | fix_laggard_indexes 报 TypeError，且会把日频 divHistory 覆盖成月频 | 用「按月列出」查询，返回 5 列月末数据，代码按固定索引解析 | 改为**日频**查询 + **合并**（只补"最后日期之后"缺口）+ 按列名解析 + 原子写入（2026-09-13）|
| 20 | sync_yuebao_history 某段瞬时失败 → 全量重写后静默丢约 3 个月历史（956 < 1007 条）| 全量重写且无重试 | 每段**重试 3 次** + 写回前**与现有文件合并**兜底缺口（2026-09-13）；启动前先看日志的 `[WARN] 段…未获取到数据` |
| 21 | 3/5 年期国债停更（assetHistory 保留旧值，assetData 日期停在上一周）| `fetch_bond_savings` 单一措辞「2023年至今储蓄国债发行记录票面利率3年期5年期」随 Wind 语义**漂移失效**（返回"没找到数据"）→ `safe_fetch` 保留旧数据 | 改为**多措辞依次兜底**（`BOND_PHRASINGS`：储蓄国债 票面利率 三年期 五年期 发行 → 旧措辞 → 储蓄国债发行记录 票面利率 3年期 5年期），取首个返回非空表者（2026-09-19）；验收看 `assetHistory` 国债最新日期是否达最近周五（周频前向填充口径）|
| 22 | **未上市新 ETF 被静默漏收**（广发标普港股通低波红利ETF 158039 成立 09-18 却未进列表）| `sync_new_etf` 用**裸代码**（`split('.')[0]`）去查详情/规模/扩位简称；已上市 ETF 裸代码恰好唯一（159589→159589.SZ），但**未上市**基金在 Wind 是 `.OF`，裸代码 `158039` 撞上同号**债券** `158039.SH「18晋质20」` → `get_fund_info` 返回"没找到数据" → 走「详情拉取失败，跳过」分支**静默漏收** | 三处查询（`fetch_fund_detail` / `fetch_fund_scale` / `fetch_ext_short_names`）全部改用 **Wind 全代码**（`f['windCode']`，含后缀）；配套 `_pick_row()` 按全代码精确匹配 + 字段**按列名解析**（防列序漂移）；详情失败时打印 Wind 代码不再含糊（2026-09-20）|
| 23 | **同一指数港币版/人民币版在站内并列**（标普港股通低波红利：indexData 是人民币版，3 只 ETF 却引港币版；另 930914/930915 亦是 7:2 分裂）| Wind 对港股通类指数同时发布港币版与人民币版，两版**代码不同、股息率数值完全相同**；各脚本各自取用、无归并口径 | 新增 `index_variants.py` 作**单一事实来源**：变体代码 → 基准版代码映射 + `normalize()`；`build_lists` 在 builder 产出后**统一归并**、`sync_new_etf` 补入前归并、`check_data` 第 17 项硬校验「站内不得出现变体代码」（2026-09-20）。⏸ 其余三组（930914/930915、930839/930840、930792/930793）**用户 2026-09-20 确认保持现状、不迁移**，映射表只启用标普一组（详见 `data-catalog.md`「指数币种变体归并」及其中「已确认：其余变体对保持现状」）|
| 24 | cnEtfData 管理费率显示 **15.00%**、费率筛选分档错误（158023 / 562150 / 562180）| auto-discover 的 ETF 把管理费率**百分数**（0.15）直接写入 `feeNum`，而站点约定 `feeNum` 为**小数**（0.0015）；与 #17 同类"单位混用" | `sync_new_etf` 改为 `fee/100`；修复存量 3 只；check_data 增「cnEtfData feeNum 单位」校验（0.0005~0.02）（2026-09-13）|
| 25 | 周更"中途停顿 / 整轮中断 / 像卡住"三类运维陷阱 | ① `sync_asset_macro` 的 `END` **硬编码日期**（`2026-08-28`），过点后每周卡住；② `sync_money_fund` 拉取失败直接 `raise` → **中断整轮周更**；③ 部署/长命令用 `2>&1 \| tail`，**管道缓冲到进程结束才输出** + `curl` 无超时在被拦截出口**挂死** → 误判"卡住" | ①改**动态今日**；②改**告警 + 保留原值**（不中断）；③`PYTHONUNBUFFERED=1` + `curl --connect-timeout 10 --max-time 20` + 各步心跳/计时（2026-09-19）；详见 `wind-query-tips.md` I |
| 26 | 部分指数 `get_index_price_indicators` 的「最新交易日」被 Wind 返回 `0`、涨跌幅为空 → `sync_daily_change` 写入**畸形日期**（930740 曾显示 `0--`；932584/SPAHLVCP 长期停在 09-18 未被察觉，因正常周与全局最新日恰好同值）| Wind 对个别指数（新指数/停牌口径）不返回截面，旧解析按固定格式硬拼出 `0--` | 解析前**校验日期为 8 位数字**、否则丢弃；对缺失/无效者**单只重查 + `get_index_kline` 兜底**（取最近两日收盘算涨跌幅）；2026-09-26 |
| 27 | **跨市场日历周**（A股休市、港股开市）：「dailyChange / reitsDaily 全覆盖」按单一 `latest`（=各指数 divHistory 最大值）判定 → 全部 A股指数与 REITs 被误判滞后、部署被拦 | 站点同时覆盖 A股与港股指数，节假日两市场最新交易日可差 1 天 | 覆盖率检查一律改「**允许滞后 ≤2 天**」（与 `divHistory 全覆盖` 一致）；2026-09-26 |
| 28 | `backup_db.py` 仍备份已归档的 `weeklyData.json`，而**日报数据 `dailyData` / `dailyTagColors` 未纳入备份与 offline-db** | 09-20 周报→日报迁移未同步到备份脚本 | `DATA_FILES` 换为 `dailyData.json` / `dailyTagColors.json`（校验由 10→12 个 JSON）；2026-09-26 |
| 29 | 周更单条 Wind 查询**串行**致大头耗时（`fund_divdate` 136 只≈17 min、`reits_daily` 58 只≈2.5 min）；且 `sync_reits_daily.call_wind` 缺「没找到数据」兜底 → 无数据区间每只空耗 3 次重试（~18s） | 逐只 `subprocess` 调用 + 逐只 `sleep` 串行；无数据时 Wind 返回非 JSON 触发异常重试 | 两脚本改 `ThreadPoolExecutor` 并发（默认 8 路，`SX_WIND_WORKERS` 可调；多措辞/保留旧值/原子写回语义不变）；`call_wind` 增 `没找到` → 空结果不重试（2026-09-26）|
| 30 | 密集重跑触发 Wind「**单日请求次数超限**」→ 全部查询失败、脚本空跑（× 措辞 × 重试次数）白烧额度、耗时反而拉长 | CLI 返回 `ok:false`（非异常），旧 `call_wind` 走 3 次重试 | `call_wind` 识别 CLI 级 `ok:false`（含超限）**不重试**、立即返回；失败一律**保留旧值**（铁律不受影响）；**排期避免同日密集重跑**（2026-09-26）|
| 31 | 每周重复重查「**确无分红记录**」的基金（cnEtf ~46 只）白耗 Wind 额度 | 无"无记录"记忆，每周对空值基金全量重查 | 新增 `data/divNoRecord.json` 缓存（**仅确证无记录时写、取到记录即删、失败不写**；`SX_DIV_NORECORD_DAYS` 默认 28 天复查）；独立文件防被 `build_lists` 重建覆盖（2026-09-26）|
| 32 | 页脚文案改一处要改 **7 遍**、易漏；同一段 HTML 被复制成 7 份（1 global + 6 detail） | 早期图省事静态复制；CSS 是共用的（`.site-footer` 基类一处生效）让人**误以为 HTML 也是一处**——实际不是 | 页脚改造为「**网站地图 + 单源渲染**」：7 处 `.site-footer` 收敛为**空壳容器**，正文由 `index.html` 的 `renderFooter()` 统一写入（读 `#mainNav` 导航 DOM）。验收：`grep -c 'class="site-footer' index.html` = 7（容器数不变），但页脚正文在源码里只出现 1 次（2026-09-27）|
| 33 | 想在 iframe / 窄屏里读「导航栏目」做单源派生校验，结果 `#mainNav` 里读不到 `.dropdown-item`（子项数为 0） | 窄屏 `mobile.js` 会把 `#mainNav` 重构成抽屉（`.m-nav-drawer`）并把 `.dropdown-item` **搬到兄弟容器**（`#mainNav .dropdown` 残留但已空） | 单源派生/校验一律以**桌面导航**为基准（宽屏帧或 `renderFooter()` 在移动脚本之前执行）；`renderFooter()` 绝不可挪到 `mobile.js` 之后；测试断言别用 `#mainNav` 逐项取子项（2026-09-27）|
| 34 | 页头设 80% 透明度「看不出效果」——`.main-content`（唯一滚动容器，`overflow-y:auto`）与 `.top-bar` 是**并列的两个 flex 兄弟**，内容在 `.main-content` 顶部即被裁切，**永远不会经过页头下方**，故 0.80 与 0.88 视觉无差 | 站点用 `html,body{height:100%}` + `.app-shell{display:flex;flex-direction:column}`，滚动发生在 `.main-content` 而非 body；`.top-bar` 的 `position:sticky` 因此从不真正"粘"，页头只是普通首行 | 页头改 **`position:fixed` 覆盖层** + 主内容 `padding-top: var(--topbar-h)`（等高占位，布局逐像素不变）；高度用 JS 实测写回 `--topbar-h`（`ResizeObserver` 兜底 mobile.js 重构导航后的高度变化）；⚠️ 同页 `.index-table th` 的 `position:sticky` **不可**跟随 `--topbar-h`——表格自带 `overflow:hidden`（表格即其粘性滚动容器），改 `top` 会把表头整体下推 60px 留空隙，须保持 `top:0`（2026-09-27）。⚠️ **当日晚些时候已按 Tier1-② 彻底修复**——详见 #35 |
| 35 | 红利指数 / 境内ETF / 港交所ETF / 月月分红 **长表滚动后表头消失**（`.index-table th` 的 `position:sticky` 形同虚设，49/95 行的表滚下去无法辨认列） | `.index-table-wrap { overflow-x:auto }` + `.index-table { overflow:hidden }` 让**表格自身成为粘性滚动容器**（wrap 高度=表高、从不纵向滚动），`th` 只相对表格吸顶＝永不吸顶；`.page` / `.sub-page` 祖先链无其它滚动容器，sticky 因此解析到 wrap 而非 `.main-content` | 实测 768–1440 各档宽度 × 5 个列表：`.index-table-wrap` `scrollWidth === clientWidth`（**表格从不横向溢出**）→ 把 `.index-table-wrap` / `.index-table` 改 **`overflow: visible`**，`th` 即相对 `.main-content` 吸顶，`top:0` 落在固定页头正下方（粘性偏移 = `top` + 容器 `padding-top`）。验收：1440/1280/1024 × 5 路由滚到 maxScroll 时 `th.top == 60`（≡ 页头高）、表格与页面横向溢出均 0；≤767 移动端 `thead` 本就 `display:none`，不受影响。⚠️ 若日后新增列导致横向溢出，**不可**回退成 `overflow:auto`（会再次破坏吸顶），须从列宽 / 省略号解决（2026-09-27）|
| 36 | 每周 `sync_daily.py`（同步食息资讯）**卡住约 19 分钟**才出结果 | `find_db()` 的兜底 glob `~/Library/CloudStorage/*/**/dividend-guide-digest-workbuddy/digest-db.json` 对**整个坚果云目录树**做递归 glob；目录树巨大时实测 **1122s**。稳定位置 `CANDIDATES[0]` 明明 **0.00s 即命中**，却仍无条件跑完全部 glob | `find_db()` 改为**短路**：`CANDIDATES` 一旦命中即返回，**仅在无候选命中时**才退回落盘 glob（跨设备探测语义保留）；实测 **1122s → 0.02s**（2026-10-01）|
| 37 | 周更 `check_data.py` **误报**「assetHistory 3/5年期储蓄国债 最新日期」滞后（国债 09-25 vs divHistory 09-30）→ 阻塞部署 | 国债为**周频**序列（储蓄国债票面利率，每周五采样 + 前向填充，见 `wind-query-tips.md` §H），但该检查曾按**日频 ≤3 天**判等；历史上最新交易日恰逢周五（09-11/09-18/09-25）故未暴露，本周最新交易日为**节前周三 09-30**，间隔 5 天 → 误报 | 国债检查改为**周频口径**：期望值 =「divHistory 最新日期之前最近的那个周五」，逐日校验（余额宝/REITs 仍为日频 ≤3 天）；打印项独立为「最新日期(周频·最近周五)」（2026-10-01，与 `wind-query-tips.md` §H「验收看最新日期是否达最近周五」一致）|
| 38 | **港交所 ETF 管理费率显示 `0.00%`**（易方达高股息 3483.HK），且多只 ETF 规模/成立日长期失真 | `sync_wind_fields.update_hk_etf()` 两处缺陷：① **列名漂移**——Wind 规模列时而「基金规模合计」、时而「上市基金规模_WIND计算」，旧代码按精确列名取值 → 取不到即 `None` → 规模**长期漏更新**；② **0 值误写**——`管理费率` 偶发返回 0（Wind 对新基金时段性缺值）被当有效值 `upd`，把真实费率**覆盖为 `0.00%`** | 取值函数改 **精确名优先 + 子串模糊匹配**（规模 `('基金规模合计','规模')`、跟踪指数 `('跟踪指数名称','跟踪指数')`）；4 个 builder（cnEtf/etfData/fundData/hkEtf）费率更新统一加护栏 **`v>0` 才写**（≤0 = 缺值，绝不覆盖），hk 规模同加 `v>0`。存量用 `sync_wind_fields.py hk` 重取修正（3483 费率 0→0.50%、9 只成立日、12 只规模）（2026-10-05）|
| 39 | ETF「跟踪指数名称」与站内指数库/**指数改名**不同步：港交所 3469 被 Wind 措辞写成「恒生港股通红利低波动」、3031 多「指数」尾巴；恒生指数公司把 HSHYLV 官方更名为「恒生港股通红利低波动指数」后**全站 8 处 trackName + 联接基金产品名仍旧名** | ETF.trackName 由 Wind/Excel 各自写入，**无单一事实来源**；指数更名无联动机制，只改指数库不会传染到全部引用处 | `sync_wind_fields.py` 新增 `_index_name_map()`：4 个取数模块（cn/hk/etf/fund）在 trackCode 命中指数库时一律 **trackName = 指数库 `name`**；**指数改名只需改 `indexData` 一处，全站 ETF 自动跟随**（2026-10-05）|

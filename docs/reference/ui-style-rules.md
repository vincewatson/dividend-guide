# 前端样式规则（reference）

> 来源：《网站更新与数据管理对照文档》（2026-08-22 拆分；原件归档为 `docs/_archived_网站更新与数据管理对照文档.md`）**规范篇**「前端样式约定」+ 文末「Mobile 版本 CSS 样式要求（2026-08-17 汇总）」（整段并入为「移动端样式规则」）。
---

> 本文档内容迁移自《网站更新与数据管理对照文档》（2026-08-22 docs 重组）。
> 当前唯一权威规范以 `reference/` 与 `data-governance/` 下的文件为准；`changelog/` 只是历史记录，不代表当前状态。

## 设计 Token 速查（全站统一，2026-09-20 汇总）

> 新增任何 UI 前先对齐下表；「最近对话里给的偏好」都收敛在这里，不要再逐次重新定。

| Token | 值 | 用途 |
|---|---|---|
| 主色 | `#4680FD` | 链接 / hover / 选中态（蓝底白字，或蓝字加粗）/ 股息率列 / 图表主线（**2026-10-03 完全对齐 ElevenReader**，由 `#001AFF` 改）|
| 次要文字 | `#767676` | 标签标题、来源行、meta、非选中项（ElevenReader neutral-500，由 `#8e8e93` 改，2026-10-03）|
| 正文 | `#404040` | 正文（由 `#3a3a3c` 改，2026-10-03）|
| 标题 / 墨色 | `#000000` | 卡片 / 区块标题、表格名称、导航项、姓名等**所有原「墨色」文字统一为纯黑**（2026-10-03 用户要求完全对齐 ElevenReader：由深藏青 `#1a2b45` 改为纯黑。历史：2026-10-01 曾由 `#1c1c1e` / `#111` / `#23262f` / `#1e2a4a` / `#2c2c2e` 收敛为 `#1a2b45`；`#4a4f5e` 次级灰 → `#525252`）|
| 外框 | `#e5e5e5`（1px） | ⚠️ **已基本被 `--line-soft` 取代**：2026-10-03 两轮统一后，控件 / 标签 / 卡片 / 分隔线的外框一律改 `var(--line-soft)`（`rgba(0,0,0,0.06)`）。`#e5e5e5` 现仅余作**背景填充**（`.fund-card .tag` / `.knowledge-item .tag` / `.hint` 圆 / `.detail-slider-track` 底）与图表网格线 `CHART_C_GRID` |
| 表头背景 | `#fff`（`--th-bg`） | **全站表头统一纯白底**：`.asset-table-header` / `.index-table th` / `.blog-overlay-body th`；hover 用 `--th-bg-hover`（=`--hl-lilac: rgba(70,128,253,0.05)`，与顶部二级菜单 hover **同色浅紫**；2026-10-03 品牌蓝变更后同步为 `rgba(70,128,253,…)`） |
| 细分隔线（统一）| `rgba(0,0,0,0.06)`（`--line-soft`） | **全站「浅灰线」唯一色**（2026-10-03 用户多次强调「所有类似的线条都统一成 header 下沿那种很浅的浅灰」；叠白底 ≈ `#F0F0F0`、像素亮度 ≈ 240）。① **分隔线**：`.top-bar` 下沿 / `.site-footer` 上灰线 / `.footer-bottom` 下灰线 / 表头分隔线（`.asset-table-header`、`.index-table th`、`.blog-overlay-body th`）/ `#pageWeekly .df-day-h` 底线 / `.df-cal-acts` 顶线 / `#pageWeekly ul.df-items li` 条目线 / `.detail-card-section + .detail-card-section` 分块横线 / `.blog-overlay-content hr` / `.blog-overlay-body th,td` 表格网格；② **组件外框（2026-10-03 第二轮统一）**：`.index-tag` / `.df-chip` / `.df-btn`（含 disabled hover）/ `.detail-chart-range`（分段控件）/ `.index-dd-menu`（A–Z 下拉面板）/ `mobile.css` 的 `.index-table tr`（手机列表卡片）/ `.df-cal.cal-open .df-cal-toggle` 底线。**❌ 不用于**：背景填充色（`.fund-card .tag` / `.knowledge-item .tag` / `.hint` 圆 / `.detail-slider-track` 底）与图表网格线 `CHART_C_GRID` |
| 表头分隔线 | `var(--line-soft)`（`--th-line`） | 表头与表体之间一条**浅灰细线**——2026-10-01 原为**纯黑实线**，**2026-10-03 用户要求改与顶栏下沿同色**（浅灰）。⚠️ **列表页表头必须用 `box-shadow: inset 0 -1px 0 var(--th-line)` 绘制，禁用 `border-bottom`**：`.index-table` 是 `border-collapse: collapse` + `th` 又 `position: sticky; z-index:3`，`border-bottom` 会被**绘制两次**（`0.06` 叠成 ≈`0.116`、渲染 ≈`#E2E2E2`/226，比顶栏深一倍）；inset 阴影只由 `th` 自身画一次 → 与顶栏同为 240。`.asset-table-header` 是普通 div（非 collapse 表格），仍用 `border-bottom: 1px solid var(--th-line)`（单涂，240） |
| 表头文字 | `#000000`（`--th-fg`） | 表头默认文字（纯黑，与全站墨色一致）；表头内的**个性化彩色 / 浅灰文字除外**（当前排序列图标 = 主色 `#4680FD`、普通排序图标 = `rgba(0,0,0,.45)`） |
| 成功绿 | `#10b978` | 复制成功等成功态文字（ElevenReader green-500，2026-10-03）|
| 涨（正） | `#dc2626` | 上涨 / 当日涨跌幅为正（ElevenReader red-600，2026-10-03）|
| 跌（负） | `#059661` | 下跌 / 当日涨跌幅为负（ElevenReader green-600，2026-10-03）|
| 图表主线蓝 | `#4680FD` | 详情页图表主线（该指数/资产股息率，仅图内；2026-10-03 由 `#1B4B8F` 对齐品牌蓝）|
| 基准线绿 | `#15A877` | 余额宝 / 一年期整存整取基准线（仅图内；2026-10-03 由 `#12794D` 改，ElevenReader success 绿）|
| 图卡标题深蓝 | `#171717` | 详情页图表卡片第一行标题（仅图卡；2026-10-03 由 `#0E2747` 改，ElevenReader chart-title）|
| 图卡灰蓝 | `#737373` | 图表卡片更新日期 / 图例文字 / 说明行 / 坐标轴（2026-10-03 由 `#5C7391` 改，ElevenReader chart-tick/tertiary）|
| 区间按钮文字 | `#525252` | 区间分段按钮未选中态文字（选中态 = `#4680FD` 底 + 白字；2026-10-03 由 `#3A5272` 改）|
| 占位符 | `—`（em dash） | 缺数据一律此符号（禁 `-`/`--`/`暂无…`） |
| 内容宽度 | `1280px`（`--content-max`） | 表格 / 筛选器 / 顶部导航内容盒统一宽 |
| 圆角 | `0`（直角） | **全站默认直角**（2026-10-01 用户要求：控件圆角全部回退直角）；**非零圆角仅剩三类**：`--r-ctl` = 6px（**首页 `.reminder` 与资产详情红色提示条 `.reminder-warn`**）、提示气泡 `.hint-tip` 6px、`50%`（圆形头像 / 问号 / **详情页图表滑块手柄 `.detail-slider-handle`**，2026-10-03）——见「字号 / 行高 / 圆角令牌」 |
| 阴影 | 一律不设 | 仅浮动交互元素（下拉 / 气泡 / tab 高亮）例外（**滑块手柄 2026-10-03 起去阴影**） |
| 图标 / 箭头 | 内联 SVG | 复用 PC 一级菜单 chevron `<path d="M6 9l6 6 6-6">`（14×14、`currentColor`）；❌ 不用 `▾ / ▴ / >` 文本字符 |
| 字体（拉丁 / 数字）| **`Arial`**（置于字体栈最前） | **2026-10-03 用户要求：英文 / 数字 / 符号统一用 `Arial` 起头**（当日本日早些时候曾一度改为自托管 `Inter` 完全对齐 ElevenReader，随后按要求**整体回退 Arial**）：栈 = `Arial, -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', 'Helvetica Neue', sans-serif`；中文仍走 **`PingFang SC`**。**自托管 Inter 已删除**（`@font-face` 与仓库 `fonts/` 目录一并移除，页面不再拉取 woff2）。**详情页图表 canvas 同步回退 Arial**（`CHART_FONT_NUM` = `'Arial,"Helvetica Neue",Helvetica,sans-serif'`、`CHART_FONT_TXT` = `'Arial,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif'`，`ctx.font` 亦 Arial）。改字体要同时改 `body` 的 `font-family` **和** 图表 `ctx.font`（canvas 不复用 CSS 字体）。历史：2026-09-20 起用 Arial；2026-10-03 一度改 Inter，同日回退 Arial |
| 禁用符号 | ❌ `【】` | 资讯正文及任何正文一律不加【】等强调符号（详见 `data-format-rules.md` 显示格式统一） |

### 字号 / 行高令牌（2026-10-03：常规文字统一 14px）

> 全站 CSS **一律引用令牌，不再散写裸 px 字号 / 行高**。**2026-10-03 先按用户要求把「字号 + 颜色 + 字体」完全对齐 ElevenReader（elevenreader.io）**（正文 17px）；随后实测**「中文 12px 明显比英文 12px 偏小」**，用户再次要求：**全站常规文字统一为 `14px`（含顶栏）**。当前口径 = 常规文字（小字 / 小正文 / 紧凑正文 / 正文基准）**一律 `14px`**，微字（角标 / 图标 / 标签）保留 **`12px`**，标题 20–30px、展示 34–46px。历史：2026-09-27 曾收敛为 11 档（10–38px）。

**字号 `--fs-*`（11 档）**

| 令牌 | 2026-09-27 旧值 | 当前值（2026-10-03 二次修订） | 用途 |
|---|---|---|---|
| `--fs-2xs` | 10px | **12px** | 微字：图标、角标、标签、副标题 |
| `--fs-xs` | 11px | **14px** | 小字：次级标签、注脚、食息资讯条目区 |
| `--fs-sm` | 12px | **14px** | 小正文：表格、按钮、工具栏 |
| `--fs-md` | 13px | **14px** | 紧凑正文 |
| `--fs-base` | 14px | **14px** | 正文基准（`body`） |
| `--fs-lg` | 16px | **20px** | 卡片标题 / 强调 |
| `--fs-xl` | 18px | **22px** | 区块标题 / 详情页指标名称标题 |
| `--fs-2xl` | 20px | **26px** | 大数字（移动卡片右上角关键数字） |
| `--fs-3xl` | 22px | **30px** | 博客 h2 / 详情返回箭头 / 收藏☆（原「详情页指标名称标题」已于 2026-10-03 改用 `--fs-xl`）|
| `--fs-4xl` | 28px | **34px** | 超大标题 / 头像 |
| `--fs-5xl` | 38px | **46px** | 空态图标 |

> 说明：常规四档（`--fs-xs` / `--fs-sm` / `--fs-md` / `--fs-base`）**同值 `14px`**，按用户「常规字号统一改成 14px」要求执行；标题档（`--fs-lg`–`--fs-5xl`）保持 2026-10-03 ElevenReader 对齐值**未动**。⚠️ 后续若新增「大于 14px 的正文档」需重新引入档位。**2026-10-03（v0.1.47，用户要求）**：详情页正文最大标题 **`.detail-index-title`（指标名称）由 `--fs-3xl`（30px）改为 `--fs-xl`（22px）**，与首页区块标题 `.section-title` 字号一致（字重 / 颜色 / 字距不变）；令牌 `--fs-3xl` 仍为 30px，仅该消费方改档（`--fs-3xl` 现用于 `.detail-back` / `.detail-fav-btn` / 博客 `.blog-overlay-body h2` / `.blog-detail-title`）。

**行高 `--lh-*`（5 档）**：`--lh-1:1`（单行图标）/ `--lh-tight:1.2`（标题，向 ElevenReader 110% 靠拢但给中文留余量；原 1.3）/ `--lh-snug:1.4`（UI 紧凑，= ElevenReader 140%；原 1.5）/ `--lh-body:1.6`（正文）/ `--lh-loose:1.7`（长文、通栏说明）。

**图表字号**（canvas，随全站放大）：`CHART_FS_TICK` 12→13、`CHART_FS_END` 13→14、`CHART_FS_TIP` 12→13。

**圆角**：**全站控件 / 卡片 / 表格 / 纯展示标签一律 `0`（直角）**。非零圆角仅剩三类：① `--r-ctl`（**6px**）——使用者 = 首页 `.reminder` 与资产详情红色提示条 `.reminder-warn`（2026-10-04 新增）（2026-10-01 用户要求，其余控件由 2026-09-27 Tier1-③ 的 6px 全部回退为直角）；② 提示气泡 `.detail-chart-title .hint .hint-tip` / `.detail-info-row .hint .hint-tip` 的 `6px`（浮层气泡，未随回退改动）；③ 圆形 `50%`（`.profile-header .avatar`、`.hint` 问号、**详情页图表滑块手柄 `.detail-slider-handle`**，2026-10-03）。移动端另有 `mobile.css` 的 1px 细小横条圆角。

**间距 · 内容框体上下内边距**：**非表格内容框体统一 `--pad-row: 18px`**（2026-10-03 用户要求「全站正常内容区域框体内，文字到上下沿的距离统一且合理」）；**表格行/表头另用专用令牌 `--pad-row-tb: 11px`**（2026-10-03 二次：用户要求「表格每一行行高缩 ~1/4」，18→11 → 行高 56~59px 缩到 **42~45px ≈ −25%**）。应用于这些框体的**纵向** padding（横向各自保留不动）：① **表格（用 `--pad-row-tb: 11px`）**——`.asset-table-header`、`.asset-row`、`.index-table th/td`、平板 `.index-table th/td`（`mobile.css`）；② 列表项——`#pageWeekly ul.df-items li`、`.df-day-h`（底线间距）、`.detail-info-row`；③ 内容卡——`.df-day`、`.df-cal`、`.fav-item`、`.blog-card`、`.knowledge-item`、`.detail-main-card`、`.detail-chart-area`、`.reminder-warn`、`.reminder`；④ 筛选面板——`.index-tagbar`、`.df-toolbar`。非表格内容框体文字到上下沿距离统一 **≈20.8px**（18px padding + 约 2.8px 半行距）；**表格行高见 ①（现 42~45px）**。**例外 / 未改**：footer（用户明确要求文字离上下沿更远，见页脚规则）、顶栏、`.profile-header`（hero 32px）、胶囊控件（`.index-tag`/`.df-chip`/`.df-btn` 纵向仅 4px，属控件非内容框体）、空态 / toast、以及 `mobile.css` 手机卡片 `.index-table tr`/`.asset-row`/`.m-card`（卡片而非表格行）与 `.blog-overlay-body th/td`（仍 18px）。

**对齐 · 模块盒贴边、盒内文字留白**（2026-10-03 两次修订后的最终口径）：**内容模块的「盒子」对齐内容区左右沿**（`--content-max` 内容盒，桌面 1440 视口下 = 80 / 1360），但**盒内的文字保留舒适内边距**——❌ 不要把文字顶到盒边。即表格盒 / 卡片盒 / 面板盒横跨 80→1360，其内部文字各自内缩：列表单元格左右 **8px**、首页资产表 **12px**、`.reminder` **20px**、`.df-cal` **16px**、`.df-day` **20px**、`.fav-item` **16px**、`.blog-card` **20px**、`.knowledge-item` **18px**、`.detail-main-card` **22px**、`.detail-chart-area` **20px**。**唯一例外 = 筛选面板** `.index-tagbar`/`.df-toolbar`——其内容是**胶囊控件**，用户明确要求标签行顶到内容区两端，故左右内边距 = 0。⚠️ 历史：2026-10-03 曾一度把所有内容模块左右内边距清零（v0.1.32「文字贴边」），用户反馈**「改过头了」**（表格 / reminder / 很多内容页文字离框边太近）→ **v0.1.33 已整体回退**，恢复盒内留白。**不变**：footer（盒级 `.footer-inner`/`.footer-map`/`.footer-cols` 已对齐 80/1360）、顶栏、`.profile-header`、胶囊控件、空态 / toast、博客阅读浮层。

**表单控件**：`button / input / select / textarea` 显式 `font: inherit` + `font-size: inherit`（否则 Chrome 对表单控件用 UA 默认 `13.3333px`，破坏字号阶梯）。

**顶栏（header）文字统一（2026-10-03 用户要求）**：`.top-bar` 内的**所有文字统一 `14px`、默认纯黑 `#000`、加粗 `700`**——覆盖 `.brand-name`（站名 / 详情页标题）、`.brand-subtitle`（副标题 / 「点击返回」）、`.main-nav-item`（一级导航）、`.dropdown-item`（二级菜单）、`.nav-btn`（「我的」）与 `#verBadge`（版本号，原 12px 灰 / 400）。**选中态**仍用品牌蓝 `#4680FD`（`.active` 的 `font-weight` 由 600 提到 **700**，与默认同粗，仅靠颜色 + 下划线区分）。桌面 / 平板（`mobile.css` 768–1024）/ 手机三档同步。**例外（非文字，不参与统一）**：`.brand-icon`（logo 方块 / 详情页返回箭头）、`#detailFavBtn`（☆ 收藏图标）。⚠️ **同日二次修订**：顶栏原定 `12px`，因「中文 12px 偏小」改回 **`14px`**（= 全站常规字号）。⚠️ **同日三次修订（2026-10-03）**：首页顶栏 logo 区**只保留站名「食息指南」四个字**——移除首页 `.brand-subtitle`（「低利率时代的理财之道」）与 `#verBadge`（版本号）；`#verBadge` 迁移到页脚底栏 `.footer-ver`（保留同 id，部署 / 复验流水线仍可读）。**详情页顶栏的 `.brand-subtitle`（「点击返回」）是返回控件的一部分，保留不动**；`#verBadge` 规则（14px/`#000`/700）随元素一并迁至页脚。

## 前端样式约定

1. 红利指数浏览器"股息率"列：亮蓝 `#4680FD` + 加粗（`.col-yield`）；各列表/详情页"管理费率"默认黑色正常字重，不套用 yield 类。
2. "最近分红日期"仅存在于基金/ETF（详情页 + 月月分红列表），**指数无此概念**。
3. **Footer 规则**（08-04 确立；08-05/08-10 修订；**2026-09-27 改造为「网站地图 + 单源渲染」**）：
   - **结构 = 网站地图**：`.site-footer > .footer-inner > ( .footer-map[ .footer-brand + .footer-cols ] + .footer-bottom )`。
     - `.footer-brand` 与 `.footer-cols` 是**两个独立容器**（❌ 绝不合并成同一张 grid：合并后新增列会落到品牌正下方，语义错）；宽屏 `.footer-map` = `minmax(260px,1fr) auto`（品牌列拉伸、列区按内容宽右置、中段 gap 留白）。
     - 品牌块：**站名（`--fs-lg` / 700 / `#000000`，由首页顶栏 `.brand-name` 派生，即「食息指南」）+ 其下方一行副名小字**；整块 = 首页入口，链接用 **inline-flex**（可点区域只覆盖文字宽度，❌ 不用块级 flex）。**2026-10-03 用户要求（v0.1.43）：品牌名下方加一行副名小字「低利率时代的理财之道」**——新增 `.footer-brand-subtitle`（`--fs-2xs`＝12px、`#767676`、`margin-top:3px`），**文案写死为常量**（❌ 不再由 `_footerBrandText` 派生，避免再次取到详情页头部文字）。注：同日前一版曾因 `_footerBrandText('.brand-subtitle')` 命中 DOM 中**第一个**副标题（＝详情页头部「点击返回」）而删除过副名，本次以写死文案方式恢复。品牌块**只放站名 + 副名两行**（❌ 不放快捷链接——无二级的一级菜单同样是列，见下）。**2026-10-04 用户要求（v0.1.64，最终版）：页脚品牌块**去掉红蓝图形**，站名「食息指南」与副名「低利率时代的理财之道」**都用黑色字体**（v0.1.62「站标在站名上方」与 v0.1.63「站标在左侧 + 默认浅灰 / hover 彩色」均作废）**——`.footer-brand-link` 回退为**纵向** `inline-flex`（`gap:1px`，站名在上、副名在下）；`.footer-brand-name` 保持 `--fs-lg`/700/`#000000`；`.footer-brand-subtitle` 由 `#767676` 改 **`#000000`**；删除 `.footer-logo` / `.footer-brand-titles` 及 v0.1.63 的浅灰默认与 hover 变色规则（页脚品牌块**不再随 hover 变色**）。⚠️ 首页**顶栏**的红蓝站标不受影响（只动页脚）。
     - 列区：**所有一级菜单各占一列**（首页留作品牌块；本项目当前 5 列：食息资讯 / 红利指数 / 月月分红 / 子弹列车 / 我的），**固定列宽 140px 左对齐**；**列标题即入口**（`<a class="footer-group-title">` 可点、hover 变蓝，点击进该栏目；有二级的在其下列出二级链接，无二级的标题即为该列唯一入口）。**列标题（每列第一行）= 一级菜单链接，2026-10-03 用户要求改纯黑 `#000000`**（原 `#767676`）；二级子链接 `.footer-link` 仍为灰 `#767676`。**列内链接行距（2026-10-03 用户要求「略放宽、但勿过多」）**：`.footer-group` 纵向 gap `6 → 8px`、`.footer-link` 行高 `1.6 → 1.75`（14px×1.75=24.5px），实测相邻链接 pitch `28 → 32/33px`（≈+15%）。末尾「相关站点」列为外链（`target="_blank" rel="noopener"`），**须用户确认后才渲染**（`RELATED_SITES = []` 为空则整列不输出，❌ 不自行编外部链接）。
     - 底栏：**两行**——① `© <年> 食息指南 · 本网址所呈现的数据和信息仅为交流学习之用，不保证及时更新，也不作为面向任何人的投资建议。`（`.footer-copyright`）② `🚄 Embrace a world that never stops moving forward. Created by AERO.`（`.footer-aero`）。**2026-10-03 用户要求删除版本号**：原第三行 `.footer-ver`（`#verBadge`）已整条移除——CSS 规则 `.footer-ver`、`renderFooter()` 的 `'<div class="footer-ver">…'`、以及两处 `vb.textContent='vX.Y.Z'` 写入、`_footerBrandText` 内的 `#verBadge` 清理分支全部删除；版本仅保留在 `<meta name="app-version">`。**2026-10-03 用户要求两行字号一致**：`.footer-copyright` 由 `var(--fs-xs)`（14px）改为 **`var(--fs-2xs)`（12px）**，与下方 `.footer-aero`（12px）相同（颜色不变：版权 `#767676`、AERO `#949494`）。（年份北京时间现算；免责声明属法律文本，正文不改）。
     - **上下留白（2026-10-03 用户要求「各增一倍」）**：品牌块 + 列区（`.footer-map`）与**上灰线**（`.site-footer` 的 `border-top`）、**下灰线**（`.footer-bottom` 的 `border-top`）之间的间距**各翻倍**——上 = `.global-footer` / `.detail-footer` 的 `padding-top` `16 → 32px`（实测含 1px 线 = 33px）；下 = `.footer-bottom` 的 `margin-top` `26 → 52px`。`.footer-bottom` 的 `padding-top: 14px`（灰线向下到版权文字）与 `.detail-footer` 的 `margin-top`（与上方卡片留空）**见下**。
     - **⭐「上灰线 ← 主体内容」间隔（2026-10-03 二次，用户要求「太近了，增加一倍左右」）**：即 footer 元素**之上**（灰线以上）与上方内容之间的空白。来源分两类——① 全局 footer（首页 / 列表页 / 食息资讯等）：原间隔由 `.page { padding-bottom: 28px }` + 末元素自身 margin 提供（首页 ≈40px、列表 ≈32px）；**给 `.global-footer` 增加 `margin-top: 40px`** → 首页 **40 → 80px**、列表 **32 → 72px**、食息资讯 ≈68px；② 详情页 footer：原为 `.detail-footer { margin-top: 16px }` → **`16 → 32px`**（桌面 `margin: 32px -28px 0`、平板 `32px -10px 0`〔mobile.css〕、手机 `32px -14px 0`）。改动**只加在 footer 自身**（`.global-footer` 的 `margin` 简写 `40px -15px 0 0`、`.detail-footer` 的 `margin-top`），不动 `.page` / `.detail-body` 的内容 padding。⚠ `.global-footer` 原有 `margin-right:-15px`（滚动条补偿）须保留。`mobile.css` 因平板区间改动 → `?v=55 → 56`。
   - **单源渲染（本轮修掉的根因）**：7 处 `.site-footer` 均为**空壳容器**，正文由 `index.html` 的 **`renderFooter()`** 统一写入（读 `#mainNav` 的 `.main-nav-item[data-tab]` + 其 `.dropdown-item[data-sub]`，再补 `.nav-right #profileBtn`「我的」）。
     - 改导航栏目 → 页脚自动跟随；改页脚文案 → 只改一处（`renderFooter`）。
     - ⚠ **只改 CSS 基类 ≠ 全站一致**：CSS 一处生效，但 HTML 旧版是 **7 份静态副本**（改文案要改 7 处、易漏）——本轮已收敛为 1 处渲染（`grep -c 'class="site-footer' index.html` 仍为 7＝容器数，但页脚正文在源码里只出现 1 次）。
     - ⚠ **窄屏 `mobile.js` 会把 `#mainNav` 重构成抽屉**（`.m-nav-drawer`）并把 `.dropdown-item` 搬到兄弟容器；`renderFooter()` 在移动脚本**之前**执行、读的是原始桌面导航，故页脚在窄屏仍完整（勿把 `renderFooter` 挪到移动脚本之后）。
   - **视觉**：**纯白底 `#fff`、无任何装饰层**（2026-09-27 用户要求：先去掉右下青绿光晕、再去掉整个光晕，最终只留纯白 footer —— 原 `.site-footer::before`（径向光晕 + 渐变打底）**整条已删除**；仅保留顶部细分隔线（`.site-footer` 的 `border-top`，**2026-10-03 起 = `var(--line-soft)`＝`rgba(0,0,0,0.06)`**，与顶栏下沿 / 表头分隔线同色；原 `#e5e5e5`）。更早的深色 `#21292e`、以及「浅色 `#ffffff` + 极浅蓝色炫彩」均不再使用）；`.footer-inner{position:relative;z-index:1}` 保留（装饰层已删，不影响视觉）；链接 `#767676` → hover `#4680FD`；保持直角、无阴影、hover 只变色不出下划线。（若将来改回深色底，必须单独覆写页脚链接色：全局深蓝 hover 在深底上几乎不可见。）
   - **继续成立（铁律，不许为新页脚破掉）**：footer **不悬浮**（`position:relative` 跟随滚动）；首页 footer 在 `.main-content` 内、**详情页 footer 必须在 `.detail-body` 内部**；全宽负 margin（桌面 `margin:16px -28px 0; width:calc(100% + 56px); max-width:none`；≤767 `margin:16px -14px 0; width:calc(100% + 28px)`，**与 `.detail-body` 的 media query 成对修改**）；与上方卡片留 `margin-top:16px`；❌ 禁止把 footer 移到 `.detail-body` 外部、禁止 `-43px` 大负 margin。
   - **内容与 1280 对齐**：`.footer-inner` 左右 padding = `max(var(--page-pad), calc((100vw - var(--content-max)) / 2))`（与 `.top-bar` 同口径）→ 页脚内容左边缘 == 表格左边缘；横向 padding 从 `.global-footer`/`.detail-footer` 移到 `.footer-inner`（`100vw` 口径，避开 `.global-footer` 的 +15px 滚动条补偿偏差）；≤767 覆写为 14px。
   - **响应式**：≥1121px 品牌列 + 列区（5 列 ×140px）右置；≤1120px 单列（品牌独占一行、列区 3 列）；≤767px 列区 2 列、间距 24px（窄屏断点用本项目 767 口径，非参照站 720）。⚠ 宽屏两栏总需宽 ≈1112px，故两栏断点由早先的 1100 提到 **1121**（否则 1101–1120 区间 5 列会横向溢出）。
4. **无阴影 + 外框**（08-04/05）：表格/卡片不设 box-shadow（仅浮动交互元素：下拉/气泡/tab 高亮保留阴影；滑块手柄 2026-10-03 起去阴影）；数据可视化区保留 1px 浅色外框（`.asset-table` #e5e5e5、`.detail-main-card` #e5e5e5、`.fund-card`/`.knowledge-item`/`.fav-item`/`.fav-empty`/`.blog-card`/`.blog-empty` #e5e5e5、`.detail-chart-select` #e5e5e5）。
   - **食息资讯（日报）区块**（2026-09-20 统筹对齐）：卡片 `.df-toolbar`/`.df-day`/`.df-cal` **白底无边框**（同 `.fund-card`）；控件外框/条目分隔线统一 `1px #e5e5e5`；主色统一 `#4680FD`（链接、hover、月历选中、标签选中态=蓝底白字加粗）、次要文字 `#767676`、正文 `#404040`、标题 `#000000`、字号 12–13px、全局直角。
5. **详情页溢出控制**（08-05/10 修订）：`.detail-body` 用 `overflow-x:hidden`；`.detail-card-section` **不得设 overflow**（`hidden`/`overflow-x:hidden` 都会裁剪 hint 气泡，向上弹出超出 section 顶部被裁）；滑块 handle 定位（**手柄外缘贴区间边界**）：左 `calc(p0%)`、右 `calc(p1% - 16px)`——左缘对齐 p0、右缘对齐 p1，两端（p0=0 / p1=100%）可顶到轨道尽头。⚠️ **2026-10-03 修正**：左手柄原为 `calc(p0% + 8px)`（比右手柄多内移 8px，导致最左时留 8px 白、左右不对称），已改为 `calc(p0%)` 与右手柄镜像。**滑块手柄视觉（2026-10-03 用户要求）**：`.detail-slider-handle` = **纯圆形**（`border-radius:50%`）、**空心**（内部白 `#fff` + 外框 `1.5px solid #000000`）、**无阴影**、**无 `|||` 抓手**（HTML 内的 `|||` 字符已移除）；桌面 `16×16`（= JS 定位假设的半宽 8px），`mobile.css` 手机 `22×22`。
6. **详情页基准线**（08-05 初定，2026-09-20 视觉重做换色）：余额宝 7 日年化基准线为**绿色实线 `#15A877`**（线尾圆点/数值标签/hover 圆点与气泡内数值/图例均同色）；主曲线深蓝 `#4680FD` 实线（线尾标注同色）。天弘余额宝详情页的基准线对标"一年期整存整取"，其余资产为"余额宝七日年化收益率"。
7. **展示内容区宽度统一 `1280px`**（2026-09-20 用户要求：表格 / 筛选器 / 顶部导航 三处宽度统一）：
   - `:root { --content-max: 1280px; --page-pad: 28px }` —— 口径是**内容盒**宽 1280px。
   - `.page { max-width: calc(var(--content-max) + var(--page-pad) * 2); margin-left/right: auto }` → 容器外框 1336px 居中；表格（`.index-table-wrap`/`.asset-table`）、筛选器（`.index-tagbar`/`.df-toolbar`）、卡片随之全部 = **1280px**（1920/1440 视口实测：x 居中、宽 1280）。
   - 顶部导航（首页 + 6 个详情页头部共用 `.top-bar`）：`padding-left/right: max(var(--page-pad), calc((100% - var(--content-max)) / 2))`。推导：`.page` 内容左边缘 = `(100% - 1336)/2 + 28 = (100% - 1280)/2`；**白条本身仍满宽**，只有内容内缩。不支持 `max()` 的老浏览器自动回退 28px（与改动前完全一致）。
   - 详情页 `.detail-body` 同口径：`max-width: calc(...); margin-left/right: auto; width: 100%`（flex 列内 auto margin 水平居中）。1920 视口实测：详情页头部内容左边缘 == 正文内容左边缘 == 卡片左边缘 == 320px。
   - ❌ 不要把 `max-width` 加在 `.main-content`（它是滚动容器，会让滚动条内缩、偏移）。
   - **页头是 fixed 覆盖层**（2026-09-27 起，首页 + 6 个详情页共用的 `.top-bar`）：`position:fixed; top/left/right:0`，背景 `rgba(255,255,255,0.70)`（2026-09-27 由 0.88 逐步调到 0.70） + `backdrop-filter:blur(20px)`；主内容 `.main-content` 用 `padding-top: var(--topbar-h)` 等高占位（布局与改动前逐像素一致）→ **内容从页头下方穿过**，透明才可见。`--topbar-h` 由 `syncHeaderHeights()`（含 `ResizeObserver`、`resize`/`orientationchange`）实测 `.top-bar` 高度写回（**2026-10-04 起：桌面/平板默认 64px**（原 60px）、**≤767 手机 60px**（原 52px，2026-10-04 二次调整），兼容 safe-area），**不写死**；详情页 `.detail-body` 同用 `padding-top: var(--topbar-h)`。⚠️ 同页 `.index-table th` 的 `position:sticky` **须保持 `top:0`**（不可改成 `var(--topbar-h)`，会把表头下推 60px 留空隙）；并且 `.index-table-wrap` / `.index-table` **须保持 `overflow:visible`** —— 若任一轴非 `visible`，表格会变成自身的粘性滚动容器、表头即失效（2026-09-27 Tier1-② 已修复，详见「七、长表吸顶表头」）。
   - **首页顶栏无 logo**（2026-09-27 用户要求「去掉网站左上角的 logo」）：`.brand` 内**不再有** `.brand-icon`，只保留 `.brand-text`；**2026-10-03 用户要求「logo 区只保留『食息指南』四个字」** → `.brand-text` 内**仅剩 `.brand-name`（「食息指南」）**（副标题已移出；版本号 `#verBadge` 亦于 2026-10-03 从**页脚**一并删除，全站不再显示版本号，仅 `<meta name="app-version">` 保留，见第 3 条页脚）；文字左缘 = 内容左边缘（桌面 28px / 手机 14px）。**2026-10-03 用户要求（v0.1.43）：把「食息指南」做成首页入口链接**——首页 `.brand-text` 由 `<div>` 改 `<a class="brand-text brand-home-link" href="#/">`（`text-decoration:none; color:inherit; cursor:pointer`，hover 站点名变蓝 `#4680FD`），点击回首页（hash → `#/` → `applyRoute('')`）。注：`_footerBrandText()` 选择器 `.top-bar .brand-text .brand-name` 仍命中该 `<a>` 内的 `.brand-name`，页脚站名不受影响；6 个详情页头部仍是「返回」控件，不改。⚠️ **6 个详情页头部仍保留 `.brand-icon`**——那里是**「返回」箭头**（功能控件，`#detailBack` 等，`cursor:pointer`），与首页 logo 语义不同，`.brand-icon` 的 CSS 规则因此保留。**2026-10-03 用户要求（v0.1.41）：该「返回」控件去掉蓝底（`background:none; box-shadow:none`）、箭头改纯黑（`color:#000`，SVG 22→28px、平板 26px）、文字由「指数详情／点击返回」简化为「返回」**（并移除全站 `.brand-subtitle` CSS 规则与 6 处 DOM 副标题）。页脚品牌名由 `.brand-text .brand-name` 派生，不受影响。**2026-10-04 用户要求（v0.1.59）：在「食息指南」四字之前加回一个图标（= 网站 favicon `favicon.svg` 红蓝双圆），并要求图标上下沿与四字上下沿一致**——① `.brand-home-link` 改 **`display:inline-flex; flex-direction:row; align-items:center; gap:7px`**（图标 + 文字横向、垂直居中、间距 7px）；② 图标插在 `<span class="brand-name">` 之前；③ **尺寸与对齐**：用 canvas `measureText` 实测「食息指南」在 **14px/700** 下的**汉字字面墨迹高 = 13.174px**（非 line-box 高），据此定图标高度；flex 的 `align-items:center` 按 **line-box 中心**对齐、而 CJK 墨迹中心比 line-box 中心低约 **0.844px**，故加 **`transform: translateY(-0.84px)`**。⚠️ **同日二次修订（v0.1.60，用户反馈「太小了，上沿应是圆圈的上沿而非图片的上沿」）**：v0.1.59 直接 `<img src="/favicon.svg">` 并令**图片盒** = 13.17px → 因 `favicon.svg` 画布 512×512、两圆墨迹仅占中间 **460.8×264.4**（上下各留白 ~123.8px），实际圆圈只有 **~6.8px 高**。改为**内联 `<svg>` + 紧贴圆圈的 viewBox**：`viewBox="25.6 123.8 460.8 264.4"`（两圆 cx=157.8/354.2、cy=256、r=132.2，渐变 id 用页面唯一的 `blRedGrad`/`blBlueGrad`）→ **图标盒 = 圆圈墨迹**；`.brand-logo { width:22.96px; height:13.17px; transform:translateY(-0.84px) }`（高 13.17 = 汉字墨迹高；宽按 viewBox 比例 460.8/264.4 = 22.96px，两圆水平并排故非正方形）。实测桌面/手机两档圆圈上下沿与四字墨迹上下沿偏差均 **≤0.02px**。⚠️ **`favicon.svg` 本体不动**（浏览器标签页仍用带留白的方图）；**仅首页顶栏**加图标，6 个详情页头部仍是「返回」箭头（`.brand-icon`），语义不同、不改。**2026-10-04 用户要求（v0.1.61，品牌块改版）**：站名「食息指南」`14 → 16px`，其下新增一行**灰色小字副名**「低利率时代的理财之道」`10px`（`#767676`，与页脚副名同文案）；**红蓝 logo 上下沿改为对齐「站名 + 副名」两行整体**——① HTML 把站名包进纵向容器 `.brand-titles`（`display:flex; flex-direction:column; align-items:flex-start`），下方加 `.brand-tagline`；② **站名 16px 只作用于首页品牌块**：选择器用 **`.brand-home-link .brand-name`**（特异性高于基类 `.brand-name`），故 6 个详情页头部共用 `.brand-name` 的「返回」**仍 14px**（移动端媒体查询里的 `.brand-name{14px}` 也压不过它）；③ **logo 尺寸** = 站名四字墨迹上沿 ~ 副名小字墨迹下沿的**整体**高度（实测 **28.727px**）→ `.brand-logo { width:50.07px; height:28.73px; transform:translateY(-0.63px) }`（宽按 viewBox 比例 460.8/264.4；offset = 整体墨迹中心 − 文字块盒中心 = −0.628px）。⚠️ 顶栏总高约 31.4px（< 60/52px），未溢出。**2026-10-04 用户要求（v0.1.75）：详情页「返回」控件更独立** —— ① **箭头贴近「返回」**：`.brand { gap: 10px → 0 }`，并给 `.brand-icon` 加 `margin-right: -8px` 抵消 28px svg 内箭头墨迹右侧约 13.7px 空白；实测箭头右缘→「返回」= **23.67 → 5.67px（桌面）/ 3.83px（手机）**。② **「返回」与「首页」拉开**：`.index-detail-page .top-bar .main-nav { margin-left: 40px }`（原 24px，**仅详情页**，首页导航不受影响）→ 间距 **24 → 40px**。⚠ `.brand { gap:0 }` 不影响首页（首页 `.brand` 只有一个子元素 `.brand-home-link`，flex gap 不生效）；`.brand-icon` 仍仅 6 个详情页头部使用。**2026-10-04 用户要求（v0.1.76）：详情页「返回」二次微调** —— ① **间距略放宽**：`.brand-icon` 负右边距 `-8px → -3px`，箭头→「返回」= **5.67 → 10.67px（桌面）/ 3.83 → 8.83px（手机）**；② **整块改蓝 `#4680FD`**：`.brand-icon { color:#4680FD }`（仅详情页用）＋ `.index-detail-page .top-bar .brand-name { color:#4680FD }`（覆盖基类黑，**仅详情页**；首页站名不受影响）。
   - **顶栏品牌文字与菜单文字基准线对齐**（2026-10-03 用户反馈「『食息指南』/『返回』与菜单文字横向、纵向都没对齐」）：根因 = `.main-nav-item` 的选中下划线原用 `border-bottom: 2px solid`，占掉 1px 内容高度 → 菜单文字整体比左侧 `.brand-name` **上移 1px**。改为 **`box-shadow: inset 0 -2px 0`**（默认透明、`.active` 时 `#4680FD`）绘制下划线，不参与布局 → 品牌文字与全部菜单项文字同 `top/bottom/cy`（21/37/29）严格对齐；菜单选中下划线位置/外观不变。
   - `.site-footer` 仍为**满宽条**（2026-09-27 起为**纯白底 `#fff`、无装饰层**；更早已废的「深色条」与「浅色底 + 光晕」均不再使用），**条本身**不参与 1280 约束，但**内容层 `.footer-inner`** 用与 `.top-bar` 同口径的 padding 与之对齐（见第 3 条）；`.global-footer` 的 +15px 滚动条补偿逻辑保持不变。
   - ≤1335px 视口：容器不受 1336 限制，表现与改动前一致（1024/768/390 三档实测无横向溢出，`.page` padding 仍为 16/16/12px）。
8. **详情页图表视觉规范**（2026-09-20 视觉重做；设计原则「数据是主角，装饰退到背景」）：6 个详情图表（`detail` / `assetDetail` / `hkEtfDetail` / `cnEtfDetail` / `monthlyEtfDetail` / `monthlyFundDetail`）共用 `drawDetailChart` + `drawChartHover`，**改一处即 6 图同步**；canvas 不继承 CSS 字体，须显式 `ctx.font`。重做只改视觉层，数据与抽稀口径不动。
   - **统一色板**（常量 `CHART_C_*` 定义在 `index.html`）：主线深蓝 `CHART_C_MAIN='#4680FD'`（2px、`lineJoin/lineCap='round'`）；基准线绿 `CHART_C_BASE='#15A877'`（2px）；网格 `CHART_C_GRID='#e5e5e5'`（1px，**只画水平线，不画竖线**）；坐标轴文字 `CHART_C_AXIS='#737373'`；图表区域底色 `CHART_C_CARD='#FFFFFF'`（纯白）；提示框描边同 `#e5e5e5`。**canvas 背景透明**，由外层 `.detail-chart-area{background:#FFFFFF}` 透出（2026-09-20 用户要求恢复白底）。❌ 图表不再用站点主色 `#4680FD` / 旧绿 `#1FBE7F`（那两色仍用于站内链接/按钮，与图表无关）。
   - **渐变面积**：仅主线下方填充 `rgba(70,128,253,0.08)`→`rgba(70,128,253,0)`；基准线不填充。
   - **y 轴**：永远从 0 起；步长取整齐值（`0.1/0.2/0.25/0.5/1/2/2.5/5/10`），选使网格线 ≈5 条（3–7 条）者；`maxY = ceil(数据最大值×1.04/步长)×步长`（避免"最高 10% 而数据仅 5%"）。刻度文字 `整%`（步长 ≥1 不带小数，<1 带一位），如「2%」「0.5%」。
   - **x 轴**：真实时间轴（`Date.parse`），等分 5 个日期刻度；跨度 <200 天用 `MM-DD`，否则 `YYYY-MM`。
   - **线尾标注**：主线、基准线最后一个点各画实心圆点 `r=4.5`，外圈 2px 描边用图表区域底色 `#FFFFFF`；圆点右侧写当前值（如 `5.30%`），颜色与线条一致，字体 `CHART_FONT_NUM` 13px/600；按 `measureText` 实测，靠右超界自动翻转到左侧（不裁切）。`pad={top:14,right:62,bottom:26,left:52}`。
   - **悬停**：竖直虚线 `setLineDash([3,3])`、色 `#737373`，各线对应位置画圆点（`r=4` + 底色描边）；提示框为**浅色卡片**（`#FFFFFF` 底、`1px #e5e5e5` 边框、圆角 6、轻阴影 `rgba(70,128,253,.12)`）：首行日期灰色（`CHART_C_TITLE='#8A97A8'`），其后每行「色块 + 名称 + 数值」，数值右对齐用 `CHART_FONT_NUM`。❌ 不再用深色半透明提示框。
   - **字体**：英文/数字 `CHART_FONT_NUM='Inter,"Helvetica Neue",Helvetica,sans-serif'`、中文 `CHART_FONT_TXT='Inter,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif'`（**2026-09-20 用户要求恢复 Inter**：图表内英文/数字走 Inter，中文因 Inter 无字形自动回退 PingFang SC）；字号下限：坐标轴与日期 **12px**、线尾 **13px/600**、提示框 **12px**；**任何图表文字不得小于 12px**（线尾 ≥13px）。
   - **数据抽稀**：`decimateChartData()` —— 点数 >`CHART_MAX_PTS=500` 时按步长 `ceil(n/500)` 抽样，**必保留最后一个点**；原始全量数据仍存 `chartDataByPrefix` 供 hover 查值。
   - ❌ 不要给 `.detail-card-section` 加 `overflow`；手机端图表规则只写在 `mobile.css` 的 `@media (max-width:767px)` 内。
9. **详情页图表卡片版式**（2026-09-20 版式调整，6 张卡片同规格）：
   - **头部两行**：第一行 `.detail-chart-header` = 标题 `.detail-chart-title`（文案「历史走势」，16px / 600 / `#171717`）在左 + `.detail-chart-update`（12px / `#737373`）在右（`align-items:baseline`）；第二行 `.detail-chart-legend` 一行内 = 图例 `.detail-legend-items` 在左 + 区间切换 `.detail-chart-range` 在右（`justify-content:space-between`）。
   - **图例**：`.detail-legend-item` 12px / `#737373`，项间距 **16px**；线段色块 `.detail-legend-line` **16×2px**，`.blue = #4680FD`、`.orange = #15A877`（**必须与图中线条同色**）。
   - **区间分段按钮**（≤5 项，故以下拉框 `.detail-chart-select` 换成分段按钮）：容器 `.detail-chart-range`（`inline-flex` + `1px #e5e5e5` 边框 + 圆角 **0**（直角；2026-09-27 Tier1-③ 曾由 8px 收敛为 6px，2026-10-01 用户要求回退为直角）+ `overflow:hidden` 裁圆角）内 `.detail-range-btn` —— 高 **28px** / 字号 **12px** / 未选中透明底 + `#525252` 文字 / hover 转 `#4680FD` / 选中 `.active` = `#4680FD` 底 + 白字 600；5 个预设 `1m/6m/1y/3y/max` = 近1月 / 近半年 / 近1年 / 近3年 / 最长。
     - ⚠️ 原生 `<select class="detail-chart-select" id="…ChartRange" hidden>` **仍保留在 DOM**：分段按钮只做「写 select 值 + `dispatchEvent(new Event('change',{bubbles:true}))`」，6 个既有 change 监听整段复用，**图表绘制函数一行未改**；`syncActive()` 负责 `.active` 与 select 值同步。
   - **说明行** `.detail-chart-note`（12px / `#5C7391`，位于图表下方、滑块上方）：`「<区间名>区间：最低 x.xx% · 最高 x.xx% · 较<基准名>高/低 x.xx 个百分点」`，由 `updateChartNote(prefix)` 从 `chartDataByPrefix[prefix]` 实时计算（`sliderRenderChart` 末尾调用）；最低/最高取区间内主线极值，差值 = 区间内**最后一点**主线值 − 基准值（负数显示「低」）；基准名 `assetDetail` 取 `assetOrangeLabel`（余额宝页 = 一年期整存整取，其余 = 余额宝）；**缺数据一律 `—`**。区间名取自隐藏 select 的当前值。
   - **卡片内边距 / 高度**：`.detail-chart-area { background:#FFFFFF; padding:20px }`（图表区域**纯白底**，2026-09-20 恢复；6 张卡片的 canvas **全部**包在 `.detail-chart-area` 内）；`.detail-chart-canvas` 高度 PC **320px**（≥320）、手机 **300px**（2026-10-04 由 240 提到 300，用户要求「图显小 / 版面挤」；`mobile.css` `@media(max-width:767px)` 覆写）。
   - **手机端**（仅写在 `mobile.css` 的 `@media (max-width:767px)`）：`.detail-chart-legend` 改纵向堆叠（`.detail-legend-items` gap 12px）；**区间分段按钮铺满整行、左右两端顶格、5 段等宽**（2026-10-04 用户要求）——`.detail-chart-range { align-self:stretch; width:100%; max-width:none; overflow:visible }` + `.detail-range-btn { flex:1 1 0; min-width:0; padding:0 4px }`（原为 `align-self:flex-start; overflow-x:auto` + 按钮 `flex:0 0 auto`，按内容收缩且右侧留 ~30px 空白）。
   - **兼容**：`.chart-mask`（`inset:0`，包在 `.chart-canvas-wrap` 内）与 `.detail-slider` 未改动、继续可用；canvas **内部的**悬停提示框不受任何 CSS 裁切影响。
   - **滑块手柄 `.detail-slider-handle`**（2026-10-04 本轮更新）：纯圆形空心——`border-radius:50%` + 白底 `#ffffff` + **描边 `4px solid #525252`（深灰）**、**无阴影**；尺寸桌面 **16×16**、手机 **22×22**（`mobile.css` 只覆写宽高）。**颜色 / 粗细统一（用户要求「都用深灰色」「粗细统一」）**：描边色由黑 `#000` 改为与**已选区间条同色的深灰 `#525252`**，描边宽 `3 → 4px` = 区间条 `4px`，轨道 `.detail-slider-track` 手机端亦由 `5 → 4px`，三者（手柄描边 / 区间条 / 轨道）**粗细一致、同色**。⚠️ 因全站 `box-sizing:border-box`，加粗**只向内**、外径不变（手记 22px 内白圈 14px；桌面 16px 内白圈 8px）。⚠️ Chrome 会把小数 `border-width` 向下取整，故取整数值。**已选区间底色 `.detail-slider-range`** = **深灰 `#525252`**（未选区轨道 `.detail-slider-track` = 浅灰 `#e5e5e5`）。
     - **手柄定位（改由 JS 用 translate 完成，2026-10-04 修复右把手被裁）**：`updateSliderRange()` 中**左手柄** `left:p0%`（左缘贴 p0）；**右手柄** `left:p1% + transform:translateY(-50%) translateX(-100%)`（右缘贴 p1）。原右手柄为 `left: calc(p1% - 16px)`（**硬编码桌面手柄宽 16px**），手机手柄 22px 时右缘溢出 `100% + 6px`，被 `.detail-slider{overflow:hidden}` **裁成缺口**（用户报「选最长时右把手显示不全」）→ 现改为与手柄宽度**解耦**的 `translateX(-100%)`；同时 `.detail-slider` 的 `overflow` 由 `hidden` 改 `visible` 双保险。三端（390/1200）实测两端外缘差 0px。


10. **全站表头配色 / 分隔线 / 排序箭头**（2026-10-01 用户要求更新）：表头底一律**纯白 `#fff`**（`--th-bg`，2026-10-01 由 `#fafafd` 改）、表头默认文字一律 `#1a2b45`（`--th-fg` 深藏青），**表头与表体之间加一条纯黑实线 `1px solid #000`**（`--th-line`）、hover 底 `--th-bg-hover`（=`--hl-lilac: rgba(0,26,255,0.05)`，与顶部二级菜单 hover **同色浅紫**；2026-10-01 由 `#f2f3f8` 改、并自 `0.08` 调淡至 `0.05`）。范围 = `.asset-table-header`（首页资产表）、`.index-table th`（红利指数 / 境内ETF / 港交所ETF / 月月分红，4 个渲染器共用）、`.blog-overlay-body th`（文章内表格）。**原「蓝底 `#001AFF` + 白字」表头已废，不要再改回**。**排序图标 = 内联 SVG 箭头**（`SI_UP_SVG` 常量；用户提供的上箭头 SVG，收边 `viewBox="10 10 28 28"`、`stroke:currentColor`、CSS 定 `12×12`）——**升序 `↑`、降序由 CSS `rotate(180deg)` 得到 `↓`**（2026-10-01 用户要求：先由三角符号 `▼` 换字符箭头，再换为用户 SVG；`.sort-icon` 改 `inline-flex`）。**排序箭头默认隐藏（`visibility:hidden`），仅当前排序列 `.sort-icon.active` 显示（`visibility:visible`）——即「点某列表头后该列才出现箭头」**（2026-10-01 用户要求；用 `visibility` 而非 `display` 以**避免列宽跳动**）。例外 = 表头内的个性化彩色 / 浅灰文字不被覆盖：当前排序列图标用主色 `#001AFF`、普通排序图标 `rgba(26,43,69,.45)`、数据列本身仍用主色（如 `.col-yield`）。⚠️ `.index-table th` 是 sticky，底色必须不透明。**表头 hover 一律「只预选中鼠标所在的那一个字段」**（2026-10-04 用户要求；此前首页 `.asset-table-header:hover` 是**整行**一起变色，与各列表页口径不一致）：列表页用 `.index-table th:hover`（逐单元格，天然如此），**首页改为 `.asset-table-header > span:hover`**（逐格 span；grid 格，7 列 = 6 个具名字段 + 1 个空 span 对应收藏列），且**hover 时整格填满、列与列无缝**（2026-10-04 二次用户要求「要像列表页一样是整块的，整格被填满、列间别留缝」）——做法：① `.asset-table-header` 上下 padding 由 `var(--pad-row-tb) 4px` → **`0 4px`**，上下留白改由 span 自带的 `padding: var(--pad-row-tb) 14px` 承担，span 自身高度即整格高度，背景覆盖全部上下留白（改前 11px 上下留白不着色 → 看着「只在文字上有高亮」）；② 左右 `margin: -4px` 使背景向两侧各溢出 4px（= 列 `gap`），相邻格背景互相搭接、间隙被完整覆盖；③ 净文字内缩 = 14 − 4 = **10px**，与数据单元格一致，**列轨道不变、表头文字与数据仍对齐**。改后首页与列表页观感一致。⚠️ 触屏 `@media (hover:none)` 下 `.index-table th:hover` / **`.asset-table-header > span:hover`** 复位为 `--th-bg`（不再残留蓝底）。

11. **表格列对齐统一**（2026-10-03 用户要求；**唯一依据 = `reference/table-alignment.md`**）：全站表格列按「字段类别」对齐——
    - **文本 / 标签类 → 左对齐**：代码、名称、简称、分类、来源、市场、币种、跟踪指数名称等（**不加类名**，走默认 `left`）。
    - **数值类 → 右对齐**：净值、涨跌幅、股息率、规模、成交额、份额占比、成分个数、管理费率、分红次数、月均分红等（加 `class="col-num"`）。
    - **日期类**：**元数据日期**（成立/上市/发布/更新日期）→ **左**；**时效/分红日期**（最近分红日期、派息日）→ **右**（加 `class="col-date-r"`）。同类日期全站统一。
    - **短徽章类**（风险等级、多空标签）**可居中**；图标列（首页资产表 ☆）居中。
    - **表头必须与该列数据同对齐**（❌ 禁止表头统一居中）。
    - **单元格留白（2026-10-03 二次，用户反馈「文字贴单元格边界 / 相邻列黏连」；当日定稿口径 = 10px inset / 相邻 ≥20px）**：每个单元格左右各留内边距——`.index-table th/td` 与首页 `.asset-table` 的 `.asset-*-cell` 统一 **`padding: 0 10px`**（平板 `mobile.css` 的 `.index-table th/td` 亦 10px），行/表头外 padding `12px→4px` → 相邻列文字间距 `10+4(gap)+10 = 24px`（列表 `10+10 = 20px`）（此前「右对齐列 + 左对齐列」只剩 4px grid gap → 食息率/更新日期黏连）。**新增右对齐列时须确认其右侧相邻列仍有 ≥20px 文字间隙。**
    - **表格行高（2026-10-03 二次）**：行/表头**纵向**内边距改用专用令牌 **`--pad-row-tb: 11px`**（`--pad-row` 18px 仅供非表格内容框体）→ 行高 56~59px → **42~45px（≈ −25%）**。详见「间距 · 内容框体上下内边距」。
    - 实现：`.index-table th/td.col-num`、`.index-table th/td.col-date-r`（`index.html` `<style>`）；`.col-yield`/`.col-pct` 自带 `text-align:right`；月月分红表的列定义用 `align:'col-num'/'col-date-r'`；首页资产表用 `.asset-table-header span:nth-child(n)` + `.asset-*-cell` 逐列声明。**新增字段 → 先登记 `table-alignment.md` 再实现**。

12. **中英文 / 数字空格规范（全站；2026-10-04 用户立为「网站最基本要求」）**：全站所有**用户可见**文案（列表副标题、筛选器、下拉选项、区间/图注、日历、页脚、资讯正文、数据字段等）一律遵守——
    - **中英文混合时，中英文之间不留空格**：`Wind数据`、`AAA级`、`ETF排序`、`腾讯新闻CLI`（❌ `Wind 数据` / `AAA 级` / `ETF 排序`）。
    - **英文与英文、英文与数字之间留空格**：`Page 1`、`v0.1.96`、`2026-10-04 07:29`（时间戳 / 英文短语内部照常留空格）。
    - **中文与数字之间不留空格**：`共95只`、`近1年`、`2026年10月`、`38关键词`（❌ `共 95 只` / `近 1 年` / `2026 年 10 月`）。
    - **落地范围**：① 数据层 `data/*.json` 的文案字段；② UI 层 `index.html` / `mobile.js` 的字符串字面量与 HTML 文本节点。2026-10-04 全站根治（数据层 20 处、UI 层「近N年/共N只/图注/日历/排序」若干）；校验脚本 `scan_data_spacing.py` / `scan_src_spacing.py` + 渲染级 `scan_spacing.js`（15 路由 × 桌面 1280 / 手机 390 + 各页筛选器展开 → 期望 0 违规）。

---

## 移动端样式规则（原「Mobile 版本 CSS 样式要求」整段）


> 以下为移动端（≤767px）样式规范，全部经 iPhone Safari 实测反馈后定稿。桌面端不受影响。
> 相关实现文件：`mobile.css`、`mobile.js`（移动端独立渲染层）。

### ⛔ 修改纪律（2026-08-17 用户严格立规，必须遵守）

1. **mobile.css 的所有规则必须写在 `@media (max-width: 767px)` 媒体查询内**，严禁在媒体查询外新增规则（否则会污染 PC 端）。
2. **严禁为适配移动端去修改 index.html / mobile.js 里的全局生成函数**（如 idxTagBarHtml 等）——这些函数 PC 端共用，改了会破坏 PC 版。如需结构变化：优先用 CSS 媒体查询；非改结构不可时，必须同时补 PC 端样式并在 PC 端验证。
3. **每次改完 mobile 相关样式，必须 PC + 移动两端都实测验证**，再部署。
4. 本次教训（2026-08-17）：改 idxTagBarHtml 结构（标题+滚动区分离）时只给移动端写了 CSS，PC 端标签失去间距（标签进入新容器 .index-tagbar-scroll，PC 无 gap）→ 已补 `.index-tagbar-scroll { display:flex; flex-wrap:wrap; gap:6px 10px }` 到主样式修复。
5. **`mobile.css` 版本号纪律**：只要改了 `mobile.css`，必须同步 bump `index.html` 中引用处的 `mobile.css?v=NN`（当前 **v=58**），以强制客户端刷新缓存；只改 `index.html` / `data/*.json`（未动 `mobile.css`）时**不 bump**。

### 一、汉堡菜单（全局导航）

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | **全屏抽屉**（2026-10-04 用户要求：从左到右全屏，替换原半屏 220px）＋ **高度=内容**（下沿不贴屏幕底部）；背景遮罩半透明黑 rgba(15,18,32,0.45)，点击遮罩关闭 | `.m-nav-drawer`：`left:0; right:0; width:auto; max-width:none`（全屏）＋ `height:auto; max-height:100dvh`（fit 内容，超高才封顶并整体滚动）；`transform:translateX(100%)` 右侧滑入；`.m-nav-list` 用 `flex:0 0 auto`（不再 `flex:1` 撑满）。`.m-nav-mask` 点击关闭 |
| 2 | 一级项：**文字横向单行**（禁止竖排）、**左对齐**、44px 行高、**16px**（2026-10-04 用户指定：15 → 16；更早曾试 10px 偏小）、#000000、无装饰（无胶囊/无彩色） | `.m-nav-list .main-nav-item`：`white-space:nowrap; text-align:left; height:44px; font-size:16px` |
| 3 | **子层级右侧箭头**：svg 线条 chevron（非字符">"），16px、#737373、与文字间距 8px | `.m-nav-arrow` 内 svg（stroke-width 1.5），间距由 gap:0 + padding-left:8px 保证 |
| 4 | **二级菜单**：返回按钮（svg 左箭头）+ 标题 + 子项列表；无灰色分组小字；子项点击直接进页面 | `.m-nav-sub` 层，标题与子项文字左对齐同一列 |
| 5 | 二级返回箭头**悬挂在文字左侧**（右缘贴文字起点），左侧留白 8px | `.m-nav-sub-back`：absolute left:8px，箭头 flex-start；文字列 padding-left 32px |
| 6 | 一/二级**选项字号颜色统一**：全部 **16px**（2026-10-04 用户指定：15 → 16）、#000000；选中项 = 加粗 + 蓝字（详见 #8，2026-10-04）。⚠ logo「食息指南」与二级标题 `.m-nav-sub-title` 仍为 20px（属标题非「选项」，未动） | `.m-nav-sub .dropdown-item` 与一级同款 `font-size:16px` |
| 7 | **两个方向箭头大小颜色一致**：16px、#737373、线宽 1.5 | 返回箭头与一级右箭头同规格 |
| 8 | **选中态**：仅 **加粗（700）+ 蓝字 `#4680FD`**，**无背景**（2026-10-04 用户要求，v0.1.69：取消原蓝底白字；**汉堡菜单内任何位置都不出现蓝底白字**）；取消选中恢复正常；同时去掉主样式遗留的桌面蓝色下划线 `box-shadow` | 一级 `.m-nav-list .main-nav-item.active`、二级 `.m-nav-sub .dropdown-item.active` / `.m-nav-drawer .dropdown-item.active` 均 `font-weight:700; color:#4680FD; background:none`。⚠ 仅 `.index-tag.active`（列表筛选标签，**非**汉堡菜单）保留蓝底白字 |
| 9 | 选中状态**实时同步**：打开菜单时按当前所在页面高亮（一级项由主脚本管理；二级项由 mobile.js `syncMenuActive` 基于 **当前激活 .page** 的 .sub-page.active 匹配 data-sub） | 注意：pageIndex 隐藏后其 sub-page 会残留 active，必须查 `.page.active` 内的 |
| 10 | 禁止 Safari 点击蓝色高亮残留：`-webkit-tap-highlight-color: transparent`、`:active/:focus` 无背景、无 outline | `.m-nav-list .main-nav-item / .m-nav-sub .dropdown-item` |
| 11 | **logo 与首个菜单项之间加一条浅灰分隔线**（2026-10-04 用户要求，v0.1.68；样式与「食息资讯」条目分隔线一致） | `.m-nav-drawer-header { border-bottom: 1px solid var(--line-soft) }`（= `rgba(0,0,0,0.06)`）；即抽屉顶部「食息指南」行（高 60px）底部一条线，正好落在首个一级项「首页」上方（header.bottom == list.top）。⚠ 仅手机端抽屉有此 header |
| 12 | **禁止抽屉横向滑动**（2026-10-04 用户反馈，v0.1.70）：抽屉内在一/二级菜单上左右滑动**不产生任何平移** | `.m-nav-drawer { overflow-x:hidden; touch-action:pan-y }`。⚠ 根因：隐藏的二级层 `.m-nav-sub`（`position:absolute` + `translateX(100%)`）悬在 `left:390..780`，会撑宽抽屉的**可滚动宽度**（780 vs 390）；因抽屉只写了 `overflow-y:auto`，按规范 `overflow-x` 计算为 `auto` 从而可横向滚动 → 显式锁 `overflow-x:hidden` 并对齐 `touch-action:pan-y`。纵向滚动仍 `auto` 不受影响 |
| 13 | **抽屉外观**（2026-10-04 用户要求，v0.1.73）：菜单 **80% 不透明**（半透明毛玻璃，同 web `.top-bar` 风格）＋ **下沿一条与 web 版一致的浅灰分隔符** | `.m-nav-drawer { background: rgba(255,255,255,0.80); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid var(--line-soft) }`（`--line-soft`=`rgba(0,0,0,0.06)`，同 `.top-bar` 下沿） |
| 14 | **断点自适应**（2026-10-04 用户反馈，v0.1.73）：桌面加载后缩窄窗口 / 手机↔横竖屏切换时，汉堡菜单与移动层能即时启用（此前桌面加载后缩窄，汉堡永不出现） | `mobile.js` **不再在加载时按宽度 `return`**；改为 `resize`（rAF 节流）监听断点：进入手机端 → `run()`（注入排序框＋构建抽屉）＋ `_rerenderListsForMode()` 把 6 列表由表格重渲染为移动卡片；回到桌面 → 抽屉已破坏性改造导航（搬到 body、丢 ▼/emoji），无法无损还原 → `location.reload()` 干净恢复（hash 路由，重载仍停留同一子页）。⚠ 因此「手机→桌面」会触发一次重载 |

### 二、筛选器（指数浏览器 / 境内ETF）

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | **标题固定**（"主题/市场/调仓频率/指数公司"等），**只滑动标签** | 结构性分离（不用 sticky，Safari 兼容）：`.index-tagbar-row > [.index-tagbar-group 固定 + .index-tagbar-scroll 独立 overflow-x:auto]`；生成函数 `idxTagBarHtml`、`cnEtfTagBarHtml` |
| 2 | 标题**统一宽度 72px**（border-box），4 组标签严格左对齐 | `.index-tagbar-group { width:72px; min-width:72px }` |
| 3 | 标签不换行、横向滑动、隐藏滚动条 | `.index-tagbar-scroll`：`flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none` |
| 4 | 标题背景需**盖住滑过的标签白底**（等高同位） | 结构分离后天然满足（标签在独立滚动区） |
| 5 | **筛选器整体为纯白底面板**（2026-09-20 用户要求：所有带筛选器的页面，筛选器部分加纯白 background） | `.index-tagbar { background:#fff }`——桌面 `padding:14px 0; margin-bottom:12px`，手机 `padding:10px 0; margin-bottom:10px`（**2026-10-03 用户要求：左右内边距 20px / 12px → 0，使筛选标签行顶到内容区两端、与 `.section-title` / `.index-table` 左沿严格对齐**；改前因左右各 20px 内缩、视觉不齐）。直角、无边框、无阴影——与全站白底卡片同规范；❌ 标签按钮自身的 `background:#fff` 不变（选中态仍为 `#4680FD` 蓝底白字）。覆盖页面：红利指数浏览器、境内红利ETF（`.df-toolbar` 早已白底，不重复处理；✅ **2026-10-03 第二轮：`.df-toolbar` 亦做同样收边**——桌面 `padding:18px 0`、平板/手机左右 `0`，食息资讯「内容标签」左沿与内容区左沿对齐） |
| 6 | **标签外框：`1px solid var(--line-soft)`**（2026-10-03 用户要求：改用与 header 下沿那种**很浅的浅灰**同色 = `rgba(0,0,0,0.06)`；历史：2026-09-20 原 `#eef1f8`，11reader 对齐时→`#e5e5e5`） | `.index-tag { border:1px solid var(--line-soft) }`（`mobile.css` 第 6 节同款覆盖；`box-sizing:border-box` 下手机仍 **36px** 高）；选中态 `.index-tag.active { border-color:#4680FD }` + 蓝底白字不变；`@media (hover:none)` 的 `.index-tag:hover` 补 `border-color:var(--line-soft)`——否则触屏轻点后蓝色描边会残留。✅ **2026-10-03 第二轮：食息资讯 `.df-chip` 亦同步为本色**，列表页与食息资讯筛选标签外框现已一致 |
| 7 | **基金公司 = A–Z 索引 + hover 弹出**（2026-09-20 用户要求，参照用户另一站点 `am-lens.vercel.app/#/product/fund-approval` 的「管理人」筛选） | 公司组单独渲染（不再平铺 chips）：字母取 `cnEtfCompanyAlphaGroups()` → 首字拼音首字母（`CNETF_COMPANY_INITIAL` 映射，未收录归 `#` 排末）；HTML `.index-dd > .index-dd-btn（字母）+ .index-dd-menu（公司）`；菜单 grid（**列数 = 该字母下的公司数，最多 3 列**，由 JS 在构建时内联 `grid-template-columns` 设定；❌ 不可固定 3 列——空网格列会残留 `column-gap` 导致「左窄右宽」留白不等，2026-10-01 用户要求）、白底、`padding:8px`、`border:1px solid var(--line-soft)`（2026-10-03 第二轮由 `#e5e5e5` 改）、`box-shadow:0 8px 24px rgba(0,0,0,.08)`、`z-index:200`，贴字母正下方（`top:100%; left:0`） |
| 8 | **三种触发方式 + 已选状态** | `document` 级事件委托（DOM 每次 `innerHTML` 重建，委托无需重绑）：`mouseover` 展开并收起其它、`click` 兜底触屏（同一手势 500ms 内不立即收起）、`focusin/focusout` 支持键盘；**已选公司在行首显示为蓝色标签**（再点一次取消，与其余筛选组「再点一次取消」一致），其所属**字母同时高亮** |
| 9 | **手机端适配**（绝对定位菜单会被滚动容器裁剪，必须放开） | `.index-tagbar-row--alpha { flex-wrap:wrap }` + 标题 `flex-basis:100%`（独占一行）+ `.index-tagbar-scroll--alpha { flex-wrap:wrap; overflow:visible }`（覆盖第 9 节的 `nowrap + overflow-x:auto`）；字母 `padding:4px 10px`、`gap:6px` → 16 个字母压到 **2 行**（行高 116px）；菜单右缘越界时由 JS 加 `transform:translateX(-over)` 左移，不溢出视口 |

### 三、触屏 hover（全站，@media hover:none）

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | 轻点元素**不改变底色**：未选中=白底/默认外观，点中才蓝底白字 | 原 hover 规则 `background:transparent` 会致轻点瞬时无底色 → 已改为 hover=各元素默认（`.index-tag:hover{background:#fff}`、`.main-nav-item:hover{background:transparent;color:#767676}`、`.dropdown-item:hover{background:transparent;color:#000000}` 等） |
| 2 | 选中态：**汉堡菜单** = 加粗 + 蓝字 `#4680FD`、**无背景**（2026-10-04，v0.1.69：取消蓝底白字）；其余组件选中态仍为蓝底 #4680FD + 白字 + 加粗 | 蓝底白字：`.index-tag.active`（列表筛选标签）等；汉堡菜单：`.main-nav-item.active` / `.dropdown-item.active` → 仅加粗蓝字（食息资讯为日报视图，选中态用 `.df-chip.df-act` 外圈高亮 + 月历 `.d.sel` 深底，2026-09-20 起） |

### 四、移动端列表卡片

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | 港交所红利ETF / 月月分红ETF / 月月分红指数基金：**卡片间隙与网页整体背景色一致**（浅灰 #f4f2f7，白卡片间隙） | 容器 + **表格背景**都要改：这三个列表移动端是表格卡片化（tr 白底 block + margin），**间隙透出的是 .index-table 的白底**（只改容器无效）→ `#hketfListContainer/#monthlyEtfContainer/#monthlyFundContainer { background:#f4f2f7 }` 且容器内 `.index-table { background:#f4f2f7 }`；实测 tableBg=bodyBg=rgb(244,242,247) |
| 2 | 主流资产/指数浏览器/境内ETF 移动端用独立卡片层（.m-card） | mobile.js `renderAssetTableMobile / renderIndicesMobile / renderCnEtfMobile` |
| 3 | **卡片右上角「大数字」**（2026-09-27 Tier1-④）：关键数字（食息率 / 股息率 / 对应指数股息率）放大到右上角，指标名作其下小字标签。**⚠ 2026-10-04：红利指数浏览器 + 境内红利ETF + 月月分红ETF + 月月分红指数基金 已全部弃用大数字**——改为浅蓝底蓝字数据胶囊（见 3a） | 统一 helper `_mStat(num, label, color)`（mobile.js）→ `<span class="m-stat"><b class="m-stat-num">值</b><i class="m-stat-lb">指标名</i></span>`；`.m-stat-num` = `--fs-2xl`（20px）/700/`font-variant-numeric:tabular-nums`，颜色沿用**类型色或主色 `#4680FD`**；`.m-stat-lb` = `--fs-2xs`/`#767676`。**现仅剩 `renderAssetTableMobile`（首页主流资产的「食息率」）仍用大数字** |
| 3a | **「股息率 / 对应指数股息率」= 浅蓝底蓝字数据胶囊**（2026-10-04 用户要求：右上角大数字看着不舒服，改成浅蓝底蓝字标签，放在「本年」**之前**、去掉右上角；并强调「有数据的就加，没数据的就不加」）：**红利指数浏览器**（标签 `股息率`）＋ **境内红利ETF / 港交所红利ETF / 月月分红ETF / 月月分红指数基金**（标签 `对应指数股息率`） | 各 `renderIndicesMobile / renderCnEtfMobile / renderHkEtfMobile / renderMonthlyEtfMobile / renderMonthlyFundMobile`：`.m-card-top` 内**不再**渲染 `_mStat`（名称独占整行）；`.m-card-pcts` = `_mPill('股息率'\|'对应指数股息率' + 值, 'blue')` ＋（如有）「本年」涨跌胶囊。样式沿用 `.m-pct.blue { background: rgba(70,128,253,.08); color: #4680FD }`。**无数据则不渲染该胶囊**（⚠ `hkEtfData` 源头无 `yield` 字段 → 港交所按 `trackCode` 到指数库 `_trackIdx()` 匹配，匹配不到不显示；12 只里 5 只有数据）；`renderAssetTableMobile`（首页食息率）仍用右上角大数字 |
| 4 | **条目之间 + 列表最上方加一条分隔横杠**（2026-10-04 用户要求，样式同「食息资讯」两条资讯之间的分隔线；追加：首个条目最上方也要一条） | 6 个手机端列表页（首页资产表 / 红利指数浏览器 / 境内红利ETF / 港交所红利ETF / 月月ETF / 月月基金）均为 `.m-list > .m-card`。原 `.m-list{gap:10px}` 在**纯白底**（卡片与页面背景皆 `#fff`）**不可见** → 改 **`gap:0` + `.m-list > .m-card{ border-top:1px solid var(--line-soft) }`**（**含首条**，即列表最上方也有一条线），与 `#pageWeekly ul.df-items li{ border-top:1px solid var(--line-soft) }` 同款（`--line-soft`=`rgba(0,0,0,0.06)`）。仅 `mobile.css` 手机段（≤767px）生效；桌面 / 平板仍为表格。⚠ 后续若要「卡片式留白」观感，不要改回 gap——需另建分隔方案。 |

### 五、食息资讯（日报）日期模块与手机端（2026-09-20）

> 全部手机规则写在 `mobile.css` 的 `@media (max-width:767px)` 内，桌面（≥768px）与平板（768–1024px）**零影响**；桌面回归须保持「工具栏仅标签 + meta（92px 高）+ 月历 sticky 260px + 两列 grid + 正文 13px」。
> **该栏目只有一个日期模块 = 日历**：日期选择、日期操作、数据日高亮全部集中在 `.df-cal` 内。

> **2026-09-27 用户要求（列表范围与分页）**：① **未选标签时只显示一天** —— 选了具体日期显示该日；未选（＝「全部日期」）只显示**最新有数据的一天**，不再把全历史铺开；② **选中标签时**显示该标签的**全历史**资讯（若同时选了日期则叠加该日限制），按 **`DF_PAGE_SIZE = 20` 条/页分页**（>20 条才渲染分页条 `.df-pager`：「‹ 上一页 / 第 x / y 页 · 共 n 条 / 下一页 ›」）；③ **跨天视图**加日期分隔条 `.df-day-h`（左日期 + 右「n 条」），单天视图不加；④ **标签计数跟随展示范围**（无标签=当日计数，选标签=全历史计数）。分页口径：任何筛选变化（选标签 / 选日期 / 清标签 / 全部日期）一律把 `dailyState.page` 重置为 1，越界页码自动收敛到末页；翻页后把列表滚到页头下方。

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 0 | ❌ **不得再加**：原生态 `<input type="date">`、工具栏内的日期按钮行、「日期检索」标签、关键词搜索框（均已于 2026-09-20 删除） | 工具栏 `.df-toolbar` 现在只有两个 `.df-row`：`#dfChips`（标签，前置 `.df-lb`「内容标签」标题）+ `#dfMeta`（范围说明） |
| 1 | **日期操作行在日历内**：`‹ 前一日`／`后一日 ›`／`回到最新`／`全部日期` | `.df-cal-acts`（位于 `.df-cal-grid` 之后）：桌面 2 列 grid（`1fr 1fr`，按钮 ~111×30）、手机 2×2 等宽（167×36）；`border-top:1px solid #e5e5e5` 分隔；按钮 id（`dfBtnPrev/Next/Latest/All`）不变，JS 监听与按钮位置无关 |
| 2 | **日历为唯一日期选择器**：网格高亮「有数据的日期」，无数据日不可点 | `renderDailyCal` 写 `#dfCalGrid`，`.d.has` 可点、`.d.sel` 为选中蓝底；月份切换用 `.df-cal-hd` 内的 `.df-btn.df-sm` |
| 3 | **手机端默认折叠**（首屏优先给资讯），展开后压缩行高 | `.df-cal-toggle`（`#dfCalToggle`，桌面 `display:none`，手机 `display:flex`，文案在 `#dfCalToggleTxt`，`aria-expanded` 同步）；`.df-cal:not(.cal-open)` 下 `.df-cal-hd` / `.df-cal-grid` / **`.df-cal-acts`** 一并 `display:none`；折叠 52px、展开 357px |
| 4 | **日历箭头复用 PC 版一级菜单 SVG** | 与 `.main-nav-item .arrow` 完全同款：`<span class="arrow"><svg viewBox="0 0 24 24" fill="none"><path stroke="currentColor" stroke-width="1.5" d="M6 9l6 6 6-6"/></svg></span>`，`14×14`、`currentColor`、`transition:transform .2s`；展开时 `.df-cal.cal-open .df-cal-toggle .arrow { transform:rotate(180deg) }`。❌ 不用 `▾/▴` 文本字符 |
| 5 | **字号两档**：工具栏 12px / 资讯条目区 `--fs-xs`（11px） | **工具栏**（`.df-chip` chips、`.df-meta` meta、日历月标题、日期数字、操作行按钮）**全部 12px**；**资讯条目区**（`.df-tag` 资讯标签、`.df-copy` 复制按钮、`.df-src` 日期+资讯来源、`.df-lnk` 原文链接、`.df-dot` 分隔点）**统一 `--fs-xs`（11px）**（2026-09-20 原为 10.5px；2026-09-27 Tier1-① 收敛为 `--fs-xs` 令牌）。其余：周标题 10px、正文 `.df-txt` 桌面 13px / 手机 14px。❌ 不要在组件里散写裸 px 字号（全站已令牌化）：工具栏用 `--fs-sm`、条目区用 `--fs-xs` |
| 6 | **留白统一 12px**（与 `.page` 内边距对齐） | `.df-toolbar { padding:12px }`、`.df-day { padding:14px 12px }`、`.df-row { gap:8px }`、`.df-layout { gap:10px }`、`.df-cal { padding:10px 12px }` |
| 7 | **触控热区**：复制按钮不改变视觉尺寸也能易点 | `.df-copy { position:relative }` + `.df-copy::after { top/bottom:-9px; left/right:-6px }` 隐形热区；`#pageWeekly .df-btn/.df-chip/.df-reset { min-height:36px }`；折叠开关 `min-height:32px` |
| 8 | **标签行有「内容标签」标题**（2026-09-20 加；文案当日由「筛选标签」改为「内容标签」） | `.df-row` 内先 `.df-lb` 再 `.df-chips` 两元素：标题 12px / `#8e8e93` / 600（同 `.index-tagbar-group` 规范），手机端 `flex-basis:100%` 独占一行；`.df-chips` 为 `flex:1; min-width:0` 的自适应容器（桌面与标题同行、手机换行）。❌ 不要把标题写进 `#dfChips` 内部（chips 由 `renderDailyChips()` 整体重渲染，会被清掉） |
| 9 | **复制按钮无外框（2026-09-20 用户要求「去掉复制按钮的边框」）** | `#pageWeekly .df-copy` = **纯文字按钮**：`border:none` + `background:none`，颜色 `#767676`；hover → 文字变 `#4680FD`、成功态 `.ok` → 文字变 `#10b978`（**只有颜色变化，不再有 border-color**），`transition:color .15s`。字号/内边距（桌面 `--fs-xs` 11px / `0 7px`，手机 `--fs-xs` 11px / `1px 8px`）、`margin-left:auto` 右对齐、手机端 `::after` 隐形热区（top/bottom -9px、left/right -6px）**均保持不变**。❌ 不要再给它加 `border` / `background` |
| 10 | **日历左侧贴内容区左沿 + 第一条资讯补上框线（2026-10-04 用户要求，v0.1.67）** | ① **日历贴边**：`.df-cal` 左内边距 `16px → 0`（桌面 `padding: var(--pad-row) 16px var(--pad-row) 0`；手机 `12px → 0`，`mobile.css`）→ 日历盒（`.df-cal-hd`/`.df-cal-grid`/`.df-cal-acts`）左沿与内容区左沿（桌面 **80** / 手机 **12**，= `.section-title` 左沿）严格对齐；右内边距**保留**。② **首条框线**：原 `ul.df-items li:first-child { border-top:none; padding-top:0 }`（首条无线）→ 改为**仅当上方有日期分隔条时**才取消：`#pageWeekly .df-day-h + ul.df-items li:first-child { border-top:none; padding-top:0 }`。故**单天视图**（无 `.df-day-h`）下第一条也带 `1px solid var(--line-soft)` 上框线且 `padding-top:18px`，与其它条目**完全一致**；**跨天视图**下 `.df-day-h` 已有下边框，首条仍取消（避免双线）。`index.html` 与 `mobile.css` **两侧同口径**改。⚠ **2026-10-04 v0.1.74**：其中 `padding-top:0` 已改为 `var(--pad-row)`（见 #12，修「标签顶着分隔条下边线」） |
| 11 | **内容标签配色改用「鲜艳版」并去掉刷新跳色（2026-10-04 用户反馈，v0.1.74）** | `.df-tag`（及 chips 计数等）颜色取自 `index.html` 内嵌 `dailyTagColors`（鲜艳版，如 债券 `#e5eaff`/`#9570ff`）。历史：运行时曾被 `/data/dailyTagColors.json`（digest-db `meta.tagColors`，哑光版，如 债券 `#e8eaf6`/`#283593`）覆盖 → 刷新瞬间先显示鲜艳版、随后被覆盖 → **跳色**。现 **从 `DATA_FILES` 移除 `dailyTagColors` 条目**，内嵌表即最终配色。⚠ `data/dailyTagColors.json` 文件仍存在（`sync_daily.py` 生成），但前端不再加载它 |
| 12 | **跨天视图（点选内容标签后）首条与日期分隔条的间距（2026-10-04 用户反馈，v0.1.74）** | `#pageWeekly .df-day-h + ul.df-items li:first-child`：`padding-top:0 → var(--pad-row)`（保留 `border-top:none` 避免双线）→ 首条 `.df-tags` 与 `.df-day-h` 下边线间距 = **18px**（桌面/手机一致）。`index.html` 与 `mobile.css` 两侧同口径 |

### 六、首页「食息提示」折叠面板（2026-09-20；2026-09-26 更名；2026-09-27 改浅蓝紫光晕；2026-10-01 成全站唯一保留圆角的元素；2026-10-03 单块回退至 11reader 前配色）

> 食息数据页（`#pageData`）原静态提示卡 `.intro-card`（标题「📌 适合普通人的几种常见生息资产」+ 6 条 `.intro-item`）改为**默认折叠**面板，标题文案改为「食息提示」。

> **2026-09-26 用户要求**：容器类名由 `.intro-card` **更名为 `.reminder`**（内部元素类 `.intro-toggle*`/`.intro-list`/`.intro-item`/`.intro-icon`、状态类 `.intro-open`、id `introPanel` 均保持不变）；样式改为 **外框 `1px solid #F2E397` + 内部填充 `#FDF9E5` + `border-radius:5px`**（不再是无边框纯白卡；该 5px 已于 2026-09-27 Tier1-③ 统一为 `var(--r-ctl)` = 6px；**2026-10-01 用户要求全站控件回退直角，`.reminder` 作为唯一例外保留该圆角**）。

> **2026-09-27 用户要求（配色再调）**：原黄底 `#FDF9E5` / 黄框 `#F2E397` **与全站色系不协调**，改为 **浅蓝紫底 + 极浅炫彩光晕**（两团径向光晕 + 渐变打底；注意 footer 光晕已于 2026-09-27 全部去掉，本框为**独立保留**）。定为——`.reminder { position:relative; overflow:hidden; background:#FBFBFE; border:1px solid #E7E9FB; border-radius:var(--r-ctl) }`；装饰层 `.reminder::before { inset:0; background: radial-gradient(circle at 12% 0%, rgba(0,26,255,.07), transparent 42%), radial-gradient(circle at 88% 100%, rgba(124,92,255,.08), transparent 46%), linear-gradient(135deg,#FBFBFE,#F5F4FE) }`（左上偏**蓝**、右下偏**紫**）；内容层 `.reminder > * { position:relative; z-index:1 }`。❌ 黄色 `#FDF9E5` / `#F2E397` 已废，不要再改回。折叠逻辑 / 文案 / 箭头 / 触控高度一律不动。**2026-10-01**：全站控件圆角回退直角后，`--r-ctl` 仅剩本框使用，本框 `border-radius:var(--r-ctl)` 按要求**保留**。

> **2026-10-03 用户要求（仅本块回退，反 11reader 对齐）**：11reader 全站对齐时，本块底色被改成中性灰 `#fafafa`、外框 `#e5e5e5`、渐变 `#fafafa→#f5f5f5`，光晕改用新品牌蓝 `rgba(70,128,253,.07)`，整体视觉「发灰」。用户要求**仅本块**恢复到 11reader 之前 → 底色 `#FBFBFE` / 外框 `#E7E9FB` / 光晕 `rgba(0,26,255,.07)`+`rgba(124,92,255,.08)` / 渐变 `#FBFBFE→#F5F4FE` / 面板内文字（`.intro-toggle`·`.intro-title` = `#1a2b45`、箭头 `#8e8e93`、`.intro-item` = `#4a5260`）**全部回退**。⚠ **本块是全站唯一「非 11reader 调色板」的例外**（其余全站仍为纯黑 / `#404040` / `#767676` 体系）；后续不要把它「再统一」回去。

> **2026-10-04 用户要求（光晕改品牌蓝 + 新增红色变体）**：① 首页 `.reminder` 原「蓝 + 紫」双晕不符合站点「蓝色为辅助色」的基调 → 改为**品牌蓝 #4680FD 双晕**：底 `#FBFCFE` / 框 `#E3EBFC` / 双晕 `rgba(70,128,253,.11)`+`rgba(70,128,253,.09)` / 渐变 `#FBFCFE→#F0F5FF`。② **资产详情页新增红色提示条 `.reminder-warn`**（用于「REITs特许经营权类」特别提示）：沿用 `.reminder` 同款构造（圆角 `var(--r-ctl)` + 双径向光晕 + 135° 渐变）**仅色相改警示红**——底 `#FFFBFB` / 框 `#F7DADC` / 双晕 `rgba(220,38,38,.10/.08)` / 渐变 `#FFFBFB→#FEF1F2`；标题 `.reminder-warn-title`（`--fs-base`/700/`#dc2626`）+ 正文 `.reminder-warn-body`（`--fs-md`/**纯黑 `#000000`**）。**纯展示、无折叠**（区别于首页 `.reminder`：无 toggle / 无箭头）。旧类 `.detail-warning`（直角红框）**已废弃、不再使用**。

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | **标题即开关，文案「💡 食息提示：适合普通人的几种常见生息资产」**（2026-09-20 由「食息提示」扩写；**灯泡符号与正文之间保留一个半角空格**） | 原 `.intro-title` 换成 `<button class="intro-toggle" id="introToggle" aria-expanded="false" aria-controls="introList">`：左 `.intro-toggle-txt` 放标题文案 + 右 `.arrow`（`justify-content:space-between` 分居两端）。**长标题实测仍单行**（文本 283px，390 宽度下与箭头间距 ≥25px），箭头始终贴右内缘。`.intro-title` 保留样式但已无 DOM 引用 |
| 2 | **箭头在面板右侧** | 复用 PC 版一级菜单 SVG（与 `.main-nav-item .arrow`、`.df-cal-toggle .arrow` 同款）：`<span class="arrow"><svg viewBox="0 0 24 24" fill="none"><path stroke="currentColor" stroke-width="1.5" d="M6 9l6 6 6-6"/></svg></span>`，`14×14`、`currentColor`、`transition:transform .2s`。❌ 不用 `▾/▴` 文本字符 |
| 3 | **默认折叠（首屏即为折叠态）** | `.reminder:not(.intro-open) .intro-list { display:none }`——**靠"无 `.intro-open` 类"实现，不需要 JS 初始化**；展开时 `.reminder.intro-open .intro-toggle .arrow { transform:rotate(180deg) }`、`.reminder.intro-open .intro-toggle { margin-bottom:12px }`（补上原 `.intro-title` 的下间距） |
| 4 | **点击标题切换** | `#introToggle` 的 click 监听：`introPanel.classList.toggle('intro-open')` + 同步 `aria-expanded`。默认折叠态：390 面板高 **72px** / 桌面 **57px**；展开：**436px / 234px** |
| 5 | **手机端触控下限** | `.intro-toggle { min-height:36px }`（`mobile.css` 第 4 节）——折叠态下标题是唯一可点区域，须达站点 36px 触控规范；桌面不设 `min-height`（自然 21px 行高） |
| 6 | **6 条内容不动** | `.intro-item` / `.intro-icon` 文本与 `.intro-item b { flex:0 0 108px }` 等宽占位（2026-08-17 要求）**全部保持原样** |

### 七、长表吸顶表头（2026-09-27）

> 红利指数浏览器 / 境内红利ETF / 港交所红利ETF / 月月分红（ETF / 指数基金）列表在桌面是**长表**（50 / 95 / 12 / 15 / 28 行），滚动时必须**吸顶在固定页头正下方**。

| # | 要求 | 实现位置 / 说明 |
|---|------|----------------|
| 1 | 长表 `thead th` 随页滚动吸顶在**页头正下方**（不遮挡、不留缝） | `.index-table th { position:sticky; top:0 }` **且必须** `.index-table-wrap { overflow:visible }`、`.index-table { overflow:visible }`。⚠️ 关键：wrap/table 只要有 `overflow-x:auto` 或 `overflow:hidden`，**表格自身即成为粘性滚动容器**，`th` 只相对表格吸顶＝永不吸顶（这正是 2026-09-27 修复前的症状）。放开 overflow 后 `th` 相对 `.main-content` 吸顶；因 `.main-content` 有 `padding-top: var(--topbar-h)`，`top:0` 恰好落在固定页头正下方（Chrome 粘性偏移 = `top` + 滚动容器 `padding-top`） |
| 2 | 放开 overflow 的前提：**表格不产生横向滚动** | 实测 768–1440 各档宽度 × 5 个列表：`.index-table-wrap` `scrollWidth === clientWidth`（溢出 0）。后续若因新增列导致横向溢出，**不可**直接回退成 `overflow:auto`（会再次破坏吸顶），须从列宽 / 省略号下手 |
| 3 | ❌ 不要给 `.index-table-wrap` / `.index-table` 再加任何 `overflow` | 任一轴非 `visible` 都会把另一轴计算成 `auto`，从而**重新制造**粘性滚动容器 |
| 4 | ≤767px 不受影响 | 移动端 `.index-table thead { display:none }`（表格卡片化），本就无表头 |

### 八、网站图标（favicon）（2026-10-03 首次；2026-10-04 换为 SVG 源）

> 用户要求（2026-10-04）：改用上传的 **`user_upload/red-blue.svg`**（512×512，透明底，红/蓝渐变双圆，蓝圆覆盖在红圆之上）作为网站图标。历史：2026-10-03 首个版本用的是小猫照片 `user_upload/cat_drink_coffee.png`。

- **资源位置 = 仓库根目录**：`favicon.svg`（矢量首选）、`favicon.ico`、`favicon-16x16.png`、`favicon-32x32.png`、`apple-touch-icon.png`。⚠️ **不要**放 `user_upload/`——该目录被部署排除清单（原 `.vercelignore` / 现行 Cloudflare 部署 rsync 的 `--exclude`）排除、**不会上线**；放根目录即随 `index.html` / `mobile.css` 一起上线。根目录静态文件**不受**任何 SPA 兜底 rewrite 影响（实测线上 200、`content-type: image/*`）。
- **生成口径**：SVG → `rsvg-convert` 光栅化为 **512 母版**（透明）→ 按 **alpha 通道裁掉透明留白** → 留 **~6% 内边距** → 正方形画布 → Lanczos 缩放。`favicon.svg` = 直接复制源 SVG；`favicon.ico` 含 **16/32/48** 三档（保留透明）；`apple-touch-icon.png` **180×180 压纯白底**（iOS 对透明背景会填黑）。
- **引用（`index.html` `<head>`，紧跟 `<title>`）**：`<link rel="icon" type="image/svg+xml" href="/favicon.svg">`（现代浏览器首选，矢量无损）+ `<link rel="icon" href="/favicon.ico" sizes="any">` + `<link rel="icon" type="image/png" sizes="32x32">` + `sizes="16x16"` + `<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">`。`studio/index.html` 不含图标引用。
- **重新生成**：`python3 make_favicon.py`（仓库根目录，依赖 **rsvg-convert(librsvg)** + **Pillow**）——换 SVG 后重跑即可，产物覆盖写入仓库根目录。⚠️ 浏览器对 favicon 缓存很强，换图后用户端可能需强制刷新才看到新图标。
- **顶栏左上角复用同款图标（2026-10-04 用户要求）**：把红/蓝双圆图标放到首页顶栏「食息指南」四字**之前**，并要求**圆圈上下沿与文字整体上下沿严格一致**（2026-10-04 v0.1.61 起，文字为「食息指南」16px + 副名小字 10px 两行，故 logo 上下沿对齐**两行整体**）。实现 = **内联 `<svg>` + 紧贴圆圈的 `viewBox`（`25.6 123.8 460.8 264.4`）**，`.brand-logo { width:50.07px; height:28.73px; transform:translateY(-0.63px) }`（详见「前端样式约定」第 7 条「首页顶栏无 logo」末段）。⚠️ **不要**把 `favicon.svg` 直接当 `<img>` 用（其 512 方图含大片留白，会使圆圈缩得很小）。

### 九、详情页路由（2026-10-03）

> 用户要求：给详情页加路由，地址为 `/detail`。

- **地址形式**：hash 路由 **`#/detail/<type>/<key>`**。`type` ∈ `index` / `asset` / `hketf` / `cnetf` / `monthlyetf` / `monthlyfund`；`key` = 指数/ETF 代码（如 `930955.CSI`、`03070.HK`、`158023.OF`）或资产名（`asset` 类型，中文做 URL 编码，如 `5年期储蓄国债` → `5%E5%B9%B4%E6%9C%9F%E5%82%A8%E8%93%84%E5%9B%BD%E5%80%BA`）。可直达、可分享、刷新保持、支持前进后退。
- **实现**：`applyRoute()` 首部新增 `detail` 分支（调 `DETAIL_ROUTE[type].open(key)`）；各 `showXxxDetail()` 末尾调 `pushDetailRoute(type, key)` 写地址栏——站内点击推送一条历史；若当前已在某详情 URL（深链进入 / `asset`→`index` 归一化）则**只记录、不重复推送**。
- **延迟打开**：详情深链在首屏执行时数据尚未就绪，`_openDetail()` 将其挂起到 `_pendingDetail`，待 `finishIfDone()`（数据加载完成）再打开。
- **「返回」**：统一走 `closeDetailRoute()`——站内进入（`detailPushedByApp=true`）→ `history.back()` 回上一页；深链直接进入 → 关闭浮层并 `location.replace('#/')` 回首页（**不退出站点**）。
- **裸 `#/detail` / 未知 type**：`applyRoute` 直接 return，保持当前视图、不报错（回落首页）。

### 十、手机端筛选器（漏斗按钮 + 底部弹出面板）（2026-10-04）

> 用户要求（参考豆瓣 App 手机端筛选器）：手机端**未筛选时只留一颗「漏斗 + 筛选器」按钮**，点击后**从底部弹出**筛选面板；选项名称与标签的排版借鉴豆瓣。**仅 ≤767px 生效；桌面端（≥768px）一律不动。**

- **适用范围**：仅**多维筛选页** —— 红利指数浏览器（key `idx`）、境内红利ETF（key `cnetf`）。**食息资讯 `.df-chip`（日报日期 / 单维标签）保持常驻不动** —— 单维 tab 不属于「筛选器」，同豆瓣「想看 / 在看」留在页面上。
- **折叠态**：手机端隐藏 `.index-tagbar`（及 `.cn-etf-count`），改为工具条 `.mf-bar` = 左「共 N / M 只」计数 `.mf-count` + 右按钮 `.mf-btn`（内联漏斗 SVG `MF_FUNNEL_SVG` + 文字「筛选器」+ 数量徽标 `.mf-badge`）。未选=灰框；已选=蓝框（`border-color:#4680FD`、文字蓝）、徽标显示（数字 = 已选维度数）。
- **展开态**：底部弹出 `.mf-sheet`（`max-height:86vh`，`transform:translateY(101%) → 0`，`.28s cubic-bezier(.22,.61,.36,1)`）+ 遮罩 `.mf-mask`（`rgba(0,0,0,.35)`，`.25s`）。层级：遮罩 **z-index 70** / 面板 **71**（低于顶部二级菜单 200，不遮挡顶栏下拉）。
- **面板结构（借鉴豆瓣排版）**：标题行 `.mf-head`（左标题「筛选」+ 右 ✕ `.mf-close`——**2026-10-04 起与汉堡抽屉 `.m-nav-close` 完全一致**：纯黑内联 SVG `22×22`、`stroke-width:1.5`、`40×40` 热区）→ 可滚动主体 `.mf-body`（每组 `.mf-group`：`.mf-group-title` 组名 + `.mf-chips` 内 `.mf-chip` 标签，标签右侧 `<i>` 显示该标签在**当前草稿**下的命中数）→ 底部固定操作行 `.mf-foot`（`.mf-cancel`「取消」/ `.mf-ok`「确定」，各占一半、`52px` 高、`border-left` 分隔，`确定` 蓝字加粗）。
- **交互口径**：① 打开时把**已应用状态**复制为草稿 `mfDraft`，面板内点击**只改草稿**（标签命中数随之实时联动，计数按 `exceptKey` 排除本组做 AND）；② `确定` → 应用草稿并重渲染列表（`mfSyncBadge` 刷新徽标）；`取消` / ✕ / 点遮罩 → **丢弃草稿、结果不变**；③ 「全部 N」= 清空该组，与「再点一次取消选中」等义。
- **「清除筛选」（2026-10-04 追加）**：面板标题行右侧、✕ 左侧（`.mf-head-actions` → `#mfClear`，蓝字文本按钮 `.mf-clear`）。**无任何已选筛选时置灰禁用**（`mfRenderBody()` 每次重渲染时同步 `disabled`）；点击 → 清空草稿全部分组（各组「全部 N」回选中态、命中数联动），**需再点「确定」才写回列表**（与「取消」区分：取消 = 放弃改动）。
- **配置方式**：`mfRegister(key, cfg)` —— `rows()` 取数据源、`get()/set()` 读写该页筛选状态对象（`idxTagFilter` / `cnEtfTagFilter`）、`groups[]` 定义各维度（`label` + `tags` + `match(row, tag)`）。新增多维筛选页按同法注册即可复用本组件。
- **⚠️ 双渲染路径（关键）**：`mobile.js` 在手机端**覆写**了 `window.renderIndices` / `renderCnEtf`（改为 `renderIndicesMobile` / `renderCnEtfMobile` 卡片层）→ `mfBarHtml(...)` 工具条**必须在 `index.html` 与 `mobile.js` 两条路径都注入**；`mobile.js` `placeSelect` 亦改为**优先插到 `.mf-bar` 之后**（排序下拉紧随工具条）。**遗漏任一路径 = 手机端工具条不出现**（2026-10-04 首轮即踩此坑）。
- **样式约定**（用户确认）：选中态沿用全站**蓝底白字 `#4680FD`**、外框 **`var(--line-soft)`**、**直角**（不加圆角）；字号走令牌（计数 / 标签 `--fs-sm`、命中数 `--fs-2xs`、组标题 `--fs-md`）。基础样式 `index.html` 的 `</style>` 前有 `.mf-bar,.mf-mask,.mf-sheet{display:none}` 兜底；手机样式集中在 `mobile.css` 末尾的 `@media (max-width:767px)` 段（桌面 / 平板零影响）。

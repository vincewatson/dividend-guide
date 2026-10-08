# data/curation —— 「清单 + 标注」单一事实来源（Excel-free）

> 目的：**摆脱 Excel 依赖**。本目录是站点「哪些标的要收录」+「个性化标注/口径修正」的
> **唯一来源**（仓库内、git 版本化、零外部依赖）。数据**取值**仍由 Wind / 其它供应商 MCP 提供。
> 见 `docs/data-governance/excel-exit-plan.md`。

## 状态

- **✅ P0 已完成（2026-10-06）**：由 `export_curation.py` 把 Excel 快照 + 博客表的**清单 + 标注**
  一次性冻结为下列 JSON（迁移基线）。
- **✅ P1 已完成（2026-10-06）**：`build_lists.py` 的**标注类字段**（`load_user_index_info` /
  `load_user_hk_etf`）与 `sync_blog.py`（清单 + 标注）均已改读本目录。
- **✅ P2 已完成（2026-10-06）**：`build_lists.py` **不再读任何 xlsx** —— 8 个 builder 全部改读本目录，
  按【列名】取值；Excel 快照文件**已无脚本引用**。`sync_blog.py` 亦已完全脱离 Excel。
- **✅ P3 已完成（2026-10-06）**：`build_lists.py`（由 `sync_excel.py` 更名）、`backup_db.py`、`preflight.py` **全部去 Excel**；原 xlsx 归档至 `archive/excel-baseline-20261006/`。**至此全站无任何 Excel 依赖**。

## 文件

| 文件 | domain | 来源表 | 对应站点数据 | 谁在读（P2/P3 后）|
|---|---|---|---|---|
| `indices_pro.json` | indices | PRO·境内红利指数 | indexData | build_lists（**清单**）|
| `indices_feishu_info.json` | indices | 飞书·红利指数信息表（**指数标注**：详情页/加权方式附加条件/调整周期/调整生效日…）| indexData | build_lists（**标注**）|
| `indices_feishu_yield.json` | indices | 飞书·红利指数股息率（港股税系数等）| indexData | build_lists（**标注**）|
| `indices_main.json` | indices | 主表·红利指数 | indexData | build_lists（**清单**）|
| `cn_etf.json` | cn_etf | PRO·境内红利ETF | cnEtfData | build_lists（**清单**）|
| `hk_etf_pro.json` / `hk_etf_feishu.json` | hk_etf | PRO / 飞书·港交所红利ETF（**标注**：详情页/互联互通）| hkEtfData | build_lists（清单 / **标注**）|
| `monthly_etf.json` | monthly_etf | 主表·月月可分红ETF | etfData | build_lists（**清单**）|
| `monthly_fund.json` | monthly_fund | 主表·月月可分红（场外） | fundData | build_lists（**清单**）|
| `money_fund.json` | money_fund | 主表·货币基金 | moneyFundData | build_lists（**清单**）|
| `reits_equity.json` / `reits_concession.json` | reits | 主表·REITs 产权/经营权类 | reitsData | build_lists（**清单**）|
| `assets.json` | assets | 主表·总表 | assetData | build_lists（**清单**）|
| `blog_articles.json` | blog_articles | 公众号历史文章 | blogData | sync_blog（**清单**）|
| `blog_annotations.json` | blog_annotations | 博客文章标注表 | blogData | sync_blog（**标注**）|
| `_retired.json` | retired | （停用名单 · 非导出项）| cnEtf/hkEtf/reits/moneyFund | sync_lifecycle 维护；build_lists 读取跳过 |
| `_hk_etf_universe.json` | hk_etf_universe | （中央数据库导出的港交所上市 ETF 全量名单 · 非导出项）| hkEtfData | sync_lifecycle 读取（港ETF「出」比对）|
| `_manifest.json` | — | 导出清单（来源文件 / mtime / 行数）| — | 参考 |

> **关于 `money_fund.json`（2026-10-06 说明）**：这是一份**静态对比样本**，站点**仅使用其中「天弘余额宝」（000198.OF）**一支——`sync_money_fund.py` 只实时刷新 000198.OF 的 7 日年化/日万份，`build_money_fund_data()` 每周重建时也**只对带 `yieldDate` 的行（即余额宝）保留 Wind 实时值**，其余 42 行一律沿用本清单的冻结值（停在原处、不更新）。**前端不展示其余货基**（无「货币基金列表」页面；`getYuebaoRate()` 只按名称取余额宝）。清单暂保留 43 行：一是 `check_data.py` 对 `moneyFundData.json` 有「≥30 行」硬校验，二是留作对比样本备用。

## 每个 JSON 的结构

**表格式（清单 + 指数/ETF/基金标注）** —— `indices_*` / `cn_etf` / `hk_etf_*` / `monthly_*` / `money_fund` / `reits_*` / `assets`：

```json
{
  "domain": "...", "source": "<原 xlsx 文件名>", "sourceMtime": "YYYY-MM-DD HH:MM",
  "sheet": "<工作表名>", "headerRow": 0, "unitsRow": 1, "dataStartRow": 2,
  "exportedAt": "YYYY-MM-DD HH:MM:SS",
  "columns": ["...", "..."],
  "rows": [ { "<列名>": <值>, ... }, ... ]
}
```

- 列为**表头名**（非下标）—— 消除「挪列忘改下标」的隐性契约（backlog B-1）。
- `dataStartRow` = 首个数据行在**原表**中的 0 基下标（PRO/飞书/总表 = 1；主表 红利指数/月月*/货币基金/REITs = 2，因其第 1 行是单位行）。导出时用它定位首个数据行（`rows` 已按此裁剪）；**P2 后 builder 直接遍历 `rows`，不再涉及行偏移**。
- 日期统一 `YYYY-MM-DD`；空值 `null`；重复表头追加 ` #2`。
- Excel 里的 `=HYPERLINK("url",...)` 公式列（如「详情页」）已由 `export_curation.py` 用 `openpyxl(data_only=False)` 解析为纯 URL。

**博客专用结构**：

```json
// blog_articles.json
{ "domain":"blog_articles", "source":"...", "columns":["date","title","url","column"], "rows":[{...}] }
// blog_annotations.json
{ "domain":"blog_annotations", "schema":"url -> {direction, indexes}", "annotations": { "<url>": {"direction":"...","indexes":[...]} } }
```

## 编辑约定（今后）

1. **不要**再回到 Excel：清单/标注的增改**直接改本目录 JSON**。
2. 也可**在对话里告知**，由 AI 落到这里并登记 `docs/data-governance/manual-overrides.md`。
3. 本目录随 git 版本化；改口径只改这里，重建脚本统一引用。
4. `export_curation.py` **不入流水线**，仅作「从旧 Excel 重新冻结 / 核对」的一次性工具；它会在 `archive/excel-baseline-*/` 下自动检索 xlsx（见其 `_xlsx_dirs()`）。本目录 JSON 是那批 xlsx 的**冻结结果**，两者已解耦——xlsx 是否留存都不影响站点。
5. **停用名单 `_retired.json`（「出」机制 · 2026-10-06；2026-10-07 判据升级）**：清单的「出」= 基金已结束（清盘/退市/终止）或停止月月分红，由编号外步骤 `sync_lifecycle.py`（及步骤 14 `sync_fund_divdate`）维护，`build_lists.py` 重建时**在全部表外行护栏之后**跳过对应 code（**历史数据不删**，仅移出展示清单；**删条目即恢复**）。三条判据：
   - **清盘名单（中央数据库）** → **境内红利ETF / 货币基金 / 月月分红ETF / 指数基金月月分红**：读 `../../data_center/exports/common/fund-liquidated.json`（全市场已清盘名单，用户在 data_center 点「更新数据库」生成；2026-10-07 已到位），按代码**前 6 位**比对；命中 ⇒ 已清盘 ⇒ **立即移出**。文件缺失 ⇒ 跳过并打印（绝不误判）。
   - **港交所红利ETF** → 用 **中央数据库**（与「策略魔方」同源）的「港交所上市 ETF」全量名单比对：优先读 `../../data_center/exports/common/hk-etf-list.json`，缺失时回退本地冻结副本 `_hk_etf_universe.json`（451 只，由会话内 MCP 从中央库 `fund.product` 导出），再缺则退回抓 aastocks 港股 ETF 列表作后备；标的若**不在**该名单 ⇒ 退市/终止 ⇒ 停用。
   - **REITs** → 仍用 Wind **「基金到期日」**：到期日为空（常青）或为**未来**（合约存续期，如 180101.SZ=2071-06-07）⇒ 保留；**≤ 今天 ⇒ 已结束 ⇒ 停用**。⚠️ **不可**按「非空即出」判定（会误杀全部 REITs）。约 28 天节流。清盘名单命中 ⇒ 立即移出；其它判据需**连续两次运行都命中**才移出（首次标「待观察」）。
6. **新上市红利港ETF 发现（「进」机制 · 2026-10-06）**：编号外步骤 `sync_new_hk_etf.py`，数据源 = `_hk_etf_universe.json` 的 **`dividend_funds`**（中央数据库全量名单中按关键词「红利/高息/高股息/股息率/股东回报/央企回报」筛出、**排除 REIT** 的红利类基金，含简称/全称/互联互通、含 -R/-U 多柜台）。脚本按 **ETF 全称归并**（剥离「(上市类别)」后缀后比对）多柜台/多份额类别，每只基金只保留**主柜台（港元，代码最小）**，再与 `hkEtfData.json` + `_retired.json` 对照得「新标的」。**流水线默认 `--add` 自动补入** `hkEtfData.json`（与 cnEtfData 同机制，靠 `build_lists` 表外行护栏保留）；不带 `--add`（或 `--dry-run`）则仅报告、不改数据。⚠️ 自动补入的行可能缺 `trackCode`/`detailUrl`（Wind 对部分新港ETF不提供跟踪指数代码，如 3590.HK），须人工补。

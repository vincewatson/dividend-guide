# data/curation —— 「清单 + 标注」单一事实来源（Excel-free）

> 目的：**摆脱 Excel 依赖**。本目录是站点「哪些标的要收录」+「个性化标注/口径修正」的
> **唯一来源**（仓库内、git 版本化、零外部依赖）。数据**取值**仍由 Wind / 其它供应商 MCP 提供。
> 见 `docs/data-governance/excel-exit-plan.md`。

## 状态

- **✅ P0 已完成（2026-10-06）**：由 `export_curation.py` 把 Excel 快照 + 博客表的**清单 + 标注**
  一次性冻结为下列 JSON（迁移基线）。
- **✅ P1 已完成（2026-10-06）**：`sync_excel.py` 的**标注类字段**（`load_user_index_info` /
  `load_user_hk_etf`）与 `sync_blog.py`（清单 + 标注）均已改读本目录；**Excel 快照仅剩「清单」作用**。
- **⏳ P2/P3 待做**：清单改由 curation + Wind 自动发现维护；最终删除 `sync_excel.py` 的 `read_excel` 路径。

## 文件

| 文件 | domain | 来源表 | 对应站点数据 | P1 后谁在读 |
|---|---|---|---|---|
| `indices_pro.json` | indices | PRO·境内红利指数 | indexData | sync_excel（**清单**）|
| `indices_feishu_info.json` | indices | 飞书·红利指数信息表（**指数标注**：详情页/加权方式附加条件/调整周期/调整生效日…）| indexData | sync_excel（**标注**）|
| `indices_feishu_yield.json` | indices | 飞书·红利指数股息率（港股税系数等）| indexData | sync_excel（**标注**）|
| `indices_main.json` | indices | 主表·红利指数 | indexData | sync_excel（**清单**）|
| `cn_etf.json` | cn_etf | PRO·境内红利ETF | cnEtfData | sync_excel（**清单**）|
| `hk_etf_pro.json` / `hk_etf_feishu.json` | hk_etf | PRO / 飞书·港交所红利ETF（**标注**：详情页/互联互通）| hkEtfData | sync_excel（清单 / **标注**）|
| `monthly_etf.json` | monthly_etf | 主表·月月可分红ETF | etfData | sync_excel（**清单**）|
| `monthly_fund.json` | monthly_fund | 主表·月月可分红（场外） | fundData | sync_excel（**清单**）|
| `money_fund.json` | money_fund | 主表·货币基金 | moneyFundData | sync_excel（**清单**）|
| `reits_equity.json` / `reits_concession.json` | reits | 主表·REITs 产权/经营权类 | reitsData | sync_excel（**清单**）|
| `assets.json` | assets | 主表·总表 | assetData | sync_excel（**清单**）|
| `blog_articles.json` | blog_articles | 公众号历史文章 | blogData | sync_blog（**清单**）|
| `blog_annotations.json` | blog_annotations | 博客文章标注表 | blogData | sync_blog（**标注**）|
| `_manifest.json` | — | 导出清单（来源文件 / mtime / 行数）| — | 参考 |

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
- `dataStartRow` = 首个数据行在**原表**中的 0 基下标（PRO/飞书/总表 = 1；主表 红利指数/月月*/货币基金/REITs = 2，因其第 1 行是单位行）。必须与 `sync_excel.py` 各 builder 的行偏移一致。
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
4. `export_curation.py` **不入流水线**，仅作「从旧 Excel 重新冻结 / 核对」的一次性工具；P3 后即使删除 xlsx 也不影响站点。

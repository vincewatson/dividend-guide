# data/curation —— 「清单 + 标注」单一事实来源（Excel-free）

> 目的：**摆脱 Excel 依赖**。本目录是站点「哪些标的要收录」+「个性化标注/口径修正」的
> **唯一来源**（仓库内、git 版本化、零外部依赖）。数据**取值**仍由 Wind / 其它供应商 MCP 提供。
> 见 `docs/data-governance/excel-exit-plan.md`。

## 状态

- **P0 已完成（2026-10-06）**：由 `export_curation.py` 把当前 Excel 快照的**清单 + 标注**
  一次性冻结为下列 JSON（迁移基线）。
- **P1/P2/P3 待做**：逐步让重建脚本改读本目录，最终删除 `sync_excel.py` 的 `read_excel` 路径。

## 文件

| 文件 | domain | 来源表 | 对应站点数据 |
|---|---|---|---|
| `indices_pro.json` | indices | PRO·境内红利指数 | indexData |
| `indices_feishu_info.json` | indices | 飞书·红利指数信息表（**指数标注**：详情页/加权方式附加条件/调整周期/调整生效日…）| indexData |
| `indices_feishu_yield.json` | indices | 飞书·红利指数股息率（港股税系数等）| indexData |
| `indices_main.json` | indices | 主表·红利指数 | indexData |
| `cn_etf.json` | cn_etf | PRO·境内红利ETF | cnEtfData |
| `hk_etf_pro.json` / `hk_etf_feishu.json` | hk_etf | PRO / 飞书·港交所红利ETF（**标注**：详情页/互联互通）| hkEtfData |
| `monthly_etf.json` | monthly_etf | 主表·月月可分红ETF | etfData |
| `monthly_fund.json` | monthly_fund | 主表·月月可分红（场外） | fundData |
| `money_fund.json` | money_fund | 主表·货币基金 | moneyFundData |
| `reits_equity.json` / `reits_concession.json` | reits | 主表·REITs 产权/经营权类 | reitsData |
| `assets.json` | assets | 主表·总表 | assetData |
| `_manifest.json` | — | 导出清单（来源文件 / mtime / 行数）| — |

## 每个 JSON 的结构

```json
{
  "domain": "...", "source": "<原 xlsx 文件名>", "sourceMtime": "YYYY-MM-DD HH:MM",
  "sheet": "<工作表名>", "headerRow": 0, "unitsRow": 1,
  "exportedAt": "YYYY-MM-DD HH:MM:SS",
  "columns": ["...", "..."],
  "rows": [ { "<列名>": <值>, ... }, ... ]
}
```

- 列为**表头名**（非下标）—— 消除「挪列忘改下标」的隐性契约（backlog B-1）。
- 日期统一 `YYYY-MM-DD`；空值 `null`；重复表头追加 ` #2`。

## 编辑约定（今后）

1. **不要**再回到 Excel：清单/标注的增改**直接改本目录 JSON**。
2. 也可**在对话里告知**，由 AI 落到这里并登记 `docs/data-governance/manual-overrides.md`。
3. 本目录随 git 版本化；改口径只改这里，重建脚本（P1/P2 后）统一引用。

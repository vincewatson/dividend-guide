# 摆脱 Excel 依赖 · 迁移方案（excel-exit）

> 背景（2026-10-06 用户指令）：① 数据一律从 **Wind / 其它数据供应商 MCP** 取；② **尽量所有工作都不再依赖 Excel**，**包括「标注」这块也要做好**。
> 本文为**现状核查 + 目标架构 + 分阶段实施**方案。执行前请先确认「四、待确认」。

---

## 一、现状核查（**历史快照 · 迁移前状态**；P0→P3 已完成，见文末「执行进度」）

> **P0→P3 全部完成后现状（2026-10-06）**：`build_lists.py`（由 `sync_excel.py` 更名）**已不读任何 xlsx**（8 个 builder 全读 `data/curation/*.json`）；`sync_blog.py` 亦完全脱离 Excel；`backup_db.py` / `preflight.py` 已去 Excel；原 xlsx 已归档 `archive/excel-baseline-20261006/`。**站点已无任何 Excel 依赖**。下表为迁移前的原始核查记录，保留以备追溯。


- `sync_excel.py`（**1139 行**）在 `auto_sync_deploy.sh` 的 **step 4 / step 11 每周各跑一次**，从 3 个 Excel 快照**按列下标**重建 **8 个**数据文件：
  `assetData / indexData / cnEtfData / hkEtfData / etfData / fundData / moneyFundData / reitsData`。
- 快照文件（`data/user/*.xlsx`）修改时间：**主表/PRO = 2026-09-20**、**飞书表 = 2026-08-02**（已陈旧）；且 **xlsx 未入库**（`.gitignore` 排除 `data/user/`、`user_upload/`、`*.xlsx`）→ 「事实来源」不在版本控制里。
- 因此：用户认为「已不依赖 Excel」，**实际未退出**；每周流水线仍在用陈旧 Excel 的**名单**（数值多由后续 Wind 步骤刷新）。

### Excel 提供的东西 = 两类
| 类别 | 内容 | 现存放 |
|---|---|---|
| **① 清单（哪些标的）** | 指数 / 境内红利ETF / 港交所红利ETF / 月月分红ETF / 月月分红(场外) / 货币基金 / REITs / 首页资产 的**名单** | 3 个 xlsx |
| **② 标注（个性化口径 / 修正）** | 指数：全称·发布机构·发布日期·目标市场·币种·加权方式(**附加条件**)·样本调整周期·调整生效日·**详情页**；港交所ETF：**详情页**·互联互通；港股红利税系数；月月金额字段；首页资产 note/desc/来源 | 飞书表 + 主表/PRO 表 +（部分）代码常量 |

### 已有的「标注」机制（迁移时须一并搬迁，不能丢）
1. **飞书表 `data/user/食息指南Pro-飞书.xlsx`** —— 用户的**指数 / 港ETF 元数据与口径标注**：
   - `红利指数信息表`：指数代码/名称/**详情页**/全称/发布机构/发布日期/成分个数/目标市场/加权方式/**加权方式(附加条件)**/**样本调整周期**/**样本调整生效日**/股息率
   - `红利指数股息率`：港股红利税系数、每月千元分红需总投入
   - `港交所红利ETF`：**详情页**/互联互通ETF/跟踪指数/管理人/费率/规模/最近分红日
2. **博客标注表 `user_upload/博客文章标注表*.xlsx`**（2026-10-05，**仍在用**）—— 内容标签 / 相关指数；由 `sync_blog.py` 合并、并**回写** `data/blogAnnotations.json`。 → **✅ P1 已迁移**：清单/标注冻结为 `data/curation/blog_articles.json` + `blog_annotations.json`，`sync_blog.py` 只读它们、**不再读写任何 xlsx**；旧镜像 `data/blogAnnotations.json` 已删除。
3. **代码常量（`sync_excel.py`）**：`MANUAL_FIELDS` / `AUTHORITATIVE_MANUAL` / `NOTE_OVERRIDE` / `BOND_OVERRIDE` / `EXTRA_ASSETS` / `ASSET_DESC` / `smart_tax_rate`。
4. **对话落地通道**：用户在对话里告知的修正 → AI 落到 `data/*.json` + 登记 `docs/data-governance/manual-overrides.md`（**本身就是「无 Excel」通道**）。

---

## 二、目标架构（Excel-free）

| 层 | 目标 |
|---|---|
| **取数** | 一律 **Wind MCP**（+ 其它供应商 MCP）；已入中央库的优先走 `central-market-db`（见根 `AGENTS.md`）|
| **清单 + 标注** | 收敛到**一个仓库内、git 版本化的单一事实来源**（建议 `data/curation/*.json`）；**不再读写任何 xlsx** |
| **重建** | 保留「整表重建 + 表外行护栏」思路；builder 改由 **curation + Wind** 生成，删除 `pd.read_excel` 路径 |
| **标注通道** | ① `data/curation/` 里的**按实体覆盖**（字段级修正）；② **对话 → AI 写 JSON + 登记台账**（沿用 `manual-overrides.md`）；两者都**不依赖 Excel** |

---

## 三、分阶段实施（每阶段独立上线，`check_data` 仍为硬门槛）

- **P0 冻结 & 导出**：把当前 Excel 的**清单 + 标注一次性导出**为 `data/curation/*.json`（whitelists + overrides），作为迁移基线与「单一事实来源」初版。**不改流水线**。
- **P1 标注切换**：`sync_excel.py`（及 `sync_blog.py`）的**标注类字段**改读 curation JSON（此阶段 Excel 仅剩「清单」作用）；博客标注改读写 JSON。
- **P2 清单切换**：清单改由 **curation JSON + Wind 自动发现**（`sync_new_etf` / `sync_new_reits` / `sync_new_monthly`）维护；`sync_excel` 不再读 xlsx。
- **P3 移除 Excel 层**：删除 `find_snapshot` / `load_sheet` / `SNAP1·SNAP2·SNAP_USER` 与 `pd` 依赖；`backup_db.py` / `preflight.py` 去掉 Excel；归档 xlsx 与相关文档章节。

---

## 四、已确认（2026-10-06 用户拍板）

1. **单一来源** = **仓库内 JSON** → `data/curation/*.json`（git 版本化、可 review、零外部依赖）。
2. **移除力度 = 分阶段（P0→P3）**：先建 JSON 源并双跑校验，稳定后再删 Excel 层。

### 执行进度
- **✅ P0 已完成（2026-10-06）**：新增一次性迁移工具 `export_curation.py`，把 Excel 快照 + 博客表的**清单 + 标注**导出为 `data/curation/` 下 **15 个 JSON**（+ `_manifest.json`），列按**表头名**存储（消除「按列下标取值」的隐性契约，见 backlog B-1）；已 git 版本化。**未改任何流水线**。
  - 修 2 处导出缺陷：① **数据起始行 off-by-one**（PRO/飞书/总表实为第 1 行数据，非第 2 行）；② 飞书「红利指数信息表」**详情页为 `=HYPERLINK()` 公式**（pandas 读为 None）→ `openpyxl(data_only=False)` 正则补全 **49/49**。
  - 导出对照（修正后）：indices（PRO 48 / 飞书信息表 49 / 飞书股息率 23 / 主表 22）、cn_etf 88、hk_etf（PRO 12 / 飞书 12）、monthly_etf 15、monthly_fund 26、money_fund 43、reits（产权 35 / 经营权 23）、assets 16；博客 `blog_articles.json` 289、`blog_annotations.json` 115。
- **✅ P1 已完成（2026-10-06）**：`sync_excel.py` 的标注类字段（`load_user_index_info` / `load_user_hk_etf`）改读 `data/curation/`（**Excel 仅剩「清单」作用**）；`sync_blog.py` **完全脱离 Excel**——文章清单 + 标注均读 curation JSON，不再读 `user_upload/*.xlsx`、不再回写，**删除**冗余镜像 `data/blogAnnotations.json`。
  - **一致性验证**：parity 工具逐字段比对「旧 Excel 载入器 vs 新 curation 载入器」→ `load_user_index_info` / `load_user_hk_etf` / `build_index_data` / `build_hk_etf_data` **端到端 0 差异**；`blogData.json` 仅 1 处预期订正（`上证红利`→`红利指数`）。`check_data` ✅。
- **✅ P2 已完成（2026-10-06）**：`sync_excel.py` **不再读任何 xlsx** —— 8 个 builder（asset/index/cnEtf/hkEtf/etf/fund/moneyFund/reits）全部改读 `data/curation/*.json`，按【列名】取值（**消除「按列下标取值」隐性契约 → backlog B-1 关闭**）；删除 `find_snapshot` / `load_sheet` / `SNAP1·2·USER` 与 `pandas` / `openpyxl` 依赖；`sizeDate` 改取 curation `sourceMtime`（= 原 xlsx mtime）。Wind 自动发现（`sync_new_etf` / `sync_new_reits` / `sync_new_monthly`）继续以「表外行护栏」并入重建结果，**逻辑不变**。
  - **一致性验证**：parity 工具比对「HEAD(P1: Excel 清单) vs 新(P2: curation 清单)」→ **8 个 builder 输出 0 差异**（顺序 + 逐字段）；`sizeDate` 来源 5 项全部一致；`main()` 输出与 P1 逐字节一致；`check_data` ✅。
- **✅ P3 已完成（2026-10-06）**：① `backup_db.py` 去掉 Excel 源文件备份（仅备份 `data/*.json`）；`preflight.py` 清理 `excel_*` 残留命名（改 `lists_*`）、清单检测来源说明。② `sync_excel.py` **更名为 `build_lists.py`**，流水线（`auto_sync_deploy.sh` 步骤 4/11）与各脚本/文档引用同步。（注：2026-10-07 起 `build_lists` 的两次重建已**合并为一次**、脚本中无编号。）③ 原 xlsx（`data/user/*` 3 个 + `user_upload/*` 3 个）**归档**至 `archive/excel-baseline-20261006/`（不入库）；`export_curation.py` 改在归档目录自动检索，仍可对归档 Excel 重跑核对。
  - **一致性验证**：`build_lists.py` 仅改文件名/注释/入口说明，逻辑未动 → 与 P2 逐字段一致；全部 `.py` 语法检查通过；`check_data` ✅。站点数据无变化。

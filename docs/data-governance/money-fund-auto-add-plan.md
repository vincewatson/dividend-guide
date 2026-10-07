# 货币基金「进」机制 · 自动补入方案（未实测）

> 建立：2026-10-07 · 状态：**方案（未实测；流水线尚未接入，仅此文档 + 代码预留护栏）**
> 归属：清单「进」机制（与境内红利ETF / 港交所红利ETF / REITs / 月月分红 的自动补入并列）。

## 一、为什么要做 / 现状

- 站点 `moneyFundData.json` 目前**仅「天弘余额宝」（000198.OF）**被实际使用（首页 `getYuebaoRate()` 只按名称取余额宝；
  无「货币基金列表」页）。`data/curation/money_fund.json` 另存 43 行作为**静态对比样本**——
  一是 `check_data.py` 对 `moneyFundData.json` 有「≥30 行」硬校验，二是留作样本备用。
- 现状下货基清单**不自动更新**：既不自动「进」（新货基不补入），「出」则已在 `sync_lifecycle.py` 改为
  按中央库 `fund-liquidated.json` 清盘名单判定（按代码前 6 位）。
- 本文档给出**「进」的做法**：如何从中央数据库 / 全市场筛选货币基金，自动补入 `moneyFundData.json`，
  并登记到 `data/curation/_auto_added.json` 与 `.list_changes.json`（与其它清单同一套机制）。

## 二、判据与口径

1. **筛选范围**：全市场**货币市场型基金**（Wind 投资类型「货币市场型基金」；中央库 `fund.product` 的
   `sec_type='货币基金'`）。**不**预设主题白名单。
2. **份额去重**：同一产品的多个份额类别（A/C/E/I/Y 等）只保留一类（与 `sync_new_monthly.py` 的
   「A 类优先、无则取检出之一」一致），避免同基金多份额重复收录。
3. **代码口径**：站点 `code` 一律 `base + '.OF'`（与 `build_lists` / 中央库「基金用 .OF 代码」一致）。
4. **字段**：`code / name / size / fee / feeNum / yield7d / yield7dNum / dailyWan / yieldDate`（见
   `build_lists.build_money_fund_data`）。缺值**留空/不写 0**（站点规则：无值显示 `—`，禁止假值）。
5. **不含已清盘**：与 `_retired.json`（清盘名单）对照，已清盘的**不补入**。
6. **站点展示**：即便补入，前端目前**不展示**其它货基——本机制目的是**数据完备**（`moneyFundData.json`
   与中央库对齐、为将来可能的「货基列表」页做准备），不改变首页余额宝取数。

## 三、做法（三步）

### 步骤 1：取全量货基清单（优先中央库，0 Wind）
- **首选**：读中央库导出 `exports/common/fund-list.json`（`meta.title`=「基金名录（场内 + 场外，不含已清盘）」，
  `sec_type` 取值含「货币基金」），筛出 `sec_type=='货币基金'` 的 `security_id`。
  → **0 次 Wind**，且天然「不含已清盘」。
- **回退**：中央库导出缺失时，用 Wind `search_funds` 查询「货币市场型基金」（或按投资类型/成立日筛）。
  - 预期返回列：`Wind代码 / 证券简称 / 成立日`（列名会漂移，须**按列名解析**，禁用固定下标）。

### 步骤 2：与现有清单对照，得「新货基」
- 读 `data/moneyFundData.json` + `data/curation/_retired.json`（清盘）+ `data/curation/_auto_added.json`（已自动补入）。
- 差集 = 新货基候选；做**份额去重**。

### 步骤 3：取详情并写回 + 登记
- 对每个新货基（用 **Wind 全代码**，如 `000198.OF`）批量取详情：
  - `get_fund_info`：`基金简称 / 基金成立日 / 管理费率 / 基金扩位场内简称`（12 只/批）。
  - `get_fund_holders`：`最新规模`（12 只/批；规模字段建议带 `sizeDate`，与其它清单一致）。
  - 7 日年化 / 日万份（`get_fund_financials`）：**货币基金数值每日波动**，若纳入则属「日更」类，
    需评估额度；**本方案建议首版只补身份/规模/费率字段**，7 日年化仍由既有 `sync_money_fund.py`
    口径维护（目前只刷余额宝）。
- 写回 `moneyFundData.json`（**只追加、不删除**；原子 `save_json`）。
- 登记：`lifecycle_common.record_auto_added([{code,list:'money',...}])` +
  `record_list_changes([{action:'add',list:'money',...}])`；由 `build_lists.py` 的
  「表外行保留」护栏（`_auto_added.json`）保证每周整表重建不被冲掉。

## 四、预计 Wind 用量（**未实测**）

| 环节 | 调用 | 批量 | 预计次数 |
|---|---|---|---|
| 全量货基清单（中央库 `fund-list.json`） | 0 | — | **0** |
| （回退）全量货基检索 `search_funds` | 1–3 | — | **1–3** |
| 新货基详情 `get_fund_info` | ⌈N/12⌉ | 12 只/批 | **⌈N/12⌉** |
| 新货基规模 `get_fund_holders` | ⌈N/12⌉ | 12 只/批 | **⌈N/12⌉** |
| （可选）7 日年化逐只 | N | — | N（**不建议首版纳入**） |

- 记号：**N = 去重后的「新货基」数**。
- **首次全量**（假设全市场货基去重后约 **250–350 只**，其中绝大多数已在中央库 `fund-list.json`，
  仅需补规模/费率）估算 **≈ 30–60 次**；若回退到 Wind 检索全量，另加 **1–3 次**。
- **日常增量**（每周新成立 0–3 只货基）估算 **≈ 0–3 次 / 周**。
- ⚠️ 上述均为**纸面估算**，**未经实跑验证**（本方案未接入流水线、未跑任何 Wind 调用）。
  实际用量取决于：中央库 `fund-list.json` 的覆盖度、Wind 批量契约（单次 ≤7 字段 / ≤12 只）、
  份额去重比例、以及是否纳入 7 日年化。

## 五、护栏与联动

- **入库护栏**：`data/curation/_auto_added.json`（**入库**，不 gitignore）记录补入的 `code`；
  `build_lists.py` 重建时并入各清单「表外行保留」，防止被整表重建冲掉。
- **清盘**：`sync_lifecycle.py` 按 `fund-liquidated.json`（前 6 位）判定，命中即移出。
- **变动报告**：`add` 事件进 `.list_changes.json`，由 `make_run_report.py` 汇总到当日运行报告。
- **校验**：`check_data.py` 对 `moneyFundData.json` 有「≥30 行」门槛——自动补入只会增加行数，不会触发该门槛失败。

## 六、风险与未决

1. **未实测**：批量契约、列名漂移、中央库覆盖度均未实测；上线前须先 `--dry-run` 核对。
2. **站点暂不展示**：补入的货基短期无可见效果，属「数据治理/完备性」投入，需确认是否有必要。
3. **7 日年化口径**：若纳入则变为日更类、额度敏感；首版建议**不纳入**，沿用 `sync_money_fund.py`。
4. **命名口径**：货基 `简称` 与站点其它清单一致以 Wind「基金简称/扩位场内简称」为准，需人工复核个别。

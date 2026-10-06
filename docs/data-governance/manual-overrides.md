# 手工修订台账（manual-overrides）

> 用途：用户**在对话里告知**的手工修正，统一登记在这里，并由 AI 负责落到 `data/*.json` 且**保证不被每周整表重建冲掉**。
> 建立：2026-09-27（用户约定）。

## 一、工作约定（2026-09-27 用户确认）

1. **今后的手工修订 → 直接在对话里告诉 AI**，不要改飞书/Excel 表。
2. **飞书/Excel 表**只在「做全新表格、需要一次性批量提交数据」时使用，不作为日常手工修订通道。
3. AI 收到手工修订后必须做三件事：
   - ① 落到对应 `data/*.json`；
   - ② 登记到本台账（日期 / 目标 / 字段 / 原值→新值 / 依据）；
   - ③ **确认该字段能扛住重建**——见下节「落地方式」。
4. 本台账位于 `docs/`，不随站点部署；它是"记录"，权威值本身以 ② 落地的 JSON/代码为准。

## 二、落地方式（决定手工值会不会被冲掉）

`build_lists.py` 对 8 个文件是**整表重建**。手工值要长期有效，必须按下表选择落地方式：

| 落地方式 | 适用 | 说明 |
|---|---|---|
| **A. 直接改 JSON** | `indexData` 的 `MANUAL_FIELDS`（共 10 个：publisher/listedDate/weight/weightExtra/yield/yieldNum/components/market/currency/fullReturn） | `build_lists` 会「旧值非空**且非 0** 则保留」，直接改 JSON 即长期有效 ✅ |
| **B′. 代码硬编码（补加名单）** | `indexData` 的 `adjustCycle/adjustDate`、或任何不在 `MANUAL_FIELDS` 的字段 | 这些字段目前只从用户表读入、直接改 JSON **不会**保留；需加入 `MANUAL_FIELDS` 或用方式 B |
| **B. 代码硬编码** | 任意文件的任意字段 | 写进 `build_lists.py` 的 `AUTHORITATIVE_MANUAL`（indexData）或为其他文件新增同类常量/护栏；**最稳**，但需改代码 |
| **C. 新增保留护栏** | 该文件尚无对应白名单 | 在 `build_lists` 的重建循环里加「保留旧值」逻辑后再落地 |
| **D. 不改 JSON** | 每日/每周自动源已覆盖的字段 | 应改数据源脚本，而非手工值 |

> 约定：登记时**必须写明本行用了哪种落地方式**，否则视为未完成。

## 三、台账

| 日期 | 目标（文件 / 记录） | 字段 | 原值 → 新值 | 依据 | 落地方式 | 状态 |
|---|---|---|---|---|---|---|
| 历史 | `indexData.json` `000922.CSI` | listedDate | → 2008-05-09 | 用户/官方核对 | B（AUTHORITATIVE_MANUAL） | ✅ |
| 历史 | `indexData.json` `930917.CSI` | components | → 99 | 用户/官方核对 | B | ✅ |
| 历史 | `indexData.json` `SPCADMCP.SPI` | components / weight | → 100 / 因子加权 | 用户/官方核对 | B | ✅ |
| 历史 | `indexData.json` `995128.SSI` | components / market | → 50 / 沪港深 | 用户/官方核对 | B | ✅ |
| 历史 | `indexData.json` `995127.SSI` | components / market | → 100 / 沪港深 | 用户/官方核对 | B | ✅ |
| 历史 | `indexData.json` `995082.SSI` | components | → 50 | 用户/官方核对 | B | ✅ |
| 2026-10-06 | `assetData.json` **新增**「红利低波」 | 整条记录（`type=红利`；`yield`/`date` 取 `indexData` `H30269.CSI` divHistory 最新 = `4.39%` / `2026-09-30`；`note=近12个月股息率`；`source=Wind`） | 无 → 新增（红利组末尾第 6 条） | 用户要求「首页『主流资产食息率』加一个红利低波指数」 | B（`build_lists.py` 新增常量 `EXTRA_ASSETS`，`build_asset_data` 重建时按 `type` 追加到红利组末尾）+ A（同步改 `data/assetData.json`）；另 `index.html` `ASSET_TO_INDEX_CODE` 增 `'红利低波':'H30269.CSI'` 使点击进入指数详情页 | ✅ |
| 2026-10-06 | `fundData.json` **移出**「022097.OF 长城中证红利低波100ETF联接A」| 整条记录（从「月月分红场外」名单删除）| 在名单（最近分红 2026-07-28）→ 移出 | 用户要求：月月分红名单应只含「每月连续分红」产品；该基金 8、9 月均无分红，Wind 核实最近一次分红 2026-07-28，已非月月 | **C（新增规则护栏）**：`sync_fund_divdate.py` 增 `prune_stale_monthly`（步骤 14 自动移出「最近分红早于上一个月」的 etfData/fundData 成员；Excel 仍会带回，恢复月月分红则自动回归）+ 已同步删 JSON；`check_data.py` 增 7b 硬校验 | ✅ |
| 2026-10-06 | `data/etfData.json` / `fundData.json` **新增**「月月名单」3 只 | 整条记录：`021583.OF 中欧中证港股通央企红利指数A`、`022325.OF 长城中证港股通高股息投资指数A`、`021375.OF 中欧中证红利低波动100指数A` | 无 → 新增（fundData 25 → 28） | 用户口径「**≥11 次 / 全市场口径 / 直接自动加**」：月月名单**新增**成员改为自动（近 1 年分红次数 ≥ 11，A 类去重，限指数产品；主动管理产品不纳入）| **C（新增规则护栏 + 新脚本）**：新建 `sync_new_monthly.py`（编号外步骤，位于 step 13 后、step 14 前）；`build_lists.py` 增 etfData/fundData **表外行保留护栏**（防每周整表重建冲掉）；`check_data.py` 增 7c 行结构完整性校验 | ✅ |
| 2026-10-06 | `indexData.json` **新增** `HSSSCHD.HI`（trackOnly 详情页补充指数） | 整条记录（`trackOnly: true`；`name=恒生沪深港(特选企业)高股息率`；`yield=5.50%`/`yieldNum=5.5033`；`divHistory` 504 点 2024-09-13~2026-10-02；全称/发布机构/发布日期/30 成分/港股/HKD） | 无 → 新增（indexData 57 → 58；**不入红利指数浏览器**）| 用户要求：该指数在港交所红利ETF（`3190.HK 富邦沪深港高股息`）有挂钩产品、Wind 可取股息率，应把数据补入数据库并展示在对应详情页（不入浏览器）。同批核实的另两个指数（`HSHD30.HI`、`DAAXJP.GI`）Wind 取不到股息率、用户确认「缺的话就不用管」→ 不纳入 | **C（表外行护栏）**：`build_lists.py` 已保留 Excel/用户表外的 indexData 条目；`divHistory` 由 `sync_div_history` 每周自动维护（遍历全部代码）；前端 `findIndexForTrack` 按 code 命中、`renderIndices` 用 `!trackOnly` 排除出列表 | ✅ |

> 上表"历史"行 = 代码 `build_lists.py · AUTHORITATIVE_MANUAL` 中既有的权威硬编码值（补登记，非本次新增）。
> 后续新增手工修订请**追加行**，勿覆盖历史行。

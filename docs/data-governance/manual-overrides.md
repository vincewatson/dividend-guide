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

`sync_excel.py` 对 8 个文件是**整表重建**。手工值要长期有效，必须按下表选择落地方式：

| 落地方式 | 适用 | 说明 |
|---|---|---|
| **A. 直接改 JSON** | `indexData` 的 `MANUAL_FIELDS`（共 10 个：publisher/listedDate/weight/weightExtra/yield/yieldNum/components/market/currency/fullReturn） | `sync_excel` 会「旧值非空**且非 0** 则保留」，直接改 JSON 即长期有效 ✅ |
| **B′. 代码硬编码（补加名单）** | `indexData` 的 `adjustCycle/adjustDate`、或任何不在 `MANUAL_FIELDS` 的字段 | 这些字段目前只从用户表读入、直接改 JSON **不会**保留；需加入 `MANUAL_FIELDS` 或用方式 B |
| **B. 代码硬编码** | 任意文件的任意字段 | 写进 `sync_excel.py` 的 `AUTHORITATIVE_MANUAL`（indexData）或为其他文件新增同类常量/护栏；**最稳**，但需改代码 |
| **C. 新增保留护栏** | 该文件尚无对应白名单 | 在 `sync_excel` 的重建循环里加「保留旧值」逻辑后再落地 |
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
| 2026-10-06 | `assetData.json` **新增**「红利低波」 | 整条记录（`type=红利`；`yield`/`date` 取 `indexData` `H30269.CSI` divHistory 最新 = `4.39%` / `2026-09-30`；`note=近12个月股息率`；`source=Wind`） | 无 → 新增（红利组末尾第 6 条） | 用户要求「首页『主流资产食息率』加一个红利低波指数」 | B（`sync_excel.py` 新增常量 `EXTRA_ASSETS`，`build_asset_data` 重建时按 `type` 追加到红利组末尾）+ A（同步改 `data/assetData.json`）；另 `index.html` `ASSET_TO_INDEX_CODE` 增 `'红利低波':'H30269.CSI'` 使点击进入指数详情页 | ✅ |

> 上表"历史"行 = 代码 `sync_excel.py · AUTHORITATIVE_MANUAL` 中既有的权威硬编码值（补登记，非本次新增）。
> 后续新增手工修订请**追加行**，勿覆盖历史行。

# docs 索引（食息指南）

> 2026-08-22 重组：原《网站更新与数据管理对照文档.md》按"参考 / 治理 / 手册 / 日志 / 问题 / 待办"拆分。
> **当前唯一权威规范以 `reference/` 和 `data-governance/` 下的文件为准；`changelog/` 只是历史记录，不代表当前状态。**

| 目录 / 文件 | 回答什么问题 |
|---|---|
| [reference/](reference/) | **规则是什么**——格式 / 口径 / 样式约定，随时查阅 |
| [data-governance/](data-governance/) | **数据从哪来、怎么更新、有什么铁律**——数据字典 + 更新机制 + Wind 经验 |
| [runbooks/](runbooks/) | **具体怎么操作**——每周更新 checklist、季度 SOP，照着做不出错 |
| [changelog/](changelog/) | **历史上改过什么**——按月归档，仅供追溯，不代表当前状态 |
| [known-issues.md](known-issues.md) | **踩过什么坑、怎么防复发**——问题 → 根因 → 解决方案 |
| [backlog.md](backlog.md) | **已知但暂不实施的改进项**（技术债）——现状 → 风险 → 目标 → 触发时机 |

## reference/ · 规则是什么

| 文件 | 内容 |
|---|---|
| [data-format-rules.md](reference/data-format-rules.md) | 显示格式统一（日期 / 占位 / 小数 / 资讯禁【】）、数据源口径统一（股息率 / 手动字段保护 / REITs 两类口径 / 红利指数覆盖 / ETF 简称唯一口径 / 指数币种变体归并）、其他约定 |
| [ui-style-rules.md](reference/ui-style-rules.md) | **设计 Token 速查** + 前端样式约定（footer / 阴影外框 / 详情页 / 基准线 / 内容宽 1280px）+ 移动端样式规则（汉堡菜单 / 筛选器 / 触屏 hover / 列表卡片 / 食息提示折叠，全部 Mobile CSS 规范）|
| [ui-colors.md](reference/ui-colors.md) | Tailwind CSS v4 全色板（26 色板 × 11 阶），配色参考 |

## data-governance/ · 数据从哪来、怎么更新

| 文件 | 内容 |
|---|---|
| [data-catalog.md](data-governance/data-catalog.md) | 数据矩阵（文件→来源→脚本→保护）、数据文件清单、各数据域来源明细、数据源优先级、指数币种变体归并、口径模糊 / 数据重复问题的标准处理范式 |
| [update-mechanism.md](data-governance/update-mechanism.md) | 三条铁律、标准流程（**原 21 步；2026-10-07 起 `build_lists` 合并为一次、`fix_laggard_indexes` 已删**）、**更新频次总表（数据→来源→脚本→频次）**、新 ETF / 新指数自动发现、数据更新机制（增量优先 / 防回退 / 离线保障 / 上传区 / 目录规范）|
| [wind-query-tips.md](data-governance/wind-query-tips.md) | Wind 拉取经验清单（拉取前 / 中 / 出错纪律 / 落地优化 / 08-16 实测补充）|
| [manual-overrides.md](data-governance/manual-overrides.md) | **手工修订台账**——用户在对话里告知的手工修正登记处 + 落地方式（防重建冲掉）｜2026-09-27 建 |

## runbooks/ · 具体怎么操作

| 文件 | 内容 |
|---|---|
| [weekly-update-checklist.md](runbooks/weekly-update-checklist.md) | 更新后必查清单（部署前）+ 定期更新内容总清单（B1 每周六 21 步流水线 / B2 季度租金率 / B3 不定期 / B4 每日手动）|
| [quarterly-rent-sop.md](runbooks/quarterly-rent-sop.md) | 重点50城租金房价比 · 季度收集 SOP（中指研究院口径、发布节奏、收集流程、口径铁律）|

## changelog/ · 历史上改过什么

> 归档粒度与条目写法约定见 [changelog/README.md](changelog/README.md)：**按月归档，单月超 40 KB 则次月起按半月拆分**；单条只记「结论 + 验证方式」。

- [2026-10.md](changelog/2026-10.md)：10 月变更记录（周更 21 步 + sync_daily 性能修复 + check_data 国债周频口径）
- [2026-09.md](changelog/2026-09.md)：09 月变更记录（食息资讯日报化 + 4 项脚本修复 + 数据治理）
- [2026-08.md](changelog/2026-08.md)：08 月全部变更记录（98 条，v168 → v302）
- [2026-07-and-earlier.md](changelog/2026-07-and-earlier.md)：更早记录（当前为空）

> ⚠️ **每周自动更新前置步骤（统一编号：步骤 1 修订文档 → 步骤 2 确认逻辑 → 步骤 3 语法预检；2026-08-15 用户指令，最高优先级）**：
> - **步骤 1 · 修订索引对应文件**：发现新规范先写入 `reference/` 或 `data-governance/` 对应文件（简洁 + 准确），冲突需求一律**以用户最新指令为准**。
> - **步骤 2 · 确认自动任务执行逻辑**：核对「食息指南网站数据更新」定时任务与 `auto_sync_deploy.sh` 的步骤数、顺序、脚本清单是否与 `data-governance/update-mechanism.md` 一致；发现不一致先修正脚本/任务，再执行更新。顺序固定：**修订文档 → 确认逻辑 → 才允许开始数据同步**（脚本流水线从**步骤 3 语法预检**起）。
> - 变更执行后，在 `changelog/` 对应月份文件追加一条记录（| 日期 | 变更 | 验证/要点 |）。
>
> 完整步骤清单见 `data-governance/update-mechanism.md`「标准流程」或 `runbooks/weekly-update-checklist.md` B1。⚠️ **2026-10-07 重构阶段 3/4 起**：`build_lists` 由原「第 4 + 第 11 步」两次重建**合并为只跑一次**（脚本中打印为无编号的 `[重建]`）；`fix_laggard_indexes.py` **已删除**（逻辑并入 `sync_div_history.py`）。

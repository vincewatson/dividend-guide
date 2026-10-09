# Agent 规则

## 工作目录约定（2026-10-04 确立）

**本站（食息指南 dividend-guide）的所有网站改动，只能写入本目录：**
`/Users/vincentwatson/Library/CloudStorage/坚果云-vincent.watson@live.com/Codes/trae/dividend-guide-website`

不得写入本目录以外的任何其他位置。

## Git 提交约定（2026-10-04 确立）

本仓库有远端 `origin`（GitHub 公开仓 `vincewatson/dividend-guide`）。**每次改动完成后，直接 `git commit` 并 `git push origin main`，不要逐个询问用户**（用户明确要求：不要把提交/推送做成一轮对话）。

- 提交信息用 `feat:` / `fix:` / `docs:` 前缀 + 简述；版本类改动带上版本号（如 `v0.1.84`）。
- 推送前确认 `.gitignore` 已排除敏感/大文件（`data/user/`、`user_upload/`、`*.xlsx`、`backup/`、`archive/`、`*.bak*`）。
- 仓库为 **public**：禁止提交/推送用户原始数据与上传文件。
- 推送凭据：GitHub 细粒度 PAT（仅本仓 `Contents: Read and write`）存于 `~/.config/dividend-guide/studio-credentials.txt`，且已写入 macOS 钥匙串（`host=github.com`）。若 push 报 `Invalid username or token`，从该文件取 `GITHUB_PAT` 重新写入钥匙串（`git credential-osxkeychain store`）或临时用 `git -c http.extraheader="Authorization: Basic <base64(x-access-token:PAT)>" push origin main`。

## 统一数据库 data_center（2026-09-24 确立）

本项目与食息指南、资管棱镜、Index Analyzer、策略魔方、食息资讯归档共用同一个资本市场数据库 **data_center**。它分成 9 个独立的库（ref 公共参照 / idx 指数 / fund 基金 / rates 利率 / quote 行情 / industry 行业统计 / portfolio 组合 / fundnews 基金行业动态 / yielddaily 食息日报），库之间通过 `hub.*` 视图互相关联：

- Windows：`D:\Codes\data_center`；MacBook：坚果云同步目录下的 `data_center` 文件夹
- **读写 data_center 之前，必须先完整阅读其中的 `AGENTS.md`，并按其中的规则操作。**

要点（有出入时以 AGENTS.md 为准）：

1. **读取**：首选 MCP 服务 `central-market-db`（先 `find_data`，库里没有的再去外部取，取到后用 `submit_data` 写回）；没有配置 MCP 时，用 `exports/` 下的 JSON；直接查 `db/<库>.duckdb` 时必须用 `read_only=True`（跨库查询用 `pipelines/hub.py` 的 `open_all()`）。
2. **写入**：只能通过 `python pipelines/submit.py`，本项目的 project 名为 `dividend-guide`。禁止直接修改 `db/`、`warehouse/`、`exports/`、`sources/`、`domains/`（含各库合同）、`curated/`、`pipelines/`。
3. **口径**：比率一律用小数（5% 写 0.05），日期写成 YYYY-MM-DD，基金用 .OF 代码。只能使用 `domains/<库>/contracts/` 里登记过的指标、标签和字段；需要新增时，在 `data_center/proposals/` 里写提案，不要自己改合同。
4. **不要运行** data_center 的 `build.py`，除非用户明确要求。它只在 Windows 主构建机上运行。
5. **本站自己的 `data/` 目录目前仍是网站的数据来源**，本规则不改变现有的取数、同步和部署流程。
6. **和 data_center 重叠的数据**：红利 ETF、红利指数股息率、利率序列（见 `exports/dividend/`）。修改这几类数据的取数口径时，要同步考虑 data_center。
7. **规模字段已带日期（2026-10-08 更新）**：2026-09-26 起规模字段已补 `sizeDate`（清单来源快照日期 / Wind 取数日期），历史上的「`cnEtfData.json` 规模字段没有标注日期」问题**已修复**。截至 2026-10-08 仅 3 只新 ETF（`158039`/`561650`/`562200`）缺 `sizeDate`（`sync_wind_fields` 下轮补齐）。

## 数据更新流程重构（2026-10-06 起）

**数据更新流程一律以 `docs/data-governance/update-redesign.md` 为唯一目标规范**（重构期间其优先级高于 `update-mechanism.md`；重构完成后把现行规则并入 `update-mechanism.md`，本规范归档）。

- 按该规范的「实施顺序」**分阶段进行，一次只做一个阶段**；每阶段完成后必须：`check_data.py` 全部通过、与改造前 `data/*.json` 对比除日期外无意外差异、在该规范附录记一行「阶段 N 完成：耗时 / Wind 次数 前→后」。
- **额度不足时停在当前阶段**，下次继续；**不为赶进度跳过验收**。
- 自阶段 0 起新增统一 Wind 客户端 **`wind_client.py`**：**所有 Wind 调用只经它**（按日/按步计数，写 `.wind_usage/YYYY-MM-DD.json`），各脚本不再直接 `subprocess.run(['node', <cli.mjs>, ...])`。新增取数脚本必须走 `wind_client`。
- Wind 额度保护（2026-10-06）：`wind_guard_cli.mjs`（调用级每日硬上限）+ `run_gate.py`（每日整跑闸，`SX_FORCE_RUN=1` 可强制）。
- **入口自动判档（2026-10-07 · 按星期 · 北京时间）**：`auto_sync_deploy.sh` 默认按星期自动决定档位——**周一至周五只跑日更；周六/周日同一次运行「日更 + 周更」、只部署一次**；**同一个周末只跑一次周更**（若本周六 0 点后已跑过周更，即 `.run_state.json:lastWeekly ≥ 本周六`，则周日再点只跑日更）；**兜底：距上次周更 > 13 天，不论周几都补跑周更**。手动覆盖：`--weekly` 只跑周更、`--daily` 只跑日更（手动优先）。运行报告开头写明本次档位与原因。
- **测试与额度规矩（2026-10-07）**：见 `./.trae/rules/project_rules.md`「数据更新 · 测试与额度规矩」——一天最多真实整跑一次；改代码先用模拟/单项检查；不用 `SX_FORCE_RUN=1`（除非用户明确同意）；日更 ≤300 / 周更 ≤650 / 当天合计 ≤1600；开跑前用 1 次最轻调用确认账号可用。

## 治理档案（供 project-governance-review 使用）

- **项目名 / 复盘目录名**：`dividend-guide`（复盘报告写 `Codes/all_coding_projects/_复盘/dividend-guide/<日期>.md`）
- **主力 Agent 与电脑**：TRAE · Mac；⚠️ Windows 侧 Claude / WorkBuddy 会经坚果云同步同一目录，易产生冲突副本（已在 `.gitignore` 忽略 `*冲突*`）
- **规则文档**：`.trae/rules/project_rules.md`（Agent 规则）+ `docs/reference/*`（格式 / 口径 / 样式）
- **误操作记录**：`docs/known-issues.md`（`## N. 标题（日期）` 体例）
- **数据清单文档**：`docs/data-governance/data-catalog.md` + `docs/data-governance/update-mechanism.md`
- **数据目录**：`data/`（体检用 `--data data`）
- **更新方式**：`bash auto_sync_deploy.sh`（入口按【星期·北京时间】自动判「日更 / 周更」）；定时任务 = TRAE「食息指南 - 网站数据更新」`a0479427`（cron `0 15 * * SAT`，Paused，按需手动触发）
- **部署**：Cloudflare Pages 项目 `dividend-guide`（主域 `divlab.net`）；脚本 `deploy_cloudflare.sh`（wrangler 直传；排除清单见其 rsync `--exclude`）
- **与 data_center 的关系**：**上游**——只读取 `../../data_center/exports/common/*.json`（`hk-etf-list.json` / `fund-liquidated.json`）；写入须经 `data_center/pipelines/submit.py`，project 名 `dividend-guide`
- **文档惯例**：`reference/` 与 `data-governance/` 为权威；`changelog/` 仅为历史；手工修订登记到 `docs/data-governance/manual-overrides.md`
- **本项目特有的检查项**：① `check_data.py` 全 ✅ 是**部署硬门槛**；② 清单进出闭环（`data/curation/_retired.json` / `_auto_added.json`）；③ 港交所代码统一 **5 位 + `.HK`**（与中央库 `sec_code` 对齐）；④ 坚果云冲突副本（`*冲突*`）不入库、不部署

## 本地开发模式 · 暂停自动部署（2026-10-08 用户确立）

**`deploy/LOCAL_MODE` 存在期间，手工改动（样式、页面、脚本等）做完不部署；数据更新照常部署。** 规则全文见 `deploy/README.md`，要点：

1. 任何任务做完：给用户看**本地页面**（双击 `deploy/本地预览.command`，或本地打开 `http://localhost:8090/`），**不要部署**。
2. 每完成一项改动，在 `deploy/待部署清单.md` **追加一行**（时间 / 类型 / 用户看得懂的一句话 / 涉及文件）；没有就新建。
3. **数据更新（日更 / 周更）例外：照常部署。** 部署会连带上线清单里已完成的本地改动，脚本部署成功后自动把清单记入 changelog 并删除清单。还没改完、不想上线的改动，先不要跑数据更新（或先告诉用户）。
4. **其他时候只有用户明确说“部署”才部署**：复述清单 → `check_data.py` 全通过 → 提交 → `deploy_cloudflare.sh` → 逐项线上核对 → 清单内容写入 `docs/changelog/` 当月文件 → **删除 `deploy/待部署清单.md`**。
5. 退出本地模式 = 删除 `deploy/LOCAL_MODE`（需用户同意）。

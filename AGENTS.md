# Agent 规则

## 工作目录约定（2026-10-04 确立）

**本站（食息指南 dividend-guide）的所有网站改动，只能写入本目录：**
`/Users/vincentwatson/Library/CloudStorage/坚果云-vincent.watson@live.com/Codes/trae/dividend-guide-website`

不得写入微云（`~/Documents/微云/...`，该目录已废弃、即将删除）或任何其他位置。

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
7. **已知口径问题**：`cnEtfData.json` 的规模字段没有标注日期，和资管棱镜的数据有出入（见 data_center 的 `docs/build-report.md`）。修改取数脚本时请补上日期字段。

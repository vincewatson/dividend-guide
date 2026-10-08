# 给网页 Agent 的接入提示词

把下面整段复制给网页 Agent（TRAE）。

---

请把仓库里的 `红利机会值/` 页面接入食息指南网站并部署。要求：

1. **只做接入，不改算法和数字**
   - `红利机会值/engine/`、`红利机会值/data/` 下的文件由 Claude 维护，不要修改、不要重算。
   - 页面的所有数字都来自 `红利机会值/data/opportunity.js`（同内容的 `opportunity.json` 供程序读取）。如果数字看起来不对，停下来告诉我，不要自行改。

2. **路由与入口**
   - 页面入口：`红利机会值/index.html`。若中文路径不便，可在 `_redirects` 里加一个英文别名（如 `/dividend-opportunity` → `/红利机会值/`），不要重命名文件夹。
   - 在顶部导航合适的位置（建议放在「红利指数」下拉里）加一个入口「红利机会值（A股）」。
   - 页面自带一个简化顶栏（logo 链回首页）。如果改为嵌入站内页面框架，就去掉页面自带的 `<header class="top-bar">`，换成站点统一页头和页脚；其余样式保留。

3. **样式规范**：页面已按 `docs/reference/ui-style-rules.md` 做过对齐（品牌蓝 #4680FD、直角、无阴影、14px、Arial + PingFang SC、中文与数字不加空格）。接入时如发现与站点不一致的地方，按站点规范微调 CSS 即可。配色只用蓝、绿、红、浅蓝（加中性灰），不要引入黄色、橙色。

4. **部署与仓库**
   - `红利机会值/inputs/` 下的 Wind 原始数据（`*.xlsx`、`*.csv`）**不能提交**（文件夹内已有 `.gitignore`，请确认生效）；`inputs/observe.json` 可以提交。
   - 部署前检查：`deploy_cloudflare.sh` 的 rsync 排除清单不要把 `红利机会值/data/` 排除掉；`inputs/` 和 `engine/` 不需要部署到线上，可以加进排除清单。
   - 按仓库现有约定 commit + push，提交信息用 `feat: 新增红利机会值页面`。

5. **以后的数据更新**（暂不自动化）：用户从 Wind 导出新数据放进 `红利机会值/inputs/`，运行 `python3 红利机会值/engine/opportunity_engine.py` 重新生成 `data/`，然后照常部署。若要并入 `auto_sync_deploy.sh`，请另开任务，并且取数必须走 `wind_client.py`（届时由 Claude 提供改造后的取数函数）。

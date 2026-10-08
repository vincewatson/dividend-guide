# 给 TRAE 的指令：红利机会值 · 首次 Wind 取数验证（2026-10-08）

把下面整段发给 TRAE。

---

请在 `dividend-guide-website` 仓库根目录，帮我验证「A股红利机会值」的万得取数脚本能不能正常取到数。**只按下面步骤运行和汇报，不要修改任何代码或配置文件。**

背景：`fetch_opportunity_inputs.py` 和 `opportunity_central.py` 是 Claude 写的，说明见 `docs/data-governance/opportunity/README.md` 的「更新数据」一节。机会值现在从中央库 data_center 读历史数据，每周用万得只补最近几天的缺口，取到后写回中央库。脚本已用模拟数据测过，但还没真实调用过万得。

规矩：遵守 `AGENTS.md` 和 `.trae/rules/project_rules.md` 的万得额度规则。这次一共大约 12 次万得调用。不要设 `SX_FORCE_RUN`；任何一步出现额度不足（rc=3 / QUOTA_ERROR），立刻停下来汇报。

**第 1 步：看缺口（0 次万得调用）**

```bash
python3 fetch_opportunity_inputs.py --plan
```

预期：列出 6 条序列各自覆盖到哪天（应为 2026-09-30），以及待取区间和计划调用次数。

**第 2 步：试取（约 6 次万得调用，不写任何文件）**

```bash
SX_WIND_STEP=fetch_opportunity_inputs.py SX_WIND_MODE=weekly python3 fetch_opportunity_inputs.py --probe
```

预期：每条序列都打印「取到 N 天」。最近 10 天里有国庆休市，N 是个位数，正常。

- 如果全部 N > 0，继续第 3 步。
- 如果有任何一条是「取到 0 天」或报错，**停下来，不要改代码**。把第 2 步的完整输出原样发给我，我转给 Claude 处理。

**第 3 步：正式取数 + 写回中央库（约 6 次万得调用）**

```bash
SX_WIND_STEP=fetch_opportunity_inputs.py SX_WIND_MODE=weekly python3 fetch_opportunity_inputs.py
```

预期：
- 每条序列「取到 N 天」。
- 生成 `inputs/opportunity/increments.csv`。
- 出现两行「✓ 写回中央库」（行情一批、10 年国债一批）。如果出现「⏸ 未写回中央库」或「✗ 写回失败」，照样继续第 4 步，但在汇报里写明。

**第 4 步：重算机会值并检查**

```bash
python3 opportunity_engine.py
python3 check_data.py
```

预期：
- 引擎第一行是「· 读取中央库 opportunity-inputs.json+index-dividend-yield.json+rates.json + 本地增量 … 行」，**不是**「读取 inputs/opportunity/data_add.xlsx」。
- 最后一行「✅ 数据截至 2026-10-xx，机会值 …」，日期应是最新交易日。
- `check_data.py` 全部通过。

**不要部署**（本地模式），也不要提交 `inputs/` 下的任何文件（已被 .gitignore 排除，确认一下）。

**第 5 步：汇报**

把下面这些原样发给我：
1. 第 1–4 步每一步的完整终端输出；
2. `python3 wind_client.py` 的输出（今天的万得用量）；
3. `inputs/opportunity/increments.csv` 的前 10 行；
4. `git status` 的输出。

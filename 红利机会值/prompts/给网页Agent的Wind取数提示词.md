# 给网页 Agent 的提示词：用万得 MCP 复刻「红利机会值」输入数据

> 用法：把下面「提示词正文」整段发给网站开发 Agent。它在 `dividend-guide-website/` 仓库里工作。

---

## 提示词正文

你要为 `红利机会值/` 模块写一个取数脚本，用**万得 MCP（只能经由仓库里的 `wind_client.py`）**复刻目前由用户在万得终端手工导出的输入数据，让模块逐步不再依赖手工导出。

**你的职责只是取数和对数。** 算法、权重、打分逻辑都不归你管，下面列出的文件一律不许修改。

### 一、先读这些文件，读完再动手

1. `AGENTS.md`：仓库规则，尤其是 Wind 配额那部分
2. `wind_client.py`：唯一的 Wind 调用入口
3. `sync_asset_macro.py` 里的 `call_wind`：调用方式和返回值的解析方式
4. `sync_div_history.py`：用自然语言查询指数股息率历史的写法，按 ≤90 天分段
5. `红利机会值/inputs/README.md`：手工导出的数据是什么样，这就是你要复刻的目标
6. `红利机会值/engine/opportunity_engine.py` 里的 `load_csv_inputs`：只读，看它要哪些列

### 二、不许修改的文件

- `红利机会值/engine/opportunity_engine.py`
- `红利机会值/engine/config.json`
- `红利机会值/engine/compare_inputs.py`
- `红利机会值/data/*`：只能由引擎生成，不能手改
- `红利机会值/docs/*`
- `红利机会值/index.html`

如果你认为必须改其中的任何一个，停下来，把理由写给用户。

### 三、要取的数据（日频，2010-01-01 至最新）

| 输出列 | 代码 | 含义 | Wind 字段/指标 | 单位 |
|---|---|---|---|---|
| `hl_close` | 000922.CSI 中证红利 | 收盘价（价格指数） | close | 点 |
| `hl_turn` | 000922.CSI | 换手率 | turn | %，例如 0.85 |
| `hl_tr` | H00922.CSI 中证红利全收益 | 收盘价 | close | 点 |
| `hl_dy` | 000922.CSI | 股息率（近12个月） | dividendyield2 | %，例如 4.28 |
| `wa_dy` | 881001.WI 万得全A | 股息率（近12个月） | dividendyield2 | %，例如 1.95 |
| `y10` | EDB M0048271 | 中国:国债到期收益率:10年（中国货币网） | `economic_data/query_economic_indicator_data` | %，例如 1.85 |
| `hl_amt`（可选） | 000922.CSI | 成交额 | amt | 元 |
| `wa_close`（可选） | 881001.WI | 收盘价 | close | 点 |
| `wa_turn`（可选） | 881001.WI | 换手率 | turn | % |

**口径要求：**

- **股息率必须是「近12个月 / TTM」口径（dividendyield2）**，不能用静态股息率或预测股息率。TTM 口径在中期分红时会有失真，这是已知问题，模型就是按这个口径校准的，不要自行"修正"。
- `hl_close` 用价格指数 000922.CSI，`hl_tr` 用全收益指数 H00922.CSI，两者不能混用。
- 百分比一律存成数值，不要存成小数。例如 4.28 表示 4.28%，不要写成 0.0428。
- 如果某个工具返回的单位和上表不同，先换算成上表单位再写入，并在报告里写明你做了什么换算。

**可用工具**（名称以仓库现有脚本为准）：

- `index_data/get_index_kline`
- `index_data/get_index_price_indicators`
- `index_data/get_index_fundamentals`
- `economic_data/query_economic_indicator_data`：参数为 `question`、`beginDate`、`endDate`，返回 `metrics[{meta.name, date[], value[]}]`
- 股息率历史参照 `sync_div_history.py` 的写法

**参数名不要猜。** 先在仓库里 grep 现有的调用写法；没有现成写法的，每个工具只做 **1 次**小范围探测调用（例如只取最近 10 天），确认参数和返回结构后再批量取。

### 四、要写的脚本：`红利机会值/engine/fetch_inputs.py`

1. **所有 Wind 调用都必须经过 `wind_client`**，写法照 `call_wind`，并设置 `SX_WIND_STEP=hongli_opportunity`。不要直接调 node，不要另写一个客户端。
2. **分段与缓存：**
   - 按工具允许的最大区间分段，股息率按 ≤90 天分段。
   - 每段的原始返回存到 `红利机会值/inputs/.cache/<series>_<start>_<end>.json`。
   - 已有缓存的段不再请求。如果一个段的结束日期在最近 10 个交易日内，视为"未封口"，每次都重新请求，覆盖缓存。
3. **先估算再调用：**
   - 运行时先打印本次计划调用次数。
   - 如果超过当天剩余配额，只跑配额以内的段，然后正常退出，下次接着跑（断点续传）。
   - `wind_client` 返回 rc=3（pending/配额）时，立即停止，不要重试。
4. **全量与增量：**
   - 第一次运行时从 2010-01-01 开始回补。
   - 之后只请求最后一个已封口段之后的数据。
5. **对齐：**
   - 以 000922.CSI 的交易日作为主索引。
   - 其他序列按日期 reindex 到主索引上。
   - **不要插值，也不要前向填充**，缺失的就留空（y10 的填充由引擎处理）。
6. **输出：**
   - 全部必需列都齐了，才写 `红利机会值/inputs/wind_daily.csv`。
   - 文件为 UTF-8，无 BOM，第一列是 `date`（YYYY-MM-DD），升序，其后是上表各列，列名必须一字不差。
   - 如果有任何必需列取不到，改写成 `inputs/wind_daily.partial.csv`，并在报告里说明缺哪列、为什么。这样引擎会自动回退去读手工导出的 xlsx，网站不会坏。
7. **自检：** 写完后打印每列的起止日期、非空行数、最新值。下列情况视为异常，报告给用户，不要自行处理：
   - 必需列中有任何一列最后一个非空值早于最新交易日 3 天以上
   - 股息率不在 0.5~10 之间
   - y10 不在 0.5~6 之间
8. **测试：** 先用 mock 的返回值写单元测试，跑通之后才做真实调用。真实全量运行一天最多一次。**不许设置 `SX_FORCE_RUN`**，除非用户明确同意。

### 五、验收（三步全过才算完成）

**1. 对数。** 用户的手工导出文件需要放在 `inputs/` 里：

```bash
python3 红利机会值/engine/compare_inputs.py --since 2018-01-01
```

退出码 0 才算通过。容差已经写在脚本里：
- 收盘价 ±0.01
- 股息率 ±0.01
- y10 ±0.005
- 换手率 ±0.001 或 0.1%

不通过时，把脚本输出原样贴给用户，再写上你判断的原因（口径、单位、复权、日期错位等）。**不要为了通过而改数据或改容差。**

**2. 对分。** 分别用两种数据源跑引擎，比较打印出来的机会值：

```bash
python3 红利机会值/engine/opportunity_engine.py          # source=auto，有 wind_daily.csv 就读它
python3 - <<'EOF'
import json; c=json.load(open('红利机会值/engine/config.json',encoding='utf-8'))
c['inputs']['source']='xlsx'; json.dump(c,open('/tmp/cfg_xlsx.json','w',encoding='utf-8'),ensure_ascii=False)
EOF
python3 红利机会值/engine/opportunity_engine.py --config /tmp/cfg_xlsx.json
```

两次的机会值相差 ≤0.5 才算通过。参考值：截至 2026-09-30，手工数据下是 41.7。比完以后**用 auto 再跑一次**，确保 `data/` 里的文件是由 Wind MCP 数据生成的。

**3. 不提交原始数据。** 用 `git status` 确认 `inputs/*.csv`、`inputs/*.xlsx`、`inputs/.cache/` 都没有进入提交。`.cache/` 已写进 `红利机会值/.gitignore`，确认它生效即可。

### 六、通过验收之后（先问用户，同意了再做）

- 把 `fetch_inputs.py` 和引擎接进 `auto_sync_deploy.sh`，顺序是：取数 → 引擎 → 部署。取数失败或对数异常时跳过引擎，保留上一版 `data/`。
- 建议频率：每周一次，例如周五收盘后。
- 观察指标 `inputs/observe.json` 暂时继续手工维护，不在这次范围内。

### 七、做完给用户的报告（简短）

- 新增或修改了哪些文件
- 实际调用次数，以及有没有触发配额
- 对数结果，即 `compare_inputs.py` 的输出
- 两种数据源的机会值对比
- 哪些数据仍然要手工导出，原因是什么

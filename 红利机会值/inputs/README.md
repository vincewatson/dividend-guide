# 输入数据（Wind 导出）

> 引擎优先读 `wind_daily.csv`（由 `engine/fetch_inputs.py` 经万得 MCP 生成，列定义见 `prompts/给网页Agent的Wind取数提示词.md`）；该文件不存在时，回退读下面的手工导出文件。两者可用 `engine/compare_inputs.py` 对数。

原始数据只放本地，**不要提交到公开仓库**（本目录 `.gitignore` 已排除 `*.xlsx` / `*.csv`）。

## 1. `data_add.xlsx`

用 Wind Excel 插件导出，日期 2010-01-01 至最新，日频。两个 sheet，**sheet 名和列位置要保持一致**（引擎按列位置读取，前 6 行是 Wind 表头）：

**sheet「收盘价+成交额+换手率」**：三个区块并排，每块 4 列（日期 + 3 个字段），块之间空 1 列
| 列 | 代码 | 字段 |
|---|---|---|
| A–D | 000922.CSI 中证红利 | 日期、收盘价 close、成交额 amt、换手率 turn |
| F–I | H00922.CSI 中证红利全收益 | 日期、收盘价 close、（成交额）、（换手率） |
| K–N | 881001.WI 万得全A | 日期、收盘价 close、成交额 amt、换手率 turn |

**sheet「市盈率+市净率」**：两个区块
| 列 | 代码 | 字段 |
|---|---|---|
| A–D | 000922.CSI | 日期、股息率(近12个月) dividendyield2、PE(TTM)、PB(LF) |
| F–I | 881001.WI | 日期、股息率(近12个月) dividendyield2、PE(TTM)、PB(LF) |

文件里其他 sheet（财务数据、股息率对比等）引擎不读，保留无妨。

## 2. `中国_国债到期收益率_10年.csv`

Wind EDB 指标 **M0048271（中国:国债到期收益率:10年，中国货币网）**，日频，直接导出 CSV（GBK 编码，前 5 行是指标信息）。

## 3. `observe.json`

观察指标（不计分），手工更新最新值即可，字段：`name` / `value` / `note`。

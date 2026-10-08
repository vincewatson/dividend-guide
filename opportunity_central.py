# -*- coding: utf-8 -*-
"""A股红利机会值 · 中央库输入层（2026-10-08，Claude）

引擎的历史输入改从中央数据库 data_center 读取（经 exports/，站点环境不依赖 duckdb），
再叠加本地增量（inputs/opportunity/increments.csv，由 fetch_opportunity_inputs.py 经 Wind MCP 取得）。

所需序列（中央库口径，比率为小数）：
    000922.CSI close / dividend_yield / turnover_rate
    H00922.CSI close
    881001.WI  dividend_yield
    rates「10年期国债到期收益率」yield
优先级：中央库导出 > 本地增量 > data/indexData.json（000922 股息率，站点日更已取）。
"""
import json, os
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))

# (wind_code, metric) → 引擎列名；引擎内部单位：股息率/换手率/收益率用「百分数」（4.28 表示 4.28%）
SERIES = {
    ("000922.CSI", "close"): "close",
    ("000922.CSI", "turnover_rate"): "turn",
    ("000922.CSI", "dividend_yield"): "dy",
    ("H00922.CSI", "close"): "tr",
    ("881001.WI", "dividend_yield"): "wa_dy",
    ("RATES", "10年期国债到期收益率"): "y10",
}
PCT_COLS = {"turn", "dy", "wa_dy", "y10"}
REQUIRED = ["close", "turn", "tr", "dy", "wa_dy"]   # y10 允许前向填充
Y10_NAME = "10年期国债到期收益率"


def central_dir(cfg=None):
    d = os.environ.get("SX_DATA_CENTER")
    if not d and cfg:
        d = cfg.get("inputs", {}).get("central_dir")
    d = d or "../../data_center"
    return os.path.normpath(os.path.join(BASE, d))


def _rows(path):
    import time
    for i in range(6):                         # 坚果云同步中文件会被短暂锁住（Errno 35），稍等重试
        try:
            with open(path, encoding="utf-8") as f:
                o = json.load(f)
            break
        except OSError:
            if i == 5:
                raise
            time.sleep(5)
    keys = [c["key"] for c in o.get("columns", [])]
    return keys, o.get("rows", []), o.get("meta", {})


def load_central_long(cfg=None):
    """读中央库导出 → 长表 [date, wind_code, metric, value]（小数）。缺文件的部分跳过。"""
    root = os.path.join(central_dir(cfg), "exports", "dividend")
    parts, found = [], []
    p = os.path.join(root, "opportunity-inputs.json")          # 专用导出（提案 2026-10-08-dividend-guide-190554）
    if os.path.exists(p):
        keys, rows, _ = _rows(p)
        df = pd.DataFrame(rows, columns=keys)[["date", "wind_code", "metric", "value"]]
        parts.append(df); found.append("opportunity-inputs.json")
    p = os.path.join(root, "index-dividend-yield.json")         # 已有导出：股息率
    if os.path.exists(p):
        keys, rows, _ = _rows(p)
        df = pd.DataFrame(rows, columns=keys)
        df = df[df["wind_code"].isin(["000922.CSI", "881001.WI"])]
        df = df.rename(columns={"dividend_yield": "value"})[["date", "wind_code", "value"]].assign(metric="dividend_yield")
        parts.append(df); found.append("index-dividend-yield.json")
    p = os.path.join(root, "rates.json")                        # 已有导出：利率
    if os.path.exists(p):
        keys, rows, _ = _rows(p)
        df = pd.DataFrame(rows, columns=keys)
        df = df[df["name"] == Y10_NAME].rename(columns={"yield": "value"})[["date", "value"]]
        parts.append(df.assign(wind_code="RATES", metric=Y10_NAME)); found.append("rates.json")
    if not parts:
        return pd.DataFrame(columns=["date", "wind_code", "metric", "value"]), found
    out = pd.concat(parts, ignore_index=True)
    out["date"] = out["date"].astype(str).str[:10]
    out = out.drop_duplicates(["date", "wind_code", "metric"], keep="first")   # 专用导出在前，优先
    return out, found


def load_increments(path):
    if not os.path.exists(path):
        return pd.DataFrame(columns=["date", "wind_code", "metric", "value"])
    df = pd.read_csv(path, dtype={"date": str})
    return df[["date", "wind_code", "metric", "value"]]


def load_site_dy():
    """站点日更已取的 000922 股息率（data/indexData.json divHistory，单位 %）→ 长表（小数）。"""
    p = os.path.join(BASE, "data", "indexData.json")
    try:
        data = json.load(open(p, encoding="utf-8"))
        h = next(x for x in data if x.get("code") == "000922.CSI").get("divHistory") or []
        return pd.DataFrame([{"date": x["date"], "wind_code": "000922.CSI", "metric": "dividend_yield",
                              "value": float(x["yield"]) / 100} for x in h if x.get("yield") is not None])
    except Exception:
        return pd.DataFrame(columns=["date", "wind_code", "metric", "value"])


def combined_long(cfg=None, increments_path=None):
    """中央库 > 本地增量 > 站点 indexData。返回 (长表, 说明)。"""
    c, found = load_central_long(cfg)
    inc = load_increments(increments_path) if increments_path else load_increments("")
    site = load_site_dy()
    frames = [f.assign(_p=i) for i, f in enumerate([c, inc, site]) if len(f)]
    if not frames:
        return pd.DataFrame(columns=["date", "wind_code", "metric", "value"]), {"central_files": found, "central_rows": 0, "increment_rows": 0}
    allp = pd.concat(frames, ignore_index=True)
    allp["date"] = allp["date"].astype(str).str[:10]
    allp = allp.sort_values("_p").drop_duplicates(["date", "wind_code", "metric"], keep="first")
    return allp.drop(columns="_p"), {"central_files": found, "central_rows": len(c), "increment_rows": len(inc)}


def last_dates(long_df):
    """每条所需序列的最后日期 {(code,metric): 'YYYY-MM-DD' or None}。"""
    out = {}
    for key in SERIES:
        s = long_df[(long_df.wind_code == key[0]) & (long_df.metric == key[1])]
        out[key] = s["date"].max() if len(s) else None
    return out


def to_engine_frame(long_df):
    """长表 → 引擎宽表（DatetimeIndex，列 close/turn/tr/dy/wa_dy/y10，百分数口径）。缺必需序列返回 None。"""
    cols = {}
    for (code, metric), name in SERIES.items():
        s = long_df[(long_df.wind_code == code) & (long_df.metric == metric)]
        if s.empty:
            return None, f"缺序列 {code} {metric}"
        v = pd.to_numeric(s["value"], errors="coerce").values
        cols[name] = pd.Series(v * (100 if name in PCT_COLS else 1), index=pd.to_datetime(s["date"].values))
    df = pd.DataFrame(cols).sort_index()
    df["y10"] = df["y10"].ffill()
    df = df.dropna(subset=REQUIRED)            # 只保留必需序列都齐的交易日（以 000922 交易日为准）
    return df, f"{df.index.min().date()} ~ {df.index.max().date()}，{len(df)} 个交易日"

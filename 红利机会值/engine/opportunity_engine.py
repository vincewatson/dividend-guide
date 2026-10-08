# -*- coding: utf-8 -*-
"""
红利机会值（A股）计算引擎
=========================
输入：Wind 导出的行情/估值表（data_add.xlsx）+ 10年期国债收益率（CSV）
输出：../data/opportunity.json 与 ../data/opportunity.js（页面直接读取）

用法：
    python engine/opportunity_engine.py                 # 读取 engine/config.json
    python engine/opportunity_engine.py --config 其他配置.json

方法（v4，2026-10-07 定稿）：
  1. 四项机会分（0–100，越高机会越大）
     - 阶段涨跌幅 P：价格指数近250日涨跌（−12%→100，+18%→0）与偏离250日均线（−13.5%→100，+16.5%→0）各半
     - 股息率溢价 S：股息率(剔除12月调样跳升) − 10Y国债，滚动5年分位
     - 相对性价比 R：股息率(剔除调样跳升) ÷ 万得全A股息率，滚动5年分位
     - 换手率 T：20日均换手率滚动5年分位，取反
  2. 加权：P 55% + S 20% + R 15% + T 10%
  3. 标准化：与加权分自身过去5年的均值/标准差比较，机会值 = 50 + 20 × z，截断在 0–100
依赖：pandas、openpyxl
"""
import argparse, json, os, sys, datetime as dt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------- 读数
def read_block(xls, sheet, c0, names):
    df = pd.read_excel(xls, sheet_name=sheet, header=None, skiprows=6, usecols=range(c0, c0 + len(names) + 1))
    df.columns = ["d"] + names
    df = df[pd.to_datetime(df["d"], errors="coerce").notna()].copy()
    df["d"] = pd.to_datetime(df["d"])
    for c in names:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index("d").sort_index()

# 标准化 CSV（由 engine/fetch_inputs.py 通过 Wind MCP 生成）列名 → 引擎内部列名
CSV_COLS = {"hl_close": "close", "hl_turn": "turn", "hl_tr": "tr",
            "hl_dy": "dy", "wa_dy": "wa_dy", "y10": "y10"}
CSV_OPTIONAL = {"hl_amt": "amt", "wa_close": "wa_close", "wa_amt": "wa_amt", "wa_turn": "wa_turn"}

def load_csv_inputs(cfg):
    path = os.path.join(ROOT, cfg["inputs"]["daily_csv"])
    raw = pd.read_csv(path, encoding="utf-8")
    miss = [c for c in ["date", *CSV_COLS] if c not in raw.columns]
    if miss:
        raise SystemExit(f"❌ {path} 缺少列：{miss}")
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.set_index("date").sort_index()
    keep = {**CSV_COLS, **{k: v for k, v in CSV_OPTIONAL.items() if k in raw.columns}}
    df = raw[list(keep)].rename(columns=keep).apply(pd.to_numeric, errors="coerce")
    df["y10"] = df["y10"].ffill()
    return df.dropna(subset=["close"])

def load_inputs(cfg):
    inp = cfg["inputs"]
    src = inp.get("source", "auto")
    csv_ok = "daily_csv" in inp and os.path.exists(os.path.join(ROOT, inp["daily_csv"]))
    if src == "csv" or (src == "auto" and csv_ok):
        print(f"· 读取 {inp['daily_csv']}")
        return load_csv_inputs(cfg)
    return load_xlsx_inputs(cfg)

def load_xlsx_inputs(cfg):
    inp = cfg["inputs"]
    print(f"· 读取 {inp['wind_xlsx']} + {inp['y10_csv']}")
    path = os.path.join(ROOT, inp["wind_xlsx"])
    xls = pd.ExcelFile(path)
    s1, s2 = inp["sheet_quote"], inp["sheet_valuation"]
    hl = read_block(xls, s1, 0, ["close", "amt", "turn"])
    tr = read_block(xls, s1, 5, ["tr", "_a", "_t"])[["tr"]]
    wa = read_block(xls, s1, 10, ["wa_close", "wa_amt", "wa_turn"])
    v1 = read_block(xls, s2, 0, ["dy", "pe", "pb"])
    v2 = read_block(xls, s2, 5, ["wa_dy", "wa_pe", "wa_pb"])
    df = hl.join(tr).join(wa).join(v1).join(v2)
    y = pd.read_csv(os.path.join(ROOT, inp["y10_csv"]), header=None, skiprows=5,
                    encoding=inp.get("y10_encoding", "gbk"), names=["d", "y"])
    y = y[pd.to_datetime(y["d"], errors="coerce").notna()].copy()
    y["d"] = pd.to_datetime(y["d"]); y["y"] = pd.to_numeric(y["y"], errors="coerce")
    y = y.set_index("d")["y"].sort_index()
    df["y10"] = y.reindex(df.index).ffill()
    df = df.dropna(subset=["close"])
    return df

# ---------------------------------------------------------------- 工具
def rebalance_days(index):
    """中证红利年度调样生效日：每年12月第二个星期五的下一交易日"""
    out = []
    for yv in range(index[0].year, index[-1].year + 1):
        fridays = pd.date_range(f"{yv}-12-01", f"{yv}-12-31", freq="W-FRI")
        if len(fridays) < 2: continue
        after = index[index > fridays[1]]
        if len(after): out.append(after[0])
    return out

def remove_jumps(s, days):
    d = s.diff()
    d.loc[d.index.intersection(days)] = 0
    return s.iloc[0] + d.fillna(0).cumsum()

def roll_pct(s, w, mp):
    return s.rolling(w, min_periods=mp).rank(pct=True)

def linmap(x, lo, hi):
    """x=lo → 100，x=hi → 0，线性，截断"""
    return ((hi - x) / (hi - lo) * 100).clip(0, 100)

def sgn(v, d=1, unit="%"):
    s = f"{abs(v):.{d}f}{unit}"
    return ("+" if v >= 0 else "−") + s

# ---------------------------------------------------------------- 计算
def compute(df, cfg):
    p = cfg["params"]; W, MP = p["pct_window"], p["pct_min_periods"]
    reb = rebalance_days(df.index)
    dy_adj = remove_jumps(df["dy"], reb)
    px = df["close"]
    p250 = px / px.shift(250) - 1
    dev = px / px.rolling(250).mean() - 1
    turn20 = df["turn"].rolling(20).mean()

    S = 100 * roll_pct(dy_adj - df["y10"], W, MP)
    R = 100 * roll_pct(dy_adj / df["wa_dy"], W, MP)
    T = 100 * (1 - roll_pct(turn20, W, MP))
    M1 = linmap(p250, *p["map_ret250"])
    M2 = linmap(dev, *p["map_dev250"])
    P = (M1 + M2) / 2
    w = p["weights"]
    raw = w["price"] * P + w["spread"] * S + w["relative"] * R + w["turnover"] * T
    mu = raw.rolling(W, min_periods=MP).mean(); sd = raw.rolling(W, min_periods=MP).std()
    opp = (50 + p["z_scale"] * (raw - mu) / sd).clip(0, 100)
    C = pd.DataFrame({"S": S, "P": P, "T": T, "R": R, "raw": raw, "opp": opp,
                      "p250": p250, "dev": dev, "turn20": turn20})
    return C

def backtest_bands(df, opp, start):
    tr = df["tr"]; a = tr.values; n = len(a); dn = np.full(n, np.nan)
    for i in range(n - 250):
        dn[i] = a[i + 1:i + 251].min() / a[i] - 1
    Y = pd.DataFrame({"r12": tr.shift(-250) / tr - 1, "dn": dn}, index=df.index)
    D = pd.DataFrame({"opp": opp}).join(Y).resample("ME").last()
    d = D[D.index >= start].dropna(subset=["opp", "r12"])
    g = d.groupby(pd.cut(d["opp"], [0, 20, 40, 60, 80, 100.01], include_lowest=True), observed=False).agg(
        n=("r12", "size"), r12=("r12", "mean"), win=("r12", lambda x: (x > 0).mean()), dn=("dn", "mean"))
    return [[int(r.n), round(float(r.r12) * 100, 1) if r.n else 0.0, int(round(float(r.win) * 100)) if r.n else 0,
             round(float(r.dn) * 100, 1) if r.n else 0.0] for r in g.itertuples()]

# ---------------------------------------------------------------- 文案（规则生成，不用AI）
def level(v, words):
    return words[0] if v < 20 else words[1] if v < 40 else words[2] if v < 60 else words[3] if v < 80 else words[4]

def summary(last, w):
    val = (w["spread"] * last.S + w["relative"] * last.R) / (w["spread"] + w["relative"])
    up = (w["price"] * last.P + w["turnover"] * last["T"]) / (w["price"] + w["turnover"])
    a = level(val, ["估值贵", "估值偏贵", "估值中性", "估值偏便宜", "估值便宜"])
    b = level(last.P, ["价格涨多了", "价格偏高", "价格回到常态", "价格偏低", "价格跌出坑"])
    c = level(last["T"], ["交易拥挤", "交易偏热", "交易不冷不热", "交易偏冷", "交易冷清"])
    dn = "下行风险偏高" if val < 30 else ("下行风险偏低" if val > 70 else "下行风险一般")
    upt = "上行空间有限" if up < 40 else ("上行空间较大" if up > 65 else "上行空间一般")
    return f"{a}，{b}，{c}。{dn}，{upt}。"

def build_payload(df, C, cfg):
    p = cfg["params"]; w = p["weights"]
    s = C["opp"].dropna(); last_d = s.index[-1]; last = C.loc[last_d]; row = df.loc[last_d]
    def at(d):
        x = s[s.index <= d]; return round(float(x.iloc[-1]), 1)
    compare = {"1周前": at(last_d - pd.Timedelta(days=7)), "1月前": at(last_d - pd.DateOffset(months=1)),
               "3月前": at(last_d - pd.DateOffset(months=3)), "1年前": at(last_d - pd.DateOffset(years=1))}
    spread = row.dy - row.y10
    core = [
        {"name": "阶段涨跌幅", "value": f"近一年{sgn(last.p250*100)}｜偏离年线{sgn(last.dev*100)}",
         "score": round(float(last.P), 1), "weight": int(round(w["price"] * 100)), "judge": ["up", "dn"]},
        {"name": "股息率溢价", "value": f"{spread:.2f}pct（{row.dy:.2f}%−{row.y10:.2f}%）",
         "score": round(float(last.S), 1), "weight": int(round(w["spread"] * 100)), "judge": ["dn"]},
        {"name": "相对性价比", "value": f"红利/全A股息率{row.dy / row.wa_dy:.2f}倍",
         "score": round(float(last.R), 1), "weight": int(round(w["relative"] * 100)), "judge": ["dn", "rel"]},
        {"name": "换手率", "value": f"20日均{last.turn20:.2f}%",
         "score": round(float(last["T"]), 1), "weight": int(round(w["turnover"] * 100)), "judge": ["up"]},
    ]
    wk = pd.DataFrame({"o": s, "p": df["close"]}).loc[p["series_start"]:].resample("W-FRI").last().dropna()
    dates = [i.strftime("%Y-%m-%d") for i in wk.index]; dates[-1] = last_d.strftime("%Y-%m-%d")
    obs_path = os.path.join(ROOT, cfg["inputs"]["observe_json"])
    observe = json.load(open(obs_path, encoding="utf-8")) if os.path.exists(obs_path) else []
    return {
        "schema": "dividend-opportunity/v1",
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "asof": last_d.strftime("%Y-%m-%d"),
        "index": "中证红利000922.CSI",
        "score": round(float(last.opp), 1),
        "horizon": "未来6–12个月",
        "horizonNote": "按半年到一年的持有期判断方向，不预测涨跌幅度。建议每周查看一次。",
        "summary": summary(last, w),
        "compare": compare,
        "core": core,
        "bands": backtest_bands(df, C["opp"], p["series_start"]),
        "observe": observe,
        "method": "机会值＝阶段涨跌幅55%（近一年涨跌与偏离年线各半）＋股息率溢价20%＋相对性价比15%＋换手率10%，再与自身过去5年的平均水平比较：等于平均记50分，每高（低）一个标准差加（减）20分。阶段涨跌幅用价格指数，股息率类指标已剔除年度调样跳升。",
        "series": {"d": dates, "v": [round(float(v), 1) for v in wk["o"]], "p": [int(round(v)) for v in wk["p"]]},
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    df = load_inputs(cfg)
    C = compute(df, cfg)
    out = build_payload(df, C, cfg)
    od = os.path.join(ROOT, cfg["outputs"]["dir"]); os.makedirs(od, exist_ok=True)
    js = json.dumps(out, ensure_ascii=False, indent=1)
    open(os.path.join(od, "opportunity.json"), "w", encoding="utf-8").write(js)
    open(os.path.join(od, "opportunity.js"), "w", encoding="utf-8").write("window.DIVIDEND_OPPORTUNITY = " + js + ";\n")
    C.loc[cfg["params"]["series_start"]:, ["P", "S", "R", "T", "opp"]].resample("ME").last().round(1) \
        .rename(columns={"P": "阶段涨跌幅", "S": "股息率溢价", "R": "相对性价比", "T": "换手率", "opp": "机会值"}) \
        .to_csv(os.path.join(od, "opportunity_history_monthly.csv"), encoding="utf-8-sig")
    print(f"✅ 数据截至 {out['asof']}，机会值 {out['score']}（显示 {round(out['score'])}），{out['summary']}")

if __name__ == "__main__":
    main()

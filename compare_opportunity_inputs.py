"""对比 Wind MCP 取数（inputs/opportunity/wind_daily.csv）与手工导出（inputs/opportunity/data_add.xlsx + 10Y csv）。

用法：python3 compare_opportunity_inputs.py [--since 2018-01-01]
只读、不改任何文件。全部字段在容差内 → 退出码 0，否则 1。
"""
import argparse, json, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from opportunity_engine import load_csv_inputs, load_xlsx_inputs, ROOT

# 字段: (绝对容差, 相对容差)；任一满足即算一致
TOL = {"close": (0.01, 0), "tr": (0.01, 0), "turn": (0.001, 0.001),
       "dy": (0.01, 0), "wa_dy": (0.01, 0), "y10": (0.005, 0)}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--since", default="2010-01-01")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(ROOT, "opportunity_config.json"), encoding="utf-8"))
    m = load_csv_inputs(cfg).loc[a.since:]
    x = load_xlsx_inputs(cfg).loc[a.since:]
    idx = m.index.intersection(x.index)
    print(f"重叠交易日 {len(idx)}（{idx.min().date()} ~ {idx.max().date()}）；"
          f"仅MCP {len(m.index.difference(x.index))} 天，仅手工 {len(x.index.difference(m.index))} 天")
    bad_total = 0
    for c, (ta, tr) in TOL.items():
        d = (m.loc[idx, c] - x.loc[idx, c]).abs()
        lim = pd.concat([pd.Series(ta, index=idx), x.loc[idx, c].abs() * tr], axis=1).max(axis=1)
        both_nan = m.loc[idx, c].isna() & x.loc[idx, c].isna()
        bad = ~((d <= lim) | both_nan)
        bad_total += int(bad.sum())
        print(f"{c:6s} 不一致 {int(bad.sum()):5d} 天  最大偏差 {d.max():.4f}")
        if bad.any():
            print(pd.DataFrame({"mcp": m.loc[idx, c], "manual": x.loc[idx, c], "diff": d})[bad].head(10).to_string())
    print("✅ 全部一致" if bad_total == 0 else f"❌ 共 {bad_total} 处不一致")
    sys.exit(0 if bad_total == 0 else 1)

if __name__ == "__main__":
    main()

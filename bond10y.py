#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""10 年期国债「活跃券收盘价收益率」的选券逻辑（唯一实现）。

2026-11-23（中央复盘）从 sync_asset_macro.fetch_bond_yield_10y_bond 与 fetch_opportunity_inputs.parse_bond_yield
抽出：11-16、11-19 两次选错券（僵尸券「07国债06」写成 4.27%）都要两边同时改，改漏一边就会复发。

背景：EDB「中债国债到期收益率:10年」(S0059749) 及中债指标全族对本账号无权限，债券层行情有权限，
故用活跃券收盘 YTM 续接，与中债 10 年曲线基差 −0.8~−1.6bp。
同一只债在 .SH/.SZ/.IB/.BJ 多场所重复出现（北交所报价偏高），**按券选一只**：
  1. 剩余期限在 [lo, hi] 年；
  2. 剔除僵尸券（无成交、Wind 沿用旧值）：覆盖 ≥3 点且不同值个数 < max(2, 点数/2)；
  3. 必须在最新一天有值；
  4. 排序：不同值最多（真实成交）→ 覆盖点数最多 → 剩余期限最接近 10 年 → 银行间（.IB）优先。
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pick_series(cols, rows, norm_date, lo=9.0, hi=10.6):
    """从一张 get_bond_market_data 返回表里选出一只活跃 10 年期国债，返回 {日期: 收益率(百分数, 4 位小数)}；选不出返回 {}。"""
    cols = [c.get('name', '') if isinstance(c, dict) else str(c) for c in (cols or [])]
    ci = next((i for i, n in enumerate(cols) if '代码' in n), None)
    vi = next((i for i, n in enumerate(cols) if '收盘价收益率' in n and '类型' not in n), None)
    di = next((i for i, n in enumerate(cols) if n == '日期'), None)
    mi = next((i for i, n in enumerate(cols) if '剩余期限' in n), None)
    if None in (ci, vi, di, mi):
        return {}
    by = {}
    for r in rows or []:
        if len(r) <= max(ci, vi, di, mi):
            continue
        m, v = _num(r[mi]), _num(r[vi])
        if m is None or not (lo <= m <= hi) or v is None:
            continue
        by.setdefault(str(r[ci]), [m, {}])[1][norm_date(r[di])] = round(v, 4)
    cands = []
    for code, (m, ser) in by.items():
        if not ser:
            continue
        vals = list(ser.values())
        distinct = len(set(vals))
        if len(vals) >= 3 and distinct < max(2, len(vals) // 2):
            continue
        cands.append((distinct, len(ser), m, code, ser))
    if not cands:
        return {}
    latest = max(max(c[4]) for c in cands)
    cands = [c for c in cands if latest in c[4]] or cands
    cands.sort(key=lambda c: (c[0], c[1], -abs(c[2] - 10.0), 1 if c[3].upper().endswith('.IB') else 0))
    return cands[-1][4]


def pick_from_tables(tables, norm_date, lo=9.0, hi=10.6):
    """多张返回表时各选一只，取覆盖点数最多的一张（不按收益高低挑，11-19 曾因 max(收益) 主动选中异常值）。"""
    best = {}
    for tb in tables or []:
        ser = pick_series(tb.get('columns'), tb.get('rows'), norm_date, lo, hi)
        if len(ser) > len(best):
            best = ser
    return best

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新前体检（preflight）— 食息指南
======================================================================
在任何一次数据更新前运行，用「交易日历 + 本地数据最新日期」快速判断：

  1) 今天 A股 / 港股 是否开盘，各自的「最近交易日」是什么；
  2) 各数据域本地数据是否已覆盖到最新交易日 —— 哪些需要更新、哪些可跳过；
  3) 建议执行 / 可跳过的流水线步骤 + 粗略耗时估计。

为什么需要它（2026-10-04 用户提出）：
  更新并不总是"全量重拉"。例如国庆假期 A股连续多日不开市（期间港股可能开市 1~2 天），
  此时多数 Wind 日频数据不会有新点，全量重跑纯属浪费时间。先体检 → 只跑真正需要的步骤。

只读，不修改任何数据。用法：
  python3 preflight.py                 # 体检今天
  python3 preflight.py --date 2026-10-04
  python3 preflight.py --json          # 机器可读 JSON
  python3 preflight.py --emit-skip     # 仅输出建议跳过的步骤号（空格分隔，供 shell 使用）

交易日历见 market_calendar.json（每年官方发布次年安排后更新）。
"""
import json
import os
import sys
import glob
import argparse
import datetime
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
CAL_PATH = os.path.join(BASE, "market_calendar.json")

TOL_DAYS = 2          # 与 check_data 一致的跨市场容差（A股/港股可差 1 天）
CN, HK = "CN", "HK"
WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 各步骤粗略耗时（秒，基于历史运行观察的粗估，仅用于给用户一个量级感）
STEP_TIME = {
    3: 5, 4: 20, 5: 110, 6: 60, 7: 30, 8: 45, 9: 70, 10: 70, 11: 20,
    12: 70, 13: 90, 14: 120, 15: 120, 16: 8, 17: 8, 18: 8, 19: 8, 20: 60, 21: 10,
}
# 预检可建议跳过的步骤（纯 Wind 日频 + 资讯），其余步骤一律保留
SKIPPABLE = [5, 6, 7, 8, 9, 10, 16]
# 步骤 → 中文名（报告用）
STEP_NAME = {
    3: "语法预检", 4: "重建数据(1)", 5: "股息率 div_history", 6: "涨跌幅 daily_change",
    7: "货基 money_fund", 8: "余额宝 yuebao_history", 9: "宏观 asset_macro",
    10: "REITs reits_daily", 11: "重建数据(2)", 12: "新ETF/指数 new_etf",
    13: "新REITs new_reits", 14: "分红日 fund_divdate", 15: "Wind字段 wind_fields",
    16: "食息资讯 sync_daily", 17: "备份 backup_db", 18: "校验 check_data",
    19: "内嵌 embed_data", 20: "部署 deploy_cloudflare", 21: "线上验证",
}


# ----------------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------------
def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _d(s):
    """解析 'YYYY-MM-DD...' → date；失败返回 None。"""
    if not s or not isinstance(s, str) or len(s) < 10:
        return None
    try:
        return datetime.date.fromisoformat(s[:10])
    except Exception:
        return None


def _w(s):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _pad(s, n):
    return s + " " * max(1, n - _w(s))


def load_calendar():
    try:
        return _load(CAL_PATH)
    except Exception:
        return {"CN": {}, "HK": {}}


CAL = load_calendar()


def cal_covered(mkt, year):
    return str(year) in CAL.get(mkt, {})


def is_trading_day(mkt, dd):
    if dd.weekday() >= 5:
        return False
    hols = set(CAL.get(mkt, {}).get(str(dd.year), []))
    return dd.isoformat() not in hols


def last_trading_day(mkt, dd):
    x = dd
    for _ in range(40):
        if is_trading_day(mkt, x):
            return x
        x -= datetime.timedelta(days=1)
    return None


def market_reason(mkt, dd):
    if dd.weekday() >= 5:
        return "周末"
    if not is_trading_day(mkt, dd):
        return "假期休市"
    return "交易日"


def last_friday(dd):
    return dd - datetime.timedelta(days=(dd.weekday() - 4) % 7)


def fmt(dd):
    return dd.isoformat() + "（" + WEEK[dd.weekday()] + "）" if dd else "—"


# ----------------------------------------------------------------------------
# 各数据域「最新日期」读取
# ----------------------------------------------------------------------------
def r_daily():
    arr = _load(os.path.join(DATA, "dailyData.json"))
    return _d(arr[0].get("date")) if arr else None


def r_divhistory():
    arr = _load(os.path.join(DATA, "indexData.json"))
    vs = []
    for x in arr:
        h = x.get("divHistory") or []
        if h:
            v = _d(h[-1].get("date"))
            if v:
                vs.append(v)
    return (max(vs) if vs else None), len(vs), len(arr)


def r_index_field(field):
    arr = _load(os.path.join(DATA, "indexData.json"))
    vs = [v for v in (_d(x.get(field)) for x in arr) if v]
    return (max(vs) if vs else None), len(vs), len(arr)


def r_moneyfund():
    arr = _load(os.path.join(DATA, "moneyFundData.json"))
    for x in arr:
        if x.get("code") == "000198.OF":
            return _d(x.get("yieldDate"))
    return None


def r_yuebao():
    s = (_load(os.path.join(DATA, "yuebaoHistory.json")).get("series") or [])
    return _d(s[-1].get("date")) if s else None


def r_reitsdaily():
    obj = _load(os.path.join(DATA, "reitsDaily.json"))
    mx, n = None, 0
    for _code, info in (obj.get("codes") or {}).items():
        series = info.get("series") or {}
        if series:
            v = _d(max(series.keys()))
            if v:
                mx = v if (mx is None or v > mx) else mx
                n += 1
    return mx, n


def r_asset(key):
    s = (_load(os.path.join(DATA, "assetHistory.json")).get(key) or [])
    return _d(s[-1].get("date")) if s else None


def r_lists_newest():
    """清单/标注来源（data/curation/*.json）的最新修改时间。
    excel-exit P2/P3（2026-10-06）起不再看 xlsx —— build_lists（原 sync_excel）已不读 Excel。"""
    files = [f for f in glob.glob(os.path.join(DATA, "curation", "*.json"))
             if not os.path.basename(f).startswith("_")]
    if not files:
        return None, None
    newest = max(files, key=os.path.getmtime)
    return os.path.basename(newest), datetime.datetime.fromtimestamp(os.path.getmtime(newest))


# ----------------------------------------------------------------------------
# 体检主逻辑
# ----------------------------------------------------------------------------
def build(today):
    cn_last = last_trading_day(CN, today)
    hk_last = last_trading_day(HK, today)
    both = max([x for x in (cn_last, hk_last) if x], default=None)

    warn = []
    for mkt in (CN, HK):
        if not cal_covered(mkt, today.year):
            warn.append("%s 交易日历未覆盖 %d 年（请更新 market_calendar.json），已退化为『仅跳周末』" % (mkt, today.year))

    rows = []   # (域, 步骤, 当前, 期望, 状态, 说明)

    def add(name, step, cur, exp, kind, note=""):
        if kind == "daily":
            st = "fresh" if (cur and cur >= exp) else "stale"
        elif kind == "market":
            if cur is None or exp is None:
                st = "unknown"
            elif (exp - cur).days <= TOL_DAYS:
                st = "fresh"
            else:
                st = "stale"
        elif kind == "event":
            st = "event"
        elif kind == "exempt":
            st = "exempt"
        else:
            st = "unknown"
        rows.append({"domain": name, "step": step, "current": cur, "expected": exp,
                     "kind": kind, "status": st, "note": note})

    # --- 资讯 ---
    add("食息资讯 dailyData", 16, r_daily(), today, "daily", "自然日每日更新")

    # --- 指数（A股+港股）---
    dh, dh_n, dh_tot = r_divhistory()
    add("指数股息率 divHistory", 5, dh, both, "market", "%d/%d 只" % (dh_n, dh_tot))
    dc, dc_n, dc_tot = r_index_field("dailyDate")
    add("指数涨跌幅 dailyChange", 6, dc, both, "market", "%d/%d 只" % (dc_n, dc_tot))

    # --- 货基 / 余额宝（A股口径）---
    add("货基7日年化 moneyFund", 7, r_moneyfund(), cn_last, "market", "天弘余额宝")
    add("余额宝历史 yuebaoHistory", 8, r_yuebao(), cn_last, "market", "")

    # --- 宏观（REITs 两类 + 余额宝日频 + 国债周频）---
    add("REITs日频 reitsDaily", 10, r_reitsdaily()[0], cn_last, "market",
        "%d 只有序列" % r_reitsdaily()[1])
    add("宏观·储蓄国债(周频)", 9, r_asset("3年期储蓄国债"), last_friday(today), "market", "每周五采样")
    add("宏观·余额宝(日频)", 9, r_asset("天弘余额宝"), cn_last, "market", "")
    add("宏观·REITs两类(日频)", 10, r_asset("REITs产权类"), cn_last, "market", "")
    add("宏观·低频(存单/LPR/存款/预定利率)", 9, None, None, "exempt", "周/月/不定期")
    add("重点50城租金率", "B2", r_asset("重点50城租金率"), None, "exempt", "季度")

    # --- 清单/标注类（事件驱动；excel-exit P2 起来源 = data/curation/*.json）---
    cur_name, cur_mt = r_lists_newest()
    data_mt = None
    p = os.path.join(DATA, "etfData.json")
    if os.path.exists(p):
        data_mt = datetime.datetime.fromtimestamp(os.path.getmtime(p))
    if cur_mt and data_mt and cur_mt > data_mt + datetime.timedelta(seconds=60):
        lists_note = "发现较新的清单/标注（curation）：%s（%s）→ 需重跑" % (cur_name, cur_mt.strftime("%Y-%m-%d %H:%M"))
        lists_new = True
    else:
        lists_note = "清单/标注（curation）无更新" + ("" if cur_mt else "／未找到")
        lists_new = False
    add("清单/标注类(7 文件重建)", "4/11", None, None, "event", lists_note)

    # ------------------------------------------------------------------
    # 汇总：可跳过 / 需执行
    # ------------------------------------------------------------------
    step_status = {}   # step -> 'fresh'/'stale'/'unknown'（exempt/event 中立，不参与判定）
    for r in rows:
        if not isinstance(r["step"], int):
            continue
        st = r["status"]
        if st in ("exempt", "event"):   # 中立：不代表该步骤需要跑
            continue
        prev = step_status.get(r["step"])
        if st == "stale" or prev == "stale":
            step_status[r["step"]] = "stale"
        elif st == "unknown" or prev == "unknown":
            step_status[r["step"]] = "unknown"
        else:
            step_status[r["step"]] = "fresh"

    skip = [s for s in SKIPPABLE if step_status.get(s) == "fresh"]
    run = [s for s in SKIPPABLE if s not in skip]

    all_steps = sorted(STEP_TIME.keys())
    skip_set = set(skip)
    total_time = sum(STEP_TIME[s] for s in all_steps if s not in skip_set)

    return {
        "today": today, "cn_last": cn_last, "hk_last": hk_last, "both": both,
        "rows": rows, "step_status": step_status,
        "skip": sorted(skip), "run": sorted(run),
        "lists_new": lists_new, "lists_note": lists_note,
        "warn": warn, "total_time": total_time,
    }


def _status_label(st):
    return {"fresh": "✅ 最新", "stale": "⚠️ 待更新", "event": "🔸 事件驱动",
            "exempt": "➖ 豁免", "unknown": "❓ 未知"}.get(st, st)


def print_report(rep):
    print("=" * 70)
    print("  食息指南 · 更新前体检（preflight）")
    print("=" * 70)
    for w in rep["warn"]:
        print("  ⚠️  " + w)
    today = rep["today"]
    print("  今天：%s    A股：%s   ｜   港股：%s" % (
        fmt(today),
        ("休市（%s）" % market_reason(CN, today)) if not is_trading_day(CN, today) else "开市",
        ("休市（%s）" % market_reason(HK, today)) if not is_trading_day(HK, today) else "开市",
    ))
    print("  A股最近交易日：%s" % fmt(rep["cn_last"]))
    print("  港股最近交易日：%s" % fmt(rep["hk_last"]))
    print("  → 预期最新数据日：%s" % fmt(rep["both"]))
    print("-" * 70)
    print("  " + _pad("数据域", 34) + _pad("最新日期", 20) + _pad("期望", 20) + "状态")
    for r in rep["rows"]:
        print("  " + _pad(r["domain"], 34)
              + _pad(fmt(r["current"]) if r["current"] else "—", 20)
              + _pad(fmt(r["expected"]) if r["expected"] else "—", 20)
              + _status_label(r["status"])
              + ("   " + r["note"] if r["note"] else ""))
    print("-" * 70)
    all_steps = sorted(STEP_TIME.keys())
    skip_set = set(rep["skip"])
    print("  可跳过（已是最新交易日）：%s" % (" ".join("步骤%d(%s)" % (s, STEP_NAME[s]) for s in rep["skip"]) or "无"))
    print("  需执行：%s" % " ".join("步骤%d(%s)" % (s, STEP_NAME[s]) for s in all_steps if s not in skip_set))
    if rep["lists_new"]:
        print("  🔸 清单/标注（data/curation）有更新 → 步骤 4/11（重建数据）需重跑以套用")
    print("  预计耗时：约 %d 分 %d 秒（已跳过 %d 个可跳步骤）"
          % (rep["total_time"] // 60, rep["total_time"] % 60, len(rep["skip"])))
    print("  提示：如需按建议跳过，运行流水线前设置环境变量 SKIP_STEPS=\"%s\"" % " ".join(map(str, rep["skip"])))
    print("=" * 70)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="体检日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--emit-skip", action="store_true", help="仅输出建议跳过的步骤号")
    args = ap.parse_args()

    today = _d(args.date) or datetime.date.today()
    try:
        rep = build(today)
    except Exception as e:  # 预检失败绝不阻断流水线
        if args.emit_skip:
            print("")
        else:
            print("⚠️ preflight 执行异常（不影响后续流水线）：%r" % e)
        return

    if args.emit_skip:
        print(" ".join(map(str, rep["skip"])))
        return
    if args.json:
        out = {k: v for k, v in rep.items() if k not in ("step_status",)}
        for k in ("today", "cn_last", "hk_last", "both"):
            if out.get(k):
                out[k] = out[k].isoformat()
        out["rows"] = [
            {**{kk: (vv.isoformat() if isinstance(vv, datetime.date) else vv)
                for kk, vv in r.items()}} for r in rep["rows"]
        ]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print_report(rep)


if __name__ == "__main__":
    main()

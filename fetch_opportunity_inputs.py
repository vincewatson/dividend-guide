#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股红利机会值 · Wind MCP 增量取数 + 写回中央库（2026-10-08，Claude）

做什么：
  1. 看中央库（exports）+ 本地增量 + 站点 indexData 已经覆盖到哪天；
  2. 只对缺口（到 A 股最新交易日）调用 Wind MCP —— **全部经 wind_client**（计数 / 预算 / pending）；
  3. 合并写入 inputs/opportunity/increments.csv（不入库、不部署）；
  4. 把新取到的数据经 data_center 的 pipelines/submit.py 写回中央库（取到后写回）；
     中央库导出覆盖之后，本地增量里旧于导出的行自动清掉。

Wind 调用（每周约 4–6 次）：
  - index_data/get_index_kline：000922.CSI、H00922.CSI 日 K（MATCH = 收盘）
  - index_data/get_index_fundamentals：000922.CSI 换手率（自然语言、按交易日）
  - index_data/get_index_fundamentals：881001.WI 股息率（同 sync_div_history 的措辞）
  - economic_data/query_economic_indicator_data：中国国债到期收益率 10 年（EDB）
  - 000922.CSI 股息率一般不调 Wind：取站点日更已维护的 data/indexData.json divHistory（滞后时才补取）

用法：
  python3 fetch_opportunity_inputs.py            # 正常运行（流水线周更档）
  python3 fetch_opportunity_inputs.py --plan     # 只打印缺口与计划调用次数，不调 Wind
  python3 fetch_opportunity_inputs.py --probe    # 每类各调 1 次（最近 10 天），打印解析结果，不写文件
  python3 fetch_opportunity_inputs.py --no-submit  # 取数但不写回中央库
  python3 fetch_opportunity_inputs.py --selftest # 模拟 Wind 返回，验证解析/合并/提交文件（0 次 Wind）
"""
import argparse, datetime as dt, json, os, subprocess, sys, time
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import opportunity_central as oc

INC = os.path.join(BASE, "inputs", "opportunity", "increments.csv")
QUEUE = os.path.join(BASE, "inputs", "opportunity", ".cache", "central_queue")
WIND_SKILL = os.path.expanduser("~/.agents/skills/wind-mcp-skill")
SEG_DAYS = 60                 # 单次 ≤100 行（wind-query-tips §B）：60 日历日 ≈ 42 交易日
TIMEOUT = int(os.environ.get("SX_WIND_TIMEOUT", "45"))
PROJECT, AGENT = "dividend-guide", "fetch_opportunity_inputs.py"
MAX_GAP_DAYS = int(os.environ.get("SX_OPP_MAX_GAP_DAYS", "120"))   # 只补近期缺口；更早的历史一律以中央库为准，不用 Wind 回补

# 需要取的序列：key → (wind_code, metric, 取法)
FETCH = {
    ("000922.CSI", "close"): "kline",
    ("H00922.CSI", "close"): "kline",
    ("000922.CSI", "turnover_rate"): "nl_turn",
    ("881001.WI", "dividend_yield"): "nl_dy",
    ("000922.CSI", "dividend_yield"): "nl_dy",   # 通常 0 次：站点日更 sync_div_history 已写入 indexData，仅其滞后时才补
    ("RATES", oc.Y10_NAME): "edb",
}
NAMES = {"000922.CSI": "中证红利", "H00922.CSI": "中证红利全收益", "881001.WI": "万得全A"}


# ------------------------------------------------------------------ Wind 调用（只经 wind_client）
class Quota(Exception):
    pass


class WindAPI:
    def __init__(self):
        import wind_client
        self.wc = wind_client
        self.calls = 0

    def _env(self):
        env = dict(os.environ)
        env["NODE_EXTRA_CA_CERTS"] = "/etc/ssl/cert.pem"
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NODE_USE_ENV_PROXY"):
            env.pop(k, None)
        return env

    def call(self, server, tool, params):
        """返回内层 JSON（dict）；'没找到' 返回 {}；额度拒绝抛 Quota；3 次失败返回 None。"""
        for attempt in range(3):
            try:
                r = self.wc.run(["node", self.wc.CLI, "call", server, tool, json.dumps(params, ensure_ascii=False)],
                                capture_output=True, text=True, timeout=TIMEOUT, env=self._env(), cwd=WIND_SKILL)
            except Exception:
                time.sleep(5); continue
            self.calls += 1
            if r.returncode == 3:
                raise Quota((r.stderr or "").strip())
            if r.returncode != 0:
                time.sleep(5); continue
            try:
                text = json.loads(r.stdout)["content"][0]["text"]
                if "没找到" in text:
                    return {}
                return json.loads(text)
            except Exception:
                time.sleep(5)
        return None


# ------------------------------------------------------------------ 解析（一律按列名）
def _table(inner):
    """兼容两种表结构：{'data':{'columns','rows'}} 与 {'data':{'data':[{'columns','rows'}]}}。"""
    d = (inner or {}).get("data") or {}
    if isinstance(d, dict) and "columns" in d:
        t = d
    else:
        t = ((d.get("data") if isinstance(d, dict) else None) or [{}])[0]
    cols = [c.get("name", "") if isinstance(c, dict) else str(c) for c in t.get("columns", [])]
    return cols, t.get("rows") or []


def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except Exception:
        return None


def parse_kline(inner):
    cols, rows = _table(inner)
    if "TIME" not in cols or "MATCH" not in cols:
        return {}
    ti, mi = cols.index("TIME"), cols.index("MATCH")
    out = {}
    for r in rows:
        v = _num(r[mi]) if len(r) > mi else None
        if v and v > 0:
            out[str(r[ti])[:10]] = v
    return out


def parse_nl(inner, keyword, code):
    """自然语言日频表：[Wind代码, 证券简称, …{keyword}…, 日期]（列名会随日期区间变化，按关键字匹配）。"""
    cols, rows = _table(inner)
    ci = next((i for i, n in enumerate(cols) if "代码" in n), None)
    vi = next((i for i, n in enumerate(cols) if keyword in n), None)
    di = next((i for i, n in enumerate(cols) if n == "日期"), None)
    if di is None:
        di = next((i for i, n in enumerate(cols) if "日期" in n and "发布" not in n), None)
    if vi is None or di is None:
        return {}
    out = {}
    for r in rows:
        if len(r) <= max(vi, di):
            continue
        if ci is not None and r[ci] and str(r[ci]).strip().upper() != code.upper():
            continue
        v = _num(r[vi])
        if v is not None and r[di]:
            out[str(r[di])[:10]] = v
    return out


def _norm_date(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else s[:10]


def parse_edb(inner, keyword="10年"):
    for m in (inner or {}).get("metrics", []) or []:
        if keyword in (m.get("meta") or {}).get("name", ""):
            return {_norm_date(d): v for d, v in zip(m.get("date", []), m.get("value", [])) if _num(v) is not None}
    return {}


# ------------------------------------------------------------------ 取数
def segments(start, end, days=SEG_DAYS):
    cur = start
    while cur <= end:
        e = min(cur + dt.timedelta(days=days), end)
        yield cur, e
        cur = e + dt.timedelta(days=1)


def fetch_one(api, key, start, end):
    """返回 {date: value(小数口径，与中央库一致)}。"""
    code, metric = key
    how = FETCH[key]
    out = {}
    if how == "edb":
        inner = api.call("economic_data", "query_economic_indicator_data",
                         {"question": "中国国债到期收益率10年", "beginDate": start.isoformat(), "endDate": end.isoformat()})
        return {d: float(v) / 100 for d, v in parse_edb(inner).items() if start.isoformat() <= d <= end.isoformat()}
    # 自然语言日频查询：区间只含 1 个交易日时 Wind 可能不返回「日期」列（REITs 10-08 实测，见 sync_reits_daily）。
    # → 起点往前多取 7 天，保证区间 ≥2 个交易日；多取的天数在下面按 start 过滤掉，不重复写回。
    q_start = start - dt.timedelta(days=7) if how != "kline" else start
    for s, e in segments(q_start, end):
        if how == "kline":
            inner = api.call("index_data", "get_index_kline",
                             {"windcode": code, "begin_date": s.isoformat(), "end_date": e.isoformat(), "period": "1d"})
            pts = parse_kline(inner)
        else:
            word = "换手率" if how == "nl_turn" else "股息率"
            q = f"{code} {NAMES[code]} {s.isoformat()}至{e.isoformat()}的{word}历史数据按交易日列出，给出每个交易日的值"
            pts = {d: v / 100 for d, v in parse_nl(api.call("index_data", "get_index_fundamentals", {"question": q}),
                                                 word, code).items()}
        lo = max(s, start).isoformat()
        out.update({d: v for d, v in pts.items() if lo <= d <= e.isoformat()})
        if how != "kline" and not pts:
            print(f"  [⚠️] {code} {metric} {s}~{e} 未解析到数据（可能无「日期」列或措辞漂移）", flush=True)
    return out


def target_day():
    try:
        import trade_calendar
        return trade_calendar.latest_trading_day("CN")
    except Exception:
        d = dt.date.today() - dt.timedelta(days=1)
        while d.weekday() >= 5:
            d -= dt.timedelta(days=1)
        return d


def _trading_days(start, end):
    try:
        import trade_calendar
        out, d = [], start
        while d <= end:
            if trade_calendar.is_trading_day("CN", d):
                out.append(d)
            d += dt.timedelta(days=1)
        return out
    except Exception:
        return [d.date() for d in pd.bdate_range(start, end)]


def continuous_last(dates, target, lookback=180):
    """序列「连续覆盖」到哪天：近 lookback 天内第一个缺失的 A 股交易日之前一天。
    （中央库同一序列可能混有其它项目的零星点位，不能只看最大日期。）"""
    if not dates:
        return None
    have = set(dates)
    first_dt = dt.date.fromisoformat(min(dates))
    lo = max(first_dt, target - dt.timedelta(days=lookback))
    last_ok = None
    for d in _trading_days(lo, target):
        if d.isoformat() in have:
            last_ok = d
        else:
            break
    if last_ok is None:                       # 近 lookback 天整段缺失 → 退回最大日期之前的连续段
        ds = sorted(x for x in have if x < lo.isoformat())
        return ds[-1] if ds else None
    return last_ok.isoformat()


def plan(long_df, target):
    last, todo = {}, {}
    for key in FETCH:
        s = long_df[(long_df.wind_code == key[0]) & (long_df.metric == key[1])]["date"].astype(str).tolist()
        if key[0] == "RATES":                  # 利率序列按自身日历，取最大日期即可
            ld = max(s) if s else None
        else:
            ld = continuous_last(s, target)
        last[key] = ld
        if not ld:
            continue                           # 中央库还没有这条序列：不用 Wind 回补历史（等中央库导出）
        start = dt.date.fromisoformat(ld) + dt.timedelta(days=1)
        if start < target - dt.timedelta(days=MAX_GAP_DAYS):
            print(f"  ⚠ {key[0]} {key[1]} 缺口始于 {start}，超过 {MAX_GAP_DAYS} 天：不自动回补，请检查中央库导出")
            continue
        if start <= target:
            todo[key] = (start, target)
    return last, todo


def est_calls(todo):
    n = 0
    for key, (s, e) in todo.items():
        n += 1 if FETCH[key] == "edb" else len(list(segments(s, e)))
    return n


# ------------------------------------------------------------------ 本地增量 & 写回中央库
def merge_increments(new_rows, central_long):
    old = oc.load_increments(INC)
    new = pd.DataFrame(new_rows, columns=["date", "wind_code", "metric", "value"])
    df = pd.concat([f for f in (old, new) if len(f)], ignore_index=True) if (len(old) or len(new)) else new
    df = df.drop_duplicates(["date", "wind_code", "metric"], keep="last")
    # 中央库导出已覆盖的日期 → 从本地增量中清掉（中央库为准）
    if len(central_long):
        cov = oc.last_dates(central_long)
        keep = [not (cov.get((r.wind_code, r.metric)) and r.date <= cov[(r.wind_code, r.metric)]) for r in df.itertuples()]
        df = df[keep]
    os.makedirs(os.path.dirname(INC), exist_ok=True)
    df.sort_values(["wind_code", "metric", "date"]).to_csv(INC, index=False)
    return len(df)


def build_submissions(new_rows):
    q = [r for r in new_rows if r[1] != "RATES"]
    rt = [r for r in new_rows if r[1] == "RATES"]
    unit = {"close": "点"}
    out = []
    if q:
        out.append(("quote.index_daily", [{"entity_id": c, "metric": m, "date": d, "value": round(v, 10),
                                           "unit": unit.get(m, "decimal")} for d, c, m, v in q]))
    if rt:
        out.append(("rates.value", [{"entity_id": oc.Y10_NAME, "metric": "yield", "date": d, "value": round(v, 8),
                                     "unit": "decimal"} for d, c, m, v in rt]))
    return out


def _mcp_config_pythons():
    """从 Claude 桌面版 / TRAE 的 MCP 配置里找 central-market-db 的启动 Python（它一定装了 duckdb）。"""
    home = os.path.expanduser("~")
    sup = os.path.join(home, "Library", "Application Support")
    cfgs = [os.path.join(sup, "Claude", "claude_desktop_config.json")]
    try:
        cfgs += [os.path.join(sup, d, "User", "mcp.json") for d in os.listdir(sup) if d.lower().startswith("trae")]
    except Exception:
        pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfgs.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
    out = []
    for c in cfgs:
        try:
            srv = (json.load(open(c, encoding="utf-8")).get("mcpServers") or {}).get("central-market-db") or {}
            cmd = srv.get("command")
            if cmd and "python" in os.path.basename(cmd).lower():
                out.append(cmd)
        except Exception:
            continue
    return out


def _clean_env():
    """调用其它虚拟环境的 Python 时去掉会干扰它的变量（TRAE/IDE 终端常带 PYTHONHOME/PYTHONPATH）。"""
    env = dict(os.environ)
    for k in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONSTARTUP", "__PYVENV_LAUNCHER__"):
        env.pop(k, None)
    return env


def _submit_python(dc, verbose=False):
    """data_center 的 submit.py 需要 duckdb。依次尝试：SX_DC_PYTHON → 中央库 MCP 配置里的 Python →
    中央库安装脚本的默认虚拟环境 → 当前 Python。verbose=True 时打印每个候选失败的原因。"""
    cands = [os.environ.get("SX_DC_PYTHON")] + _mcp_config_pythons() + [
        os.path.expanduser("~/.local/share/data_center/venv/bin/python"),
        os.path.join(os.environ["LOCALAPPDATA"], "data_center", "venv", "Scripts", "python.exe") if os.environ.get("LOCALAPPDATA") else None,
        sys.executable]
    for p in dict.fromkeys(c for c in cands if c):
        if not os.path.exists(p):
            if verbose: print(f"  候选 {p}：不存在")
            continue
        try:
            r = subprocess.run([p, "-c", "import duckdb; print(duckdb.__version__)"], capture_output=True, text=True,
                               timeout=120, env=_clean_env(), cwd=os.path.expanduser("~"))
            if r.returncode == 0:
                if verbose: print(f"  候选 {p}：可用（duckdb {r.stdout.strip()}）")
                return p
            if verbose: print(f"  候选 {p}：import duckdb 失败 → {(r.stderr or '').strip().splitlines()[-1:]}")
        except Exception as e:
            if verbose: print(f"  候选 {p}：{type(e).__name__} {e}")
    return None


def submit(batches, dry=False):
    """写入队列文件，再逐个经 pipelines/submit.py 提交；失败的留在队列，下次再交。"""
    os.makedirs(QUEUE, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for i, (target, rows) in enumerate(batches):
        obj = {"meta": {"project": PROJECT, "agent": AGENT, "target": target,
                        "note": "Wind MCP 增量（%s 至 %s），A股红利机会值引擎输入；站点 fetch_opportunity_inputs.py 取数后写回"
                                % (min(r["date"] for r in rows), max(r["date"] for r in rows))},
               "rows": rows}
        json.dump(obj, open(os.path.join(QUEUE, f"{stamp}_{i}_{target}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    files = sorted(f for f in os.listdir(QUEUE) if f.endswith(".json"))
    if not files:
        return 0, 0
    dc = oc.central_dir(json.load(open(os.path.join(BASE, "opportunity_config.json"), encoding="utf-8")))
    py = _submit_python(dc)
    if dry or not py or not os.path.exists(os.path.join(dc, "pipelines", "submit.py")):
        why = "演练" if dry else ("找不到 data_center" if not os.path.exists(os.path.join(dc, "pipelines", "submit.py"))
                                  else "找不到带 duckdb 的 Python（可设环境变量 SX_DC_PYTHON 指定）")
        print(f"  ⏸ 未写回中央库（{why}）：{len(files)} 个文件留在队列，下次再交")
        return 0, len(files)
    ok = 0
    for f in files:
        p = os.path.join(QUEUE, f)
        r = subprocess.run([py, os.path.join(dc, "pipelines", "submit.py"), p], capture_output=True, text=True, cwd=dc,
                           env=_clean_env(), timeout=300)
        tail = (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
        if r.returncode == 0:
            ok += 1
            os.makedirs(os.path.join(QUEUE, "done"), exist_ok=True)
            os.replace(p, os.path.join(QUEUE, "done", f))
            print(f"  ✓ 写回中央库：{f} → {tail[0]}")
        else:
            print(f"  ✗ 写回失败（留在队列）：{f} → {tail[0]}")
    return ok, len(files) - ok


# ------------------------------------------------------------------ 主流程
def run(api, args):
    cfg = json.load(open(os.path.join(BASE, "opportunity_config.json"), encoding="utf-8"))
    central, found = oc.load_central_long(cfg)
    long_df, _ = oc.combined_long(cfg, INC)
    target = args.target or target_day()
    last, todo = plan(long_df, target)
    print(f"· 中央库导出：{found or '无'}；A股最新交易日 {target}")
    for key in FETCH:
        print(f"  {key[0]:11s} {key[1]:16s} 已覆盖到 {last.get(key) or '—'}" + ("  → 待取 %s~%s" % todo[key] if key in todo else ""))
    print(f"· 计划 Wind 调用约 {est_calls(todo)} 次")
    missing = [k for k in FETCH if not last.get(k)]
    if missing:
        print(f"  ⚠ 中央库导出尚无：{missing}（等 exports/dividend/opportunity-inputs.json；期间引擎回退手工导出）")
    if args.plan or not todo:
        print("✅ 无缺口" if not todo else "（--plan：不调 Wind）")
        if not todo and not args.no_submit and not args.plan:
            submit([])          # 补交上次留在队列里的
        return 0
    new_rows, fails = [], []
    try:
        for key, (s, e) in todo.items():
            pts = fetch_one(api, key, s, e)
            print(f"  {key[0]} {key[1]}: 取到 {len(pts)} 天" + (f"（{min(pts)}~{max(pts)}）" if pts else ""))
            if not pts:
                fails.append(key)
            new_rows += [(d, key[0], key[1], float(v)) for d, v in sorted(pts.items())]
    except Quota as q:
        print(f"  ⏸ Wind 额度用尽，已取部分照常保存，其余下次续取：{q}")
    if args.probe:
        print("（--probe：不写文件、不写回）"); return 0
    n = merge_increments(new_rows, central)
    print(f"· 本地增量 inputs/opportunity/increments.csv：{n} 行")
    if new_rows and not args.no_submit:
        submit(build_submissions(new_rows), dry=args.selftest)
    if fails:
        print(f"⚠ 有序列本次未取到（措辞/接口可能漂移，或该区间无新交易日）：{fails}")
    print(f"✅ 完成：新取 {len(new_rows)} 个数据点，Wind 调用 {getattr(api, 'calls', 0)} 次")
    return 0


class FakeAPI:
    """--selftest：按真实返回结构造假数据（0 次 Wind）。"""
    calls = 0

    def call(self, server, tool, p):
        self.calls += 1
        if tool == "get_index_kline":
            days = pd.bdate_range(p["begin_date"], p["end_date"])
            return {"data": {"columns": [{"name": "TIME"}, {"name": "MATCH"}],
                             "rows": [[d.strftime("%Y-%m-%d 00:00:00"), 5500 + i] for i, d in enumerate(days)]}}
        if tool == "get_index_fundamentals":
            code = p["question"].split()[0]; s, e = p["question"].split()[2].split("的")[0].split("至")
            word = "换手率" if "换手率" in p["question"] else "股息率"
            days = pd.bdate_range(s, e)
            return {"data": {"data": [{"columns": [{"name": "Wind代码"}, {"name": "证券简称"},
                                                  {"name": f"{s}到{e}每日的{word}"}, {"name": "日期"}],
                                      "rows": [[code, "x", 0.8 if word == "换手率" else 1.9, d.strftime("%Y-%m-%d")] for d in days]}]}}
        if tool == "query_economic_indicator_data":
            days = pd.bdate_range(p["beginDate"], p["endDate"])
            return {"metrics": [{"meta": {"name": "中国:国债到期收益率:10年"}, "date": [d.strftime("%Y%m%d") for d in days],
                                 "value": [1.7] * len(days)}]}
        return {}


def main():
    ap = argparse.ArgumentParser()
    for f in ("plan", "probe", "no_submit", "selftest"):
        ap.add_argument("--" + f.replace("_", "-"), action="store_true")
    ap.add_argument("--target", type=dt.date.fromisoformat, default=None, help="补到哪天（默认 A 股最新交易日）")
    a = ap.parse_args()
    if a.selftest:
        global INC, QUEUE
        tmp = os.path.join(os.path.expanduser("~"), ".opportunity_selftest"); os.makedirs(tmp, exist_ok=True)
        INC, QUEUE = os.path.join(tmp, "increments.csv"), os.path.join(tmp, "queue")
        print(f"[selftest] 模拟 Wind，输出到 {tmp}")
        return run(FakeAPI(), a)
    if a.probe:
        global plan
        _plan = plan
        plan = lambda df, t: (_plan(df, t)[0], {k: (t - dt.timedelta(days=10), t) for k in FETCH})
    if not a.plan and not os.path.isdir(WIND_SKILL):
        print("❌ wind-mcp-skill 未找到：", WIND_SKILL); return 1
    return run(WindAPI() if not a.plan else None, a)


if __name__ == "__main__":
    sys.exit(main())

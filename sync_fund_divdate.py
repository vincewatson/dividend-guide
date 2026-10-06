#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Wind 拉取基金/ETF 最近分红发放日期，写入 divDate 字段（2026-08-05 确立）
========================================================
数据源文件: fundData.json / etfData.json / cnEtfData.json / hkEtfData.json
查询方式: get_fund_financials，问题 = "{code} 最近分红情况"（保留 .OF 后缀）
         2026-09-13 实测修订：本轮发现「{code} 最近分红发放日期」措辞会返回"没找到数据"
         （仅 fund 6/26 命中），而用户指令的「{code} 最近分红情况」稳定返回含"基金红利发放日"
         列的表（含最新发放日）。故改为以「最近分红情况」为主，另加两种兜底措辞。
写入: 每条记录的 divDate = 基金红利发放日（YYYY-MM-DD），多行时取最新；查不到留空
注意: 港股 ETF（hkEtfData，.HK 后缀）Wind 基金库不支持，脚本会跳过（保留原值）
用法: python3 sync_fund_divdate.py [fund|etf|cnetf|hketf|all] [--force]
      --force-all 强制重拉全部非港股；默认增量（空值 + 月月分红必刷 + 超期 > SX_DIV_STALE_DAYS 天）
"""
import io, json, os, subprocess, sys, time, tempfile, re, datetime
from concurrent.futures import ThreadPoolExecutor

# Wind 并发路数（2026-09-26 提速：单条查询并发化，8 路实测 ~7.6×；若遇限流可下调/用 SX_WIND_WORKERS 覆盖）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '8')))

# 增量策略（2026-09-26 提速）：默认只重查「空值 + 月月分红 + 超期」
#   - 月月分红产品（ETF月月分红 etfData + 指数基金月月分红 fundData）每周必刷，保证"最近分红日期"最新；
#   - 其余（cnEtfData 境内红利ETF）仅在 divDate 缺失、或距今天数 > SX_DIV_STALE_DAYS 时重查；
#   - `--force-all` 恢复旧行为（重查全部非港股）。
ALWAYS_FILES = {'etfData.json', 'fundData.json'}     # 月月分红：每周必刷
STALE_DAYS = int(os.environ.get('SX_DIV_STALE_DAYS', '35'))
# 「无分红记录」复查周期（2026-09-26）：cnEtf 里大量"确无分红记录"的基金不必每周重查。
RECHECK_DAYS = int(os.environ.get('SX_DIV_NORECORD_DAYS', '28'))

BASE = os.path.dirname(os.path.abspath(__file__)) + '/data'
# 单条查询间隔（秒）。原为固定 3s，整轮 ~90 条空耗约 4.5 分钟；单条查询非高频批量查询，
# 1.5s 足够。若出现 Wind 限流（连续返回空表/没找到数据），可用 SX_WIND_INTERVAL=3 调回（2026-09-19 优化）。
INTERVAL = float(os.environ.get('SX_WIND_INTERVAL', '1.5'))
WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wind_guard_cli.mjs')  # Wind 额度守卫包装器（2026-10-06；真实 cli.mjs 见 SX_WIND_CLI_REAL）

# 分红日期查询措辞（按优先级尝试；2026-09-13：主措辞改为「最近分红情况」）
PHRASINGS = ['{} 最近分红情况', '{} 最近分红发放日期', '{} 基金分红 分红发放日']
# 「无分红记录」缓存文件（code → 最近一次确认为"无记录"的日期）。独立于 cnEtfData，
# 以免被 build_lists 每周重建时覆盖（2026-09-26）。
NORECORD_FILE = os.path.join(BASE, 'divNoRecord.json')


def load_norecord():
    if os.path.exists(NORECORD_FILE):
        try:
            with io.open(NORECORD_FILE, encoding='utf-8') as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {}


def save_norecord(d):
    fd, tmp = tempfile.mkstemp(dir=BASE, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, NORECORD_FILE)

def call_wind(question):
    """返回 {'status': 'ok'|'notfound'|'error', 'has_div_col': bool, 'date': str|None}

    status 语义（2026-09-19 重构，用于减少无谓的多措辞重试）：
      ok       = 拿到了有效返回（可能含发放日，也可能为空表）
      notfound = Wind 明确回「没找到数据」（措辞失效，应换下一种措辞）
      error    = 3 次重试后仍失败（超时/异常/非零退出，应换下一种措辞）
    同时把 subprocess.run 移入 try/except，避免 TimeoutExpired 直接崩溃（原代码隐患）。
    """
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'fund_data', 'get_fund_financials',
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=env, cwd=WIND_SKILL)
        except subprocess.TimeoutExpired:
            time.sleep(6); continue
        except Exception:
            time.sleep(6); continue
        if r.returncode != 0:
            time.sleep(6); continue
        try:
            if 'backend_error' in r.stdout or '"ok": false' in r.stdout:
                # CLI 级错误（如「单日请求次数超限」）→ 不重试，立即返回（2026-09-26）
                return {'status': 'error', 'has_div_col': False, 'date': None}
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if text == '没找到数据' or '没找到' in text:
                return {'status': 'notfound', 'has_div_col': False, 'date': None}
            inner = json.loads(text)
            d0 = inner['data']['data'][0]
            cols = [c['name'] for c in d0.get('columns', [])]
            rows = d0.get('rows', [])
            div_idx = next((i for i, cn in enumerate(cols)
                            if '红利发放日' in cn or '分红发放' in cn), None)
            if div_idx is None:
                return {'status': 'ok', 'has_div_col': False, 'date': None}
            best = None
            for row in rows:
                if div_idx < len(row) and row[div_idx]:
                    v = str(row[div_idx])[:10]
                    if v and (best is None or v > best):
                        best = v
            return {'status': 'ok', 'has_div_col': True, 'date': best}
        except Exception:
            time.sleep(6)
    return {'status': 'error', 'has_div_col': False, 'date': None}

def resolve(code):
    """单只基金的历史分红发放日（多措辞依次兜底，语义与旧串行实现一致）。
    返回 (date|None, got_final)：got_final=True 表示已得定论（拿到日期，或表有效但无分红列）。"""
    for ph in PHRASINGS:
        res = call_wind(ph.format(code))
        if res['date']:
            return res['date'], True       # ok + 有发放日 → 定论
        if res['status'] == 'ok' and res['has_div_col']:
            return None, True              # 表有效含分红列但无日期 → 该基金确无发放日
    return None, False                     # 全部措辞失效 → 保留原值


def ts():
    return time.strftime('%H:%M:%S')


# 「月月分红」名单自动剔除（2026-10-06 用户要求）
# ------------------------------------------------------------------
# 规则：月月分红产品应「每月连续分红」。若某只的最近一次分红发放日
#   早于「上一个月」（例：2026-10 运行 → 要求最近分红 ≥ 2026-09-01），
#   说明它已不再月月分红，从名单中剔除（保底：divDate 为空者不动，避免误删）。
# 自愈：Excel 快照仍会把它带回来 → 每周重建后本剔除再跑一次；
#   若该产品恢复月月分红（divDate 变新），下轮自然重新纳入。
# 仅对月月名单（ALWAYS_FILES：etfData / fundData）生效。
def _prev_month_first(today=None):
    t = today or datetime.date.today()
    return datetime.date(t.year - 1, 12, 1) if t.month == 1 else datetime.date(t.year, t.month - 1, 1)


def prune_stale_monthly(d, fn):
    cutoff = _prev_month_first()
    kept, removed = [], []
    for item in d:
        dd = item.get('divDate')
        if not dd:
            kept.append(item); continue          # 无日期（新上市/查询失败）不动
        try:
            dt = datetime.date.fromisoformat(str(dd)[:10])
        except ValueError:
            kept.append(item); continue
        if dt < cutoff:
            removed.append((item.get('code', ''), item.get('name', ''), str(dd)[:10]))
        else:
            kept.append(item)
    if removed:
        print('  [月月剔除] {}：{} 只最近分红早于 {}（已非月月分红）→ 移出名单：'.format(
            fn, len(removed), cutoff.isoformat()), flush=True)
        for c, n, dd in removed:
            print('    - {} {}（最近分红 {}）'.format(c, n, dd), flush=True)
    return kept

def process(fn, label, norecord):
    p = os.path.join(BASE, fn)
    d = json.load(io.open(p, encoding='utf-8'))
    print(f'===== {fn} ({len(d)}条) =====', flush=True)
    force_all = '--force-all' in sys.argv
    always = fn in ALWAYS_FILES          # 月月分红产品：每周必刷
    today = datetime.date.today()
    mode = '全量' if force_all else ('月月分红必刷' if always else '增量(空值/超期>{}天)'.format(STALE_DAYS))
    todo_items, skipped = [], 0
    for item in d:
        code = item.get('code', '')
        name = item.get('name', '')
        if not code or not name:
            continue
        # 港股 ETF：Wind 基金库不支持，跳过（保留原值）
        if code.endswith('.HK'):
            skipped += 1
            continue
        # 增量：月月分红必刷；其余「有日期→超期才查」「无记录→命中缓存且未到复查期则跳过」（2026-09-26）
        if not force_all and not always:
            dd = item.get('divDate')
            if dd:
                try:
                    if (today - datetime.date.fromisoformat(str(dd)[:10])).days <= STALE_DAYS:
                        skipped += 1
                        continue
                except ValueError:
                    pass
            else:
                last = norecord.get(code)
                if last:
                    try:
                        if (today - datetime.date.fromisoformat(str(last)[:10])).days < RECHECK_DAYS:
                            skipped += 1
                            continue
                    except ValueError:
                        pass
        todo_items.append((item, code, name))
    print(f'  待查询 {len(todo_items)} 条，跳过 {skipped} 条（{mode}），并发 {WORKERS} 路', flush=True)

    updated, empty = 0, 0

    def _work(t):
        item, code, name = t
        dt, got_final = resolve(code)   # 每只独立并发；多措辞兜底语义同旧串行版
        return (item, code, name, dt, got_final)

    results = []
    if todo_items:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            results = list(ex.map(_work, todo_items))   # map 保持输入顺序
    for n, (item, code, name, dt, got_final) in enumerate(results, 1):
        if dt:
            item['divDate'] = dt
            updated += 1
            norecord.pop(code, None)          # 取到记录 → 移出「无分红记录」缓存
            print(f'  [{n}/{len(results)}] {ts()} {name}: {dt}', flush=True)
        else:
            empty += 1
            if got_final:
                norecord[code] = today.isoformat()   # 确无记录 → 记缓存，RECHECK_DAYS 内不再重查
            # 空结果不覆盖原值（保留旧 divDate）
            tag = '无分红记录' if got_final else '查询失败(保留原值)'
            print(f'  [{n}/{len(results)}] {ts()} {name}: {tag}', flush=True)

    # 月月名单自动剔除：最近分红早于「上一个月」的成员移出名单（仅 etfData/fundData；2026-10-06）
    if always:
        d = prune_stale_monthly(d, fn)
    fd, tmp = tempfile.mkstemp(dir=BASE, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    print(f'  → {updated} 更新, {empty} 空, 已写回 {fn}\n', flush=True)
    return updated

def main():
    targets = sys.argv[1] if len(sys.argv) > 1 else 'all'
    jobs = []
    if targets in ('all', 'fund'): jobs.append(('fundData.json', 'fundData'))
    if targets in ('all', 'etf'): jobs.append(('etfData.json', 'etfData'))
    if targets in ('all', 'cnetf'): jobs.append(('cnEtfData.json', 'cnEtfData'))
    if targets in ('all', 'hketf'): jobs.append(('hkEtfData.json', 'hkEtfData'))
    norecord = load_norecord()
    total = 0
    for fn, label in jobs:
        total += process(fn, label, norecord)
    save_norecord(norecord)
    print(f'总共更新 {total} 条（无分红记录缓存 {len(norecord)} 条）', flush=True)

if __name__ == '__main__':
    main()

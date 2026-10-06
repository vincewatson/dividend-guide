#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产品行情快照库（只追加不覆盖）—— 从 Wind 拉取各 ETF/基金的
【当日涨跌幅】【今年以来回报】（含最新交易日），按日期打标签后追加到
data/productQuotes.json，历史快照一律保留（数据库随时间越来越丰富）。

核心原则（2026-10-05 用户明确要求）：
  1. 产品回报**绝不跨取跟踪指数**——产品已扣费且含分红，口径与指数不同；
     缺数据就从 Wind 补，绝不借用挂钩指数。
  2. **每次取完数据打日期标签**；下次更新**只追加、不覆盖**，旧快照永远保留。

来源: Wind fund_data.get_fund_price_indicators
      参数 windcode（逗号分隔批量）+ indexes="最新交易日,涨跌幅,年初至今涨跌幅"
口径: dailyChange / yrChange 存小数（0.69% -> 0.0069），前端 ×100 显示；
      date 存 yyyy-mm-dd；取不到的字段写 null（不写 0）。

用法:
    python3 sync_product_quotes.py              # 全量：拉取全部产品，追加带日期快照
    python3 sync_product_quotes.py --dry-run    # 只打印将要追加的内容，不写入
    python3 sync_product_quotes.py --codes a,b  # 只拉取指定代码（调试用）
"""
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wind_guard_cli.mjs')  # Wind 额度守卫包装器（2026-10-06；真实 cli.mjs 见 SX_WIND_CLI_REAL）
QUOTES_FILE = os.path.join(DATA, 'productQuotes.json')

# 产品清单来源（与 embed_data.py / 前端 DATA_FILES 对齐）
PRODUCT_FILES = ['cnEtfData.json', 'hkEtfData.json', 'etfData.json', 'fundData.json']

# get_fund_price_indicators 实测 12 只/批可用；25 只/批报错。留安全上限 12。
BATCH = int(os.environ.get('SX_PQ_BATCH', '12'))
SLEEP = float(os.environ.get('SX_PQ_SLEEP', '0.6'))
# 并发路数（2026-10-06 提速：批次并发；流水线本身串行，不会抬高 Wind 峰值并发）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '6')))
INDEXES = '最新交易日,涨跌幅,年初至今涨跌幅'


def ts():
    return time.strftime('%H:%M:%S')


def _wind_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def load_product_codes():
    """收集所有产品代码（去重且保持稳定顺序）。"""
    codes = []
    seen = set()
    for fname in PRODUCT_FILES:
        p = os.path.join(DATA, fname)
        if not os.path.exists(p):
            print(f'  [警告] 缺少 {fname}，跳过')
            continue
        try:
            arr = json.load(io.open(p, encoding='utf-8'))
        except Exception as e:
            print(f'  [警告] {fname} 读取失败: {e}')
            continue
        if not isinstance(arr, list):
            continue
        for x in arr:
            c = (x or {}).get('code')
            if c and c not in seen:
                seen.add(c)
                codes.append(c)
    return codes


def _to_float(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ('', '--', '—', 'None', 'null'):
        return None
    try:
        f = float(s)
    except (ValueError, TypeError):
        return None
    return f


def _parse_price_table(inner):
    """按列名解析 get_fund_price_indicators 返回表 → {code: (yyyy-mm-dd, daily, yr)}。
    Wind 列顺序会漂移，一律按列名取值；日期须为 8 位数字，否则丢弃（绝不写畸形日期）。"""
    cols = [c['name'] for c in inner['data']['columns']]
    rows = inner['data']['rows'] or []
    ci = next((i for i, c in enumerate(cols) if '代码' in c), -1)
    di = cols.index('最新交易日') if '最新交易日' in cols else -1
    pi = cols.index('涨跌幅') if '涨跌幅' in cols else -1
    yi = cols.index('年初至今涨跌幅') if '年初至今涨跌幅' in cols else -1
    if di < 0:
        return {}
    out = {}
    for row in rows:
        try:
            date_raw = str(row[di]).strip()[:8]
            if not (len(date_raw) == 8 and date_raw.isdigit()):
                continue
            date_fmt = f'{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}'
        except Exception:
            continue
        code = str(row[ci]) if (ci >= 0 and len(row) > ci and row[ci]) else ''
        if not code:
            continue
        dc = _to_float(row[pi]) if pi >= 0 and len(row) > pi else None
        yc = _to_float(row[yi]) if yi >= 0 and len(row) > yi else None
        out[code] = (
            date_fmt,
            round(dc / 100.0, 4) if dc is not None else None,
            round(yc / 100.0, 4) if yc is not None else None,
        )
    return out


def call_wind_batch(codes):
    """批量拉取。返回 {code: (date, daily, yr)}；None 表示整批失败（调用方回退单只）。"""
    q = json.dumps({'windcode': ','.join(codes), 'indexes': INDEXES}, ensure_ascii=False)
    for attempt in range(4):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'fund_data', 'get_fund_price_indicators', q],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=_wind_env(), cwd=WIND_SKILL)
            if r.returncode != 0:
                time.sleep(5)
                continue
            outer = json.loads(r.stdout)
            if outer.get('ok') is False:            # NETWORK_ERROR 等：重试
                time.sleep(5)
                continue
            text = outer['content'][0]['text']
            if '没找到' in text:
                return {}
            parsed = _parse_price_table(json.loads(text))
            return parsed
        except Exception:
            time.sleep(5)
    return None


def call_wind_one(code):
    """单只回退查询。返回 (date, daily, yr) 或 (None, None, None)。"""
    got = call_wind_batch([code])
    if got and code in got:
        return got[code]
    return None, None, None


def load_store():
    if os.path.exists(QUOTES_FILE):
        try:
            obj = json.load(io.open(QUOTES_FILE, encoding='utf-8'))
            if isinstance(obj, dict) and isinstance(obj.get('quotes'), dict):
                return obj
        except Exception as e:
            print(f'  [警告] productQuotes.json 解析失败（将重建）: {e}')
    return {
        'schema': 1,
        'note': '产品行情快照库（只追加不覆盖）。键=产品代码，值=按日期升序的快照数组；'
                'date=最新交易日，dailyChange=当日涨跌幅(小数)，yrChange=年初至今涨跌幅(小数)，source=来源。',
        'updatedAt': '',
        'quotes': {},
    }


def merge_snapshot(store, code, date, dc, yc, source='wind'):
    """把一条快照并入 store（只追加不覆盖旧值；同日仅补空值）。返回 'new'|'enrich'|'skip'。"""
    hist = store['quotes'].setdefault(code, [])
    for s in hist:
        if s.get('date') == date:
            enrich = False
            for f, v in (('dailyChange', dc), ('yrChange', yc)):
                if s.get(f) is None and v is not None:
                    s[f] = v
                    enrich = True
            if s.get('source') in (None, ''):
                s['source'] = source
            return 'enrich' if enrich else 'skip'
    hist.append({'date': date, 'dailyChange': dc, 'yrChange': yc, 'source': source})
    hist.sort(key=lambda s: s.get('date') or '')
    return 'new'


def main():
    dry = '--dry-run' in sys.argv
    codes_arg = None
    for i, a in enumerate(sys.argv):
        if a == '--codes' and i + 1 < len(sys.argv):
            codes_arg = [c.strip() for c in sys.argv[i + 1].split(',') if c.strip()]

    codes = codes_arg if codes_arg else load_product_codes()
    n = len(codes)
    n_batch = (n + BATCH - 1) // BATCH if n else 0
    print(f'待拉取产品 {n} 个，分 {n_batch} 批（{BATCH} 只/批）；目标 {QUOTES_FILE}')

    store = load_store()
    if dry:
        # dry-run 也要有历史用于「补空值」判断，但绝不写回
        pass

    stats = {'new': 0, 'enrich': 0, 'skip': 0, 'miss': 0}
    batches = [codes[bi:bi + BATCH] for bi in range(0, n, BATCH)]
    print(f'  并发 {WORKERS} 路拉取 {len(batches)} 批...')
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        batch_got = list(ex.map(call_wind_batch, batches))   # 保持批次顺序
    for bi, chunk in enumerate(batches):
        got = batch_got[bi]
        if got is None:
            print(f'  [{ts()}] 批次 {bi+1}/{n_batch} 批量失败，回退单只')
            got = {}
            for c in chunk:
                d, dc, yc = call_wind_one(c)
                if d:
                    got[c] = (d, dc, yc)
                time.sleep(SLEEP)
        for c in chunk:
            hit = got.get(c)
            if not hit or not hit[0]:
                stats['miss'] += 1
                print(f'  [{ts()}] {c}: 无数据')
                continue
            date, dc, yc = hit
            if dry:
                print(f'  [{ts()}] {c}: {date} 当日{dc} 今年{yc}')
                continue
            r = merge_snapshot(store, c, date, dc, yc)
            stats[r] += 1
            flag = {'new': '＋新增', 'enrich': '○补空', 'skip': '=已存'}[r]
            print(f'  [{ts()}] {c}: {date} 当日{dc} 今年{yc}  {flag}')
        print(f'  [{ts()}] 批次 {bi+1}/{n_batch} 完成（新增 {stats["new"]} / 补空 {stats["enrich"]} / 已存 {stats["skip"]} / 缺 {stats["miss"]}）')

    if dry:
        print(f'[dry-run] 未写入。（新增 {stats["new"]} 补空 {stats["enrich"]} 已存 {stats["skip"]} 缺 {stats["miss"]}）')
        return

    store['updatedAt'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fd, tmp = tempfile.mkstemp(dir=DATA, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUOTES_FILE)
    total = sum(len(v) for v in store['quotes'].values())
    print(f'完成：新增 {stats["new"]} / 补空 {stats["enrich"]} / 已存 {stats["skip"]} / 缺 {stats["miss"]}；'
          f'快照库现有 {len(store["quotes"])} 个产品 / 共 {total} 条快照 → 已写回 productQuotes.json')


if __name__ == '__main__':
    main()

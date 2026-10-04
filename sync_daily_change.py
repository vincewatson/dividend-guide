#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Wind 拉取红利指数的每日涨跌幅，更新 indexData.json 的 dailyChange/dailyDate
============================================================================
来源: get_index_price_indicators（index_data），参数 windcode + indexes="最新交易日,涨跌幅"
口径: dailyChange 存小数（0.99% -> 0.0099），前端 ×100 显示；dailyDate 存 yyyy-mm-dd
用法: python3 sync_daily_change.py            # 全量：所有指数重拉
      python3 sync_daily_change.py --incremental  # 增量：跳过已有 dailyDate 的
"""
import io, json, os, subprocess, sys, time, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')
INDEX_FILE = os.path.join(DATA, 'indexData.json')

# 2026-09-19 优化：get_index_price_indicators 支持逗号分隔多代码（空格分隔只返回第一个，实测）。
# 实测 12 只/批 → 12 行/0 缺失；25 只/批报错。故批量上限定为 12，并保留单只回退。
BATCH = int(os.environ.get('SX_DC_BATCH', '12'))
SLEEP = float(os.environ.get('SX_DC_SLEEP', '0.5'))


def ts():
    return time.strftime('%H:%M:%S')


def _wind_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def _parse_price_table(inner, codes):
    """把 get_index_price_indicators 返回表解析为 {code: (date_fmt, pct)}。
    一律按列名取值（Wind 列顺序会漂移）。"""
    cols = [c['name'] for c in inner['data']['columns']]
    rows = inner['data']['rows']
    if not rows:
        return {}
    ci = next((i for i, c in enumerate(cols) if '代码' in c), -1)
    di = cols.index('最新交易日') if '最新交易日' in cols else -1
    pi = cols.index('涨跌幅') if '涨跌幅' in cols else -1
    if di < 0 or pi < 0:
        return None
    out = {}
    for row in rows:
        try:
            date_raw = str(row[di]).strip()[:8]
            if not (len(date_raw) == 8 and date_raw.isdigit()):
                continue  # 日期无效（Wind 对部分指数返回 "0"）→ 交由 K 线兜底，绝不写入畸形日期
            date_fmt = f'{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}'
            pct = round(float(row[pi]) / 100.0, 4)
        except Exception:
            continue
        if ci >= 0 and len(row) > ci and row[ci]:
            code = str(row[ci])
        elif len(codes) == 1:
            code = codes[0]
        else:
            continue
        out[code] = (date_fmt, pct)
    return out


def call_wind_batch(codes):
    """批量拉取多只指数最新交易日涨跌幅。返回 {code: (date, pct)}；
    返回 None 表示整批失败（调用方回退单只查询）。"""
    q = json.dumps({'windcode': ','.join(codes), 'indexes': '最新交易日,涨跌幅'}, ensure_ascii=False)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'index_data', 'get_index_price_indicators', q],
                capture_output=True, text=True, timeout=90, env=_wind_env(), cwd=WIND_SKILL)
            if r.returncode != 0:
                time.sleep(6); continue
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return {}
            parsed = _parse_price_table(json.loads(text), codes)
            if parsed is not None:
                return parsed
        except Exception:
            time.sleep(6)
    return None


def call_wind(windcode):
    env = _wind_env()
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'index_data', 'get_index_price_indicators',
                 json.dumps({'windcode': windcode, 'indexes': '最新交易日,涨跌幅'}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=90, env=env, cwd=WIND_SKILL)
            if r.returncode != 0:
                time.sleep(6); continue
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return None, None
            parsed = _parse_price_table(json.loads(text), [windcode])
            if parsed:
                return parsed.get(windcode, (None, None))
            return None, None
        except Exception:
            time.sleep(6)
    return None, None

def call_wind_kline(windcode):
    """兜底：部分指数 get_index_price_indicators 的「最新交易日」返回 "0" 或涨跌幅为空
    （Wind 对个别指数/停牌口径不返回截面），改用日 K 线取最近两日收盘价算出最新一日涨跌幅。
    2026-09-26 新增（932584/SPAHLVCP/930740 等截面缺失指数的兜底）。"""
    import datetime
    end = datetime.date.today()
    begin = end - datetime.timedelta(days=20)
    q = json.dumps({'windcode': windcode, 'begin_date': begin.isoformat(),
                    'end_date': end.isoformat(), 'period': '1d'}, ensure_ascii=False)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'index_data', 'get_index_kline', q],
                capture_output=True, text=True, timeout=90, env=_wind_env(), cwd=WIND_SKILL)
            if r.returncode != 0:
                time.sleep(6); continue
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return None, None
            inner = json.loads(text)
            cols = [c['name'] for c in inner['data']['columns']]
            rows = inner['data']['rows'] or []
            ti = cols.index('TIME')
            mi = cols.index('MATCH')
            pts = []
            for row in rows:
                try:
                    d = str(row[ti])[:10]
                    c = float(row[mi])
                    if d and c > 0:
                        pts.append((d, c))
                except Exception:
                    continue
            if len(pts) >= 2:
                return pts[-1][0], round(pts[-1][1] / pts[-2][1] - 1.0, 4)
            return None, None
        except Exception:
            time.sleep(6)
    return None, None


def call_wind_yr(question):
    """get_index_fundamentals 批量拉取（年初至今涨跌幅等）"""
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'index_data', 'get_index_fundamentals',
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=90, env=env, cwd=WIND_SKILL)
            if r.returncode != 0:
                time.sleep(6); continue
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return None
            inner = json.loads(text)
            for tb in inner.get('data', {}).get('data', []):
                if tb.get('rows'):
                    return tb['rows']
        except Exception:
            time.sleep(6)
    return None


def fetch_yr_change(d):
    """批量拉取本年涨跌幅（Wind get_index_fundamentals，存小数 -0.0358 = -3.58%）"""
    import datetime
    year = datetime.date.today().year
    BATCH = 8
    result = {}
    for i in range(0, len(d), BATCH):
        batch = d[i:i+BATCH]
        q = ' '.join('{} {}'.format(x.get('code',''), x.get('name','')) for x in batch if x.get('code')) \
            + ' {}年初至今涨跌幅'.format(year)
        rows = call_wind_yr(q)
        if rows:
            for r in rows:
                if len(r) >= 3 and r[2] is not None:
                    code = str(r[0])
                    try:
                        result[code] = round(float(r[2]) / 100.0, 4)
                    except (ValueError, TypeError):
                        pass
        time.sleep(SLEEP)
        print('  [%s] yrChange 批次 %d/%d' % (ts(), i // BATCH + 1,
              (len(d) + BATCH - 1) // BATCH), flush=True)
    return result


def main():
    incremental = '--incremental' in sys.argv
    d = json.load(io.open(INDEX_FILE, encoding='utf-8'))
    todo = [(i, item) for i, item in enumerate(d)
            if item.get('code') and not (incremental and item.get('dailyDate'))]
    skipped = sum(1 for item in d if item.get('code') and incremental and item.get('dailyDate'))
    n = len(todo)
    n_batch = (n + BATCH - 1) // BATCH if n else 0
    print(f'共 {len(d)} 个指数，待更新 {n} 个（跳过 {skipped}），分 {n_batch} 批（{BATCH} 只/批）', flush=True)

    updated = 0
    for bi in range(0, n, BATCH):
        chunk = todo[bi:bi + BATCH]
        codes = [item['code'] for _, item in chunk]
        got = call_wind_batch(codes)
        if got is None:
            # 整批失败 → 回退逐只（保数据不丢，且能定位到具体哪只查询异常）
            print(f'  [{ts()}] 批次 {bi//BATCH+1}/{n_batch} 批量失败，回退单只查询', flush=True)
            got = {}
            for c in codes:
                dt, v = call_wind(c)
                if dt and v is not None:
                    got[c] = (dt, v)
                time.sleep(SLEEP)
        for _, item in chunk:
            hit = got.get(item['code'])
            if not (hit and hit[0] and hit[1] is not None):
                # 单只兜底：截面「最新交易日」无效/涨跌幅为空 → 逐只重查 → 再走日 K 线
                dt, v = call_wind(item['code'])
                if not (dt and v is not None):
                    dt, v = call_wind_kline(item['code'])
                hit = (dt, v) if (dt and v is not None) else None
            if hit and hit[0] and hit[1] is not None:
                item['dailyDate'] = hit[0]
                item['dailyChange'] = hit[1]
                updated += 1
                print(f'  [{ts()}] {item["name"]}: {hit[0]} {hit[1]*100:.2f}%', flush=True)
            else:
                print(f'  [{ts()}] {item["name"]}: 无数据', flush=True)
        print(f'  [{ts()}] 批次 {bi//BATCH+1}/{n_batch} 完成（累计更新 {updated}）', flush=True)
        time.sleep(SLEEP)
    # 本年涨跌幅更新（Wind 实时，2026-08-16 起；sync_excel 已保护不覆盖）
    yr = fetch_yr_change(d)
    yr_updated = 0
    for item in d:
        code = item.get('code', '')
        if code in yr:
            item['yrChange'] = yr[code]
            yr_updated += 1
    print(f'yrChange 更新: {yr_updated} 个', flush=True)

    fd, tmp = tempfile.mkstemp(dir=DATA, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, INDEX_FILE)
    print(f'完成: {updated} 更新, {skipped} 跳过, 已写回 indexData.json', flush=True)

if __name__ == '__main__':
    main()

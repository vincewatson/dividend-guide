#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补齐滞后的指数股息率历史到最新交易日（逐个单查）

2026-08-22 修订：TARGET_DATE 由写死改为动态取最近工作日（跳过周末）。
2026-09-13 修订（修复 bug）：原实现用「最近36个月…按月列出」查询，Wind 实际返回
  5 列（含"发布日期"）且为**月末**数据，导致 column 错位（row[3] 为数值）报
  TypeError，且即便成功也会把日频 divHistory 覆盖成月频（违反"写回绝不删除旧数据"铁律）。
  现改为与 sync_div_history 一致的**日频**查询 + **合并**（只补最后日期之后的缺口，
  旧数据全部保留），并按列名解析（兼容不同列顺序），原子写入。
"""
import datetime, io, json, os, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
INDEX_JSON = os.path.join(BASE, 'data', 'indexData.json')
WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')
SEG_DAYS = 90  # 单段最多 90 天（Wind 单次返回 ≤100 行）
# 并发路数（2026-09-26 提速：滞后指数单查并发，8 路实测 ~7.6×；逻辑已并入 sync_div_history，本脚本通常已无滞后）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '8')))


def latest_trading_day():
    d = datetime.date.today()
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= datetime.timedelta(days=1)
    return d.isoformat()


TARGET_DATE = latest_trading_day()


def call_wind(code, start, end):
    """按交易日拉取 [start, end] 的股息率，返回 [{'date','yield'}]。"""
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    question = '{} {}至{}的股息率历史数据按交易日列出，给出每个交易日的值'.format(code, start, end)
    r = subprocess.run(
        ['node', CLI, 'call', 'index_data', 'get_index_fundamentals',
         json.dumps({'question': question}, ensure_ascii=False)],
        capture_output=True, text=True, timeout=90, env=env, cwd=WIND_SKILL)
    if r.returncode != 0:
        return []
    try:
        outer = json.loads(r.stdout)
        text = outer['content'][0]['text']
        if '没找到' in text:
            return []
        inner = json.loads(text)
        table = inner.get('data', {}).get('data', [{}])[0]
        cols = [c.get('name', '') for c in table.get('columns', [])]
        rows = table.get('rows', []) or []
        # 按列名解析（兼容列顺序变化）：股息率列 + 日期列
        yi = next((i for i, n in enumerate(cols) if '股息率' in n), None)
        di = next((i for i, n in enumerate(cols) if n == '日期'), None)
        if di is None:
            di = next((i for i, n in enumerate(cols) if '日期' in n and '发布' not in n), None)
        if yi is None or di is None:
            return []
        out = []
        for row in rows:
            if len(row) > max(yi, di) and row[yi] is not None and row[di]:
                out.append({'date': str(row[di])[:10], 'yield': row[yi]})
        return out
    except Exception:
        return []


def fetch_gap(code, last_date):
    """增量拉取 [last_date, TARGET_DATE] 的日频段（分段，不截断）。"""
    start = datetime.date.fromisoformat(last_date)
    end = datetime.date.fromisoformat(TARGET_DATE)
    pts = {}
    cur = start
    while cur <= end:
        seg_end = min(cur + datetime.timedelta(days=SEG_DAYS), end)
        for p in call_wind(code, cur.isoformat(), seg_end.isoformat()):
            pts[p['date']] = p['yield']
        cur = seg_end + datetime.timedelta(days=1)
    return pts


def main():
    with io.open(INDEX_JSON, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    laggards = [x for x in index_data if x.get('divHistory')
                and x['divHistory'][-1]['date'] < TARGET_DATE]
    print('滞后指数数:', len(laggards))
    if not laggards:
        print('无需补充')
        return

    def _one(item):
        old = item.get('divHistory') or []
        return item, old, fetch_gap(item['code'], old[-1]['date'])

    fixed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for item, old, pts in ex.map(_one, laggards):
            code = item['code']
            if not pts:
                print('[WARN] {} 查询失败/无新增（保留旧 {} 条）'.format(code, len(old)))
                continue
            merged = {p['date']: p['yield'] for p in old}   # 旧数据全部保留
            merged.update(pts)                              # 只补缺口（去重覆盖同日）
            series = sorted([{'date': d, 'yield': v} for d, v in merged.items()],
                            key=lambda x: x['date'])
            item['divHistory'] = series                     # 合并（非覆盖）
            if series[-1]['date'] >= TARGET_DATE:
                fixed += 1
                print('[OK] {} {} {}条 → 最新 {}'.format(
                    code, item.get('name', ''), len(series), series[-1]['date']))
            else:
                print('[WARN] {} 最新仍为 {}（旧 {} 条已保留）'.format(
                    code, series[-1]['date'], len(old)))

    # 原子写入（避免坚果云盘锁）
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(INDEX_JSON), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=1)
        os.replace(tmp_path, INDEX_JSON)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    print('\n已补齐 {} / {} 个指数（TARGET_DATE={}）'.format(fixed, len(laggards), TARGET_DATE))


if __name__ == '__main__':
    main()

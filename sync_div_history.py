#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股息率历史数据更新脚本
====================================
调用 Wind MCP 拉取所有指数的股息率日频历史序列（交易日），
合并写入 data/indexData.json 的 divHistory 字段。

增量更新机制（重要）:
    - 已存在 divHistory 的指数：只拉取"现有数据最后日期之后"的新数据段，旧数据保留，不重复拉取。
    - 无 divHistory 的指数（新指数/缺失）：按近 36 个月全量拉取。
    - 可用环境变量 SX_FULL_REFRESH=1 强制全量重拉（一般不需要）。

用法:
    python3 sync_div_history.py

前置条件:
    - wind-mcp-skill 已安装 (SKILL.md 存在)
    - WIND_API_KEY 已配置
    - NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem (macOS 证书问题)
"""
import io, json, os, subprocess, tempfile, collections, time, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
# 支持环境变量覆盖数据目录（坚果云盘锁定时可改到本地临时目录拉取）
DATA_DIR = os.environ.get('SX_DATA_DIR') or os.path.join(BASE, 'data')
INDEX_JSON = os.path.join(DATA_DIR, 'indexData.json')

WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')

# 每批查询的指数数量（Wind 自然语言一次可查多个，顿号连接；返回表含「Wind代码」列）
BATCH_SIZE = 3
# 每段日历天数。2026-09-19：由 90 天改为 42 天——批量 3 个指数时单次返回 ≈3×30 交易日 ≈90 行，
# 稳在 Wind「单次 ≤100 行」上限内（wind-query-tips §B），避免静默截断丢数据。
SEG_DAYS = 42
# 批次间隔（秒），避免高频触发 Wind 限流（§E）
SLEEP = 0.5

# 并发路数（2026-09-26 提速：批次并发；单批仍 ≤BATCH_SIZE 只 × ≤SEG_DAYS 天，稳在 100 行上限内）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '8')))


def latest_trading_day():
    """最近工作日（跳过周末；不含节假日——节假日时境内指数会滞后 1 天，由覆盖检查 ≤2 天容差放行）"""
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


def get_all_codes():
    with io.open(INDEX_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [x['code'] for x in data]


def call_wind(question):
    """调用 Wind CLI，返回 {code: [{'date','yield'}]}（2026-09-19 重构：批量 + 重试 + 按列名解析）。

    - 批量：question 可含多个指数（顿号连接），返回表含「Wind代码」列，按该列分组。
    - 按列名解析（wind-query-tips §G）：日频查询列为 [Wind代码, 证券简称, …股息率…, 日期]，
      其中股息率列名会随查询日期区间变化（如「2026年8月1日到2026年8月22日每日的股息率」），
      故必须按关键字匹配，不可按固定索引；否则列错位会误读数值。
    - 重试 3 次（§C：瞬时失败/QPS 限流可 3-5 秒后原样重试一次）。
    """
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'index_data', 'get_index_fundamentals',
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=90, env=env,
                cwd=WIND_SKILL)
        except Exception:
            time.sleep(5)
            continue
        if r.returncode != 0:
            time.sleep(5)
            continue
        try:
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return {}
            inner = json.loads(text)
            table = inner.get('data', {}).get('data', [{}])[0]
            cols = [c.get('name', '') for c in table.get('columns', [])]
            rows = table.get('rows', []) or []
            ci = next((i for i, n in enumerate(cols) if '代码' in n), 0)
            yi = next((i for i, n in enumerate(cols) if '股息率' in n), None)
            di = next((i for i, n in enumerate(cols) if n == '日期'), None)
            if di is None:
                di = next((i for i, n in enumerate(cols) if '日期' in n and '发布' not in n), None)
            if yi is None or di is None:
                return {}
            out = collections.defaultdict(list)
            for row in rows:
                if len(row) > max(ci, yi, di) and row[ci] and row[yi] is not None and row[di]:
                    out[str(row[ci]).strip()].append(
                        {'date': str(row[di])[:10], 'yield': row[yi]})
            return out
        except Exception:
            time.sleep(5)
    return {}


def get_existing_last_dates():
    """读取 indexData.json 中每个指数 divHistory 的最后日期（用于增量拉取）"""
    with io.open(INDEX_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for x in data:
        h = x.get('divHistory') or []
        if h:
            out[x['code']] = h[-1]['date']
    return out

def _fetch_batch(batch, last_dates, full, today, max_start):
    """单个批次：并集区间按 SEG_DAYS 切片拉取，返回 {code: [{'date','yield'}]}（无新增者返回空列表占位）。"""
    out = {}
    starts = {}
    for code in batch:
        sd = last_dates.get(code)
        start = datetime.date.fromisoformat(sd) if sd else max_start
        if sd and start >= today:
            out[code] = []          # 占位：已到最新，无新增（main 保留旧数据）
            continue
        starts[code] = start
    if starts:
        cur = min(starts.values())
        while cur <= today:
            seg_end = min(cur + datetime.timedelta(days=SEG_DAYS), today)
            active = [c for c in batch if c in starts and starts[c] <= seg_end]
            if active:
                q = '、'.join(active) + ' {}至{}的股息率历史数据按交易日列出，给出每个交易日的值'.format(
                    cur.isoformat(), seg_end.isoformat())
                grouped = call_wind(q)
                for code in active:
                    lo = max(cur, starts[code]).isoformat()
                    hi = seg_end.isoformat()
                    out.setdefault(code, []).extend(
                        p for p in grouped.get(code, []) if lo <= p['date'] <= hi)
            cur = seg_end + datetime.timedelta(days=1)
    for code in batch:
        out.setdefault(code, [])
    return out


def fetch_history(codes):
    """并发拉取（2026-09-26 提速）：**批次间并发**，批内仍按 SEG_DAYS 切片（单次 ≲90 行，不触 Wind 100 行上限）。
    增量：已有 divHistory 的只补最后日期之后；无历史的全量拉近 36 个月。SX_FULL_REFRESH=1 强制全量。"""
    full = os.environ.get('SX_FULL_REFRESH') == '1'
    last_dates = {} if full else get_existing_last_dates()
    today = datetime.date.today()
    max_start = today - datetime.timedelta(days=36 * 30)
    batches = [codes[i:i + BATCH_SIZE] for i in range(0, len(codes), BATCH_SIZE)]
    n_batch = len(batches)
    print('  并发 {} 路拉取 {} 批...'.format(WORKERS, n_batch), flush=True)
    res = [None] * n_batch
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(_fetch_batch, b, last_dates, full, today, max_start): i
                for i, b in enumerate(batches)}
        for fut in as_completed(futs):
            i = futs[fut]
            res[i] = fut.result()
            print('  批次 {}/{}: {}'.format(i + 1, n_batch, ' '.join(batches[i])), flush=True)
    hist = collections.defaultdict(list)
    for r in res:
        for code, pts in (r or {}).items():
            hist[code].extend(pts)
    return hist


def _fetch_gap_single(code, last_date, target):
    """单指数拉取 [last_date, target] 日频段（分段 ≤90 天）。返回 {date: yield}。"""
    start = datetime.date.fromisoformat(last_date)
    end = datetime.date.fromisoformat(target)
    segs = []
    cur = start
    while cur <= end:
        seg_end = min(cur + datetime.timedelta(days=90), end)
        segs.append((cur.isoformat(), seg_end.isoformat()))
        cur = seg_end + datetime.timedelta(days=1)
    out = {}
    for s, e in segs:
        q = '{} {}至{}的股息率历史数据按交易日列出，给出每个交易日的值'.format(code, s, e)
        grouped = call_wind(q)
        pts = grouped.get(code)
        if pts is None and len(grouped) == 1:
            pts = next(iter(grouped.values()))
        for p in (pts or []):
            if s <= p['date'] <= e:
                out[p['date']] = p['yield']
    return out


def fill_laggards(index_data):
    """批次后仍滞后的指数，逐个单查补齐（原 fix_laggard_indexes 逻辑并入本脚本；2026-09-26 并发）。
    只补缺口、旧数据全保留；节假日导致境内指数滞后时打印 WARN 但保留旧值。"""
    target = latest_trading_day().isoformat()
    laggards = [x for x in index_data
                if x.get('divHistory') and x['divHistory'][-1]['date'] < target]
    print('  批次后滞后指数: {}（单查补齐，TARGET={}）'.format(len(laggards), target), flush=True)
    if not laggards:
        return 0

    def _one(item):
        old = item.get('divHistory') or []
        return item, old, _fetch_gap_single(item['code'], old[-1]['date'], target)

    fixed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for item, old, pts in ex.map(_one, laggards):
            if not pts:
                print('  [WARN] {} 无新增（保留旧 {} 条）'.format(item['code'], len(old)), flush=True)
                continue
            merged = {p['date']: p['yield'] for p in old}     # 旧数据全保留
            merged.update(pts)                                # 只补缺口
            series = sorted([{'date': d, 'yield': v} for d, v in merged.items()],
                            key=lambda x: x['date'])
            item['divHistory'] = series
            if series[-1]['date'] >= target:
                fixed += 1
                print('  [OK] {} 补齐 → {}'.format(item['code'], series[-1]['date']), flush=True)
            else:
                print('  [WARN] {} 最新仍为 {}（旧值保留）'.format(item['code'], series[-1]['date']), flush=True)
    return fixed


def main():
    print('===== 股息率历史数据更新 =====')
    if not os.path.exists(CLI):
        print('[ERROR] wind-mcp-skill 未找到:', WIND_SKILL)
        return
    codes = get_all_codes()
    print('指数数:', len(codes))
    hist = fetch_history(codes)
    print('拉取到 {} 个指数的历史数据'.format(len(hist)))

    with io.open(INDEX_JSON, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
    updated = 0
    for item in index_data:
        code = item['code']
        old_hist = item.get('divHistory') or []
        if code in hist and hist[code]:
            # 合并旧历史 + 新拉取段（按日期去重）
            merged = {}
            for p in old_hist:
                merged[p['date']] = p['yield']
            for p in hist[code]:
                merged[p['date']] = p['yield']
            series = sorted([{'date': d, 'yield': v} for d, v in merged.items()],
                            key=lambda x: x['date'])
            item['divHistory'] = series
            updated += 1
        elif code in hist and not hist[code] and old_hist:
            pass  # 已有数据且本次无新增 → 保留旧数据，不覆盖
        else:
            # 拉取失败/跳过：保留旧数据，绝不删除（2026-08-10 A6 复发修复：此前这里 pop 会清空全部 divHistory）
            pass
    # 滞后指数单查补齐（原 fix_laggard_indexes 逻辑并入本脚本，2026-09-26；fix_laggard 仍可单独跑，通常已无滞后）
    fill_laggards(index_data)
    # 原子写入：先写临时文件再替换，避免坚果云盘对目标文件加锁导致 EPERM
    import tempfile
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=1)
        os.replace(tmp_path, INDEX_JSON)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    print('已写入历史数据指数数:', updated, '/', len(index_data))


if __name__ == '__main__':
    main()

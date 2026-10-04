#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
余额宝 7日年化历史数据拉取
====================================
调用 Wind MCP 拉取天弘余额宝(000198.OF)的七日年化收益率日频历史序列（交易日），
生成 data/yuebaoHistory.json（供详情页图表使用）。

用法:
    python3 sync_yuebao_history.py

2026-09-13 加固：（1）每段失败自动重试 3 次（瞬时失败不再静默丢段）；
（2）写回前与现有 yuebaoHistory.json 合并（新数据优先，旧数据兜底缺口），
杜绝"某段拉取失败 → 整体重写丢历史"（违反"写回绝不删除旧数据"铁律）。
"""
import io, json, os, subprocess, time, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
OUT_FILE = os.path.join(DATA_DIR, 'yuebaoHistory.json')

WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')

WINDCODE = '000198.OF'


def ts():
    return time.strftime('%H:%M:%S')


def call_wind(question):
    """返回 (columns, rows)；失败返回 ([], []).
    2026-09-19 优化：返回列名以便按列名取值（Wind 列顺序会漂移，见 wind-query-tips §G）。"""
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):   # 瞬时失败重试 3 次（2026-09-13 加固）
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'fund_data', 'get_fund_performance',
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=90, env=env, cwd=WIND_SKILL)
        except Exception:
            time.sleep(6); continue
        if r.returncode != 0:
            time.sleep(6); continue
        try:
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return [], []
            inner = json.loads(text)
            tb = inner['data']['data'][0]
            cols = [str(c.get('name', '')) for c in tb.get('columns', [])]
            return cols, tb.get('rows', [])
        except Exception:
            time.sleep(6)
    return [], []


def _pick_series(cols, rows):
    """按列名取 (date, yield)；列名缺失时回退到历史位置口径(row[2]/row[3])。"""
    yi = next((i for i, c in enumerate(cols) if '七日年化' in c or '年化收益' in c), None)
    di = next((i for i, c in enumerate(cols) if '日期' in c), None)
    out = []
    for row in rows:
        try:
            if yi is not None and di is not None and len(row) > max(yi, di):
                if row[yi] is None or not row[di]:
                    continue
                out.append({'date': str(row[di]), 'yield': float(row[yi])})
            elif len(row) >= 4 and row[2] is not None and row[3]:
                out.append({'date': row[3], 'yield': float(row[2])})
        except (ValueError, TypeError):
            continue
    return out


def atomic_write_json(path, obj):
    """原子写入（临时文件 + os.replace），避免坚果云同步锁导致半截文件。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def main():
    print('===== 余额宝 7日年化历史数据拉取 =====')
    if not os.path.exists(CLI):
        print('[ERROR] wind-mcp-skill 未找到:', WIND_SKILL)
        return
    # 分段拉取日频（Wind 单次返回上限约100行，用 90 天分段）
    # 覆盖范围：默认近 36 个月；若 indexData divHistory 最早日期更早，则动态延伸到其 180 天前，
    # 保证详情页图表"最长区间"的余额宝橙线不出现假平线（2026-08-11 修复）
    import datetime
    today = datetime.date.today()
    earliest = today - datetime.timedelta(days=36 * 30)
    try:
        idx_path = os.path.join(DATA_DIR, 'indexData.json')
        if os.path.exists(idx_path):
            with io.open(idx_path, 'r', encoding='utf-8') as f:
                idata = json.load(f)
            ds = []
            for x in idata:
                h = x.get('divHistory') or []
                if h:
                    ds.append(h[0]['date'])
            if ds:
                d0 = datetime.date.fromisoformat(min(ds))
                earliest = min(earliest, d0 - datetime.timedelta(days=180))
    except Exception:
        pass
    print('覆盖范围: {} ~ {}'.format(earliest, today), flush=True)
    segs = []
    seg_end = today
    while seg_end > earliest:
        seg_start = max(earliest, seg_end - datetime.timedelta(days=90))
        segs.append((seg_start.isoformat(), seg_end.isoformat()))
        seg_end = seg_start - datetime.timedelta(days=1)
    series = []
    n_seg = len(segs)
    print('分段数: {}（90 天/段）'.format(n_seg), flush=True)
    for si, (start, end) in enumerate(segs):
        question = '天弘余额宝 {} {}至{}的七日年化收益率日频数据（每个交易日的值）'.format(WINDCODE, start, end)
        cols, rows = call_wind(question)
        got = _pick_series(cols, rows)
        if not got:
            print('  [%s] 段 %d/%d %s~%s 未获取到数据（保留旧值）' % (ts(), si + 1, n_seg, start, end), flush=True)
            continue
        series.extend(got)
        print('  [%s] 段 %d/%d %s~%s: %d 条' % (ts(), si + 1, n_seg, start, end, len(got)), flush=True)
    if not series:
        print('[ERROR] 未获取到数据')
        return
    # 去重
    seen = {}
    for x in series:
        seen[x['date']] = x['yield']
    series = [{'date': d, 'yield': seen[d]} for d in sorted(seen)]
    # 与现有文件合并（新数据优先覆盖，旧数据兜底缺口）避免瞬时失败丢历史（2026-09-13）
    try:
        with io.open(OUT_FILE, encoding='utf-8') as _f:
            prev = json.load(_f).get('series', [])
    except Exception:
        prev = []
    merged = {}
    for x in prev:
        merged[x['date']] = x['yield']
    for x in series:
        merged[x['date']] = x['yield']
    series = [{'date': d, 'yield': merged[d]} for d in sorted(merged)]
    os.makedirs(DATA_DIR, exist_ok=True)
    atomic_write_json(OUT_FILE, {'code': WINDCODE, 'name': '天弘余额宝', 'series': series})
    print('已写入 {} 条历史数据 -> {}'.format(len(series), OUT_FILE), flush=True)
    if series:
        print('范围: {} ~ {} | 最新: {}%'.format(
            series[0]['date'], series[-1]['date'], series[-1]['yield']), flush=True)


if __name__ == '__main__':
    main()

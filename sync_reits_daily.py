#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REITs 日频数据增量维护（2026-08-12 确立日频口径，08-15 固化流水线；2026-09-26 覆盖范围改为全量）

覆盖范围（2026-09-26 用户要求）：
- 以 **data/reitsData.json 里的全部 REITs** 为准（此前只覆盖 reitsDaily.json 内已有的 58 只）；
  分组（property / concession）由 reitsData 的 `projectType`（产权类 / 特许经营权类）推导。

数据结构：
- data/reitsDaily.json 缓存各 REIT 原始日频派息率（基线 2023-01 起；新标的从**上市日**与 2023-01-01 的较晚者起）
- 增量：每只拉"最后日期+1 ~ 今天"的日频段（每段 135 日历日，单次 Wind 返回 ≤100 行）
- 新标的（缓存无序列）：做一次**基线拉取**（起点 = 上市日，且不早于 2023-01-01）
- 重算两类每交易日中位数 → 更新 assetHistory.json 的 REITs 两类序列
- 全量重建：--full（重新逐段拉取，约 580+ 次调用）

性能（2026-09-26）：逐只 **并发**拉取（默认 8 路，`SX_WIND_WORKERS` 可调；语义不变——失败保留旧值、
  原子写回）；`call_wind` 对「没找到数据」（无数据区间）与接口错误（含「单日请求次数超限」）**快速失败、不重试**，
  避免每只空耗约 18s。

用法：python3 sync_reits_daily.py [--full] [--dry-run]   # --dry-run 只打印覆盖清单、不调 Wind、不写回
"""
import json, os, subprocess, sys, io, time, datetime, tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CACHE = os.path.join(DATA_DIR, 'reitsDaily.json')
HIST = os.path.join(DATA_DIR, 'assetHistory.json')
REITS = os.path.join(DATA_DIR, 'reitsData.json')
CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wind_guard_cli.mjs')  # Wind 额度守卫包装器（2026-10-06；真实 cli.mjs 见 SX_WIND_CLI_REAL）
SEG_DAYS = 135          # 每段日历天数（≤100 交易日/次）
BASE_START = '2023-01-01'   # 历史序列统一起点（早于此无意义）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '8')))   # 并发路数（2026-09-26）

# 项目属性 → 现金流分组（产权类=持续租金现金流 / 特许经营权类=有限期经营权现金流）
GROUP_OF = {'产权类': 'property', '特许经营权类': 'concession'}


def ts():
    return time.strftime('%H:%M:%S')


def call_wind(question):
    """单次 Wind 查询（3 次重试 + 代理变量清理；对确定性错误快速失败）。

    2026-09-26：
      - 接口错误（含「单日请求次数超限」）→ **不重试**，直接返回 None；
      - 「没找到数据」（该区间无数据）→ **不重试**，直接返回 None（否则每只空耗 ~18s）。
    成功返回 rows（可能为空列表）；失败返回 None。
    """
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'fund_data', 'get_fund_performance',
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=env,
                cwd=os.path.expanduser('~/.agents/skills/wind-mcp-skill'))
        except Exception:
            time.sleep(4)
            continue
        if r.returncode != 0:
            time.sleep(4)
            continue
        blob = (r.stdout or '') + (r.stderr or '')
        if 'backend_error' in blob or '"ok": false' in blob or '超限' in blob or '没找到数据' in blob:
            return None   # 确定性错误/无数据 → 不重试
        try:
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            inner = json.loads(text)
            return inner['data']['data'][0]['rows']
        except Exception:
            time.sleep(4)
    return None


def atomic_write_json(path, obj):
    """原子写入（临时文件 + os.replace），避免坚果云/坚果云盘同步锁导致半截文件。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_cache():
    if not os.path.exists(CACHE):
        return None
    with io.open(CACHE, encoding='utf-8') as f:
        return json.load(f)


def save_cache(cache):
    atomic_write_json(CACHE, cache)


def load_reits_universe():
    """从 reitsData.json 取全部 REITs → [(code, name, group, listedDate)]。

    `projectType` 无法映射到 property/concession 的标的会打印告警并跳过（不静默）。
    """
    out = []
    if not os.path.exists(REITS):
        print('[错误] data/reitsData.json 不存在，无法确定覆盖范围', flush=True)
        return out
    with io.open(REITS, encoding='utf-8') as f:
        data = json.load(f)
    for x in data:
        code = x.get('code')
        if not code:
            continue
        pt = x.get('projectType') or ''
        grp = GROUP_OF.get(pt)
        if not grp:
            print('  [⚠️] %s projectType=%r 无法归类（期望 产权类 / 特许经营权类）→ 本次跳过'
                  % (code, pt), flush=True)
            continue
        out.append((code, x.get('shortName') or x.get('name') or '', grp, x.get('listedDate') or ''))
    return out


def fetch_range(code, start, end):
    q = '{} {}至{}每日的派息率，给出每个交易日的值'.format(code, start, end)
    rows = call_wind(q)
    out = {}
    if rows:
        for r in rows:
            if len(r) >= 4 and r[2] is not None and r[3]:
                d = str(r[3])[:10]
                if start <= d <= end:
                    out[d] = float(r[2])
    return out


def fetch_since(code, start):
    """从 start 起分段拉取到今天（每段 135 日历日）。"""
    today = datetime.date.today().isoformat()
    out = {}
    cur = start
    while cur <= today:
        seg_end = min(datetime.date.fromisoformat(cur) + datetime.timedelta(days=SEG_DAYS),
                      datetime.date.today()).isoformat()
        out.update(fetch_range(code, cur, seg_end))
        cur = (datetime.date.fromisoformat(seg_end) + datetime.timedelta(days=1)).isoformat()
        time.sleep(0.3)
    return out


def updates_for(code, series, listed, full_mode, today):
    """（并发 worker）计算某只 REIT 需要新增的日频点。返回 (new_pts, note)。"""
    if full_mode:
        return fetch_since(code, BASE_START), 'full'
    if not series:
        # 新标的：基线拉取（起点 = 上市日，且不早于 2023-01-01）
        start = listed if listed and listed > BASE_START else BASE_START
        return fetch_since(code, start), 'baseline:' + start
    last = max(series)
    start = (datetime.date.fromisoformat(last) + datetime.timedelta(days=1)).isoformat()
    if start <= today:
        return fetch_since(code, start), 'incr:' + start
    return {}, 'nochange'


def rebuild_medians(cache):
    """按现金流属性分组，跨标的重算每交易日中位数"""
    groups = {'property': [], 'concession': []}
    for code, v in cache.get('codes', {}).items():
        groups.setdefault(v.get('group'), []).append(v.get('series', {}))
    result = {}
    for grp, name in (('property', 'REITs产权类'), ('concession', 'REITs特许经营权类')):
        by_day = defaultdict(list)
        for s in groups.get(grp, []):
            for d, val in s.items():
                by_day[d].append(val)
        seq = []
        for d in sorted(by_day):
            vals = sorted(by_day[d])
            n = len(vals)
            med = vals[n // 2] if n % 2 == 1 else (vals[n // 2 - 1] + vals[n // 2]) / 2
            seq.append({'date': d, 'yield': round(med, 4)})
        result[name] = seq
    return result


def main():
    full_mode = '--full' in sys.argv
    cache = load_cache()
    if cache is None:
        print('[错误] data/reitsDaily.json 不存在。首次使用需先建立基线（全量拉取，约 580+ 次调用）：')
        print('       或运行 --full')
        return 1
    codes = cache.setdefault('codes', {})

    # 覆盖范围 = reitsData.json 全部 REITs（2026-09-26 用户要求）
    universe = load_reits_universe()
    if not universe:
        print('[错误] reitsData.json 无可归类标的，终止', flush=True)
        return 1
    # 使缓存条目与 reitsData 对齐（新增条目 / 更新 name）
    # 注意（2026-09-26）：**只给缓存里没有的标的**按 projectType 归组；既有标的的分组**保持不变**，
    #   避免「扩展覆盖范围」顺带改写历史分类（那会整体平移两类中位数——实测 5 只能源基础设施 REITs
    #   在旧curated列表里是 concession、Wind projectType 为「产权类」，若改写会让 2023 起 80% 点位变化）。
    pre_existing = set(codes)
    added = 0
    for code, name, grp, _listed in universe:
        if code not in codes:
            added += 1
        v = codes.setdefault(code, {})
        if name:
            v['name'] = name
        if code not in pre_existing or not v.get('group'):
            v['group'] = grp
        v.setdefault('series', {})

    today = datetime.date.today().isoformat()
    n_codes = len(universe)
    print('[REITs日频] 覆盖 reitsData 全部 %d 只（缓存新增 %d 只；截止今天 %s，模式=%s，并发 %d 路）...'
          % (n_codes, added, today, '全量' if full_mode else '增量', WORKERS), flush=True)

    # --dry-run：只打印覆盖清单，不调用 Wind、不写入（供上线前核对覆盖范围）
    if '--dry-run' in sys.argv:
        for i, (code, name, grp, listed) in enumerate(universe, 1):
            print('  [{:2d}/{:2d}] {} {}  group={}  上市={}  {}'.format(
                i, n_codes, code, name or '-', grp, listed or '-',
                '（缓存已有）' if code in pre_existing else '（新增，将基线拉取）'), flush=True)
        print('[DRY-RUN] 未调用 Wind、未写回。确认覆盖范围无误后去掉 --dry-run 正式运行。', flush=True)
        return 0

    # 并发拉取（语义不变：失败保留旧值；汇总后单线程写回）
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(
            lambda t: (t, updates_for(t[0], codes[t[0]].get('series', {}), t[3], full_mode, today)),
            universe))

    total_calls = 0
    for i, ((code, name, _grp, _listed), (new_pts, note)) in enumerate(results, 1):
        v = codes[code]
        series = v.setdefault('series', {})
        old_last = max(series) if series else ''
        if note.startswith('baseline'):
            print('  [{:2d}/{:2d}] {} {} {} 新标的 → 基线拉取 {} 起'.format(
                i, n_codes, ts(), code, name, note.split(':', 1)[1]), flush=True)
        series.update(new_pts or {})
        v['series'] = series
        new_last = max(series) if series else ''
        total_calls += 1
        if new_last != old_last:
            print('  [{:2d}/{:2d}] {} {} {} 增量 {} → {}（{} 点）'.format(
                i, n_codes, ts(), code, name, old_last or '-', new_last or '-',
                len(series)), flush=True)
        else:
            print('  [{:2d}/{:2d}] {} {} {} 无新增（最新 {}）'.format(
                i, n_codes, ts(), code, name, new_last or '-'), flush=True)
    save_cache(cache)

    # 重算中位数并更新 assetHistory
    medians = rebuild_medians(cache)
    with io.open(HIST, encoding='utf-8') as f:
        hist = json.load(f)
    for name, seq in medians.items():
        hist[name] = seq
        if seq:
            print('  [更新] {} → {} 点（最新 {:.2f}% @ {}）'.format(
                name, len(seq), seq[-1]['yield'], seq[-1]['date']), flush=True)
        else:
            print('  [更新] {} → 0 点（无数据）'.format(name), flush=True)
    atomic_write_json(HIST, hist)
    print('[完成] assetHistory.json REITs 两类已更新（覆盖 {} 只）'.format(total_calls), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())

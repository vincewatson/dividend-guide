#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""港交所红利 ETF 自动发现（清单「进」机制 · 2026-10-06）

数据源：中央数据库（与「策略魔方」共用同一库）导出的港交所上市 ETF 名单
        —— data/curation/_hk_etf_universe.json 的 dividend_funds 子集（含名称）。
判据：
1. 名称关键词命中「红利类」：红利 / 高息 / 高股息 / 股息率 / 股东回报 / 央企回报；
   并**排除** REIT（房托 / 房地产 / REIT）—— 那属另一数据域（reitsData）。
2. 多柜台 / 多份额类别（-R 人民币 / -U 美元 / A 类等）按 **ETF 全称** 归并，
   每个基金只保留 **主柜台（港元，代码最小）** 一条。
3. 与现有 hkEtfData.json + data/curation/_retired.json（停用名单）对照 → 得「新标的」。

默认**仅报告**（不修改任何数据，安全）；加 `--add` 才拉取 Wind 详情补入 hkEtfData.json
（与 cnEtfData 同机制：build_lists 的「表外行护栏」保证重建时不丢失）。

用法：python3 sync_new_hk_etf.py [--add] [--dry-run]
"""
import json, os, subprocess, sys, io, time, datetime, tempfile, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CURATION_DIR = os.path.join(DATA_DIR, 'curation')
UNIVERSE = os.path.join(CURATION_DIR, '_hk_etf_universe.json')
HK_ETF = os.path.join(DATA_DIR, 'hkEtfData.json')
RETIRED = os.path.join(CURATION_DIR, '_retired.json')
CLI = os.path.expanduser('~/.agents/skills/wind-mcp-skill/scripts/cli.mjs')

# 红利类关键词（港交所口径：红利/高息/高股息/股息率/股东回报/央企回报）
KEYWORDS = ['红利', '高息', '高股息', '股息率', '股东回报', '央企回报']
# 排除：REIT（房托/房地产）—— 属 reitsData 数据域
EXCLUDE = ['房托', '房地产', 'REIT', 'reit']

SLEEP = float(os.environ.get('SX_NHE_SLEEP', '0.4'))


def ts():
    return time.strftime('%H:%M:%S')


def load_json(path, default=None):
    try:
        with io.open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else []


def save_json(path, data):
    """原子写入（临时文件 + os.replace），避免坚果云同步锁写出半截文件。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def _code_int(code):
    """'3590.HK' → 3590；用于「主柜台 = 代码最小」判定。异常返回一个大数。"""
    try:
        return int(str(code).split('.')[0])
    except (TypeError, ValueError):
        return 10 ** 9


def _norm_fundname(full_name):
    """归一 ETF 全称用于「多柜台/多份额类别」归并。

    同一基金的港元主柜台与其 -R/-U 柜台在中央库里全称可能仅差一个
    「(上市类别)」后缀（如 3437.HK「…指数ETF(上市类别)」 vs 9437.HK「…指数ETF」），
    故先剥离该类后缀、再去空格，才能正确归并到同一只基金。
    """
    n = (full_name or '').strip()
    n = re.sub(r'[（(]\s*上市类别\s*[)）]', '', n)
    return n.replace(' ', '')


def match_dividend(name, full_name):
    """名称是否命中红利类关键词且非 REIT。"""
    text = '%s %s' % (name or '', full_name or '')
    if any(e in text for e in EXCLUDE):
        return False
    return any(k in text for k in KEYWORDS)


def detect():
    """返回（新标的列表, 关键词命中并归并后的全部基金数, 跳过的 REIT/非红利计数）。

    新标的 = 归并后的主柜台 code 既不在 hkEtfData，也不在 _retired 停用名单。
    """
    uni = load_json(UNIVERSE, {})
    funds = (uni or {}).get('dividend_funds') or []
    if not funds:
        print('[⚠] %s 无 dividend_funds 字段——请先按 note 中的 SQL 从中央数据库刷新该文件'
              % os.path.basename(UNIVERSE), flush=True)
        return [], 0, 0
    # 1) 关键词过滤 + 2) 按全称归并（保留代码最小的主柜台）
    best = {}
    skipped = 0
    for f in funds:
        code = f.get('code')
        if not code:
            continue
        if not match_dividend(f.get('name'), f.get('full_name')):
            skipped += 1
            continue
        key = _norm_fundname(f.get('full_name')) or (f.get('name') or code)
        cur = best.get(key)
        if cur is None or _code_int(code) < _code_int(cur.get('code')):
            best[key] = f
    # 3) 与现有成员 + 停用名单对照
    exist_codes = {x.get('code') for x in load_json(HK_ETF, []) if isinstance(x, dict)}
    retired = set((load_json(RETIRED, {}) or {}).get('retired', {}).keys())
    new = [f for f in best.values()
           if f.get('code') not in exist_codes and f.get('code') not in retired]
    new.sort(key=lambda x: _code_int(x.get('code')))
    return new, len(best), skipped


# ---------------------------------------------------------------------------
# Wind 取数（仅 --add 时需要；3 次重试 + 6s 退避 + 代理变量清理）
# ---------------------------------------------------------------------------
def _wind_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def call_wind_tbl(server, tool, question):
    for _ in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', server, tool,
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=120, env=_wind_env(),
                cwd=os.path.expanduser('~/.agents/skills/wind-mcp-skill'))
        except Exception:
            time.sleep(6)
            continue
        if r.returncode != 0:
            time.sleep(6)
            continue
        try:
            outer = json.loads(r.stdout)
            inner = json.loads(outer['content'][0]['text'])
            return [(tb.get('columns', []), tb.get('rows', []))
                    for tb in inner.get('data', {}).get('data', [])]
        except Exception:
            time.sleep(6)
    print('  [⚠] %s.%s 查询连续 3 次失败：%s' % (server, tool, question[:40]), flush=True)
    return []


def _col_index(cols, *keys):
    names = [(c.get('name') or '') if isinstance(c, dict) else str(c) for c in cols]
    for i, n in enumerate(names):
        if any(k in n for k in keys):
            return i
    return -1


def _pick_row(tbls, wind_code):
    """从 [(cols, rows), ...] 挑出目标行（按 Wind 全代码精确匹配）。"""
    base = str(wind_code).split('.')[0]
    cands = [(c, r) for c, rows in tbls for r in rows]
    for c, r in cands:
        if r and str(r[0]) == wind_code:
            return c, r
    if len(cands) == 1 and cands[0][1] and str(cands[0][1][0]).split('.')[0] == base:
        return cands[0]
    return None, None


def _getter(cols, row):
    def g(*keys):
        i = _col_index(cols, *keys)
        return row[i] if 0 <= i < len(row) else None
    return g


def fetch_detail(wind_code):
    q = '{} 跟踪指数代码 跟踪指数名称 基金管理人 管理费率 基金成立日 上市日期'.format(wind_code)
    cols, r = _pick_row(call_wind_tbl('fund_data', 'get_fund_info', q), wind_code)
    if not r:
        return None
    g = _getter(cols, r)

    def num(*keys):
        v = g(*keys)
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    found = g('基金成立日')
    return {
        'trackCode': str(g('跟踪指数代码') or ''),
        'trackName': str(g('跟踪指数名称') or ''),
        'manager': str(g('基金管理人') or ''),
        'feeRate': num('管理费率'),          # 百分数，如 0.65
        'foundDate': str(found)[:10] if found else '',
    }


def fetch_scale(wind_code):
    q = '{} 最新规模'.format(wind_code)
    cols, r = _pick_row(call_wind_tbl('fund_data', 'get_fund_holders', q), wind_code)
    if not r:
        return 0.0
    g = _getter(cols, r)
    try:
        return round(float(g('最新规模')), 2)
    except (TypeError, ValueError):
        return 0.0


def build_row(fund, detail, size, today):
    fee = detail.get('feeRate', 0.0)            # 百分数（Wind 口径）
    # 跟踪指数：优先 Wind，Wind 缺则回退中央数据库导出的 track_name
    # （Wind 对部分新港ETF 不返回跟踪指数代码/名称，中央库仅有名称。）
    return {
        'code': fund['code'],
        'name': fund.get('name') or '',
        'fullname': fund.get('full_name') or '',
        'connect': bool(fund.get('hk_connect')),
        'trackCode': detail.get('trackCode', ''),
        'trackName': detail.get('trackName', '') or (fund.get('track_name') or ''),
        'manager': detail.get('manager', ''),
        'listedDate': detail.get('foundDate', '') or '',
        'fee': '{:.2f}%'.format(fee) if fee else '0.00%',
        'feeNum': round(fee / 100.0, 4) if fee else 0.0,
        'size': size,
        'divDate': None,
        'sizeDate': today if size else None,
    }


def add_to_hk_etf(row):
    rows = load_json(HK_ETF, [])
    if any(isinstance(x, dict) and x.get('code') == row['code'] for x in rows):
        return False
    rows.append(row)   # 只追加、不重排：保持现有展示顺序（curation 顺序 + 表外行追加）
    save_json(HK_ETF, rows)
    return True


def main():
    add = '--add' in sys.argv
    dry = '--dry-run' in sys.argv
    print('[港ETF发现] [%s] 数据源：中央数据库港ETF名单（%s dividend_funds）'
          % (ts(), os.path.basename(UNIVERSE)), flush=True)
    new, matched, skipped = detect()
    print('  关键词命中并归并后基金数：%d（跳过 REIT/非红利 %d）' % (matched, skipped), flush=True)
    if not new:
        print('[完成] [%s] 无新标的，站点清单已与中央数据库一致' % ts(), flush=True)
        return
    print('  发现新标的 %d 只：' % len(new), flush=True)
    for f in new:
        print('    - %s %s（%s）' % (f['code'], f.get('name'), f.get('full_name')), flush=True)
    if not (add and not dry):
        print('[报告] 默认仅报告，未修改数据。加 --add 可拉取 Wind 详情补入 hkEtfData.json。', flush=True)
        return
    today = datetime.date.today().isoformat()
    for f in new:
        print('  [%s] 拉取 %s %s 详情…' % (ts(), f['code'], f.get('name')), flush=True)
        detail = fetch_detail(f['code'])
        if not detail:
            print('    [❌] Wind 详情拉取失败，跳过', flush=True)
            continue
        size = fetch_scale(f['code'])
        row = build_row(f, detail, size, today)
        if add_to_hk_etf(row):
            print('    ✅ 已补入 hkEtfData（跟踪 %s %s，管理费 %s，规模 %s 亿）'
                  % (row['trackCode'] or '—', row['trackName'] or '—', row['fee'], row['size']),
                  flush=True)
            if not row['trackCode']:
                print('    [i] 跟踪指数代码 Wind 缺（须人工补：详情页「跟踪指数」与股息率曲线依赖它）',
                      flush=True)
        time.sleep(SLEEP)
    print('[完成] [%s] 港ETF 补入结束' % ts(), flush=True)


if __name__ == '__main__':
    main()

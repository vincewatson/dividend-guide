#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基金「生命周期」体检 · 已结束标的的停用（excel-exit 机制 B，2026-10-06）

四类清单的「出」= 基金已结束（清盘/退市/终止），写入 data/curation/_retired.json，
由 build_lists.py 重建时跳过（历史数据不删，仅移出展示清单；删条目即恢复）。

两条判据（分别适用不同清单）：
  ① 港交所红利ETF —— 用 **中央数据库**（与「策略魔方」同源）的「港交所上市 ETF」全量名单比对：
       名单冻结在 data/curation/_hk_etf_universe.json（由会话内 MCP 从中央库 fund.product 导出）；
       我们的标的若**不在**该名单 → 视为已退市/终止 → 停用。
       该文件缺失时**自动退回**抓 aastocks 港股 ETF 列表（default.aspx，全量代码内嵌 HTML）作后备。
  ② 境内红利ETF / REITs / 货币基金 —— 用 Wind「基金到期日」判定：
       空（ETF/货基常青）或未来（REIT 合约存续期）⇒ 保留；**≤ 今天 ⇒ 已结束 ⇒ 停用**。
       ⚠️ 不可按「非空即出」——公募 REITs 运作中亦有未来到期日（如 180101.SZ=2071-06-07）。
       约 28 天节流（SX_LIFECYCLE_DAYS，清盘罕见，省 Wind 配额）。

用法：
  python3 sync_lifecycle.py [--dry-run] [--force] [--only hk,cn,reits,money]
      --dry-run   只报告不写入
      --force     忽略 Wind 部分的时间节流，强制重跑
      --only ...  只跑指定清单（hk=aastocks 港ETF；cn/reits/money=Wind 到期日）
"""
import io, json, os, re, subprocess, sys, time, datetime, tempfile
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
CURATION_DIR = os.path.join(DATA_DIR, 'curation')
RETIRED_PATH = os.path.join(CURATION_DIR, '_retired.json')

WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')

AASTOCKS_URL = 'https://www.aastocks.com/en/stocks/etf/default.aspx'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

# 港交所上市 ETF 全量名单（中央数据库导出，与「策略魔方」同源；由会话内 MCP 刷新）
HK_UNIVERSE_PATH = os.path.join(CURATION_DIR, '_hk_etf_universe.json')

SLEEP = float(os.environ.get('SX_LIFECYCLE_SLEEP', '0.4'))  # 保留兼容（并发化后不再逐只 sleep）
DAYS = int(os.environ.get('SX_LIFECYCLE_DAYS', '28'))
# Wind「到期日」并发拉取路数（2026-10-06：原逐只串行 + 0.4s sleep，约 227 只 → >18min；并发后约 3min）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '6')))

# Wind「基金到期日」体检的清单：key -> (站点数据文件, 中文名)
#   注：港交所ETF(hk) 不走 Wind（Wind 未返回其到期日），改由 aastocks 比对（见上）。
WIND_LISTS = [
    ('cn',    'cnEtfData.json',     '境内红利ETF'),
    ('reits', 'reitsData.json',     'REITs'),
    ('money', 'moneyFundData.json', '货币基金'),
]
HK_ETF = ('hkEtfData.json', '港交所红利ETF')


def ts():
    return time.strftime('%H:%M:%S')


def _clean_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def call_wind_tbl(tool, question):
    """Wind 查询，返回 [(columns, rows), ...]（3 次重试 + 6s 退避）。失败返回 []。"""
    for _ in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'fund_data', tool,
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=_clean_env(), cwd=WIND_SKILL)
        except Exception:
            time.sleep(6); continue
        if r.returncode != 0:
            time.sleep(6); continue
        try:
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return []
            inner = json.loads(text)
            return [(tb.get('columns', []), tb.get('rows', []))
                    for tb in inner.get('data', {}).get('data', [])]
        except Exception:
            time.sleep(6)
    return []


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path, obj):
    """原子写入（临时文件 + os.replace），避免坚果云同步锁导致半截文件。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ── 判据 ①：港交所上市 ETF 名单（中央数据库；后备 aastocks）────────────────────
def load_hk_universe():
    """读取中央数据库导出的港交所上市 ETF 名单（站点代码形式，如 '3070.HK'）。
    返回 (set, fetchedAt)；缺失/异常返回 None。"""
    try:
        obj = load_json(HK_UNIVERSE_PATH, None)
        if obj:
            codes = [c.strip() for c in str(obj.get('codes') or '').split(',') if c.strip()]
            if len(codes) >= 100:
                return set(codes), str(obj.get('fetchedAt') or '')
    except Exception:
        pass
    return None


def fetch_aastocks_universe():
    """抓 aastocks 港股 ETF 列表页，返回 5 位数字代码集合（如 {'03070','03555',...}）。
    失败或结果异常（< 100 个）返回 None —— 避免因抓取失败误判全部退市。"""
    for _ in range(3):
        try:
            r = subprocess.run(
                ['curl', '-sL', '--compressed', '-A', UA, '--max-time', '60', AASTOCKS_URL],
                capture_output=True, text=True, env=_clean_env())
        except Exception:
            time.sleep(4); continue
        if r.returncode == 0 and r.stdout:
            codes = set(re.findall(r'symbol=(\d{5})(?!\d)', r.stdout))
            if len(codes) >= 100:
                return codes
        time.sleep(4)
    return None


def to5(code):
    """站点代码 → aastocks 5 位代码：'3070.HK'→'03070'、'3555.HK'→'03555'。"""
    try:
        return '{:05d}'.format(int(str(code).split('.')[0]))
    except (TypeError, ValueError):
        return None


def check_hk_etf(retired, today):
    """港交所红利ETF「出」：标的若不在（中央数据库 / aastocks）港股ETF全量名单 → 停用。"""
    fname, label = HK_ETF
    rows = load_json(os.path.join(DATA_DIR, fname), []) or []
    codes = [x for x in rows if isinstance(x, dict) and x.get('code')]
    print('  — %s：%d 只' % (label, len(codes)), flush=True)

    uni = load_hk_universe()
    if uni:
        universe, fetched = uni
        print('    判据：中央数据库「港交所上市ETF」名单 %d 只（导出日 %s）' % (len(universe), fetched), flush=True)
        src = 'central-db'
        reason = '中央数据库「港交所上市ETF」名单中已不存在（退市/终止）'

        def present(code):
            return code in universe
    else:
        print('    [i] 未找到中央数据库名单文件（%s）→ 退回 aastocks 抓取' % os.path.basename(HK_UNIVERSE_PATH), flush=True)
        au = fetch_aastocks_universe()
        if au is None:
            print('    [WARN] aastocks 抓取失败（或结果异常）→ 本次跳过港ETF退市核对', flush=True)
            return {}
        print('    aastocks 返回 %d 个 ETF 代码' % len(au), flush=True)
        src = 'aastocks'
        reason = 'Aastocks 港股ETF列表中已不存在（退市/终止）'

        def present(code):
            c5 = to5(code)
            return c5 is not None and c5 in au

    found = {}
    for x in codes:
        code = x['code']
        if present(code) or code in retired:
            continue
        found[code] = {
            'name': x.get('name') or '',
            'lists': [label],
            'maturityDate': '',
            'retiredDate': today,
            'reason': reason,
            'source': src,
        }
        print('    ⚠ 命中：%s %s → 拟移出（%s 已无此代码）' % (code, x.get('name') or '', src), flush=True)
    return found


# ── 判据 ②：Wind「基金到期日」 ───────────────────────────────────────────────
def fetch_maturity(code, name):
    """查「基金到期日」。返回 (maturity_date_str|'', std_name)。取不到 → ('', name)。"""
    for cols, rows in call_wind_tbl('get_fund_info', '{} {} 基金到期日 证券简称'.format(code, name)):
        names = [(c.get('name') or '') if isinstance(c, dict) else str(c) for c in cols]
        ci_d = next((i for i, n in enumerate(names) if '到期日' in n), None)
        ci_n = next((i for i, n in enumerate(names) if '简称' in n), None)
        if ci_d is None:
            continue
        for r in rows:
            v = r[ci_d] if ci_d < len(r) else None
            if v:
                nm = str(r[ci_n]) if (ci_n is not None and ci_n < len(r) and r[ci_n]) else name
                return str(v)[:10], nm
    return '', name


def check_wind_maturity(retired, today, only):
    """Wind 到期日体检（cn/reits/money）。返回 found 字典。

    2026-10-06：改为**批次并发预取 + 保序应用**（ThreadPoolExecutor，SX_WIND_WORKERS 默认 6）。
    原为逐只串行 + 每只 sleep 0.4s，约 227 只 → 实测 >18 分钟（Wind 单次 ~4.5s）；并发后约 3 分钟。
    单只异常按「取不到」处理（空到期日 = 保留），绝不误杀。"""
    lists = [(k, f, lb) for (k, f, lb) in WIND_LISTS if (only is None or k in only)]
    if not lists:
        return {}
    print('  — Wind 到期日体检：%s（判据：到期日 ≤ %s）' % (
        '、'.join(lb for _, _, lb in lists), today), flush=True)

    # 组装待查清单（跳过已停用），跨清单合并后一次并发拉取
    jobs = []  # (label, code, name)
    for key, fname, label in lists:
        rows = load_json(os.path.join(DATA_DIR, fname), []) or []
        codes = [x for x in rows if isinstance(x, dict) and x.get('code')]
        print('    %s：%d 只' % (label, len(codes)), flush=True)
        for x in codes:
            code = x.get('code')
            if code in retired:
                continue
            jobs.append((label, code, x.get('name') or ''))

    found = {}
    if not jobs:
        return found
    print('    → 并发 %d 路拉取 %d 只的「基金到期日」…' % (WORKERS, len(jobs)), flush=True)

    def _probe(job):
        label, code, name = job
        try:
            mat, nm = fetch_maturity(code, name)
        except Exception:
            mat, nm = '', name
        return label, code, name, mat, nm

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for label, code, name, mat, nm in ex.map(_probe, jobs):  # map 保序
            if mat and mat <= today:
                found[code] = {
                    'name': nm or name or '',
                    'lists': [label],
                    'maturityDate': mat,
                    'retiredDate': today,
                    'reason': '基金到期日已过（%s）→ 已结束/清盘' % mat,
                    'source': 'wind',
                }
                print('      ⚠ 命中：%s %s 到期日 %s → 拟移出' % (code, nm or '', mat), flush=True)
    return found


def main():
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    only = None
    if '--only' in sys.argv:
        only = set(x.strip() for x in sys.argv[sys.argv.index('--only') + 1].split(',') if x.strip())

    obj = load_json(RETIRED_PATH, {'domain': 'retired', 'retired': {}})
    retired = obj.get('retired') or {}
    today = datetime.date.today().isoformat()

    print('[生命周期体检] [%s]' % ts(), flush=True)
    found = {}

    # ① 港交所ETF（中央数据库名单；后备 aastocks）
    if only is None or 'hk' in only:
        found.update(check_hk_etf(retired, today))
    else:
        print('  — 港交所红利ETF：本次跳过（--only 未含 hk）', flush=True)

    # ② 境内ETF / REITs / 货币基金（Wind 到期日；约 28 天节流）
    if only is None or (only & {'cn', 'reits', 'money'}):
        last = obj.get('lastWindRun') or ''
        throttled = False
        if last and not force:
            try:
                d = datetime.date.fromisoformat(str(last)[:10])
                if (datetime.date.today() - d).days < DAYS:
                    print('  — Wind 到期日体检：距上次 %s 仅 %d 天（< %d）→ 跳过（--force 可强制）'
                          % (last, (datetime.date.today() - d).days, DAYS), flush=True)
                    throttled = True
            except Exception:
                pass
        if not throttled:
            found.update(check_wind_maturity(retired, today, only))
            obj['lastWindRun'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    else:
        print('  — Wind 到期日体检：本次跳过（--only 未含 cn/reits/money）', flush=True)

    print('  合计命中 %d 只' % len(found), flush=True)
    if dry:
        print('[DRY-RUN] 未写入。确认无误后去掉 --dry-run 正式运行。', flush=True)
        return

    retired.update(found)
    obj['domain'] = 'retired'
    obj['schema'] = 'retired: { <code>: {name, lists[], maturityDate, retiredDate, reason, source} }'
    obj.setdefault('note', 'excel-exit 机制 B · 停用名单：已清盘/退市/结束标的。港交所ETF 由 aastocks 比对、'
                           '境内ETF/REITs/货币基金 由 Wind「基金到期日」判定；build_lists.py 重建时跳过。删条目即恢复。')
    obj['updatedAt'] = today
    obj['retired'] = dict(sorted(retired.items()))
    save_json(RETIRED_PATH, obj)
    print('[OK] 已更新 %s（累计停用 %d 只）' % (RETIRED_PATH, len(obj['retired'])), flush=True)


if __name__ == '__main__':
    main()

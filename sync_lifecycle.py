#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基金「生命周期」体检 · 清单「出」机制（2026-10-06 / 清单进出机制 2026-10-07）

四类清单的「出」= 基金已结束（清盘/退市/终止），写入 data/curation/_retired.json，
由 build_lists.py 重建时跳过（历史数据不删，仅移出展示清单；删条目即恢复）。

判据（2026-10-07：清盘改读中央数据库导出名单；仅 REITs 仍用 Wind）：
  ① 清盘名单（中央数据库导出 exports/common/fund-liquidated.json）——
     境内红利ETF(cnEtfData) / 货币基金(moneyFundData) / 月月分红(etfData + fundData)；
     **按代码前 6 位比对**：命中 ⇒ 已清盘 ⇒ **立即移出**（reason="已清盘（中央数据库）"、
     source="central-db-liquidated"）。文件缺失 ⇒ 该项跳过并打印说明（绝不误判）。
  ② 港交所红利ETF —— 用中央数据库导出的「港交所上市 ETF」全量名单比对：
     数据源 exports/common/hk-etf-list.json；缺失时**回退** data/curation/_hk_etf_universe.json
     （现状；再缺则退 aastocks）。标的若**不在**该名单 ⇒ 视为退市/终止 ⇒ 停用。
  ③ REITs —— 仍用 Wind「基金到期日」：空（常青）或**未来**（合约存续期）⇒ 保留；
     **≤ 今天 ⇒ 已结束 ⇒ 停用**（reason 保留「到期日已过」语义）。仅 REITs 使用；
     约 28 天节流（SX_LIFECYCLE_DAYS）。⚠️ 不可按「非空即出」——REIT 运作中亦有未来到期日。

安全阀 + 观察状态（2026-10-07）：
  ① 清盘名单命中 ⇒ **立即移出**；
  ② 其它判据（REITs 到期日已过、港股不在名单）⇒ 需**连续两次运行都命中**才真正移出，
     第一次只在「清单变动」里标「待观察」。
  观察计数与 lastWindRun 存**仓库根 .lifecycle_state.json**（data/ 会被测试回滚，故迁出）：
     {"observe": {"<code>": {"list","reason","firstSeen","hits"}}, "lastWindRun": "YYYY-MM-DD HH:MM"}

清单变动（2026-10-07）：所有自动「进/出/待观察」写入仓库根 .list_changes.json
  （load-merge-save；事件带 date+at；不同天旧事件保留，报告只取当天）。

用法：
  python3 sync_lifecycle.py [--dry-run] [--force] [--only hk,cn,money,etf,fund,reits]
      --dry-run   只报告不写入
      --force     忽略 REITs Wind 部分的时间节流，强制重跑
      --only ...  只跑指定清单（hk=港ETF；cn/money/etf/fund=清盘名单；reits=Wind 到期日）
"""
import io, json, os, re, subprocess, sys, time, datetime, tempfile
from concurrent.futures import ThreadPoolExecutor

import lifecycle_common as lc  # 清单进出机制 · 共享工具（中央库导出读取 / 状态 / 变动日志）

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
CURATION_DIR = os.path.join(DATA_DIR, 'curation')
RETIRED_PATH = os.path.join(CURATION_DIR, '_retired.json')

WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
import wind_client  # 统一 Wind 客户端（阶段 0：计数；规范见 docs/data-governance/update-redesign.md）
CLI = wind_client.CLI  # 经额度守卫包装器，并统一计数

AASTOCKS_URL = 'https://www.aastocks.com/en/stocks/etf/default.aspx'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

# 港交所上市 ETF 全量名单（**本地冻结副本**，中央库导出文件的回退；由会话内 MCP 刷新）
HK_UNIVERSE_PATH = os.path.join(CURATION_DIR, '_hk_etf_universe.json')

SLEEP = float(os.environ.get('SX_LIFECYCLE_SLEEP', '0.4'))  # 保留兼容（并发化后不再逐只 sleep）
DAYS = int(os.environ.get('SX_LIFECYCLE_DAYS', '28'))
# Wind「到期日」并发拉取路数（2026-10-06：原逐只串行 + 0.4s sleep，约 227 只 → >18min；并发后约 3min）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '6')))

# ① 清盘名单判据（中央库 fund-liquidated.json）
#    key -> (站点数据文件, 中文名, 清单变动 list 名)
LIQUIDATED_LISTS = [
    ('cn',    'cnEtfData.json',     '境内红利ETF',  'cnEtf'),
    ('money', 'moneyFundData.json', '货币基金',     'money'),
    ('etf',   'etfData.json',       '月月分红ETF',  'etf'),
    ('fund',  'fundData.json',      '月月分红基金', 'fund'),
]
# ③ Wind「基金到期日」判据：**仅 REITs**（其余清盘改走中央库名单）
WIND_LISTS = [
    ('reits', 'reitsData.json', 'REITs', 'reits'),
]
HK_ETF = ('hkEtfData.json', '港交所红利ETF', 'hkEtf')


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
            r = wind_client.run(
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


# ── 判据 ①：清盘名单（中央数据库；立即移出）─────────────────────────────────
def check_liquidated(retired, today):
    """清盘名单命中 ⇒ 立即移出。返回 (found, events)。文件缺失 ⇒ 跳过（打印说明）。"""
    liquid = lc.load_liquidated_codes()
    if not liquid:
        print('    [i] 未找到中央数据库清盘名单（%s）→ 本次跳过清盘核对'
              % os.path.join('exports/common', lc.CENTRAL_FUND_LIQUIDATED), flush=True)
        return {}, []
    set6, desc = liquid
    print('    判据：中央数据库「基金清盘名单」%d 个代码（前6位比对%s）'
          % (len(set6), ('，导出 %s' % desc) if desc else ''), flush=True)

    found, events = {}, []
    for key, fname, label, lname in LIQUIDATED_LISTS:
        rows = load_json(os.path.join(DATA_DIR, fname), []) or []
        codes = [x for x in rows if isinstance(x, dict) and x.get('code')]
        hit = 0
        for x in codes:
            code = x['code']
            if code in retired:
                continue
            c6 = lc.code6(code)
            if c6 and c6 in set6:
                found[code] = {
                    'name': x.get('name') or '',
                    'lists': [label],
                    'maturityDate': '',
                    'retiredDate': today,
                    'reason': '已清盘（中央数据库）',
                    'source': 'central-db-liquidated',
                    'list': lname,
                }
                events.append({'action': 'retire', 'list': lname, 'code': code,
                               'name': x.get('name') or '',
                               'reason': '已清盘（中央数据库）',
                               'source': 'central-db-liquidated'})
                hit += 1
                print('      ⚠ 命中：%s %s → 立即移出（清盘名单）' % (code, x.get('name') or ''), flush=True)
        print('    — %s：%d 只（命中 %d）' % (label, len(codes), hit), flush=True)
    return found, events


# ── 判据 ②：港交所上市 ETF 名单（中央库导出；回退本地副本；再退 aastocks）──
def load_hk_universe():
    """本地冻结副本 _hk_etf_universe.json 的 codes（站点代码形式，如 '3070.HK'）。
    返回 (set, fetchedAt)；缺失/异常/不足 100 只返回 None。"""
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
    """港交所红利ETF「出」：标的不在（中央库导出 / 本地副本 / aastocks）全量名单 → 停用。
    需连续两次命中才真正移出（安全阀），故此处只返回命中集合。"""
    fname, label, lname = HK_ETF
    rows = load_json(os.path.join(DATA_DIR, fname), []) or []
    codes = [x for x in rows if isinstance(x, dict) and x.get('code')]
    print('  — %s：%d 只' % (label, len(codes)), flush=True)

    src = reason = ''
    universe = set()
    present = None

    central = lc.load_central_hk_codes()
    if central:
        universe, fetched = central
        src = 'central-db'
        reason = '中央数据库「港交所上市ETF」名单中已不存在（退市/终止）'
        _ukeys = {lc.hk_num(c) for c in universe}
        print('    判据：中央库导出「港交所上市ETF」名单 %d 只（导出 %s，%s）'
              % (len(universe), fetched or '—', lc.CENTRAL_HK_LIST), flush=True)

        def present(code):
            return lc.hk_num(code) in _ukeys
    else:
        print('    [i] 未找到中央库导出名单（%s）→ 回退本地副本 %s'
              % (lc.CENTRAL_HK_LIST, os.path.basename(HK_UNIVERSE_PATH)), flush=True)
        uni = load_hk_universe()
        if uni:
            universe, fetched = uni
            src = 'central-db'
            reason = '中央数据库「港交所上市ETF」名单中已不存在（退市/终止）'
            _ukeys = {lc.hk_num(c) for c in universe}
            print('    判据：本地冻结「港交所上市ETF」名单 %d 只（导出日 %s）'
                  % (len(universe), fetched or '—'), flush=True)

            def present(code):
                return lc.hk_num(code) in _ukeys
        else:
            print('    [i] 本地副本缺失/异常 → 退回 aastocks 抓取', flush=True)
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
            'list': lname,
        }
        print('    ⚠ 命中：%s %s → 待观察（%s 已无此代码，连续两次命中才移出）'
              % (code, x.get('name') or '', src), flush=True)
    return found


# ── 判据 ③：Wind「基金到期日」（仅 REITs）───────────────────────────────────
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
    """Wind 到期日体检（仅 REITs）。返回 found 字典。

    **批次并发预取 + 保序应用**（ThreadPoolExecutor，SX_WIND_WORKERS 默认 6）。
    单只异常按「取不到」处理（空到期日 = 保留），绝不误杀。
    需连续两次命中才真正移出（安全阀），故此处只返回命中集合。
    """
    lists = [(k, f, lb, ln) for (k, f, lb, ln) in WIND_LISTS if (only is None or k in only)]
    if not lists:
        return {}
    print('  — Wind 到期日体检：%s（判据：到期日 ≤ %s）' % (
        '、'.join(lb for _, _, lb, _ in lists), today), flush=True)

    jobs = []  # (label, lname, code, name)
    for key, fname, label, lname in lists:
        rows = load_json(os.path.join(DATA_DIR, fname), []) or []
        codes = [x for x in rows if isinstance(x, dict) and x.get('code')]
        print('    %s：%d 只' % (label, len(codes)), flush=True)
        for x in codes:
            code = x.get('code')
            if code in retired:
                continue
            jobs.append((label, lname, code, x.get('name') or ''))

    found = {}
    if not jobs:
        return found
    print('    → 并发 %d 路拉取 %d 只的「基金到期日」…' % (WORKERS, len(jobs)), flush=True)

    def _probe(job):
        label, lname, code, name = job
        try:
            mat, nm = fetch_maturity(code, name)
        except Exception:
            mat, nm = '', name
        return label, lname, code, name, mat, nm

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for label, lname, code, name, mat, nm in ex.map(_probe, jobs):  # map 保序
            if mat and mat <= today:
                found[code] = {
                    'name': nm or name or '',
                    'lists': [label],
                    'maturityDate': mat,
                    'retiredDate': today,
                    'reason': '基金到期日已过（%s）→ 已结束/清盘' % mat,
                    'source': 'wind',
                    'list': lname,
                }
                print('      ⚠ 命中：%s %s 到期日 %s → 待观察（连续两次命中才移出）'
                      % (code, nm or '', mat), flush=True)
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

    state = lc.load_lifecycle_state()
    observe = state.get('observe') or {}

    print('[生命周期体检] [%s]' % ts(), flush=True)
    immediate, needs_confirm, events = {}, {}, []   # immediate=立即移出；needs_confirm=需连续两次
    observed_lists = set()                          # 本次实际评估过的「待观察」清单

    # ① 清盘名单（中央数据库；立即移出）
    if only is None or (only & {'cn', 'money', 'etf', 'fund'}):
        _f, _ev = check_liquidated(retired, today)
        immediate.update(_f)
        events += _ev
    else:
        print('  — 清盘名单核对：本次跳过（--only 未含 cn/money/etf/fund）', flush=True)

    # ② 港交所红利ETF（中央库名单；需连续两次命中）
    if only is None or 'hk' in only:
        needs_confirm.update(check_hk_etf(retired, today))
        observed_lists.add('hkEtf')
    else:
        print('  — 港交所红利ETF：本次跳过（--only 未含 hk）', flush=True)

    # ③ REITs（Wind 到期日；需连续两次命中；约 28 天节流）
    state_last_set = False
    if only is None or 'reits' in only:
        last = state.get('lastWindRun') or obj.get('lastWindRun') or ''   # 兼容从 _retired.json 迁移
        throttled = False
        if last and not force:
            try:
                d = datetime.date.fromisoformat(str(last)[:10])
                if (datetime.date.today() - d).days < DAYS:
                    print('  — REITs Wind 到期日体检：距上次 %s 仅 %d 天（< %d）→ 跳过（--force 可强制）'
                          % (last, (datetime.date.today() - d).days, DAYS), flush=True)
                    throttled = True
            except Exception:
                pass
        if not throttled:
            needs_confirm.update(check_wind_maturity(retired, today, only))
            observed_lists.add('reits')
            state_last_set = True
    else:
        print('  — REITs Wind 到期日体检：本次跳过（--only 未含 reits）', flush=True)

    # ── 安全阀 + 观察门控 ────────────────────────────────────────────────
    #   清盘命中 → 立即移出；其它判据 → 首次标「待观察」，连续两次命中才移出。
    #   仅重建「本次评估过的清单」的观察态，未评估清单的旧观察原样保留（避免误清）。
    to_retire = dict(immediate)
    new_observe = {c: v for c, v in observe.items()
                   if isinstance(v, dict) and v.get('list') not in observed_lists}

    for code, entry in needs_confirm.items():
        lname = entry.get('list', '')
        prev = observe.get(code)
        if prev:
            hits = int(prev.get('hits', 1)) + 1
            if hits >= 2:
                to_retire[code] = entry
                events.append({'action': 'retire', 'list': lname, 'code': code,
                               'name': entry.get('name') or '',
                               'reason': entry.get('reason', ''),
                               'source': entry.get('source', '')})
                print('    ✅ 二次命中 → 移出：%s %s（%s）'
                      % (code, entry.get('name') or '', entry.get('reason', '')), flush=True)
                continue
            # hits<2 不会发生（prev 存在即 hits≥1）；保守处理：继续观察
            new_observe[code] = {'list': lname, 'reason': entry.get('reason', ''),
                                 'firstSeen': prev.get('firstSeen') or today, 'hits': hits}
            continue
        new_observe[code] = {'list': lname, 'reason': entry.get('reason', ''),
                             'firstSeen': today, 'hits': 1}
        events.append({'action': 'observe', 'list': lname, 'code': code,
                       'name': entry.get('name') or '',
                       'reason': entry.get('reason', ''),
                       'source': entry.get('source', '')})
        print('    👀 首次命中 → 待观察：%s %s（%s；下次再命中才移出）'
              % (code, entry.get('name') or '', entry.get('reason', '')), flush=True)

    # 已不再命中的旧观察 → 清除（自动恢复）；已被移出的 code 也一并移除观察
    for code, v in observe.items():
        if isinstance(v, dict) and v.get('list') in observed_lists \
                and code not in new_observe and code not in to_retire:
            print('    ↩ 已恢复（不再命中）→ 取消观察：%s %s'
                  % (code, v.get('reason', '')), flush=True)
    for code in list(to_retire.keys()):
        new_observe.pop(code, None)

    print('  命中 %d 只（立即移出 %d、待观察/二次移出 %d）'
          % (len(immediate) + len(needs_confirm), len(immediate), len(needs_confirm)), flush=True)

    if dry:
        print('[DRY-RUN] 未写入。确认无误后去掉 --dry-run 正式运行。', flush=True)
        return

    # 写入 _retired.json（lastWindRun 已迁出到 .lifecycle_state.json，此处不再保留该字段）
    retired.update(to_retire)
    obj.pop('lastWindRun', None)
    obj['domain'] = 'retired'
    obj['schema'] = 'retired: { <code>: {name, lists[], maturityDate, retiredDate, reason, source} }'
    obj.setdefault('note', 'excel-exit 机制 B · 停用名单：已清盘/退市/结束标的。'
                           '清盘（境内红利ETF/货币基金/月月分红）由中央数据库 fund-liquidated.json 判定；'
                           '港交所ETF 由中央库「港交所上市ETF」名单比对；REITs 由 Wind「基金到期日」判定。'
                           'build_lists.py 重建时跳过。删条目即恢复。')
    obj['updatedAt'] = today
    obj['retired'] = dict(sorted(retired.items()))
    save_json(RETIRED_PATH, obj)

    # 写入观察状态（仓库根 .lifecycle_state.json）
    state['observe'] = dict(sorted(new_observe.items()))
    if state_last_set:
        state['lastWindRun'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    lc.save_lifecycle_state(state)

    # 写入清单变动（仓库根 .list_changes.json；load-merge-save）
    n_added = lc.record_list_changes(events)

    print('[OK] 已更新 %s（累计停用 %d 只）；观察中 %d 只；本次变动事件 %d 条'
          % (RETIRED_PATH, len(obj['retired']), len(new_observe), n_added), flush=True)


if __name__ == '__main__':
    main()

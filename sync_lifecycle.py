#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基金「生命周期」体检 · 已清盘/结束标的的停用（excel-exit 机制 B，2026-10-06）

用户口径（2026-10-06）：
  境内红利ETF / 港交所红利ETF / REITs / 货币基金 这四类清单的「出」= 基金已结束（清盘）。
  判据 = Wind「基金到期日」：
    - 空         → 正常（ETF/货基常青）→ 保留
    - 未来日期   → 仍在存续期（如 REIT 的合约存续期）→ 保留
    - ≤ 今天     → 已到期 / 已结束 → 移出清单
  ⚠️ 不能只看「非空」——公募 REITs 即使仍在运作也有**未来的**「到期日」（成立日 + 存续期）。
  实测：180101.SZ 到期日 2071-06-07、508000.SH 2056-06-07（均在存续期内）。

停用名单 data/curation/_retired.json：
  - 记录 {code, name, lists, maturityDate, retiredDate, reason}，可追溯、可回滚（删条目即恢复）；
  - build_lists.py 重建时读取并跳过这些 code（**历史数据不删**，只移出展示清单）。

频率：清盘罕见 → 默认距上次 > SX_LIFECYCLE_DAYS（默认 28）天才重跑，省 Wind 配额；--force 强制。
已知限制：港交所 ETF 的「基金到期日」Wind 未返回（仅含「存续期」），故 hk 侧实际不会命中。

用法：
  python3 sync_lifecycle.py [--dry-run] [--force] [--only cn,hk,reits,money]
"""
import io, json, os, subprocess, sys, time, datetime, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
CURATION_DIR = os.path.join(DATA_DIR, 'curation')
RETIRED_PATH = os.path.join(CURATION_DIR, '_retired.json')

WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')

SLEEP = float(os.environ.get('SX_LIFECYCLE_SLEEP', '0.4'))
DAYS = int(os.environ.get('SX_LIFECYCLE_DAYS', '28'))

# 参与「出」体检的四类清单：key -> (站点数据文件, 中文名)
LISTS = [
    ('cn',    'cnEtfData.json',     '境内红利ETF'),
    ('hk',    'hkEtfData.json',     '港交所红利ETF'),
    ('reits', 'reitsData.json',     'REITs'),
    ('money', 'moneyFundData.json', '货币基金'),
]


def ts():
    return time.strftime('%H:%M:%S')


def _wind_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def call_wind_tbl(tool, question):
    """Wind 查询，返回 [(columns, rows), ...]（3 次重试 + 6s 退避 + 代理变量清理）。失败返回 []。"""
    for _ in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'fund_data', tool,
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=120, env=_wind_env(), cwd=WIND_SKILL)
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


def fetch_maturity(code, name):
    """查「基金到期日」。返回 (maturity_date_str|'', std_name)。取不到 → ('', name)。"""
    cols_rows = call_wind_tbl('get_fund_info', '{} {} 基金到期日 证券简称'.format(code, name))
    for cols, rows in cols_rows:
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


def main():
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    only = None
    if '--only' in sys.argv:
        only = set(x.strip() for x in sys.argv[sys.argv.index('--only') + 1].split(',') if x.strip())

    obj = load_json(RETIRED_PATH, {'domain': 'retired', 'retired': {}})
    retired = obj.get('retired') or {}

    today = datetime.date.today()
    last = obj.get('lastRun') or ''
    if last and not force:
        try:
            d = datetime.date.fromisoformat(str(last)[:10])
            if (today - d).days < DAYS:
                print('[生命周期体检] 距上次 %s 仅 %d 天（< %d）→ 跳过（清盘罕见，省 Wind 配额）；如需强制 --force'
                      % (last, (today - d).days, DAYS), flush=True)
                return
        except Exception:
            pass

    lists = [(k, f, lb) for (k, f, lb) in LISTS if (only is None or k in only)]
    print('[生命周期体检] [%s] 扫描 %s（判据：基金到期日 ≤ %s 视为已结束）...'
          % (ts(), '、'.join(lb for _, _, lb in lists), today.isoformat()), flush=True)

    found = {}
    checked = 0
    for key, fname, label in lists:
        path = os.path.join(DATA_DIR, fname)
        rows = load_json(path, []) or []
        codes = [x for x in rows if isinstance(x, dict) and x.get('code')]
        print('  — %s：%d 只' % (label, len(codes)), flush=True)
        for x in codes:
            code = x.get('code')
            if code in retired:
                continue                      # 已停用，无需重查
            name = x.get('name') or ''
            mat, nm = fetch_maturity(code, name)
            checked += 1
            time.sleep(SLEEP)
            if mat and mat <= today.isoformat():
                found[code] = {
                    'name': nm or name,
                    'lists': [label],
                    'maturityDate': mat,
                    'retiredDate': today.isoformat(),
                    'reason': '基金到期日已过（%s）→ 已结束/清盘' % mat,
                }
                print('    ⚠ 命中：%s %s  到期日 %s → 拟移出' % (code, nm or name, mat), flush=True)

    print('  扫描 %d 只，命中 %d 只' % (checked, len(found)), flush=True)

    if dry:
        print('[DRY-RUN] 未写入。确认无误后去掉 --dry-run 正式运行。', flush=True)
        return

    retired.update(found)
    obj['domain'] = 'retired'
    obj['schema'] = 'retired: { <code>: {name, lists[], maturityDate, retiredDate, reason} }'
    obj.setdefault('note', 'excel-exit 机制 B · 停用名单：已清盘/结束标的。由 sync_lifecycle.py 维护；build_lists.py 重建时跳过。删条目即恢复。')
    obj['updatedAt'] = today.isoformat()
    obj['lastRun'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    obj['retired'] = dict(sorted(retired.items()))
    save_json(RETIRED_PATH, obj)
    print('[OK] 已更新 %s（累计停用 %d 只）' % (RETIRED_PATH, len(obj['retired'])), flush=True)


if __name__ == '__main__':
    main()

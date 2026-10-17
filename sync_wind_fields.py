#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字段级 Wind 化（2026-08-16 用户确认）
======================================
目标：除「产品列表本身」外，关键静态/数值字段改为随 Wind 变化，逐步摆脱 Excel 快照。

覆盖范围：
1. indexData.fundCount  —— 挂钩产品数（Wind get_index_fundamentals）
2. cnEtfData 7 字段      —— 成立日/上市日/费率/2026分红次数/规模/份额/持有人数
3. etfData 分红字段      —— 总次数/2026次数/价格/收益率/公司/成立日/费率/跟踪指数/规模
4. fundData 场外字段     —— 2026次数/净值/规模/收益率/公司/成立日/费率/跟踪指数
5. hkEtfData 字段        —— 规模/费率/跟踪指数/成立日（列表与名称不动）

不覆盖（口径存疑，保留 Excel）：
- fundData 每份分红金额类（annualDivAmt/monthlyDivAmt/divTotalAmt/cumDiv）
- etfData 的 cumDiv/divTotalAmt 若 Wind 无匹配列则保留

档位（2026-10-17 · backlog B-4 / 跨站总规则 §三 字段分层）：
- `all`（属性/规模层 B+C 层）→ 挂**周更**档；日更不跑。
- `quotes`（A 行情层：月月分红 ETF 最新收盘价、场外基金最新单位净值、近 12 月分红收益率）→ **日更**跑。

境内红利ETF 只取一遍（2026-10-17 · 跨站总规则 §六/§七）：
- `cn` 段先读中央库导出 `exports/dividend/dividend-etf.json`；若中央库 `fund_size_date` 比本地 `sizeDate`
  新，说明资管棱镜本周已取过 → 沿用中央库值、**跳过对应 Wind 调用**；否则本站自取（结果经快照同步回中央库）。

用法: python3 sync_wind_fields.py [all|cn|etf|fund|hk|fc|quotes]
      python3 sync_wind_fields.py cn --dry-run    # 只打印「沿用中央库 / 需自取」的判定，不调 Wind、不写文件
"""
import datetime, io, json, os, subprocess, sys, time, tempfile
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
import wind_client  # 统一 Wind 客户端（阶段 0：计数；规范见 docs/data-governance/update-redesign.md）
import lifecycle_common as lc  # 港股代码 5 位→4 位（hk_wind；Wind 港股查询用 4 位）
CLI = wind_client.CLI  # 经额度守卫包装器，并统一计数
BATCH = 5          # 基金批量查询数量
FC_BATCH = 4       # 指数批量查询数量（4 个/批更稳）
# 并发路数（2026-09-26 提速：批次并发；单批仍 ≤BATCH/FC_BATCH 只、字段数不变，Wind 批量契约不变）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '8')))

# 批间休眠（2026-09-19 优化）：原为 fc=10s / etf=3s / 其余=2s，
# 全量跑一趟仅休眠就 ~5 分钟。Wind 侧有 QPS 限流，call_wind 已带 3 次重试 + 6s 退避，
# 故按「轻查询 1s、重查询(fundCount) 3s」收敛，既不触发限流也大幅缩短总时长。
SLEEP_LIGHT = float(os.environ.get('SX_WF_SLEEP_LIGHT', '1.0'))
SLEEP_HEAVY = float(os.environ.get('SX_WF_SLEEP_HEAVY', '3.0'))


def ts():
    return time.strftime('%H:%M:%S')


def call_wind(question, server='fund_data', tool='get_fund_financials'):
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):
        try:
            r = wind_client.run(
                ['node', CLI, 'call', server, tool,
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=env, cwd=WIND_SKILL)
            if r.returncode != 0:
                time.sleep(6)
                continue
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return []
            inner = json.loads(text)
            return inner.get('data', {}).get('data', []) or []
        except Exception:
            time.sleep(6)
    return []


def _prefetch(queries, server='fund_data', tool='get_fund_financials'):
    """并发预取一批查询，返回与输入同序的结果列表（每项为 call_wind 的返回）。"""
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        return list(ex.map(lambda q: call_wind(q, server, tool), queries))


def load_json(name):
    p = os.path.join(DATA, name)
    if os.path.exists(p):
        return json.load(io.open(p, encoding='utf-8'))
    return []


def save_json(name, data):
    p = os.path.join(DATA, name)
    fd, tmp = tempfile.mkstemp(dir=DATA, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, p)


def num(v):
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def dstr(v):
    if not v:
        return ''
    s = str(v).strip()
    if s[:4].isdigit() and len(s) >= 10:
        if s[4] == '-':
            return s[:10]                    # 已是 yyyy-mm-dd
        return '%s-%s-%s' % (s[:4], s[4:6], s[6:8])   # yyyymmdd
    return s


def colmap(tb):
    m = {}
    for i, c in enumerate(tb.get('columns', [])):
        m[str(c.get('name', ''))] = i
    return m


def fix_n_prefix(n, wind_name):
    """上市临时 N 前缀摘除（2026-08-16 用户要求）：交易所对刚上市产品简称加 N，
    上市后摘除；Wind 证券简称为长期简称（不带 N），若网站简称带 N 而 Wind 不带则摘"""
    if n and wind_name and n.startswith('N') and not wind_name.startswith('N'):
        return n[1:]
    return n


def _rows_by_code(tbs):
    """按 Wind 代码聚合每张表首行"""
    out = {}
    for tb in tbs:
        cm = colmap(tb)
        keys = [k for k in cm if '代码' in k]
        if not keys:
            continue
        ci = cm[keys[0]]
        for r in tb.get('rows', []):
            if len(r) > ci and r[ci]:
                out.setdefault(str(r[ci]), (r, cm))
    return out


def _alias(code):
    """OF→SH/SZ 变体匹配"""
    return (code.replace('.OF', '.SH'), code.replace('.OF', '.SZ'))


# ---------- 中央库（data_center）· 境内红利ETF 只取一遍（2026-10-17）----------
#   资管棱镜的「红利ETF列表及字段」与本项目「境内红利ETF」是同一份数据：周末谁先跑谁从 Wind 取数并写入中央库，
#   后跑的站从中央库读（跨站总规则 §六「只认一个来源」、§七 第 3 条）。站点环境不装 duckdb → 只读中央库导出。
CENTRAL_DIR = os.environ.get('SX_DATA_CENTER') or os.path.normpath(os.path.join(BASE, '..', '..', 'data_center'))


def _central_dividend_etf():
    """读中央库导出 exports/dividend/dividend-etf.json → {security_id: {列名: 值}}；缺失/损坏 → {}。"""
    p = os.path.join(CENTRAL_DIR, 'exports', 'dividend', 'dividend-etf.json')
    o = None
    for i in range(6):                      # 坚果云同步中文件会被短暂锁住（Errno 35），稍等重试
        try:
            with io.open(p, encoding='utf-8') as f:
                o = json.load(f)
            break
        except OSError:
            if i == 5:
                raise
            time.sleep(5)
        except Exception as e:
            print('  [中央库] 读取 dividend-etf.json 失败（%s）→ 本次全部自取' % e)
            return {}
    keys = [str(c.get('key', '')) for c in (o or {}).get('columns', [])]
    if 'security_id' not in keys:
        print('  [中央库] dividend-etf.json 结构异常（无 security_id 列）→ 本次全部自取')
        return {}
    out = {}
    for r in (o.get('rows') or []):
        if len(r) != len(keys):
            continue
        d = dict(zip(keys, r))
        if d.get('security_id'):
            out[str(d['security_id'])] = d
    return out


def _apply_central_cn(x, c):
    """用中央库导出值更新一只境内红利ETF（沿用资管棱镜本周的取数结果）。返回变更字段名列表。"""
    chg = []

    def put(k, v):
        if v is not None and x.get(k) != v:
            x[k] = v
            chg.append(k)

    _sz = num(c.get('fund_size'))
    if _sz is not None:
        put('size', round(_sz, 2))
        _d = str(c.get('fund_size_date') or '')[:10]
        if _d:
            x['sizeDate'] = _d
    _fee = num(c.get('mgmt_fee'))            # 中央库为小数（0.005 = 0.50%）
    if _fee is not None and _fee > 0:
        put('feeNum', round(_fee, 4))
        put('fee', '{:.2f}%'.format(_fee * 100))
    put('listedDate', str(c.get('inception_date') or '')[:10] or None)
    put('listedMarketDate', str(c.get('list_date') or '')[:10] or None)
    _fs = num(c.get('floor_shares'))         # 场内份额（亿份）：中央库导出补齐该列后才会写入
    if _fs is not None and 0 < _fs <= 1000:
        put('shares', round(_fs, 2))
    # 管理人：中央库 company 多为简称，本地已是全称 → 只在本地为空时补（避免把全称降级成简称）
    if not (x.get('manager') or '').strip() and c.get('company'):
        put('manager', str(c['company']).strip())
    return chg


# 单位换算 + 规模列名候选（2026-10-10 · backlog B-6）
#   ① 列名：Wind 对「基金规模」在不同批次返回不同列名（实测同一天：`基金规模合计` /
#      `最新基金规模合计` / `上市基金规模_WIND计算`），原实现只认 `基金规模合计` → 其它批次取空、规模漏更新。
#   ② 单位：同名列的 unit 在不同批次还不一致（`亿元` / `百万元`）→ 原实现硬编码按亿元写，百万元批次会放大 100 倍。
#   现：多候选列名取第一个命中的，并按该列返回的 unit 归一到亿元；**unit 缺失/未知 → 不写**（宁可保留旧值）。
_SIZE_CANDS = ('基金规模合计', '最新基金规模合计', '上市基金规模_WIND计算')
_SIZE_TO_YI = {'亿元': 1.0, '亿': 1.0, '百万元': 0.01, '千万元': 0.1, '万元': 1e-4, '千元': 1e-5, '元': 1e-8}


def _units_of(tbs):
    """聚合各表「列名 → unit」（2026-10-10 · B-6）。"""
    m = {}
    for tb in tbs:
        for c in tb.get('columns', []):
            u = c.get('unit')
            if u:
                m.setdefault(str(c.get('name', '')), str(u).strip())
    return m



def _index_yield_map():
    """indexData → {code: yieldNum}（跟踪指数股息率，2026-08-16 用户确认口径）"""
    m = {}
    try:
        for x in load_json('indexData.json'):
            if x.get('code') and x.get('yieldNum'):
                m[x['code']] = x['yieldNum']
    except Exception:
        pass
    return m


def _index_name_map():
    """indexData → {code: name}（跟踪指数名称）。
    ETF 的 trackName 必须与站内指数库名称一致，以便与指数信息打通（2026-10-05 用户要求）：
    只要 trackCode 命中指数库，trackName 一律取指数库规范名，不采用 Wind 的措辞变体。"""
    m = {}
    try:
        for x in load_json('indexData.json'):
            if x.get('code') and x.get('name'):
                m[x['code']] = x['name']
    except Exception:
        pass
    return m


def _extend_yield_map(iy, todo, max_batch=8):
    """对 trackCode 不在 indexData 的，从 Wind 查指数股息率兜底（2026-08-16 排查补漏）"""
    miss = sorted({x.get('trackCode') for x in todo
                   if x.get('trackCode') and x.get('trackCode') not in iy})
    if not miss:
        return iy
    for i in range(0, len(miss), max_batch):
        batch = miss[i:i + max_batch]
        q = '；'.join('%s 的股息率' % c for c in batch)
        for tb in call_wind(q, 'index_data', 'get_index_fundamentals'):
            cm = colmap(tb)
            ci = cm.get('Wind代码', 0)
            yi_key = next((k for k in cm if '股息率' in k), None)
            if yi_key is None:
                continue
            yi = cm[yi_key]   # colmap 返回 {列名:索引}，必须取索引（2026-08-17 修复 TypeError）
            for r in tb.get('rows', []):
                if len(r) > max(ci, yi) and r[ci] and num(r[yi]) is not None:
                    v = num(r[yi])
                    if 0 < abs(v) < 1:
                        v = v * 100   # Wind 股息率返回小数(0.0235=2.35%)，站点约定百分数口径（2026-08-17）
                    iy[str(r[ci])] = v
        print('  [%s] 指数股息率兜底 批次 %d/%d' % (ts(), i // max_batch + 1,
              (len(miss) + max_batch - 1) // max_batch), flush=True)
        time.sleep(SLEEP_LIGHT)
    return iy


# ============ 1. indexData.fundCount ============
def update_fund_count():
    d = load_json('indexData.json')
    todo = [x for x in d if x.get('code')]
    updated = 0
    batches = [todo[i:i + FC_BATCH] for i in range(0, len(todo), FC_BATCH)]
    queries = ['；'.join('跟踪指数 %s 的基金产品数量' % x['name'] for x in b) for b in batches]
    results = _prefetch(queries, 'index_data', 'get_index_fundamentals')
    for bi, (batch, tbs) in enumerate(zip(batches, results)):
        found = {}
        for tb in tbs:
            cm = colmap(tb)
            for col in cm:
                if '基金数量' in col and '跟踪' in col:
                    # 列名含指数名（"跟踪X的基金数量"）→ 精确对应
                    idx_name = __import__('re').sub(r'^跟踪(指数)?', '', col).replace('的基金数量', '').strip()
                    rows = tb.get('rows', [])
                    v = num(rows[0][0]) if rows and rows[0] else None
                    if idx_name and v is not None:
                        found[idx_name] = int(v)
        for x in batch:
            v = found.get(x['name'])
            if v is None:
                # 兜底：唯一候选
                cand = [k for k in found if k in (x['name'], x.get('fullname'))]
                v = found.get(cand[0]) if len(cand) == 1 else None
            if v is not None and x.get('fundCount') != v:
                x['fundCount'] = v
                updated += 1
                print('  [OK] %s fundCount=%d' % (x['name'], v))
        print('  [%s] fundCount 批次 %d/%d（已更新 %d）' % (ts(), bi + 1,
              len(batches), updated), flush=True)
    save_json('indexData.json', d)
    print('fundCount 完成: %d 个指数更新' % updated)
    return updated


# ============ 2. cnEtfData ============
def update_cn_etf(dry_run=False):
    d = load_json('cnEtfData.json')
    todo0 = [x for x in d if x.get('code')]
    updated = 0
    _iname = _index_name_map()   # trackCode → 站内指数规范名（ETF.trackName 须与之对齐，2026-10-05）

    # ① 先查中央库（2026-10-17）：资管棱镜本周已取过（fund_size_date 比本地 sizeDate 新）→ 沿用其值、跳过 Wind；
    #    中央库不够新（或个别代码缺，如新上市 ETF）→ 本站自取，取到后经快照同步回中央库。
    central = _central_dividend_etf()
    todo, from_central = [], []
    for x in todo0:
        c = central.get(x['code'])
        cdate = str((c or {}).get('fund_size_date') or '')[:10]
        if c and num(c.get('fund_size')) is not None and cdate > str(x.get('sizeDate') or '')[:10]:
            from_central.append(x)
        else:
            todo.append(x)
    n_calls_all = -(-len(todo0) // BATCH) if todo0 else 0
    n_calls_wind = -(-len(todo) // BATCH) if todo else 0
    if from_central:
        print('  [中央库] 沿用资管棱镜本周取数 %d 只（省 %d 次 Wind 调用）；本站自取 %d 只'
              % (len(from_central), n_calls_all - n_calls_wind, len(todo)))
    else:
        print('  [中央库] 无可用更新（中央库未覆盖 / 不如本地新）→ 本站自取全部 %d 只' % len(todo))
    for x in from_central:
        chg = _apply_central_cn(x, central.get(x['code']) or {})
        if chg:
            updated += 1
            print('  [中央库] %s 沿用（%s）' % (x['code'], ','.join(chg)))

    if dry_run:
        print('[dry-run] cnEtfData：沿用中央库 %d 只 / 需自取 %d 只（本站将发起 %d 次 Wind）；未写入'
              % (len(from_central), len(todo), n_calls_wind))
        return len(from_central)

    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    queries = [' '.join('%s %s' % (x['code'], x['name']) for x in b) +
               ' 这些基金的成立日期 上市日期 管理费率 基金规模合计 基金份额 开放式基金认购户数 2026年分红次数'
               for b in batches]
    results = _prefetch(queries)
    for bi, (batch, tbs) in enumerate(zip(batches, results)):
        by_code = _rows_by_code(tbs)
        u_by = _units_of(tbs)           # 列名 → unit（2026-10-10 · B-6 单位归一）
        for x in batch:
            hit = by_code.get(x['code'])
            if not hit:
                for a in _alias(x['code']):
                    if a in by_code:
                        hit = by_code[a]
                        break
            if not hit:
                print('  [—] %s 无数据' % x['code'])
                continue
            row, cm = hit
            chg = 0
            def upd(k, v):
                nonlocal chg
                if v is not None and x.get(k) != v:
                    x[k] = v
                    chg += 1
            def gv(c):
                return row[cm[c]] if c in cm and len(row) > cm[c] else None
            nn = fix_n_prefix(x.get('name') or '', str(gv('证券简称')).strip() if '证券简称' in cm else '')
            if nn != x.get('name'):
                x['name'] = nn
                chg += 1
                print('  [N] %s 简称摘除N → %s' % (x['code'], nn))
            upd('listedDate', dstr(gv('基金成立日')) or None)
            upd('listedMarketDate', dstr(gv('上市日期')) or None)
            v = num(gv('管理费率'))
            if v is not None and v > 0:   # 费率 ≤0 视为 Wind 缺值/异常，不写入（防 0.00% 覆盖真实费率，2026-10-05）
                upd('feeNum', round(v / 100.0, 4))
                upd('fee', '{:.2f}%'.format(v))
            _sz = next((n for n in _SIZE_CANDS if n in cm), None)   # 规模列名候选（2026-10-10 · B-6）
            v = num(gv(_sz)) if _sz else None
            if v is not None:
                sc = _SIZE_TO_YI.get(u_by.get(_sz) or '')
                if sc is None:      # 单位未知 → 不写（防单位错放大数据，2026-10-10 · B-6）
                    print('  [!] %s 规模单位未知(%r) → 跳过' % (x['code'], u_by.get(_sz)))
                else:
                    upd('size', round(v * sc, 2))
                    x['sizeDate'] = datetime.date.today().isoformat()   # 规模取数日期（供中央数据库 data_center 区分新旧，2026-09-25 新增）
            v = num(gv('基金份额'))
            if v is not None:
                # 份额：Wind 的 unit 不可靠（都标「份」但数值多为「万份」），沿用 ÷1e4 → 亿份；
                # 再加写前护栏：结果 >1000 亿份视为异常（单位漂移）→ 跳过，防放大 1 万倍（2026-10-10 · B-6）
                _sh = round(v / 1e4, 2)
                if 0 < _sh <= 1000:
                    upd('shares', _sh)
                else:
                    print('  [!] %s 份额异常(%s → %s 亿份) → 跳过' % (x['code'], v, _sh))
            v = num(gv('开放式基金认购户数'))
            if v is not None:
                upd('holders', round(v / 1e4, 2))  # 户 → 万户
            v = num(gv('2026年分红次数'))
            if v is not None:
                upd('divCount', int(v))
            _canon = _iname.get(x.get('trackCode') or '')
            if _canon:
                upd('trackName', _canon)   # 站内指数库优先（ETF 跟踪指数名与指数库打通，2026-10-05）
            if chg:
                updated += 1
                print('  [OK] %s (%d 字段)' % (x['code'], chg))
        print('  [%s] cnEtfData 批次 %d/%d（已更新 %d）' % (ts(), bi + 1,
              len(batches), updated), flush=True)
    save_json('cnEtfData.json', d)
    print('cnEtfData 完成: %d 只更新' % updated)
    return updated


# ============ 3. etfData（月月分红 ETF）============
def update_etf_data():
    d = load_json('etfData.json')
    todo = [x for x in d if x.get('code')]
    updated = 0
    iy = _extend_yield_map(_index_yield_map(), todo)
    _iname = _index_name_map()   # trackCode → 站内指数规范名（ETF.trackName 须与之对齐，2026-10-05）
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    # 拆两次查询（字段 ≤7 个，Wind 才返回；2026-08-16 实测）；两批查询一并并发预取
    q1s = [' '.join('%s %s' % (x['code'], x['name']) for x in b) +
           ' 这些基金的基金成立日 管理费率 基金规模合计 基金份额 跟踪指数名称 基金公司名称' for b in batches]
    q2s = [' '.join('%s %s' % (x['code'], x['name']) for x in b) +
           ' 这些基金的2026年分红次数 2026年分红总额 成立以来累计分红次数 成立以来分红总额 最新收盘价 近12月分红收益率' for b in batches]
    res = _prefetch(q1s + q2s)
    r1, r2 = res[:len(batches)], res[len(batches):]
    for bi, batch in enumerate(batches):
        by_code = _rows_by_code(r1[bi])
        by_code2 = _rows_by_code(r2[bi])
        for x in batch:
            hit = by_code.get(x['code'])
            if not hit:
                for a in _alias(x['code']):
                    if a in by_code:
                        hit = by_code[a]
                        break
            if not hit:
                print('  [—] %s 无数据' % x['code'])
                continue
            row, cm = hit
            row2, cm2 = by_code2.get(x['code'], (None, None)) or by_code2.get(x['code'].replace('.OF', '.SH'), (None, None)) or (None, None)
            chg = 0
            def upd(k, v):
                nonlocal chg
                if v is not None and x.get(k) != v:
                    x[k] = v
                    chg += 1
            def gv(c, r=row, cm_=cm):
                return r[cm_[c]] if cm_ and c in cm_ and len(r) > cm_[c] else None
            nn = fix_n_prefix(x.get('name') or '', str(gv('证券简称')).strip() if '证券简称' in cm else '')
            if nn != x.get('name'):
                x['name'] = nn
                chg += 1
                print('  [N] %s 简称摘除N → %s' % (x['code'], nn))
            upd('listedDate', dstr(gv('基金成立日')) or None)
            upd('fundCompany', str(gv('基金公司名称')).strip() if gv('基金公司名称') else None)
            v = num(gv('管理费率'))
            if v is not None and v > 0:   # 费率 ≤0 视为 Wind 缺值/异常，不写入（2026-10-05）
                upd('feeNum', round(v / 100.0, 4))
                upd('fee', '{:.2f}%'.format(v))
            v = num(gv('基金规模合计'))
            if v is not None:
                upd('fundSize', round(v, 2))
                x['sizeDate'] = datetime.date.today().isoformat()   # 规模取数日期（供 data_center，2026-09-26 新增）
            _tn = str(gv('跟踪指数名称')).strip() if gv('跟踪指数名称') else ''
            _canon = _iname.get(x.get('trackCode') or '')
            upd('trackName', (_canon or _tn) or None)   # 站内指数库优先（ETF 跟踪指数名与指数库打通，2026-10-05）
            if row2 is not None:
                def gv2(c):
                    return row2[cm2[c]] if c in cm2 and len(row2) > cm2[c] else None
                v = num(gv2('2026年分红次数'))
                if v is not None:
                    upd('annualDiv', int(v))
                v = num(gv2('成立以来累计分红次数'))
                if v is not None:
                    upd('totalDiv', int(v))
                v = num(gv2('最新收盘价'))
                if v is not None:
                    upd('price', round(v, 3))
                v = num(gv2('近12月分红收益率'))
                if v is not None:
                    upd('divYieldNum', round(v / 100.0, 4))   # ETF 实际分红收益率（备用口径）
                sh = num(gv('基金份额'))
                div26 = num(gv2('2026年分红总额'))
                divAll = num(gv2('成立以来分红总额'))
                if sh and div26 is not None:
                    per = div26 * 1e8 / (sh * 1e4)      # 元/份（2026 全年）
                    aDiv = x.get('annualDiv') or 0
                    if aDiv:
                        upd('annualDivAmt', round(per / aDiv, 4))
                        upd('monthlyDivAmt', round(per / aDiv / 12, 4))
                    upd('divTotalAmt', round(div26, 2))
                if sh and divAll is not None:
                    upd('cumDiv', round(divAll * 1e8 / (sh * 1e4), 4))
            yv = iy.get(x.get('trackCode') or '')
            if yv is not None and x.get('yieldNum') != yv:
                x['yieldNum'] = round(yv, 4)
                x['yield'] = '{:.2f}%'.format(yv)
                chg += 1
            if chg:
                updated += 1
                print('  [OK] %s (%d 字段)' % (x['code'], chg))
        print('  [%s] etfData 批次 %d/%d（已更新 %d）' % (ts(), bi + 1,
              len(batches), updated), flush=True)
    save_json('etfData.json', d)
    print('etfData 完成: %d 只更新' % updated)
    return updated


# ============ 4. fundData（场外）============
def update_fund_data():
    d = load_json('fundData.json')
    todo = [x for x in d if x.get('code')]
    iy = _index_yield_map()
    _iname = _index_name_map()   # trackCode → 站内指数规范名（ETF.trackName 须与之对齐，2026-10-05）
    updated = 0
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    queries = [' '.join('%s %s' % (x['code'], x['name']) for x in b) +
               ' 这些基金的基金成立日 管理费率 最新单位净值 最新基金规模 2026年分红次数 近12月分红收益率 跟踪指数名称 基金公司名称'
               for b in batches]
    # 第二路：分红金额（**仅补空白** —— Excel 行已有值不动；自动补入/缺失行用 Wind 补）。
    #   2026-10-06 新增：月月名单自动补入（sync_new_monthly）的场外基金不在 Excel 内，
    #   否则 annualDivAmt/monthlyDivAmt/divTotalAmt 恒为 0（表现为「有最近分红日、但月均分红=0」）。
    #   Wind「最新单位年度分红」= 站点「年度单位分红」(annualDivAmt，元/份)，实测 007466 = 0.045 与 Excel 一致；
    #   「最新年度分红总额（亿元）」= divTotalAmt（亿元，与表头单位一致）。
    #   monthlyDivAmt 按站点口径 = 年度单位分红 ÷ 年度分红次数（annualDiv）。
    q2s = ['、'.join(x['code'] for x in b) + ' 最新单位年度分红 最新年度分红总额（亿元）'
           for b in batches]
    res = _prefetch(queries + q2s)
    results, results2 = res[:len(batches)], res[len(batches):]
    for bi, (batch, tbs) in enumerate(zip(batches, results)):
        by_code = _rows_by_code(tbs)
        by_code2 = _rows_by_code(results2[bi] if bi < len(results2) else [])
        for x in batch:
            hit = by_code.get(x['code'])
            if not hit:
                print('  [—] %s 无数据' % x['code'])
                continue
            row, cm = hit
            chg = 0
            def upd(k, v):
                nonlocal chg
                if v is not None and x.get(k) != v:
                    x[k] = v
                    chg += 1
            def gv(c):
                return row[cm[c]] if c in cm and len(row) > cm[c] else None
            upd('establishDate', dstr(gv('基金成立日')) or None)
            upd('fundCompany', str(gv('基金公司名称')).strip() if gv('基金公司名称') else None)
            v = num(gv('管理费率'))
            if v is not None and v > 0:   # 费率 ≤0 视为 Wind 缺值/异常，不写入（2026-10-05）
                upd('feeNum', round(v / 100.0, 4))
                upd('fee', '{:.2f}%'.format(v))
            v = num(gv('2026年分红次数'))
            if v is not None:
                upd('annualDiv', int(v))
            v = num(gv('最新单位净值'))
            if v is not None:
                upd('nav', round(v, 4))
            v = num(gv('最新基金规模'))
            if v is not None:
                upd('fundSize', round(v, 2))
                x['sizeDate'] = datetime.date.today().isoformat()   # 规模取数日期（供 data_center，2026-09-26 新增）
            v = num(gv('近12月分红收益率'))
            if v is not None:
                upd('divYieldNum', round(v / 100.0, 4))   # ETF 实际分红收益率（备用口径）
            _tn = str(gv('跟踪指数名称')).strip() if gv('跟踪指数名称') else ''
            _canon = _iname.get(x.get('trackCode') or '')
            upd('trackName', (_canon or _tn) or None)   # 站内指数库优先（ETF 跟踪指数名与指数库打通，2026-10-05）
            # 分红金额补空白（2026-10-06）：仅当当前为空/0 时用 Wind 补（Excel 行已有值 → 不动）
            _h2 = by_code2.get(x['code'])
            if _h2:
                _r2, _cm2 = _h2

                def gv2b(c, r=_r2, m=_cm2):
                    return r[m[c]] if c in m and len(r) > m[c] else None
                _u = num(gv2b('最新单位年度分红'))
                if _u is not None and not x.get('annualDivAmt'):
                    x['annualDivAmt'] = round(_u, 4)
                    _ad = x.get('annualDiv') or 0
                    if _ad:
                        x['monthlyDivAmt'] = round(_u / _ad, 4)
                    chg += 1
                _t = num(gv2b('最新年度分红总额'))
                if _t is not None and not x.get('divTotalAmt') and 0 < _t < 1000:
                    x['divTotalAmt'] = round(_t, 2)
                    chg += 1
            yv = iy.get(x.get('trackCode') or '')
            if yv is not None and x.get('yieldNum') != yv:
                x['yieldNum'] = round(yv, 4)
                x['yield'] = '{:.2f}%'.format(yv)
                chg += 1
            if chg:
                updated += 1
                print('  [OK] %s (%d 字段)' % (x['code'], chg))
        print('  [%s] fundData 批次 %d/%d（已更新 %d）' % (ts(), bi + 1,
              len(batches), updated), flush=True)
    save_json('fundData.json', d)
    print('fundData 完成: %d 只更新' % updated)
    return updated


# ============ 5. hkEtfData（港交所）============
def update_hk_etf():
    d = load_json('hkEtfData.json')
    todo = [x for x in d if x.get('code')]
    updated = 0
    _iname = _index_name_map()   # trackCode → 站内指数规范名（ETF.trackName 须与之对齐）
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    # 2026-10-08：站内港股代码为 5 位（'03070.HK'），Wind 查询须用 4 位（'3070.HK'）
    #   → 问句与返回码比对一律经 lc.hk_wind() 转换/归一，否则全部港ETF 取不到数据。
    queries = [' '.join('%s %s' % (lc.hk_wind(x['code']) or x['code'], x.get('fullname') or x['name']) for x in b) +
               ' 这些基金的基金成立日 管理费率 基金规模合计 跟踪指数名称' for b in batches]
    results = _prefetch(queries)
    for bi, (batch, tbs) in enumerate(zip(batches, results)):
        by_code = _rows_by_code(tbs)
        for x in batch:
            _wcode = lc.hk_wind(x['code']) or x['code']
            hit = by_code.get(_wcode) or by_code.get(x['code'])
            if not hit:
                print('  [—] %s 无数据' % x['code'])
                continue
            row, cm = hit
            chg = 0
            def upd(k, v):
                nonlocal chg
                if v is not None and x.get(k) != v:
                    x[k] = v
                    chg += 1
            def gv(*cands):
                # 精确列名优先，否则按子串模糊匹配。
                # 根因（2026-10-05 修复）：Wind 对同一问法会漂移列名——规模列可能是
                # 「基金规模合计」，也可能返回「上市基金规模_WIND计算」等；旧代码只认
                # 精确名 → 取不到就 None → 规模长期漏更新（费率同理，3483 曾写 0.00%）。
                for c in cands:
                    if c in cm and len(row) > cm[c]:
                        return row[cm[c]]
                for name, idx in cm.items():
                    for c in cands:
                        if c and c in name and len(row) > idx:
                            return row[idx]
                return None
            upd('listedDate', dstr(gv('基金成立日')) or None)
            v = num(gv('管理费率'))
            if v is not None and v > 0:   # 费率 ≤0 视为 Wind 缺值/异常，不写入（防 0.00% 覆盖真实费率，2026-10-05）
                upd('feeNum', round(v / 100.0, 4))
                upd('fee', '{:.2f}%'.format(v))
            v = num(gv('基金规模合计', '规模'))
            if v is not None and v > 0:
                upd('size', round(v, 2))
                x['sizeDate'] = datetime.date.today().isoformat()   # 规模取数日期（供中央数据库 data_center 区分新旧，2026-09-25 新增）
            _tn = gv('跟踪指数名称', '跟踪指数')
            _tn = str(_tn).strip() if _tn else ''
            _canon = _iname.get(x.get('trackCode') or '')
            if _canon:
                upd('trackName', _canon)   # 站内指数库为准：trackCode 命中指数库 → 用规范名（2026-10-05）
            elif not (x.get('trackName') or '').strip():
                upd('trackName', _tn or None)   # 2026-10-08：trackCode 为空且已有非空 trackName（多为手工修订）→ **不覆盖**，保住 manual-overrides
            if chg:
                updated += 1
                print('  [OK] %s (%d 字段)' % (x['code'], chg))
        print('  [%s] hkEtfData 批次 %d/%d（已更新 %d）' % (ts(), bi + 1,
              len(batches), updated), flush=True)
    save_json('hkEtfData.json', d)
    print('hkEtfData 完成: %d 只更新' % updated)
    return updated


# ============ 6. quotes：日更档 · A 行情层（2026-10-17 · backlog B-4）============
#   背景：本脚本的属性/规模字段（B/C 层）自 2026-10-17 起改挂**周更**档；
#   但「月月分红 ETF 最新收盘价」「场外基金最新单位净值」属 A 行情层（跨站总规则 §三），须每天更新，
#   故单独拆成 quotes 档（日更跑）。跟踪指数股息率不必在此重复——build_lists 每日已镜像 indexData。
def _update_quotes(name, fields):
    """按 fields=[(站内字段, Wind 列名, 小数位, 是否百分数→小数)] 刷新行情层字段。"""
    d = load_json(name)
    todo = [x for x in d if x.get('code')]
    if not todo:
        print('%s 完成: 0 只更新' % name)
        return 0
    updated = 0
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    qs = [' '.join('%s %s' % (x['code'], x.get('name') or '') for x in b) +
          ' 这些基金的' + ' '.join(w for _, w, _, _ in fields) for b in batches]
    for bi, (batch, tbs) in enumerate(zip(batches, _prefetch(qs))):
        by_code = _rows_by_code(tbs)
        for x in batch:
            hit = by_code.get(x['code'])
            if not hit:
                for a in _alias(x['code']):
                    if a in by_code:
                        hit = by_code[a]
                        break
            if not hit:
                continue
            row, cm = hit
            chg = 0
            for site_k, wind_col, nd, pct in fields:
                if wind_col not in cm or len(row) <= cm[wind_col]:
                    continue
                v = num(row[cm[wind_col]])
                if v is None:
                    continue
                v = round(v / 100.0, nd) if pct else round(v, nd)
                if x.get(site_k) != v:
                    x[site_k] = v
                    chg += 1
            if chg:
                updated += 1
                print('  [OK] %s (%d 字段)' % (x['code'], chg))
        print('  [%s] %s 批次 %d/%d（已更新 %d）' % (ts(), name, bi + 1, len(batches), updated), flush=True)
    save_json(name, d)
    print('%s 完成: %d 只更新' % (name, updated))
    return updated


def update_etf_quotes():
    """月月分红 ETF：最新收盘价 + 近 12 月分红收益率（A 行情层）。"""
    return _update_quotes('etfData.json', [('price', '最新收盘价', 3, False),
                                           ('divYieldNum', '近12月分红收益率', 4, True)])


def update_fund_quotes():
    """场外基金：最新单位净值 + 近 12 月分红收益率（A 行情层）。"""
    return _update_quotes('fundData.json', [('nav', '最新单位净值', 4, False),
                                            ('divYieldNum', '近12月分红收益率', 4, True)])


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    pos = [a for a in args if not a.startswith('--')]
    which = pos[0] if pos else 'all'
    t0 = time.time()
    if which in ('all', 'fc'):
        print('===== [%s] 1/5 indexData.fundCount =====' % ts(), flush=True)
        update_fund_count()
    if which in ('all', 'cn'):
        print('===== [%s] 2/5 cnEtfData =====' % ts(), flush=True)
        update_cn_etf(dry_run=dry_run)
    if which in ('all', 'etf'):
        print('===== [%s] 3/5 etfData =====' % ts(), flush=True)
        update_etf_data()
    if which in ('all', 'fund'):
        print('===== [%s] 4/5 fundData =====' % ts(), flush=True)
        update_fund_data()
    if which in ('all', 'hk'):
        print('===== [%s] 5/5 hkEtfData =====' % ts(), flush=True)
        update_hk_etf()
    if which == 'quotes':
        print('===== [%s] quotes：行情层字段（A 层 · 日更）=====' % ts(), flush=True)
        update_etf_quotes()
        update_fund_quotes()
    print('耗时 %.1f 分' % ((time.time() - t0) / 60), flush=True)


if __name__ == '__main__':
    main()

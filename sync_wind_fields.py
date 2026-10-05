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

用法: python3 sync_wind_fields.py [all|cn|etf|fund|hk|fc]
"""
import datetime, io, json, os, subprocess, sys, time, tempfile
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')
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
            r = subprocess.run(
                ['node', CLI, 'call', server, tool,
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=90, env=env, cwd=WIND_SKILL)
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
                cand = [k for k in found if k in (x['name'], x['fullname'])]
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
def update_cn_etf():
    d = load_json('cnEtfData.json')
    todo = [x for x in d if x.get('code')]
    updated = 0
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    queries = [' '.join('%s %s' % (x['code'], x['name']) for x in b) +
               ' 这些基金的成立日期 上市日期 管理费率 基金规模合计 基金份额 开放式基金认购户数 2026年分红次数'
               for b in batches]
    results = _prefetch(queries)
    for bi, (batch, tbs) in enumerate(zip(batches, results)):
        by_code = _rows_by_code(tbs)
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
            v = num(gv('基金规模合计'))
            if v is not None:
                upd('size', round(v, 2))
                x['sizeDate'] = datetime.date.today().isoformat()   # 规模取数日期（供中央数据库 data_center 区分新旧，2026-09-25 新增）
            v = num(gv('基金份额'))
            if v is not None:
                upd('shares', round(v / 1e4, 2))   # 万份 → 亿份
            v = num(gv('开放式基金认购户数'))
            if v is not None:
                upd('holders', round(v / 1e4, 2))  # 户 → 万户
            v = num(gv('2026年分红次数'))
            if v is not None:
                upd('divCount', int(v))
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
            upd('trackName', str(gv('跟踪指数名称')).strip() if gv('跟踪指数名称') else None)
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
    updated = 0
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    queries = [' '.join('%s %s' % (x['code'], x['name']) for x in b) +
               ' 这些基金的基金成立日 管理费率 最新单位净值 最新基金规模 2026年分红次数 近12月分红收益率 跟踪指数名称 基金公司名称'
               for b in batches]
    results = _prefetch(queries)
    for bi, (batch, tbs) in enumerate(zip(batches, results)):
        by_code = _rows_by_code(tbs)
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
            upd('trackName', str(gv('跟踪指数名称')).strip() if gv('跟踪指数名称') else None)
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
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    queries = [' '.join('%s %s' % (x['code'], x['fullname'] or x['name']) for x in b) +
               ' 这些基金的基金成立日 管理费率 基金规模合计 跟踪指数名称' for b in batches]
    results = _prefetch(queries)
    for bi, (batch, tbs) in enumerate(zip(batches, results)):
        by_code = _rows_by_code(tbs)
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
            upd('trackName', str(_tn).strip() if _tn else None)
            if chg:
                updated += 1
                print('  [OK] %s (%d 字段)' % (x['code'], chg))
        print('  [%s] hkEtfData 批次 %d/%d（已更新 %d）' % (ts(), bi + 1,
              len(batches), updated), flush=True)
    save_json('hkEtfData.json', d)
    print('hkEtfData 完成: %d 只更新' % updated)
    return updated


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    t0 = time.time()
    if which in ('all', 'fc'):
        print('===== [%s] 1/5 indexData.fundCount =====' % ts(), flush=True)
        update_fund_count()
    if which in ('all', 'cn'):
        print('===== [%s] 2/5 cnEtfData =====' % ts(), flush=True)
        update_cn_etf()
    if which in ('all', 'etf'):
        print('===== [%s] 3/5 etfData =====' % ts(), flush=True)
        update_etf_data()
    if which in ('all', 'fund'):
        print('===== [%s] 4/5 fundData =====' % ts(), flush=True)
        update_fund_data()
    if which in ('all', 'hk'):
        print('===== [%s] 5/5 hkEtfData =====' % ts(), flush=True)
        update_hk_etf()
    print('耗时 %.1f 分' % ((time.time() - t0) / 60), flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清单「进出」机制 · 共享工具（2026-10-07）
========================================
数据更新的「清单进退」三件套统一放在这里，供 sync_lifecycle / sync_new_* / build_lists /
make_run_report 共同引用（与 wind_client.py / trade_calendar.py / index_variants.py 同为共享模块）：

1. **中央库导出读取**（`<repo>/../../data_center/exports/common/`）：
   - `fund-liquidated.json` —— 基金清盘名单（境内红利ETF/货币基金/月月分红 的「出」判据）。
   - `hk-etf-list.json`     —— 港交所上市 ETF 名单（港ETF「出」比对 + 「进」发现）。
   两文件**可能尚不存在**：缺失时一律返回 None，调用方走各自回退路径，绝不报错。
   导出目录/文件均按「尽力兼容」解析：兼容 list[str]、{"codes":"a,b"}、{"liquidated":[...]}、
   [{"code":...}]、以及 data_center 惯用的表格式 {"columns":[...],"rows":[[...]]}。

2. **进出状态**（仓库根 `.lifecycle_state.json`，因 `data/` 会被测试回滚，故状态不落 data/）：
   - `observe`     —— 「待观察」计数：{"<code>": {"list","reason","firstSeen","hits"}}。
   - `lastWindRun` —— REITs Wind「到期日」体检的上次运行时间（从 _retired.json 迁出）。

3. **清单变动日志**（仓库根 `.list_changes.json`）：所有自动「进/出/待观察」事件，
   各脚本 load-merge-save 追加；事件 schema：
   {"at","date","action":"add|retire|observe","list":"cnEtf|hkEtf|reits|etf|fund|money",
    "code","name","reason","source"}。

4. **自动补入登记**（`data/curation/_auto_added.json`，**入库**、不 gitignore）：
   供 build_lists 把自动补入的 code 并入「表外行保留」护栏。
"""
import datetime
import io
import json
import os
import re
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
CURATION_DIR = os.path.join(BASE, 'data', 'curation')

# 中央库导出目录（data_center 与本站同级：<repo>/../../data_center/exports/common/）
CENTRAL_EXPORT_DIR = os.path.normpath(
    os.path.join(BASE, '..', '..', 'data_center', 'exports', 'common'))
CENTRAL_FUND_LIQUIDATED = 'fund-liquidated.json'   # 清盘名单（新数据源）
CENTRAL_HK_LIST = 'hk-etf-list.json'               # 港交所上市 ETF 名单（新数据源）

# 仓库根状态 / 日志文件（不入库）
LIFECYCLE_STATE_PATH = os.path.join(BASE, '.lifecycle_state.json')
LIST_CHANGES_PATH = os.path.join(BASE, '.list_changes.json')
# 自动补入登记（入库）
AUTO_ADDED_PATH = os.path.join(CURATION_DIR, '_auto_added.json')

LIST_CHANGES_SCHEMA = ('list_changes: [ {at,date,action: add|retire|observe,'
                       'list: cnEtf|hkEtf|reits|etf|fund|money,code,name,reason,source} ]')
AUTO_ADDED_SCHEMA = 'auto_added: { <code>: {addedDate,list,reason,source} }'

# 「清单变动」的 list 名 → 站点数据文件 key（build_lists 的表外行保守护栏用）
AUTO_LIST_TO_DATA_KEY = {
    'cnEtf': 'cnEtfData',
    'hkEtf': 'hkEtfData',
    'reits': 'reitsData',
    'etf': 'etfData',
    'fund': 'fundData',
    'money': 'moneyFundData',
}


# ── 基础 IO ────────────────────────────────────────────────────────────────
def today_str():
    return datetime.date.today().isoformat()


def now_str():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def load_json(path, default=None):
    """读取 JSON；缺失/损坏返回 default（防御式，绝不抛异常）。"""
    try:
        with io.open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    """原子写入（临时文件 + os.replace），避免坚果云同步锁导致半截文件。"""
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ── 中央库导出读取 ──────────────────────────────────────────────────────────
def central_path(name):
    return os.path.join(CENTRAL_EXPORT_DIR, name)


def load_central(name):
    """读取中央库导出文件 exports/common/<name>；缺失/损坏返回 None。"""
    p = central_path(name)
    if not os.path.exists(p):
        return None
    return load_json(p, None)


# 代码字段候选名（对象 / 表头均适用）
_CODE_KEYS = ('code', 'security_id', 'sec_code', 'wind_code', 'fund_code',
              '代码', '基金代码', 'ETF代码', '证券代码')


def _add_codes(out, v):
    """递归把任意结构里的代码字符串汇入集合 out。"""
    if v is None:
        return
    if isinstance(v, (list, tuple, set)):
        for x in v:
            _add_codes(out, x)
    elif isinstance(v, dict):
        for k in _CODE_KEYS:
            if v.get(k):
                out.add(str(v[k]).strip())
                return
    else:
        s = str(v).strip()
        if s:
            out.add(s)


def extract_codes(obj):
    """尽力从任意结构中抽出代码集合（防御式，兼容多种结构）。

    兼容：list[str] / {"codes":"a,b"|[...]} / {"liquidated":[...]} / [{"code":...}] /
          {"columns":[...],"rows":[[...]]}（data_center 表格式）。
    返回 set[str]（可能为空）。
    """
    out = set()
    if isinstance(obj, dict):
        # ① data_center 表格式：{meta, columns, rows}
        rows = obj.get('rows')
        cols = obj.get('columns')
        if isinstance(rows, list) and rows:
            ci = None
            if isinstance(cols, list):
                for i, c in enumerate(cols):
                    key = (c.get('key') if isinstance(c, dict) else str(c)) or ''
                    title = (c.get('title') if isinstance(c, dict) else '') or ''
                    blob = ('%s %s' % (key, title))
                    if any(t in blob for t in ('code', '代码', 'security_id', '证券代码')):
                        ci = i
                        break
            for r in rows:
                if isinstance(r, (list, tuple)):
                    if ci is not None and ci < len(r):
                        if r[ci] not in (None, ''):
                            out.add(str(r[ci]).strip())
                    elif r:
                        out.add(str(r[0]).strip())
                elif isinstance(r, dict):
                    _add_codes(out, r)
            return {c for c in out if c}
        # ② 常见容器键
        hit = False
        for k in ('codes', 'liquidated', 'funds', 'items', 'list', 'data', 'changes'):
            if k in obj:
                hit = True
                v = obj[k]
                if k == 'codes' and isinstance(v, str):
                    for part in re.split(r'[,\s;，、]+', v):
                        if part.strip():
                            out.add(part.strip())
                else:
                    _add_codes(out, v)
        if hit:
            return {c for c in out if c}
        # ③ 退化：整个 dict 当作单个对象
        _add_codes(out, obj)
        return {c for c in out if c}
    # list / 其它
    _add_codes(out, obj)
    return {c for c in out if c}


def extract_funds(obj):
    """尽力抽出基金对象列表（港ETF「进」用）。

    返回 [{"code","name","full_name","hk_connect","track_name"}]（可能为空）。
    兼容 {"dividend_funds":[{code,name,full_name,hk_connect,track_name}]}、
    list[{code,name}]、{"codes":"a,b"}、表格式 {columns,rows}。
    """
    funds = []

    def norm(d):
        if not isinstance(d, dict):
            return None
        code = ''
        for k in _CODE_KEYS:
            if d.get(k):
                code = str(d[k]).strip()
                break
        if not code:
            return None
        name = ''
        for k in ('name', 'short_name', '证券简称', '简称', '基金简称', 'ETF简称'):
            if d.get(k):
                name = str(d[k]).strip()
                break
        full = ''
        for k in ('full_name', 'fullname', 'name_full', '全称', 'ETF全称'):
            if d.get(k):
                full = str(d[k]).strip()
                break
        return {
            'code': code, 'name': name, 'full_name': full,
            'hk_connect': d.get('hk_connect'),
            'track_name': d.get('track_name') or d.get('trackName') or '',
        }

    def norm_codes(codes):
        out = []
        for c in (codes or []):
            c = str(c).strip()
            if c:
                out.append({'code': c, 'name': '', 'full_name': '',
                            'hk_connect': None, 'track_name': ''})
        return out

    if isinstance(obj, dict):
        for k in ('dividend_funds', 'funds', 'items', 'list', 'data'):
            v = obj.get(k)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                for d in v:
                    n = norm(d)
                    if n:
                        funds.append(n)
                if funds:
                    return funds
        if 'codes' in obj:
            codes = obj['codes']
            if isinstance(codes, str):
                codes = re.split(r'[,\s;，、]+', codes)
            return norm_codes(codes)
        rows = obj.get('rows')
        if isinstance(rows, list):
            cols = obj.get('columns') or []
            idx = {}
            for i, c in enumerate(cols):
                key = (c.get('key') if isinstance(c, dict) else str(c)) or ''
                title = (c.get('title') if isinstance(c, dict) else '') or ''
                blob = ('%s %s' % (key, title)).lower()
                if ('code' in blob or '代码' in blob) and 'code' not in idx:
                    idx['code'] = i
                if 'full' in blob and 'full' not in idx:
                    idx['full'] = i
                if ('name' in blob or '简称' in blob or '名称' in blob) and 'name' not in idx:
                    idx['name'] = i
            for r in rows:
                if not isinstance(r, (list, tuple)):
                    continue
                d = {}
                if 'code' in idx and idx['code'] < len(r):
                    d['code'] = r[idx['code']]
                if 'name' in idx and idx['name'] < len(r):
                    d['name'] = r[idx['name']]
                if 'full' in idx and idx['full'] < len(r):
                    d['full_name'] = r[idx['full']]
                n = norm(d)
                if n:
                    funds.append(n)
            return funds
    if isinstance(obj, list):
        for d in obj:
            n = norm(d)
            if n:
                funds.append(n)
    return funds


# ── 代码归一 ────────────────────────────────────────────────────────────────
def code6(v):
    """取代码前 6 位数字（'159589.OF'→'159589'、'000198'→'000198'）。取不到返回 ''。"""
    m = re.match(r'\s*(\d{6})', str(v or ''))
    return m.group(1) if m else ''


def hk_num(v):
    """港交所代码归一为数字串（'3070.HK'/'03070'→'3070'）。取不到返回 ''。"""
    m = re.match(r'\s*(\d+)', str(v or ''))
    if not m:
        return ''
    return str(int(m.group(1)))


def hk_site(v):
    """港交所代码 → 站点代码形式（5 位 + .HK，与中央库 sec_code 对齐）。

    '3070.HK' / '03070' / '3070' → '03070.HK'；取不到返回 ''。
    """
    n = hk_num(v)
    return ('%05d.HK' % int(n)) if n else ''


# ── 清盘名单（fund-liquidated.json）────────────────────────────────────────
def load_liquidated_codes():
    """读取中央库清盘名单 → (set_of_code6, 导出说明)。

    文件缺失 / 无法解析出任何代码 → 返回 None（调用方跳过并打印，绝不误判）。
    """
    obj = load_central(CENTRAL_FUND_LIQUIDATED)
    if obj is None:
        return None
    six = {code6(c) for c in extract_codes(obj)}
    six.discard('')
    if not six:
        return None
    desc = ''
    if isinstance(obj, dict):
        desc = str(obj.get('fetchedAt')
                   or ((obj.get('meta') or {}).get('asOf') if isinstance(obj.get('meta'), dict) else '')
                   or '')
    return six, desc


# ── 港交所 ETF 名单（hk-etf-list.json）──────────────────────────────────────
def load_central_hk_codes():
    """读取中央库港交所上市 ETF 全量名单（「出」比对用）→ (set[str], 导出说明)。

    要求 ≥100 个代码（防误判：结果异常视为不可用）；文件缺失/不足 → None（回退本地副本）。
    """
    obj = load_central(CENTRAL_HK_LIST)
    if obj is None:
        return None
    fetched = ''
    if isinstance(obj, dict):
        meta = obj.get('meta') if isinstance(obj.get('meta'), dict) else {}
        fetched = str(obj.get('fetchedAt') or meta.get('asOf') or '')
    raw = {c.strip().upper() for c in extract_codes(obj) if str(c).strip()}
    hk = {c for c in raw if c.endswith('.HK')}
    if len(hk) >= 100:
        return hk, fetched
    if len(raw) >= 100:
        return raw, fetched
    return None


def load_central_hk_funds():
    """读取中央库港交所 ETF 名单中「红利类」基金信息（「进」发现用）。

    返回 [{"code","name","full_name","hk_connect","track_name"}]；缺失/解析为空 → None。
    """
    obj = load_central(CENTRAL_HK_LIST)
    if obj is None:
        return None
    funds = extract_funds(obj)
    return funds or None


# ── 进出状态 .lifecycle_state.json ─────────────────────────────────────────
def load_lifecycle_state():
    """读取仓库根 .lifecycle_state.json；缺失/损坏 → {"observe":{}, "lastWindRun":""}。"""
    obj = load_json(LIFECYCLE_STATE_PATH, None)
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault('observe', {})
    obj.setdefault('lastWindRun', '')
    return obj


def save_lifecycle_state(obj):
    save_json(LIFECYCLE_STATE_PATH, obj)


# ── 清单变动 .list_changes.json ────────────────────────────────────────────
def load_list_changes():
    """返回清单变动事件列表（缺失/损坏 → []）。"""
    obj = load_json(LIST_CHANGES_PATH, None)
    if isinstance(obj, dict):
        ch = obj.get('changes')
        return ch if isinstance(ch, list) else []
    if isinstance(obj, list):
        return obj
    return []


def record_list_changes(events):
    """追加事件到 .list_changes.json（load-merge-save）。

    - 事件可含/不含 at/date（缺则补：date=今天、at=now；均为本地时间）。
    - 同日同 (action,list,code) 去重，避免重复运行产生重复事件。
    - 不同天的旧事件保留（报告端只取当天）。
    返回本次新增事件数。
    """
    if not events:
        return 0
    obj = load_json(LIST_CHANGES_PATH, None)
    if not isinstance(obj, dict):
        obj = {}
    changes = obj.get('changes')
    if not isinstance(changes, list):
        changes = []
    today = today_str()
    now = now_str()
    seen = {(e.get('date'), e.get('action'), e.get('list'), e.get('code'))
            for e in changes if isinstance(e, dict)}
    added = 0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        e = dict(ev)
        e['date'] = str(e.get('date') or today)
        e['at'] = str(e.get('at') or now)
        key = (e['date'], e.get('action'), e.get('list'), e.get('code'))
        if key in seen:
            continue
        changes.append(e)
        seen.add(key)
        added += 1
    if not added:
        return 0
    obj['schema'] = obj.get('schema') or LIST_CHANGES_SCHEMA
    obj['updatedAt'] = now
    obj['changes'] = changes
    save_json(LIST_CHANGES_PATH, obj)
    return added


def today_events():
    """返回 date == 今天 的清单变动事件（报告用）。"""
    t = today_str()
    return [e for e in load_list_changes() if str(e.get('date')) == t]


# ── 自动补入登记 data/curation/_auto_added.json ────────────────────────────
def load_auto_added():
    """读取 _auto_added.json → {code: {addedDate,list,reason,source}}（缺失/损坏 → {}）。"""
    obj = load_json(AUTO_ADDED_PATH, None)
    if isinstance(obj, dict):
        added = obj.get('added')
        if isinstance(added, dict):
            return added
    return {}


def record_auto_added(entries):
    """把自动补入的标的登记到 _auto_added.json（load-merge-save）。

    entries: [{code,list,reason,source}, ...]（可重复 code，取末次）。
    保留首次 addedDate；返回本次「新增 code」数。
    """
    if not entries:
        return 0
    obj = load_json(AUTO_ADDED_PATH, None)
    if not isinstance(obj, dict):
        obj = {}
    added = obj.get('added')
    if not isinstance(added, dict):
        added = {}
    today = today_str()
    n_new = 0
    for e in entries:
        if not isinstance(e, dict):
            continue
        code = e.get('code')
        if not code:
            continue
        code = str(code)
        if code not in added:
            n_new += 1
        prev = added.get(code) if isinstance(added.get(code), dict) else {}
        added[code] = {
            'addedDate': prev.get('addedDate') or today,
            'list': e.get('list', ''),
            'reason': e.get('reason', ''),
            'source': e.get('source', ''),
        }
    obj['schema'] = obj.get('schema') or AUTO_ADDED_SCHEMA
    obj['updatedAt'] = now_str()
    obj['added'] = added
    save_json(AUTO_ADDED_PATH, obj)
    return n_new

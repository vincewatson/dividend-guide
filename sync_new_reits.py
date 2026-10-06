#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新 REITs 自动发现 + 空字段补齐（2026-09-26 用户规则固化；参照 sync_new_etf.py）

规则：
1. 用 Wind 检索**全部已上市的公募 REITs**（代码 508xxx.SH / 18xxxx.SZ），
   与现有 data/reitsData.json 对照，新上市的自动按现有字段结构补入。
2. 新标的的「名称 / 资产类型 / 上市日 / 产权类·特许经营权类」取自 Wind
   基金级档案（get_fund_info）。资产类型允许出现站内新类目（如 Wind 的
   「新型基础设施 / 市政设施 / 商业不动产」，2026-09-26 用户确认接受）。
3. **空字段补齐（2026-09-26 用户要求）**：对「字段为空」的 REITs（含新补入的），
   用 Wind 补 累计分红次数(totalDiv) / 年化分红次数(annualDiv) / 单位累计分红(cumDivAmt) /
   单位年化分红(annualDivAmt) / 年化派息率(yield·yieldNum) / 前收盘价(prevClose)；
   **取不到继续留空、不写 0**；只补空值、绝不覆盖已有值。
4. 简称口径（2026-09-26 用户确认「全部采用扩位场内简称」）：**全部 REITs**
   （含站内已有行）的 `shortName` 统一为 Wind「基金扩位场内简称」；每次运行
   批量取回（12 只/批、并发）并刷新站内已有行，以覆盖 build_lists 每周重建后的值。

用法：
    python3 sync_new_reits.py --dry-run   # 只打印，不写入（上线前先跑这个核对）
    python3 sync_new_reits.py             # 正式写入 data/reitsData.json

注意：只**追加**新标的 / **刷新既有行 `shortName`** / **补齐空字段**，
      绝不删除或改动其它既有字段（三条铁律之一：写回绝不删除旧数据）。
"""
import json, os, subprocess, sys, io, time, tempfile
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
REITS = os.path.join(DATA_DIR, 'reitsData.json')
CLI = os.path.expanduser('~/.agents/skills/wind-mcp-skill/scripts/cli.mjs')
# 并发路数（2026-09-26 提速：扩位简称批 / 新档案件 / 补字段 并发；单批仍 ≤12 只，Wind 批量契约不变）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '8')))

# 代码范围（2026-09-26 用户指定）：沪市 508xxx；深市 18xxxx（180xxx / 181xxx）。
#   2026-09-26 用户「放开」：Wind 返回的 181xxx.SZ（如 181001.SZ 创金合信北京国资公司REIT）
#   一并纳入，故深市前缀放宽为 '18'。范围外的其它代码仍会被单独打印、不自动纳入。
ALLOWED_PREFIX = (('SH', '508'), ('SZ', '18'))

# 全量检索措辞（首个返回非空表者即用；Wind 措辞会漂移，故多措辞兜底）
SEARCH_PHRASINGS = ['全部已上市的公募REITs', '已上市基础设施公募REITs基金列表']

# 基金级档案字段（单代码查询，≤7 字段；措辞漂移时多措辞兜底）
DETAIL_PHRASINGS = [
    '{} 证券简称 基金扩位场内简称 上市日期 资产类型 项目类型 基金成立日',
    '{} 基金扩位场内简称 上市日期 基础资产类型 项目类型 基金成立日',
]

# 空字段补齐：目标字段 + 分红/派息类查询措辞（一次查多个字段；漂移时多措辞兜底）
FILL_FIELDS = ['totalDiv', 'annualDiv', 'cumDivAmt', 'annualDivAmt', 'yield', 'yieldNum', 'prevClose']
DIV_PHRASINGS = [
    '{} 累计分红次数 年化分红次数 单位累计分红 单位年化分红 年化派息率',
    '{} 累计分红次数 单位累计分红 年化派息率',
]

# 与 sync_new_etf.py 一致：3 次重试 + 6s 退避 + 代理变量清理 + 批次间限速
SLEEP = float(os.environ.get('SX_NR_SLEEP', '0.4'))


def ts():
    return time.strftime('%H:%M:%S')


def _wind_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def call_wind_params(server, tool, params):
    """Wind 查询（任意参数 dict），返回 [(columns, rows), ...]（3 次重试 + 6s 退避）。失败返回 []。"""
    for _attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', server, tool, json.dumps(params, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=_wind_env(),
                cwd=os.path.expanduser('~/.agents/skills/wind-mcp-skill'))
        except Exception:
            time.sleep(6)
            continue
        if r.returncode != 0:
            time.sleep(6)
            continue
        # CLI / 接口级错误（含「单日请求次数超限」）→ 不重试，直接返回空（2026-09-26）
        # 注意：错误信封可能落在 stderr，故 stdout+stderr 一起判断
        _blob = (r.stdout or '') + (r.stderr or '')
        if 'backend_error' in _blob or '"ok": false' in _blob or '超限' in _blob:
            print('  [⚠️] %s.%s 接口错误（可能为单日请求次数超限）' % (server, tool), flush=True)
            return []
        try:
            outer = json.loads(r.stdout)
            inner = json.loads(outer['content'][0]['text'])
            d = inner.get('data') or {}
            # 两种返回形态：{data:{data:[{columns,rows}]}}（多表，如 get_fund_info/financials）
            #            与 {data:{columns,rows}}（单表，如 get_fund_price_indicators 行情指标）
            if isinstance(d, dict) and isinstance(d.get('data'), list):
                return [(tb.get('columns', []), tb.get('rows', [])) for tb in d['data']]
            if isinstance(d, dict) and d.get('columns') is not None and d.get('rows') is not None:
                return [(d.get('columns', []), d.get('rows', []))]
            return []
        except Exception:
            time.sleep(6)
    print('  [⚠️] %s.%s 查询连续 3 次失败: %s' % (server, tool, str(params)[:60]), flush=True)
    return []


def call_wind_tbl(server, tool, question):
    """自然语言查询（question 形式）→ call_wind_params。"""
    return call_wind_params(server, tool, {'question': question})


def _prefetch_tbl(queries, server, tool):
    """并发预取一批查询，返回与输入同序的 [(columns, rows), ...] 列表（每项为 call_wind_tbl 的返回）。"""
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        return list(ex.map(lambda q: call_wind_tbl(server, tool, q), queries))


def _col_index(cols, *keys):
    """按列名取下标：任一候选关键词命中即返回；找不到返回 -1（Wind 列序会漂移，禁用固定下标）。"""
    names = [(c.get('name') or '') if isinstance(c, dict) else str(c) for c in cols]
    for i, n in enumerate(names):
        if any(k in n for k in keys):
            return i
    return -1


def _getter(cols, row):
    """返回 g(*keys) 取值函数；列不存在返回 None。"""
    def g(*keys):
        i = _col_index(cols, *keys)
        return row[i] if 0 <= i < len(row) else None
    return g


def load_json(path):
    if not os.path.exists(path):
        return []
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    """原子写入（临时文件 + os.replace），避免坚果云同步锁导致半截文件。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def in_scope(code):
    """代码是否落在用户指定范围（508xxx.SH / 18xxxx.SZ）。"""
    num, _, suf = code.partition('.')
    return any(suf == s and num.startswith(p) for s, p in ALLOWED_PREFIX)


def fetch_all_reits():
    """Wind 检索全部已上市公募 REITs。

    返回 (in_scope_list, out_of_scope_list)：
      - in_scope： {code, name, listedDate}（落在 508xxx.SH / 18xxxx.SZ）
      - out_of_scope：形如 'xxx.SH 名称'（范围外，供人工判断）
    """
    tbls = []
    for q in SEARCH_PHRASINGS:
        tbls = call_wind_tbl('fund_data', 'search_funds', q)
        if any(rows for _c, rows in tbls):
            print('  [%s] 检索措辞命中：%s' % (ts(), q), flush=True)
            break
        time.sleep(SLEEP)
    seen = {}
    for cols, rows in tbls:
        ci = _col_index(cols, 'Wind代码')
        ni = _col_index(cols, '证券简称', '基金扩位场内简称')
        di = _col_index(cols, '上市日期')
        if ci < 0 or di < 0:
            continue
        for r in rows:
            if ci >= len(r):
                continue
            code = str(r[ci] or '').strip()
            if not code or code in seen:
                continue
            name = str(r[ni]).strip() if 0 <= ni < len(r) and r[ni] else ''
            d = str(r[di])[:10] if di < len(r) and r[di] else ''
            seen[code] = {'code': code, 'name': name, 'listedDate': d}
    in_s, out_s = [], []
    for code, m in seen.items():
        (in_s if in_scope(code) else out_s).append(m)
    in_s.sort(key=lambda x: x['code'])
    out_s.sort(key=lambda x: x['code'])
    return in_s, out_s


def fetch_ext_short_names(wind_codes):
    """批量取「基金扩位场内简称」（站内 REITs `shortName` 统一口径；12 只/批、并发）。

    实测：单字段查询返回**基金级**表 `[Wind代码, 证券简称, 基金扩位场内简称]`，12 只/批稳定。
    返回 {Wind代码: 扩位简称}；取不到的键不出现（调用方据此保留原值、绝不写空）。
    """
    out = {}
    if not wind_codes:
        return out
    groups = [wind_codes[i:i + 12] for i in range(0, len(wind_codes), 12)]
    queries = [','.join(g) + ' 基金扩位场内简称' for g in groups]
    print('  [%s] 扩位场内简称 并发 %d 路（%d 批 / %d 只）'
          % (ts(), WORKERS, len(groups), len(wind_codes)), flush=True)
    for tbls in _prefetch_tbl(queries, 'fund_data', 'get_fund_info'):
        for cols, rows in tbls:
            ci = _col_index(cols, 'Wind代码')
            ei = _col_index(cols, '扩位')
            if ci < 0 or ei < 0:
                continue
            for r in rows:
                if len(r) > max(ci, ei) and r[ci] and r[ei]:
                    out[str(r[ci]).strip()] = str(r[ei]).strip()
    return out


def fetch_reit_detail(wind_code):
    """拉新 REIT 的基金级档案（名称/上市日/资产类型/项目类型/成立日）。

    只认「基金级」表——即**含『项目类型』列**的表（Wind 有时会把查询解析成
    「底层资产明细」表：一项目一行、无项目类型列、证券简称为基金全称，须排除）。
    入参必须是 Wind 全代码（含后缀）。
    """
    for tpl in DETAIL_PHRASINGS:
        tbls = call_wind_tbl('fund_data', 'get_fund_info', tpl.format(wind_code))
        for cols, rows in tbls:
            if _col_index(cols, '项目类型') < 0:   # 非基金级表 → 跳过（关键护栏）
                continue
            ci = _col_index(cols, 'Wind代码')
            if ci < 0:
                continue
            for r in rows:
                if ci < len(r) and str(r[ci]).strip() == wind_code:
                    g = _getter(cols, r)
                    return {
                        'name': str(g('证券简称') or '').strip(),
                        'shortName': str(g('基金扩位场内简称') or '').strip(),
                        'listedDate': str(g('上市日期') or '')[:10],
                        'assetType': str(g('资产类型', '基础资产类型') or '').strip(),
                        'projectType': str(g('项目类型') or '').strip(),
                        'foundDate': str(g('基金成立日') or '')[:10],
                    }
        time.sleep(SLEEP)
    return None


def build_reit_item(m):
    """按 reitsData 现有字段结构构造新行（明细字段先留空，随后由补齐阶段填充）。

    字段顺序与既有行保持一致；取不到的字段**留空、不写 0**（数值型 null / 字符串型 ''）。
    """
    return {
        'code': m['windCode'],
        'name': m['name'],
        'assetType': m['assetType'],
        'listedDate': m['listedDate'],
        'totalDiv': None,
        'annualDiv': None,
        'cumDivAmt': None,
        'annualDivAmt': None,
        'yield': '',
        'yieldNum': None,
        'volatility': None,
        'shortName': m.get('shortName') or '',
        'projectType': m['projectType'],
        'prevClose': None,
    }


# ---------------------------------------------------------------------------
# 空字段补齐（2026-09-26 用户要求）
#   分红/派息类：get_fund_financials（一次查多个字段，按列名解析，取各列最后一个非空值）
#   收盘价：get_fund_price_indicators（索引名「前收盘价」，见 references/fund-indicators.md）
#   仅补空值、绝不覆盖；取不到继续留空、不写 0。
# ---------------------------------------------------------------------------
def _blank(v):
    return v is None or v == ''


def needs_fill(row):
    return any(_blank(row.get(k)) for k in FILL_FIELDS)


def _to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_reit_dividend_fields(wind_code):
    """取 累计分红次数/年化分红次数/单位累计分红/单位年化分红/年化派息率。

    Wind 自然语言查询返回的列会漂移/不完整，故多措辞**累积合并**（已取到的键不再覆盖），
    拿到关键字段（totalDiv + yieldNum）即提前结束。返回 dict（可能部分键缺失）；全部缺失返回 {}。
    """
    vals = {}
    for tpl in DIV_PHRASINGS:
        tbls = call_wind_tbl('fund_data', 'get_fund_financials', tpl.format(wind_code))
        for cols, rows in tbls:
            for key, field in (('累计分红次数', 'totalDiv'), ('年化分红次数', 'annualDiv'),
                               ('单位累计分红', 'cumDivAmt'), ('单位年化分红', 'annualDivAmt'),
                               ('年化派息率', 'yieldNum')):
                if field in vals:
                    continue
                i = _col_index(cols, key)
                if i < 0:
                    continue
                unit = ''
                if i < len(cols) and isinstance(cols[i], dict):
                    unit = cols[i].get('unit') or ''
                got = None
                for r in rows:
                    if i < len(r) and r[i] not in (None, ''):
                        got = r[i]
                if got is not None:
                    if field == 'yieldNum':
                        # 年化派息率：Wind 单位 % → 一律转小数存储（无单位时按 >1.5 兜底）
                        v = _to_num(got)
                        if v is not None:
                            if unit == '%' or (not unit and v > 1.5):
                                v = v / 100.0
                            vals[field] = round(v, 4)
                    else:
                        vals[field] = got
        if 'totalDiv' in vals and 'yieldNum' in vals:
            break
        time.sleep(SLEEP)
    return vals


def fetch_reit_prev_close(wind_code):
    """取前收盘价。"""
    for cols, rows in call_wind_params('fund_data', 'get_fund_price_indicators',
                                       {'windcode': wind_code, 'indexes': '前收盘价'}):
        i = _col_index(cols, '前收盘价')
        if i < 0:
            continue
        for r in rows:
            if i < len(r) and r[i] not in (None, ''):
                return r[i]
    return None


def apply_fill(row, div, px):
    """把取到的值写入仍为空的字段（**绝不覆盖已有值**）。返回实际写入的 {字段: 值}。

    口径（2026-09-26 用户确认）：**0 视为「取不到」→ 留空、不写 0**。
    """
    applied = {}

    def setv(k, val):
        if _blank(row.get(k)) and val is not None and val != 0:
            row[k] = val
            applied[k] = val

    t = _to_num(div.get('totalDiv'))
    if t:
        setv('totalDiv', int(t))
    a = _to_num(div.get('annualDiv'))
    if a:
        setv('annualDiv', round(a, 2))
    c = _to_num(div.get('cumDivAmt'))
    if c:
        setv('cumDivAmt', round(c, 4))
    am = _to_num(div.get('annualDivAmt'))
    if am:
        setv('annualDivAmt', round(am, 4))
    y = _to_num(div.get('yieldNum'))
    if y:   # 0 → 留空
        # yieldNum 已在 fetch 阶段归一为小数（如 0.0754）
        if _blank(row.get('yieldNum')):
            row['yieldNum'] = round(y, 4)
            applied['yieldNum'] = row['yieldNum']
        if _blank(row.get('yield')):
            row['yield'] = '{:.2f}%'.format(y * 100)
            applied['yield'] = row['yield']
    p = _to_num(px)
    if p:
        setv('prevClose', round(p, 3))
    return applied


def fetch_fill_pair(row):
    """并发执行单元：返回 (row, div_dict, prev_close)。"""
    code = row['code']
    return row, fetch_reit_dividend_fields(code), fetch_reit_prev_close(code)


def main():
    dry_run = '--dry-run' in sys.argv
    mode = 'DRY-RUN（只打印，不写入）' if dry_run else '写入'
    print('[新REITs发现] [%s] 检索全部已上市公募 REITs（范围：508xxx.SH / 18xxxx.SZ），模式=%s ...'
          % (ts(), mode), flush=True)

    all_reits, out_scope = fetch_all_reits()
    print('  [%s] Wind 返回 %d 只在范围内（另有 %d 只超出代码范围）'
          % (ts(), len(all_reits), len(out_scope)), flush=True)
    if out_scope:
        print('  [i] 超出代码范围（本次不纳入，请人工确认是否放开）：', flush=True)
        for m in out_scope:
            print('      · %s %s（上市 %s）' % (m['code'], m['name'], m['listedDate']), flush=True)

    site = load_json(REITS)
    by_code = {x.get('code'): x for x in site}
    new_items = [m for m in all_reits if m['code'] not in by_code]
    print('  站内现有 %d 只；本次新发现 %d 只:' % (len(site), len(new_items)), flush=True)
    for m in new_items:
        print('    - %s %s（上市 %s）' % (m['code'], m['name'], m['listedDate']), flush=True)

    # 全量取「基金扩位场内简称」（12 只/批、并发）——新标的取简称用；站内已有行统一刷新
    ext = fetch_ext_short_names([m['code'] for m in all_reits]) if all_reits else {}
    sn_changes = []
    for code, row in by_code.items():
        new_sn = ext.get(code)
        if new_sn and row.get('shortName') != new_sn:
            sn_changes.append((code, row.get('shortName') or '', new_sn))

    # 新标的：并发拉基金级档案，构造新行
    built = []
    if new_items:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            resolved = list(ex.map(lambda m: (m, fetch_reit_detail(m['code'])), new_items))
    else:
        resolved = []
    total = len(resolved)
    for k, (m, detail) in enumerate(resolved, 1):
        print('  [%s] (%d/%d) 取得 %s %s 档案' % (ts(), k, total, m['code'], m['name']), flush=True)
        if not detail:
            print('    [❌] 档案拉取失败，跳过（Wind 全代码 %s）——请检查 get_fund_info 措辞是否漂移'
                  % m['code'], flush=True)
            continue
        merged = {
            'windCode': m['code'],
            'name': detail.get('name') or m['name'],          # 回退用检索返回的证券简称
            'assetType': detail.get('assetType') or '',
            'listedDate': detail.get('listedDate') or m['listedDate'],
            'projectType': detail.get('projectType') or '',
            'shortName': ext.get(m['code']) or detail.get('shortName') or '',
            'foundDate': detail.get('foundDate') or '',
        }
        if not merged['projectType']:
            print('    [i] %s 的项目类型 Wind 未返回 → 留空，请人工复核' % m['code'], flush=True)
        if not merged['assetType']:
            print('    [i] %s 的资产类型 Wind 未返回 → 留空，请人工复核' % m['code'], flush=True)
        built.append(build_reit_item(merged))
        print('      → 名称=%s｜资产类型=%s｜项目类型=%s｜上市=%s｜成立=%s｜扩位简称=%s'
              % (merged['name'], merged['assetType'] or '—', merged['projectType'] or '—',
                 merged['listedDate'] or '—', merged['foundDate'] or '—', merged['shortName'] or '—'),
              flush=True)

    # ③ 空字段补齐：对「字段为空」的 REITs 用 Wind 补 分红次数/派息率/派息额/收盘价（并发）
    fill_pool = list(site) + built
    need = [r for r in fill_pool if needs_fill(r)]
    fills = []
    if need:
        print('\n  [%s] 补齐空字段：需补 %d 只（并发 %d 路取数）...'
              % (ts(), len(need), WORKERS), flush=True)
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for row, div, px in ex.map(fetch_fill_pair, need):
                fills.append((row['code'], apply_fill(row, div, px)))
    filled_cnt = sum(1 for _c, ap in fills if ap)

    if not new_items and not sn_changes and not filled_cnt:
        print('[完成] [%s] 无新 REITs、shortName 无变化、空字段无需补，无需更新' % ts(), flush=True)
        return 0

    print('\n===== 本次变更 =====', flush=True)
    print('  ① 新增 %d 条：' % len(built), flush=True)
    for it in built:
        print('    ' + json.dumps(it, ensure_ascii=False), flush=True)
    print('  ② 既有行 shortName 刷新 %d 条（统一为 Wind 扩位场内简称）：' % len(sn_changes), flush=True)
    for code, old, new in sn_changes:
        print('    %s  %s → %s' % (code, old or '（空）', new), flush=True)
    print('  ③ 空字段补齐 %d / %d 只（仅补空值、取不到留空不写 0）：' % (filled_cnt, len(need)), flush=True)
    for code, ap in fills:
        if ap:
            print('    %s  +%s' % (code, json.dumps(ap, ensure_ascii=False)), flush=True)

    if dry_run:
        print('\n[DRY-RUN] 未写入 data/reitsData.json。确认无误后去掉 --dry-run 正式运行。', flush=True)
        return 0

    # 写回：追加新行 + 刷新既有行 shortName + 补齐空字段（均已在内存中就地修改）
    for code, _old, new in sn_changes:
        by_code[code]['shortName'] = new
    site.extend(built)
    site.sort(key=lambda x: x.get('code', ''))
    save_json(REITS, site)
    print('\n[完成] [%s] 新增 %d 只、刷新 shortName %d 条、补齐空字段 %d 只；reitsData.json 现 %d 行'
          % (ts(), len(built), len(sn_changes), filled_cnt, len(site)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())

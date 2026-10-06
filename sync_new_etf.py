#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新 ETF 自动发现与补入（2026-08-15 用户规则固化）

规则：
1. 定期用 Wind 检索近期新成立的红利类 ETF（名称含 红利/高股息/股东回报/央企回报），
   与现有 cnEtfData.json 对照，新标的自动补入（不再依赖用户 Excel 判断新产品）。
2. 新 ETF 的跟踪指数若在现有 indexData.json 中匹配不到 → 该指数为新指数，
   自动纳入指数数据浏览器（indexData.json，含基础信息 + 股息率历史）。

用法：python3 sync_new_etf.py [--days 30]
"""
import json, os, subprocess, sys, io, time, datetime, tempfile

# 指数币种变体归并（数据治理 · 单一事实来源；见 index_variants.py 顶部说明）
# 用户口径（2026-09-20）：同一指数的港币/人民币两版站内只保留一条，取「基准版」。
from index_variants import normalize as iv_norm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CN_ETF = os.path.join(DATA_DIR, 'cnEtfData.json')
INDEX = os.path.join(DATA_DIR, 'indexData.json')
CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wind_guard_cli.mjs')  # Wind 额度守卫包装器（2026-10-06；真实 cli.mjs 见 SX_WIND_CLI_REAL）

KEYWORDS = ['红利', '高股息', '股东回报', '央企回报']
DAYS = 30

# 2026-09-19 优化：原先 call_wind 无重试、无代理变量清理、无进度输出，
# 遇到一次 Wind 抖动（QPS 限流/网络瞬断）就会静默丢数据；且 save_json 非原子写，
# 坚果云同步锁下可能写出半截 json。此处统一补齐（与其余脚本口径一致）。
SLEEP = float(os.environ.get('SX_NE_SLEEP', '0.4'))


def ts():
    return time.strftime('%H:%M:%S')


def _wind_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def call_wind_tbl(server, tool, question):
    """Wind 查询，返回 [(columns, rows), ...]（按列名取值用；3 次重试 + 6s 退避 + 代理变量清理）。失败返回 []。"""
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', server, tool,
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=_wind_env(),
                cwd=os.path.expanduser('~/.agents/skills/wind-mcp-skill'))
        except Exception:
            time.sleep(6)
            continue
        if r.returncode != 0:
            time.sleep(6)
            continue
        try:
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            inner = json.loads(text)
            return [(tb.get('columns', []), tb.get('rows', []))
                    for tb in inner.get('data', {}).get('data', [])]
        except Exception:
            time.sleep(6)
    print('  [⚠️] %s.%s 查询连续 3 次失败: %s' % (server, tool, question[:40]), flush=True)
    return []


def call_wind(server, tool, question):
    """Wind 查询（3 次重试 + 6s 退避 + 代理变量清理）。失败返回 []，绝不抛异常。"""
    rows = []
    for _cols, rs in call_wind_tbl(server, tool, question):
        rows.extend(rs)
    return rows


# ---------------------------------------------------------------------------
# 按列名取值 + 行匹配（2026-09-20 新增）
# 背景：Wind 返回的**列序会漂移**（同一次查询前后两次都可能不同），
#       早期按固定下标取值的写法已在多处踩坑；本脚本原先 fetch_fund_detail 用
#       `r[2]/r[3]/...`、ensure_index_in_browser 也用下标，2026-09-20 实测均已错位
#       （甚至 `int('2017-02-20')` 直接抛 ValueError 中断脚本）。
#       故统一改为按列名解析。
# ---------------------------------------------------------------------------
def _col_index(cols, *keys):
    """按列名取下标：任一候选关键词命中即返回；找不到返回 -1。"""
    names = [(c.get('name') or '') if isinstance(c, dict) else str(c) for c in cols]
    for i, n in enumerate(names):
        if any(k in n for k in keys):
            return i
    return -1


def _pick_row(tbls, wind_code):
    """从 [(cols, rows), ...] 里挑出目标行，返回 (cols, row)；找不到返回 (None, None)。

    ⚠️ 必须按 **Wind 全代码**（含后缀）匹配：2026-09-20 修复的坑 ——
    **未上市**基金在 Wind 的代码是 `.OF`（如 158039.OF），只给裸代码 `158039` 时
    Wind 会撞上同号**债券** 158039.SH「18晋质20」，get_fund_info 直接返回“没找到数据”，
    导致新基金被当成“详情拉取失败”静默跳过。已上市 ETF（159589.SZ）裸代码恰好唯一，
    所以这个缺陷此前一直没暴露。
    """
    base = wind_code.split('.')[0]
    cands = []
    for cols, rows in tbls:
        for r in rows:
            cands.append((cols, r))
    for cols, r in cands:                      # 优先：Wind 全代码精确匹配
        if r and str(r[0]) == wind_code:
            return cols, r
    if len(cands) == 1 and cands[0][1] and str(cands[0][1][0]).split('.')[0] == base:
        return cands[0]                        # 退让：仅一行且数字部分一致
    return None, None


def _getter(cols, row):
    """返回 g(*keys) 取值函数；列不存在返回 None。"""
    def g(*keys):
        i = _col_index(cols, *keys)
        return row[i] if 0 <= i < len(row) else None
    return g


def fetch_ext_short_names(wind_codes):
    """批量取「基金扩位场内简称」（站点 ETF 简称统一口径 = 场内扩位简称，取自 Wind；2026-09-20 用户要求）

    ⚠️ 入参必须是 **Wind 全代码**（含后缀，如 158039.OF / 159589.SZ），不是裸代码。
    2026-09-20 修复：原先传裸代码，未上市基金（Wind 代码 .OF）会撞上同号债券
    （158039 → 158039.SH「18晋质20」）而取不到简称，简称归一静默失效。
    search_funds 返回的是证券简称（= 基金简称），与站点口径不符，故此处用 get_fund_info 覆盖。
    12 只/批（Wind 批量契约）。返回 {纯代码: 扩位简称}；取不到的键不出现，调用方回退原证券简称。
    """
    out = {}
    total = (len(wind_codes) + 11) // 12
    for i in range(0, len(wind_codes), 12):
        grp = wind_codes[i:i + 12]
        print('  [%s] 场内扩位简称 批 %d/%d（%d 只）' % (ts(), i // 12 + 1, total, len(grp)), flush=True)
        for cols, rows in call_wind_tbl('fund_data', 'get_fund_info',
                                        ','.join(grp) + ' 基金扩位场内简称'):
            names = [(c.get('name') or '') if isinstance(c, dict) else str(c) for c in cols]
            try:
                ci = next(j for j, n in enumerate(names) if '代码' in n)
                ei = next(j for j, n in enumerate(names) if '扩位' in n)
            except StopIteration:
                continue
            for r in rows:
                if len(r) > max(ci, ei) and r[ci] and r[ei]:
                    out[str(r[ci]).split('.')[0]] = str(r[ei]).strip()
        time.sleep(SLEEP)
    return out


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


def find_new_etfs():
    """Wind 检索近 DAYS 天成立的红利类 ETF，返回与 cnEtfData 对照后的新标的列表"""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=DAYS)
    q = '{}至{}成立的ETF，名称包含红利或高股息或股东回报或央企回报'.format(start, end)
    rows = call_wind('fund_data', 'search_funds', q)
    cn_etf = load_json(CN_ETF)
    exist_codes = set()
    for x in cn_etf:
        exist_codes.add(x['code'].split('.')[0])
    new_funds = []
    for r in rows:
        if len(r) < 3:
            continue
        code = str(r[0]).split('.')[0]
        name = str(r[1] or '')
        if not name:
            continue
        if any(k in name for k in KEYWORDS) and code not in exist_codes:
            new_funds.append({'code': code, 'windCode': str(r[0]), 'name': name,
                              'foundDate': str(r[2])[:10] if len(r) > 2 else ''})
    return new_funds, rows


def fetch_fund_detail(wind_code):
    """拉新 ETF 详情（跟踪指数/管理人/费率/成立/上市日期）

    ⚠️ 入参必须是 **Wind 全代码**（含后缀，如 158039.OF / 159589.SZ），不是裸代码。
    2026-09-20 修复：原先传裸代码，未上市基金（Wind 代码 .OF）会与同号债券冲突而查不到；
    另外字段改为**按列名解析**（Wind 列序会漂移，固定下标不可靠）。

    未上市基金：`上市日期` 为 None → marketDate 返回 ''（站点显示 `—`），
    待上市后由后续周更自动补齐。
    """
    q = '{} 跟踪指数代码 跟踪指数名称 基金管理人 管理费率 托管费率 基金成立日 上市日期'.format(wind_code)
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

    fee = num('管理费率')
    found = g('基金成立日')
    mkt = g('上市日期')
    return {
        'trackCode': str(g('跟踪指数代码') or ''),
        'trackName': str(g('跟踪指数名称') or ''),
        'manager': str(g('基金管理人') or ''),
        'feeRate': fee,
        'trusteeRate': num('托管费率'),
        'foundDate': str(found)[:10] if found else '',
        'marketDate': str(mkt)[:10] if mkt else '',   # 未上市 → ''
    }


def fetch_fund_scale(wind_code):
    """拉新 ETF 规模/份额（入参同样必须是 Wind 全代码）

    未上市基金 Wind 返回 None → 规模/份额为 0，属预期（上市后有值）。
    """
    q = '{} 最新规模 最新份额'.format(wind_code)
    cols, r = _pick_row(call_wind_tbl('fund_data', 'get_fund_holders', q), wind_code)
    if not r:
        return {'size': 0, 'shares': 0}
    g = _getter(cols, r)

    def num(*keys):
        v = g(*keys)
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    return {'size': round(num('最新规模'), 2),
            'shares': round(num('最新份额') / 10000.0, 2)}   # 份 → 亿份


def add_to_cn_etf(fund, detail, scale):
    """构造 cnEtfData 条目并写入

    字段口径：
      - `code` **一律** base + '.OF'（站点对境内 ETF 的既有约定，与规范数据库 Excel 一致；
        不随上市地/交易所后缀变化，如 159589.SZ → 159589.OF）
      - `listedDate` = 基金**成立日**；`listedMarketDate` = **上市日**
        —— 未上市基金上市日为空 ''（站点该列显示 `—`，2026-09-20 用户确认照常收录）
    """
    fee = detail.get('feeRate', 0)
    item = {
        'code': fund['code'] + '.OF',
        'name': fund['name'],
        'trackCode': detail.get('trackCode', ''),
        'trackName': detail.get('trackName', ''),
        'manager': detail.get('manager', ''),
        'listedDate': detail.get('foundDate', ''),
        'listedMarketDate': detail.get('marketDate', ''),
        'fee': '{:.2f}%'.format(fee) if fee else '0.00%',
        'feeNum': round(fee / 100.0, 4),   # 管理费率为百分数(0.15) → feeNum 存小数(0.0015)，与站点一致（2026-09-13 修复）
        'divCount': 0,
        'size': scale.get('size', 0),
        'sizeDate': datetime.date.today().isoformat() if scale.get('size') else None,   # 规模取数日期（供 data_center，2026-09-25 新增）
        'shares': scale.get('shares', 0),
        'holders': 0.0,
        'divDate': None,
    }
    cn_etf = load_json(CN_ETF)
    if any(x['code'] == item['code'] for x in cn_etf):
        return False
    cn_etf.append(item)
    cn_etf.sort(key=lambda x: x['code'])
    save_json(CN_ETF, cn_etf)
    return True


def ensure_index_in_browser(track_code, track_name):
    """新 ETF 跟踪指数不在 indexData.json → 补入指数浏览器（新指数）

    返回值：'exists'（已在）/ 'added'（本次已补入）/ 'nodata'（无股息率数据，未补入）

    2026-09-20 修复两处：
      ① 基础信息改**按列名解析**——Wind 实测列序已漂移（返回「Wind代码/证券简称/交易币种/
         证券全称/发布机构/发布日期/成份个数/所属国家或地区」），原按固定下标取值会全部错位，
         且 `int(r[5])` 会把日期串 '2017-02-20' 丢进 int() 直接 ValueError 中断脚本；
      ② 新增**空股息率不纳入**的护栏——站点规则明确「Wind 无值 → yield 置空显示 —，
         ❌ 禁止 0.00%」，若无数据仍强行纳入会写入一条 0.00% 的假指数。
    """
    idx = load_json(INDEX)
    if any(x['code'] == track_code for x in idx):
        return 'exists'
    # 拉指数基础信息（按列名解析）
    info = {}
    q = '{} {} 指数全称 指数发布方 指数成立日期 成分股数量 所属市场 币种'.format(track_code, track_name)
    cols, r = _pick_row(call_wind_tbl('index_data', 'get_index_basicinfo', q), track_code)
    if r:
        g = _getter(cols, r)

        def num(*keys):
            v = g(*keys)
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return 0

        pub = g('发布日期', '成立日期')
        mkt = g('所属市场', '市场类型')
        if not mkt:
            print('  [i] %s 的「市场」字段 Wind 未返回（已知限制），本次留空，请人工复核' % track_code, flush=True)
        info = {
            'fullname': str(g('证券全称', '指数全称') or ''),
            'publisher': str(g('发布机构', '指数发布方') or ''),
            'listedDate': str(pub)[:10] if pub else '',
            'components': num('成份个数', '成分股数量'),
            'market': str(mkt or ''),
            'currency': str(g('交易币种', '币种') or ''),
        }
    if not info:
        print('  [⚠️] 指数基础信息拉取失败，仅补最小字段')
        info = {'fullname': '', 'publisher': '', 'listedDate': '',
                'components': 0, 'market': '', 'currency': 'CNY'}
    # 拉股息率历史（2023 年以来，按段）
    div_history = []
    seg_start = datetime.date(2023, 1, 1)
    seg_end = datetime.date.today()
    seg_total = 0
    _s = seg_start
    while _s <= seg_end:
        _e = min(_s + datetime.timedelta(days=135), seg_end)
        seg_total += 1
        _s = _e + datetime.timedelta(days=1)
    seg_i = 0
    while seg_start <= seg_end:
        s_end = min(seg_start + datetime.timedelta(days=135), seg_end)
        seg_i += 1
        q2 = '{} {} {}至{}的股息率历史数据按交易日列出，给出每个交易日的值'.format(
            track_code, track_name, seg_start, s_end)
        print('  [%s] 股息率历史 段 %d/%d %s~%s' % (ts(), seg_i, seg_total, seg_start, s_end), flush=True)
        rows2 = call_wind('index_data', 'get_index_fundamentals', q2)
        for r2 in rows2:
            if len(r2) >= 4 and r2[2] is not None and r2[3]:
                div_history.append({'date': str(r2[3])[:10], 'yield': float(r2[2])})
        seg_start = s_end + datetime.timedelta(days=1)
        time.sleep(SLEEP)
    # 去重排序
    seen = {}
    for p in div_history:
        seen[p['date']] = p['yield']
    div_history = [{'date': d, 'yield': round(v, 4)} for d, v in sorted(seen.items())]
    # 护栏：无股息率数据则不纳入指数浏览器（站点禁止 0.00% 假值；2026-09-20 新增）
    if not div_history:
        print('  [i] %s %s 无股息率历史数据（Wind 全为空）→ 本次不纳入指数浏览器，'
              '避免写入 0.00% 假值' % (track_code, track_name), flush=True)
        return 'nodata'
    last_yield = div_history[-1]['yield']
    item = {
        'code': track_code,
        'name': track_name,
        'fullname': info['fullname'],
        'publisher': info['publisher'],
        'listedDate': info['listedDate'],
        'market': info['market'],
        'components': info['components'],
        'currency': info['currency'],
        'weight': '',
        'fundCount': 0,
        'yield': '{:.2f}%'.format(last_yield) if last_yield else '0.00%',
        'yieldNum': round(last_yield, 4),
        'yrChange': 0.0,
        'fullReturn': '',
        'detailUrl': '',
        'weightExtra': '',
        'adjustCycle': '',
        'adjustDate': '',
        'taxRate': 1.0,
        'investMonthly': 0.0,
        'divHistory': div_history,
        'dailyChange': None,
        'dailyDate': '',
    }
    idx.append(item)
    idx.sort(key=lambda x: x['code'])
    save_json(INDEX, idx)
    return 'added'


def main():
    days = DAYS
    if '--days' in sys.argv:
        days = int(sys.argv[sys.argv.index('--days') + 1])
    print('[新ETF发现] [%s] 检索近 %d 天成立的红利类 ETF（关键词：%s）...' % (
        ts(), days, '/'.join(KEYWORDS)), flush=True)
    new_funds, all_rows = find_new_etfs()
    print('  Wind 返回 %d 只（含已收录），其中新发现 %d 只:' % (len(all_rows), len(new_funds)), flush=True)
    for f in new_funds:
        print('    - %s %s（成立 %s）' % (f['code'], f['name'], f['foundDate']), flush=True)
    if not new_funds:
        print('[完成] [%s] 无新 ETF，无需更新' % ts(), flush=True)
        return
    # 站点口径：ETF 简称统一使用 Wind「基金扩位场内简称」
    # （search_funds 返回的是证券简称=基金简称，与此口径不符，故在此覆盖；2026-09-20 用户要求）
    # ⚠️ 传 Wind 全代码（含后缀），否则未上市基金（.OF）会与同号债券冲突而取不到简称（2026-09-20 修复）
    ext = fetch_ext_short_names([f['windCode'] for f in new_funds])
    for f in new_funds:
        if ext.get(f['code']) and f['name'] != ext[f['code']]:
            print('    ↳ 简称统一为场内扩位简称: %s → %s' % (f['name'], ext[f['code']]), flush=True)
            f['name'] = ext[f['code']]
    total = len(new_funds)
    for k, f in enumerate(new_funds, 1):
        print('  [%s] (%d/%d) 拉取 %s %s 详情...' % (ts(), k, total, f['windCode'], f['name']), flush=True)
        # ⚠️ 必须传 Wind 全代码（f['windCode']，含后缀）：裸代码会让未上市基金撞上同号债券而查不到
        detail = fetch_fund_detail(f['windCode'])
        if not detail:
            print('    [❌] 详情拉取失败，跳过（Wind 全代码 %s）——'
                  '若为新增代码形态请检查 _pick_row 的匹配规则' % f['windCode'], flush=True)
            continue
        scale = fetch_fund_scale(f['windCode'])
        # 币种变体归并（2026-09-20）：跟踪指数若为港币版，统一改「基准版」
        #   如 SPAHLVHP.SPI「标普港股通低波红利指数(港币)」→ SPAHLVCP.SPI「标普港股通低波红利指数」，
        #   避免站内出现同指数的港币/人民币两条（两版股息率数值相同，归并不丢数据）
        _old_tc = detail.get('trackCode', '')
        detail['trackCode'], detail['trackName'] = iv_norm(_old_tc, detail.get('trackName', ''))
        if detail['trackCode'] != _old_tc:
            print('    ↳ 币种变体归并: 跟踪指数 %s → %s' % (_old_tc, detail['trackCode']), flush=True)
        # 未上市：上市日期为空。按用户口径（2026-09-20）照常收录，该列显示 —，上市后由周更补齐
        if not detail.get('marketDate'):
            print('    [i] %s 尚未上市（成立 %s）→ 照常收录，上市日期暂显 —'
                  % (f['name'], detail.get('foundDate') or '?'), flush=True)
        if add_to_cn_etf(f, detail, scale):
            print('    ✅ 已补入 cnEtfData（%s，跟踪 %s %s）' % (
                f['name'], detail.get('trackCode', '?'), detail.get('trackName', '?')), flush=True)
        # 新指数检查
        track_code = detail.get('trackCode', '')
        if track_code:
            st = ensure_index_in_browser(track_code, detail.get('trackName', ''))
            if st == 'added':
                print('    🆕 新指数已纳入指数浏览器: %s %s' % (track_code, detail.get('trackName', '')), flush=True)
            elif st == 'exists':
                print('    （跟踪指数 %s 已在指数浏览器，无需新增）' % track_code, flush=True)
            # 'nodata' 已在 ensure_index_in_browser 内打印原因
        time.sleep(SLEEP)
    print('[完成] [%s] 新 ETF 检查与补入结束' % ts(), flush=True)


if __name__ == '__main__':
    main()

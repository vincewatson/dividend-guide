#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
食息指南 · 宏观资产历史数据同步脚本
====================================
调用 Wind MCP 拉取首页「食息数据」中 7 类宏观资产的历史收益率序列，
生成 data/assetHistory.json（供首页食息详情页历史曲线使用）。

资产映射（name → Wind 取数方式）:
   5年期LPR                 → EDB: 中国:贷款市场报价利率(LPR):5年
   3年期整存整取            → EDB: 中国工商银行:定期存款利率(整存整取):3年
   1年期整存整取            → EDB: 中国工商银行:定期存款利率(整存整取):1年
   3年期储蓄国债            → Wind 债券发行记录: 储蓄国债票面利率（3年期，周频采样）
   5年期储蓄国债            → Wind 债券发行记录: 储蓄国债票面利率（5年期）
                             （原注释写「iFind EDB: 中债国债到期收益率」，但 Wind 账号对该 EDB 指标无权限，
                              2026-10-05 用户确认对外展示即用「储蓄国债票面利率」）
   人身保险产品预定利率研究值 → EDB: 中国:预定利率研究值:普通型人身保险
   中证同业存单AAA指数      → index: 931059.CSI 每月年化收益率（2026-08-15 用户确认标的）
   重点50城租金率           → 用户/季度报告维护（中指研究院季度口径，2026-08-16 起）；中原口径→重点城市租金率(中原6城均值) 备用
   天弘余额宝              → 复用 data/yuebaoHistory.json

用法:
    python3 sync_asset_macro.py
"""
import io, json, os, subprocess, time, tempfile, datetime
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
OUT_FILE = os.path.join(DATA_DIR, 'assetHistory.json')

WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')

# 时间范围：近36个月（EDB 新契约要求 yyyy-MM-dd，2026-08-29 修正）
# 2026-09-19 修复：END 原硬编码 '2026-08-28'，导致每周跑都停在 8/28，新数据进不来 → 改为动态取今天。
# BEGIN 保持固定（不可滚动，否则历史序列会被逐步截断）。
BEGIN = '2023-08-01'
END = datetime.date.today().isoformat()

# 租金代表性城市（中原地产口径，可扩充）
RENT_CITIES = ['上海', '北京', '深圳', '广州', '成都', '天津']

# 并发路数（2026-10-06 提速：各资产序列并发拉取；流水线本身串行，不会抬高 Wind 峰值并发）
WORKERS = max(1, int(os.environ.get('SX_WIND_WORKERS', '6')))


def ts():
    return time.strftime('%H:%M:%S')


def atomic_write_json(path, obj):
    """原子写入（临时文件 + os.replace），避免坚果云同步锁导致半截文件。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def call_wind(server, tool, params):
    """2026-09-19 优化：加入 3 次重试 + 代理变量清理；失败返回 {'data': {}}，
    不再抛异常中断整脚本（原实现 raise 会让一次瞬时失败毁掉整轮取数）。"""
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', server, tool, json.dumps(params, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')), env=env, cwd=WIND_SKILL)
        except Exception:
            time.sleep(5); continue
        if r.returncode != 0:
            time.sleep(5); continue
        try:
            outer = json.loads(r.stdout)
            text = outer.get('content', [{}])[0].get('text', '')
            inner = json.loads(text)
            return inner
        except Exception:
            time.sleep(5)
    return {'data': {}}


def norm_date(d):
    """统一日期格式为 yyyy-mm-dd（EDB 可能返回 yyyymmdd compact 格式）"""
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return '{}-{}-{}'.format(s[:4], s[4:6], s[6:8])
    if '.' in s and '-' not in s:
        return s.replace('.', '-')
    return s[:10] if len(s) > 10 else s


def parse_edb_series(inner, keyword):
    """从 EDB 返回中提取含 keyword 的指标序列（日期统一 ISO 格式）。
    2026-08-29 适配新工具契约：query_economic_indicator_data 返回 metrics 数组（meta/date[]/value[]）。"""
    items = inner.get('metrics', [])
    for item in items:
        meta = item.get('meta', {})
        name = meta.get('name', '')
        if keyword in name:
            dates = item.get('date', [])
            vals = item.get('value', [])
            return [{'date': norm_date(d), 'yield': v} for d, v in zip(dates, vals) if v is not None]
    return []


def fetch_edb(question):
    """EDB 指标时序：2026-08-29 起 Wind skill 新契约
    （natural_language_get_edb_data 已下线，改用 query_economic_indicator_data，beginDate/endDate 必填）。"""
    return call_wind('economic_data', 'query_economic_indicator_data',
                     {'question': question, 'beginDate': BEGIN, 'endDate': END})


def fetch_lpr():
    inner = fetch_edb('中国贷款市场报价利率LPR5年')
    return parse_edb_series(inner, 'LPR')


def fetch_deposit(term):
    inner = fetch_edb('中国工商银行定期存款利率整存整取{}年'.format(term))
    return parse_edb_series(inner, '整存整取')


# 保险预定利率研究值官方发布记录（保协官网，EDB 可能滞后，官方值优先）
# date -> yield（%），每季度例会发布
INSURANCE_OFFICIAL = {
    '2026-07-20': 1.94,  # 2026年二季度例会，来源: 中国保险行业协会官网
}


def fetch_insurance():
    """拉取普通型人身保险预定利率研究值，并用官方发布值覆盖（EDB 可能滞后）"""
    series = parse_edb_series(fetch_edb('中国预定利率研究值普通型人身保险'), '预定利率')
    # 合并官方发布值
    merged = {p['date']: p['yield'] for p in series}
    for d, v in INSURANCE_OFFICIAL.items():
        merged[d] = v
    out = [{'date': d, 'yield': merged[d]} for d in sorted(merged)]
    # 去重（同一天可能 EDB 与官方重复）
    dedup = {}
    for p in out:
        dedup[p['date']] = p['yield']
    return [{'date': d, 'yield': dedup[d]} for d in sorted(dedup)]


def fetch_rent():
    """取北上广深+成都+天津 租金回报率均值（按月对齐）"""
    all_series = []
    for city in RENT_CITIES:
        inner = fetch_edb('{}租金回报率二手住宅'.format(city))
        s = parse_edb_series(inner, city + ':租金回报率')
        if s:
            all_series.append(s)
    if not all_series:
        return []
    # 按日期对齐求均值
    date_map = {}
    for series in all_series:
        for p in series:
            date_map.setdefault(p['date'], []).append(p['yield'])
    out = []
    for d in sorted(date_map):
        vals = date_map[d]
        out.append({'date': d, 'yield': round(sum(vals) / len(vals), 4)})
    return out


# 储蓄国债发行记录查询措辞（按优先级尝试；2026-09-19：措辞会漂移，改为多措辞依次兜底）
BOND_PHRASINGS = [
    '储蓄国债 票面利率 三年期 五年期 发行',
    '2023年至今储蓄国债发行记录票面利率3年期5年期',
    '储蓄国债发行记录 票面利率 3年期 5年期',
]


def fetch_bond_savings(term):
    """储蓄国债票面利率序列：从 bond 发行记录中筛选 3/5 年期。
    2026-09-19 修复：原单一措辞「2023年至今储蓄国债发行记录票面利率3年期5年期」实测返回
    "没找到数据"（措辞漂移），导致 3/5 年期国债停在上周。改为多措辞依次兜底，取首个返回行的措辞。"""
    tables = []
    for ph in BOND_PHRASINGS:
        inner = call_wind('bond_data', 'get_bond_basicinfo', {'question': ph})
        tabs = inner.get('data', {}).get('data', [])
        if any(tb.get('rows') for tb in tabs):
            tables = tabs
            break
    series = []
    for tb in tables:
        cols = [c.get('name', '') for c in tb.get('columns', [])]
        rows = tb.get('rows', [])
        for r in rows:
            if len(r) < 5:
                continue
            code, name = str(r[0]), str(r[1])
            if '储蓄' not in name and '凭证式' not in name:
                continue
            # term 在发行期限列（索引3）
            try:
                r_term = int(float(r[3]))
            except (ValueError, TypeError):
                continue
            if r_term != term:
                continue
            try:
                rate = float(r[4])
            except (ValueError, TypeError):
                continue
            # 日期从发行起始（索引2）
            date = str(r[2])[:10] if r[2] else None
            if date and rate:
                series.append({'date': date, 'yield': rate})
    # 去重（同月多次发行取最新），排序
    series.sort(key=lambda x: x['date'])
    dedup = {}
    for p in series:
        dedup[p['date']] = p['yield']
    out = [{'date': d, 'yield': dedup[d]} for d in sorted(dedup)]
    return out


def fetch_ncd():
    """同业存单AAA指数月度年化收益率"""
    import datetime
    inner = call_wind('index_data', 'get_index_fundamentals',
                      {'question': '931059.CSI 中证同业存单AAA指数 近36个月每月的年化收益率'})
    tables = inner.get('data', {}).get('data', [])
    series = []
    for tb in tables:
        rows = tb.get('rows', [])
        for r in rows:
            if len(r) < 5:
                continue
            code = str(r[0])
            if '931059' not in code:
                continue
            try:
                rate = float(r[2])
            except (ValueError, TypeError):
                continue
            end_date = str(r[4])[:10] if r[4] else None
            if end_date and rate:
                # 未来日期修正（2026-08-15）：Wind 返回月末日期（如 08-31），当月未结束时改为实际截至日
                try:
                    _ed = datetime.date.fromisoformat(end_date)
                    if _ed > datetime.date.today():
                        end_date = datetime.date.today().isoformat()
                except ValueError:
                    pass
                series.append({'date': end_date, 'yield': round(rate, 4)})
    series.sort(key=lambda x: x['date'])
    return series


# REITs 分类（2026-08-11 用户确认：按现金流属性口径，非 Wind 物权口径）
# 产权类 35 只：园区16 + 仓储物流6 + 保障房6 + 消费7（持续租金现金流）
REITS_PROPERTY = [
    '508056.SH', '180101.SZ', '180301.SZ', '508000.SH', '508027.SH', '508099.SH', '180501.SZ',
    '508058.SH', '508068.SH', '180102.SZ', '508021.SH', '508088.SH', '508077.SH', '180103.SZ',
    '508098.SH', '508019.SH', '508031.SH', '508017.SH', '508011.SH', '180601.SZ', '180602.SZ',
    '180302.SZ', '508002.SH', '508005.SH', '508022.SH', '180603.SZ', '180105.SZ', '180502.SZ',
    '180303.SZ', '508003.SH', '508097.SH', '508010.SH', '180106.SZ', '508048.SH', '508012.SH',
]
# 特许经营权类 23 只：交通13 + 新能源7 + 生态环保2 + 水利1（有限期经营权现金流，派息含本金返还）
REITS_CONCESSION = [
    '180201.SZ', '508001.SH', '180202.SZ', '508018.SH', '508008.SH', '508066.SH', '508009.SH',
    '508007.SH', '508086.SH', '508033.SH', '508069.SH', '180203.SZ', '508036.SH',
    '180401.SZ', '508028.SH', '508096.SH', '508026.SH', '508089.SH', '508015.SH', '180402.SZ',
    '180801.SZ', '508006.SH', '180701.SZ',
]


def fetch_reits_median(codes):
    """REITs 月度派息率中位数序列（2023 年以来全量，按现金流属性口径分组聚合）。
    每只一次调用返回整段月度序列（Wind 区间批量），跨标的按月份取中位数。"""
    import datetime as _dt
    today = _dt.date.today().isoformat()
    all_series = []
    for code in codes:
        question = '{} 2023年1月1日至{}按月统计派息率，给出每个月末的值'.format(code, today)
        inner = call_wind('fund_data', 'get_fund_performance', {'question': question})
        tables = inner.get('data', {}).get('data', [])
        for tb in tables:
            rows = tb.get('rows', [])
            series = {}
            for r in rows:
                if len(r) < 4:
                    continue
                try:
                    rate = float(r[2])
                except (ValueError, TypeError):
                    continue
                d = str(r[3])[:10]
                if d and rate:
                    series[d] = rate  # 同月取最后一条（wind 返回按日期升序）
            if series:
                all_series.append(series)
    if not all_series:
        return []
    # 按月聚合跨标的中位数
    months = {}
    for s in all_series:
        for d, v in s.items():
            months.setdefault(d[:7], []).append(v)
    out = []
    for ym in sorted(months):
        vals = sorted(months[ym])
        n = len(vals)
        med = vals[n // 2] if n % 2 == 1 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        # 月末日期：当月最后一天
        day = 31
        import datetime as _dt2
        while day > 28:
            try:
                _dt2.datetime.strptime(ym + '-{:02d}'.format(day), '%Y-%m-%d')
                break
            except ValueError:
                day -= 1
        out.append({'date': ym + '-{:02d}'.format(day), 'yield': round(med, 4)})
    return out


def fetch_reits_concession():
    """特许经营权类 REITs 月度派息率中位数（2023 年以来全量）"""
    return fetch_reits_median(REITS_CONCESSION)


def fetch_reits_property():
    """产权类 REITs 月度派息率中位数（2023 年以来全量）"""
    return fetch_reits_median(REITS_PROPERTY)


def expand_to_weekly(series, end_date=None):
    """将阶梯型数据（利率仅在调整日变化）展开为周频序列。

    从首个数据点到 end_date（默认今天），每周生成一个点，
    值按前向填充（利率未变化则保持上一个值）。
    这样图表时间轴完整、覆盖满近3年，且呈清晰阶梯状。
    """
    import datetime as _dt
    if not series:
        return []
    # 统一日期格式为 YYYY-MM-DD
    norm = []
    for p in series:
        d = str(p['date']).replace('-', '')
        if len(d) == 8:
            dd = d[:4] + '-' + d[4:6] + '-' + d[6:8]
        else:
            dd = str(p['date'])
        try:
            _dt.datetime.strptime(dd, '%Y-%m-%d')
        except ValueError:
            continue
        norm.append({'date': dd, 'yield': p['yield']})
    if not norm:
        return []
    norm.sort(key=lambda x: x['date'])
    if end_date is None:
        end_date = _dt.date.today().isoformat()
    # 生成周频时间轴：每周五作为采样点
    start = _dt.datetime.strptime(norm[0]['date'], '%Y-%m-%d').date()
    end = _dt.datetime.strptime(end_date, '%Y-%m-%d').date()
    if end < start:
        return norm
    # 从 start 所在周的周五开始
    cur = start + _dt.timedelta(days=(4 - start.weekday()) % 7)
    idx = 0
    out = []
    while cur <= end:
        # 前进填充：找 <= cur 的最近利率
        while idx + 1 < len(norm) and norm[idx + 1]['date'] <= cur.isoformat():
            idx += 1
        if norm[idx]['date'] <= cur.isoformat():
            out.append({'date': cur.isoformat(), 'yield': norm[idx]['yield']})
        cur += _dt.timedelta(days=7)
    # 若最后一个点晚于 end（未来），截断
    return out


def load_yuebao():
    """复用余额宝历史"""
    try:
        with io.open(os.path.join(DATA_DIR, 'yuebaoHistory.json'), 'r', encoding='utf-8') as f:
            return json.load(f).get('series', [])
    except Exception:
        return []


def main():
    print('===== 宏观资产历史数据同步 =====', flush=True)
    if not os.path.exists(CLI):
        print('[ERROR] wind-mcp-skill 未找到:', WIND_SKILL, flush=True)
        return

    # 读旧数据：任何序列拉取失败/为空时保留旧值（绝不删除旧数据，2026-08-11 确立）
    old = {}
    try:
        with io.open(OUT_FILE, 'r', encoding='utf-8') as f:
            old = json.load(f)
    except Exception:
        old = {}

    def safe_fetch(tag, fn):
        v = fn()
        if not v and tag in old and old[tag]:
            print('  [WARN] %s 拉取为空，保留旧数据 %d 条' % (tag, len(old[tag])), flush=True)
            return old[tag]
        return v

    def step(i, total, label, fn):
        print('  [%s] (%d/%d) 拉取 %s ...' % (ts(), i, total, label), flush=True)
        return safe_fetch(label, fn)

    result = {}
    # 并发拉取各资产序列（2026-10-06 提速）：各 fetch 相互独立、各写自己的 key；safe_fetch 只读旧值，线程安全。
    jobs = [
        ('5年期LPR', '5年期LPR', fetch_lpr),
        ('3年期整存整取', '3年期整存整取', lambda: expand_to_weekly(fetch_deposit(3))),
        ('1年期整存整取', '1年期整存整取', lambda: expand_to_weekly(fetch_deposit(1))),
        ('人身保险产品预定利率研究值', '人身保险产品预定利率研究值', lambda: expand_to_weekly(fetch_insurance())),
        ('重点城市租金率(中原6城均值)', '重点城市租金率(中原{}城均值)'.format(len(RENT_CITIES)), fetch_rent),
        ('3年期储蓄国债', '3年期储蓄国债', lambda: expand_to_weekly(fetch_bond_savings(3))),
        ('5年期储蓄国债', '5年期储蓄国债', lambda: expand_to_weekly(fetch_bond_savings(5))),
        ('中证同业存单AAA指数', '中证同业存单AAA指数', fetch_ncd),
        ('天弘余额宝', '天弘余额宝', load_yuebao),
    ]
    print('  [%s] 并发 %d 路拉取 %d 类资产序列 ...' % (ts(), WORKERS, len(jobs)), flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        vals = list(ex.map(lambda j: safe_fetch(j[1], j[2]), jobs))
    for (key, _label, _fn), v in zip(jobs, vals):
        result[key] = v
    # REITs 两类序列由 sync_reits_daily.py 独立维护（日频口径，2026-08-15 起）：
    # 此处仅保留现有值，避免月度口径覆盖日频数据（且省去每周 58 次月度调用）
    # 重点50城租金率由用户/季度报告维护（中指研究院季度口径，2026-08-16 起），本脚本不覆盖（中原口径另存备用 key）
    print('  [%s] (10/10) REITs 两类 + 重点50城租金率 由独立机制维护，保留现有值 ...' % ts(), flush=True)
    _ah_path = os.path.join(DATA_DIR, 'assetHistory.json')
    _ah = {}
    try:
        with io.open(_ah_path, 'r', encoding='utf-8') as _f:
            _ah = json.load(_f)
    except Exception:
        pass
    for _k in ('REITs产权类', 'REITs特许经营权类', '重点50城租金率'):
        result[_k] = safe_fetch(_k, lambda: _ah.get(_k, []) if _ah else [])

    # 输出统计
    for k, v in result.items():
        print('  {}: {} 点'.format(k, len(v)), flush=True)

    atomic_write_json(OUT_FILE, result)
    print('已写入:', OUT_FILE, flush=True)


if __name__ == '__main__':
    main()

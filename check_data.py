#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据一致性验证脚本（防复发工具，2026-08-10 建立）
====================================================
每次数据更新后（每周任务/手动同步）必须运行本脚本，验证所有关键数据点，
任何 ❌ 都必须修复后才能部署。

用法: python3 check_data.py
覆盖的验证点（对应历史踩坑记录）：
  1. 所有 JSON 可解析、非空、条数合理
  2. indexData divHistory 最新日期 == 最新交易日（任务顺序 bug：assetData 滞后）
  3. assetData 5 个红利指数 date == divHistory 最新日期（08-10 bug）
  4. assetData 天弘余额宝 date == moneyFundData.yieldDate（余额宝滞后 bug）
  5. assetData 天弘余额宝 yield 为 2 位小数（数据规则）
  6. moneyFundData 天弘余额宝有 yieldDate（yieldDate 丢失 bug）
  7. fundData/etfData/cnEtfData divDate 覆盖率达标（Excel 覆盖 bug）
  8. indexData dailyChange 日期 == 最新交易日（任务缺失 bug）
  9. yuebaoHistory 为 dict 结构且 series 日频、最新为最新交易日
  10. divHistory 缺失指数数量
"""
import io, json, os, sys, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
FAIL = []
latest = ''   # divHistory 合并最新日期（数据派生；在下方 check 2 计算）

import datetime

# ---------------------------------------------------------------------------
# 按市场分别判断「最新交易日」（2026-10-07 · 重构阶段1/2 合并）
#   背景：A股/港股假期不同步时（如 2026-10-07 A股休市、港股开市），原用「合并最新日期」
#   会把未开市市场的全部序列误判为滞后。改为：A股系序列对照 A股日历、港股系对照港股日历。
#   日历来源 market_calendar.json（与 preflight 同源，单一真实来源）。
# ---------------------------------------------------------------------------
try:
    import trade_calendar   # 交易日历（含收盘时间：A股 15:30 / 港股 16:30 前今天不算最新交易日）
    _TODAY = datetime.date.today()
    _cn = trade_calendar.latest_trading_day('CN')
    _hk = trade_calendar.latest_trading_day('HK')
    CN_LATEST = _cn.isoformat() if _cn else None
    HK_LATEST = _hk.isoformat() if _hk else None
except Exception:
    CN_LATEST = HK_LATEST = None

# 额度不足「待补」的步骤（由 wind_client 写 .wind_pending.json）：
#   这些步骤产出的数据项本次豁免「新鲜度」校验（额度不足不失败，符合 update-redesign.md）。
def _load_pending():
    try:
        with io.open(os.path.join(BASE, '.wind_pending.json'), encoding='utf-8') as _f:
            return set(json.load(_f).get('steps') or [])
    except Exception:
        return set()

PENDING = _load_pending()


def _mkt_of_index(x):
    """指数所属日历市场：'港股' → HK；其余（沪深/沪市/深市/沪港深/未知）→ CN。
    market 缺失时按代码后缀兜底（.HI → HK）。"""
    mk = str(x.get('market') or '')
    if mk == '港股':
        return 'HK'
    if mk:
        return 'CN'
    return 'HK' if str(x.get('code') or '').endswith('.HI') else 'CN'


def _name_market(name):
    """按名称判定市场（用于 assetData 红利项——其无 market 字段）。"""
    return 'HK' if any(k in str(name) for k in ('港股', '香港', '恒生', 'HK')) else 'CN'


def _exp_for(mkt):
    """某市场当前应达到的最新交易日；日历不可用时回落数据合并最新日期（退化为原行为）。"""
    return (HK_LATEST if mkt == 'HK' else CN_LATEST) or latest


def _behind(d, exp):
    """d 落后 exp 的天数（d 早于 exp 为正；d 达到/超过 exp 为 0 或负）。解析失败返回 999。"""
    try:
        return (datetime.date.fromisoformat(str(exp)[:10])
                - datetime.date.fromisoformat(str(d)[:10])).days
    except Exception:
        return 999


def days_between(a, b):
    try:
        return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)
    except Exception:
        return 999

def jload(fn):
    try:
        with io.open(os.path.join(DATA, fn), encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        FAIL.append('[{}] 读取失败: {}'.format(fn, e))
        return None

def check(tag, ok, detail, step_label=None):
    # 若失败项对应的步骤本次「额度不足待补」，则只告警、不计入 FAIL（额度不足不失败）
    if not ok and step_label and step_label in PENDING:
        print('⚠️ {}: {}（步骤 {} 本次额度不足待补，已豁免）'.format(tag, detail, step_label))
        return True
    mark = '✅' if ok else '❌'
    print('{} {}: {}'.format(mark, tag, detail))
    if not ok:
        FAIL.append('{}: {}'.format(tag, detail))
    return ok

print('===== 食息指南 数据一致性验证 =====\n')

# 1. JSON 可解析 + 条数
specs = {
    'indexData.json': 40, 'cnEtfData.json': 80, 'hkEtfData.json': 10,
    'etfData.json': 14, 'fundData.json': 20, 'moneyFundData.json': 30,
    'reitsData.json': 40, 'assetData.json': 10, 'assetHistory.json': 1,
    'dailyData.json': 1, 'dailyTagColors.json': 9, 'yuebaoHistory.json': 1,
}
for fn, min_n in specs.items():
    d = jload(fn)
    if d is None:
        continue
    n = len(d) if isinstance(d, (list, dict)) else 0
    check(f'{fn} 条数', n >= min_n, f'{n} 条 (≥{min_n})')

# 2. divHistory 最新日期
idx = jload('indexData.json')
if idx:
    dates = []
    missing = []
    for x in idx:
        h = x.get('divHistory') or []
        if h:
            dates.append(h[-1].get('date', ''))
        elif not x.get('trackOnly'):
            # trackOnly（详情页图表补充的跟踪指数，2026-10-04）不进「红利指数浏览器」列表，不参与该计数
            missing.append(x.get('name', '?'))
    latest = max(dates) if dates else ''
    # 日历不可用 / 数据缺失时回落：CN、HK 均取合并最新日期（退化为原「合并口径」）
    if CN_LATEST is None:
        CN_LATEST = latest
    if HK_LATEST is None:
        HK_LATEST = latest
    check('divHistory 最新日期', bool(latest),
          f'{latest or "无数据"}（A股最新 {CN_LATEST} / 港股最新 {HK_LATEST}）')
    check('divHistory 缺失指数', len(missing) <= 3, f'{len(missing)} 个: {missing[:5]}')

# 3. assetData 红利指数 == 对应市场最新交易日（股息率非每日更新，允许滞后≤2天，2026-08-19）
#    2026-10-07：部分指数（尤其港股）股息率序列滞于其行情序列（行情已更新、股息率源滞后）——
#    这类「行情新、股息率旧」属数据源特性，不判滞后：容许日期 ∈ 该市场「行情时效达标指数」的股息率日期集合。
ad = jload('assetData.json')
if ad and dates:
    _tol = {'CN': set(), 'HK': set()}
    for _x in (idx or []):
        _h = _x.get('divHistory') or []
        if not _h:
            continue
        _m = _mkt_of_index(_x)
        _e = _exp_for(_m)
        _dd = _x.get('dailyDate') or ''
        if not _dd or _behind(_dd, _e) <= 2:
            _tol[_m].add(str(_h[-1].get('date', ''))[:10])
    red_bad = []
    for x in ad:
        if x.get('type') == '红利' and x.get('date'):
            _m = _name_market(x.get('name', ''))
            exp = _exp_for(_m)
            if _behind(x['date'], exp) > 2 and str(x['date'])[:10] not in _tol[_m]:
                red_bad.append((x.get('name'), x['date'], exp))
    check('assetData 红利指数 date == 对应市场最新交易日(允许滞后≤2天)', not red_bad,
          ('异常: %s' % red_bad) if red_bad else f'全部达标(CN {CN_LATEST} / HK {HK_LATEST})')

# 4/5/6. 余额宝相关
if ad:
    yb = next((x for x in ad if '余额宝' in x.get('name', '')), None)
    if yb:
        _y = yb.get('yield', '').rstrip('%')
        _frac = _y.split('.')[1] if '.' in _y else ''
        y2d = len(_frac) == 2
        check('assetData 余额宝 2 位小数', y2d, yb.get('yield', ''))
mf = jload('moneyFundData.json')
mf_date = ''
if mf:
    mf_yb = next((x for x in mf if '余额宝' in x.get('name', '')), None)
    if mf_yb:
        mf_date = mf_yb.get('yieldDate', '') or ''
        check('moneyFundData 余额宝 yieldDate', bool(mf_date), mf_date or '缺失!')
if ad and mf_date:
    yb2 = next((x for x in ad if '余额宝' in x.get('name', '')), None)
    if yb2:
        check('assetData 余额宝 date == yieldDate', yb2.get('date') == mf_date,
              f"assetData {yb2.get('date')} vs moneyFund {mf_date}")

# 7. divDate 覆盖率
for fn, th in [('fundData.json', 20), ('etfData.json', 14), ('cnEtfData.json', 50)]:
    d = jload(fn)
    if d is not None:
        n = len([x for x in d if x.get('divDate')])
        check(f'{fn} divDate 覆盖率', n >= th, f'{n}/{len(d)}')

# 7b. 月月名单连续性（2026-10-06 用户要求）：月月分红产品最近一次分红须在「上一个月」或更近；
#     超期成员应由 sync_fund_divdate.py prune_stale_monthly 自动剔除。此处为安全网——
#     若此检查失败，说明未跑 steps 14（剔除）就部署，名单里混入了已停止月月分红的成员。
_today = datetime.date.today()
_cutoff = datetime.date(_today.year - 1, 12, 1) if _today.month == 1 else datetime.date(_today.year, _today.month - 1, 1)
for fn in ('etfData.json', 'fundData.json'):
    d = jload(fn)
    if d is None:
        continue
    bad = []
    for x in d:
        dd = x.get('divDate')
        if not dd:
            continue
        try:
            if datetime.date.fromisoformat(str(dd)[:10]) < _cutoff:
                bad.append((x.get('code'), str(dd)[:10]))
        except ValueError:
            pass
    check(f'{fn} 月月名单无超期成员(最近分红≥{_cutoff.isoformat()})', not bad,
          ('超期: %s' % bad) if bad else '全部达标')

# 7c. 月月名单行结构完整性（2026-10-06 新增）：etfData/fundData 每行必须含站点 schema 全部字段。
#     目的：自动补入（sync_new_monthly）/ 表外行护栏写入时若漏字段，前端渲染会异常；此处兜底拦截。
_MONTHLY_KEYS = {
    'etfData.json': ['code', 'name', 'fundCompany', 'listedDate', 'divDate', 'fee', 'feeNum', 'totalDiv',
                     'annualDiv', 'annualDivAmt', 'monthlyDivAmt', 'price', 'cumDiv', 'trackCode',
                     'trackName', 'divTotalAmt', 'yield', 'yieldNum', 'taxRate', 'investMonthly'],
    'fundData.json': ['code', 'name', 'fundCompany', 'establishDate', 'divDate', 'fee', 'feeNum', 'annualDiv',
                      'annualDivAmt', 'monthlyDivAmt', 'nav', 'trackCode', 'trackName', 'fundSize',
                      'divTotalAmt', 'yield', 'yieldNum', 'taxRate', 'investMonthly'],
}
for fn, keys in _MONTHLY_KEYS.items():
    d = jload(fn) or []
    miss = [(x.get('code'), [k for k in keys if k not in x]) for x in d if any(k not in x for k in keys)]
    check(f'{fn} 行结构完整', not miss,
          ('缺字段: %s' % miss[:3]) if miss else f'{len(d)} 行齐备')

# 7d. 清单未含「停用名单」标的（2026-10-08 新增 · 防 _retired.json 的「出」成员被重建带回）。
#     与「进」机制（表外行护栏 + _auto_added）互为对手方：护栏只保留、停用剔除，此处确认最终 JSON 里
#     没有任何已停用 code 回灌（022097.OF 这类问题的安全网）。
try:
    with io.open(os.path.join(BASE, 'data', 'curation', '_retired.json'), encoding='utf-8') as _rf:
        _retired = (json.load(_rf) or {}).get('retired') or {}
except Exception:
    _retired = {}
for fn in ('cnEtfData.json', 'hkEtfData.json', 'etfData.json', 'fundData.json',
           'moneyFundData.json', 'reitsData.json'):
    d = jload(fn)
    if not d:
        continue
    _hit = [x.get('code') for x in d if x.get('code') in _retired]
    check(f'{fn} 未含停用名单标的', not _hit,
          ('仍含: %s' % _hit) if _hit else f'停用名单 {len(_retired)} 项均未回灌')

# 7e. 月月名单「分红日期为空」成员（信息项，**不计入 FAIL**，2026-10-08）。
#     022097 失守的根因正是「divDate 为空 → 7b 跳过 → 不被察觉」。此处显式列出，提示日更会
#     用 `sync_fund_divdate --monthly-empty` 补查；连续为空且确无分红时应走人工/停用，而非静默留在名单。
_any_empty = False
for fn in ('etfData.json', 'fundData.json'):
    d = jload(fn) or []
    _empty = [x.get('code') for x in d if not x.get('divDate')]
    if _empty:
        _any_empty = True
    print('{} {} 分红日期为空成员: {}'.format(
        'ℹ️' if _empty else '✅', fn,
        ('%d 只 %s（日更 --monthly-empty 会补查）' % (len(_empty), _empty[:8])) if _empty
        else '无'))
if _any_empty:
    print('   ↳ 提示：空 divDate 成员不参与 7b「超期」判定，需人工确认是否已停止月月分红。')

# 7f. 港交所 ETF 代码格式（5 位 + .HK，与中央库 fund.product.sec_code 对齐，2026-10-08 新增）。
#     2026-10-08 站内港股代码统一为 5 位；此项防回退（出现 4 位/非 .HK 即报错）。
_hk_list = jload('hkEtfData.json') or []
_bad_hk = [x.get('code') for x in _hk_list
           if x.get('code') and not (str(x.get('code')).endswith('.HK')
                                     and len(str(x.get('code'))) == 8
                                     and str(x.get('code'))[:5].isdigit())]
check('hkEtfData 代码为 5 位.HK', not _bad_hk,
      '异常: %s' % _bad_hk[:5] if _bad_hk else f'{len(_hk_list)} 只均为 5 位.HK')

# 8. dailyChange 日期（与 divHistory 合并最新一致；跨市场/源差异允许 ≤2 天，2026-10-07 放宽）
if idx:
    dc_dates = [x.get('dailyDate', '') for x in idx if x.get('dailyDate')]
    dc_latest = max(dc_dates) if dc_dates else ''
    check('dailyChange 最新日期(与 divHistory 最新一致·允许≤2天)',
          bool(dc_latest) and days_between(dc_latest, latest) <= 2,
          f'{dc_latest} vs divHistory {latest}')

# 9. yuebaoHistory 结构 + 日频
# assetHistory 各序列非空（sync_asset_macro 拉取失败不得清空，2026-08-11 确立）
ah = jload('assetHistory.json')
if ah and isinstance(ah, dict):
    ah_empty = [k for k, v in ah.items() if isinstance(v, list) and not v]
    check('assetHistory 无空序列', len(ah_empty) == 0, f'空序列: {ah_empty}' if ah_empty else f'{len(ah)} 个序列均非空')

yh = jload('yuebaoHistory.json')
if yh:
    s = yh.get('series') or []
    check('yuebaoHistory dict 结构', isinstance(yh, dict) and 'series' in yh, type(yh).__name__)
    yh_latest = s[-1].get('date', '') if s else ''
    # 余额宝 7 日年化按公布节奏滞后于指数行情（当日数据次日/收盘后公布），允许 ≤3 天
    yh_ok = False
    try:
        dt1 = datetime.datetime.strptime(yh_latest[:10], '%Y-%m-%d')
        dt2 = datetime.datetime.strptime(str(CN_LATEST)[:10], '%Y-%m-%d')
        yh_ok = 0 <= (dt2 - dt1).days <= 3
    except Exception:
        pass
    check('yuebaoHistory 最新日期(允许滞后≤3天)', yh_ok, f'{yh_latest} vs A股最新 {CN_LATEST}',
          step_label='sync_yuebao_history.py')
    # 起点检查：yuebaoHistory 起点必须早于 divHistory 起点（否则图表最长区间早期会无数据/假填充，2026-08-11 余额宝假平线 bug）
    yh_first = s[0].get('date', '') if s else ''
    # divHistory 最早日期（单独收集：dates 存的是最后日期）
    div_first = ''
    if idx:
        _firsts = []
        for x in idx:
            h = x.get('divHistory') or []
            if h:
                _firsts.append(h[0].get('date', ''))
        if _firsts:
            div_first = min(_firsts)
    yh_start_ok = False
    try:
        dt1 = datetime.datetime.strptime(yh_first[:10], '%Y-%m-%d')
        dt2 = datetime.datetime.strptime(div_first[:10], '%Y-%m-%d')
        yh_start_ok = dt1 <= dt2
    except Exception:
        pass
    check('yuebaoHistory 起点早于 divHistory 起点', yh_start_ok,
          f'yuebao {yh_first} vs div {div_first}')
    check('yuebaoHistory 日频条数', len(s) >= 200, f'{len(s)} 条')

# 10. divHistory 全覆盖：所有有 divHistory 的指数最后日期 == 其市场最新交易日（防单指数滞后漏检，2026-08-16）
#    2026-10-07 起按市场分别判定：A股系对照 A股日历、港股系对照港股日历（原「合并最新日期」在跨市场假期会误判）
if idx and dates:
    lag_div = []
    for x in idx:
        h = x.get('divHistory') or []
        if not h:
            continue
        exp = _exp_for(_mkt_of_index(x))
        dl = h[-1].get('date', '')
        dd = x.get('dailyDate') or ''
        # 滞后判据：股息率序列落后 >2 天，且该指数「行情」也落后 >2 天。
        #   行情仍新（如港股某指数行情到 10-06、股息率源只到 09-30）→ 视为源滞后，豁免；
        #   无 dailyDate 的 trackOnly 指数仅看股息率序列。
        if _behind(dl, exp) > 2 and (not dd or _behind(dd, exp) > 2):
            lag_div.append((x.get('name', '?'), dl, exp))
    check('divHistory 全覆盖(按市场·允许滞后≤2天)', len(lag_div) == 0,
          f'{len(lag_div)} 个滞后: {lag_div[:5]}' if lag_div else f'{len(idx) - len(missing)} 个指数均到各自市场最新日',
          step_label='sync_div_history.py')

# 11. dailyChange 全覆盖：所有有 divHistory 的指数 dailyDate 应达其市场最新交易日（允许滞后≤2天）
#     2026-10-07 起按市场分别判定（沿用 check 10 口径；仍可拦截 932584 类多日停滞）。
if idx and dates:
    lag_dc = [(x.get('name', '?'), x.get('dailyDate') or '—', _exp_for(_mkt_of_index(x))) for x in idx
              if x.get('divHistory') and not x.get('trackOnly')
              and _behind(x.get('dailyDate') or '', _exp_for(_mkt_of_index(x))) > 2]
    check('dailyChange 全覆盖(按市场·允许滞后≤2天)', len(lag_dc) == 0,
          f'{len(lag_dc)} 个滞后: {lag_dc[:5]}' if lag_dc else f'{len(idx) - len(missing)} 个指数均到各自市场最新日',
          step_label='sync_daily_change.py')

# 12. assetHistory 日频序列最新日期（余额宝/REITs 允许 ≤3 天；LPR/整存整取/预定利率/租金率/同业存单 等周频月度手动序列豁免）
#     国债为**周频**（储蓄国债发行票面利率，每周五采样 + 前向填充，见 wind-query-tips.md §H）：
#     其最新日期应为「divHistory 最新日期之前最近的那个周五」，不能按日频 ≤3 天判等——
#     否则当最新交易日不是周五（如节前最后交易日落在周三）时会误报滞后（2026-10-01 修订）。
if ah and isinstance(ah, dict):
    def _last_friday(dstr):
        try:
            _dt = datetime.date.fromisoformat(str(dstr)[:10])
            return (_dt - datetime.timedelta(days=(_dt.weekday() - 4) % 7)).isoformat()
        except Exception:
            return None
    for _k in ('3年期储蓄国债', '5年期储蓄国债', '天弘余额宝', 'REITs产权类', 'REITs特许经营权类'):
        _v = ah.get(_k)
        if not isinstance(_v, list) or not _v:
            continue
        _last = _v[-1].get('date', '') if isinstance(_v[-1], dict) else str(_v[-1])[:10]
        if _k.endswith('国债'):
            # 国债为周频（储蓄国债票面利率，每周五采样 + 前向填充）：序列随「运行日」前向填充，
            # 可能领先于 A股日历（如 A股休市期间仍填到当周周五）→ 期望取「数据最新日之前最近周五」。
            _exp = _last_friday(latest)
            _ok = _exp is not None and str(_last)[:10] == _exp
            check(f'assetHistory {_k} 最新日期(周频·最近周五)', _ok, f'{_last} vs 期望周五 {_exp}',
                  step_label='sync_asset_macro.py')
            continue
        _ok = False
        try:
            _ok = 0 <= (datetime.datetime.strptime(str(CN_LATEST)[:10], '%Y-%m-%d')
                        - datetime.datetime.strptime(str(_last)[:10], '%Y-%m-%d')).days <= 3
        except Exception:
            pass
        check(f'assetHistory {_k} 最新日期', _ok, f'{_last} vs A股最新 {CN_LATEST}',
              step_label='sync_asset_macro.py')

# 13. reitsDaily 每只 REITs 最后日期（日频缓存全覆盖，允许 ≤5 只滞后；停牌/无成交豁免，2026-08-16 新增）
rd = jload('reitsDaily.json')
if rd and isinstance(rd, dict):
    codes = rd.get('codes') or {}
    lag_r = []
    for code, info in codes.items():
        ser = info.get('series') or {}
        if ser and days_between(max(ser.keys()), CN_LATEST) > 2:
            lag_r.append((code, max(ser.keys())))
    check('reitsDaily 全覆盖(允许滞后≤2天)', len(lag_r) <= 5,
          f'{len(lag_r)}/{len(codes)} 只滞后: {lag_r[:5]}' if lag_r else f'{len(codes)} 只均到 A股最新 {CN_LATEST}',
          step_label='sync_reits_daily.py')

# 14. yieldNum 单位校验（indexData/etfData/fundData 百分数约定 4.2756=4.28%，2026-08-16）
for _fn in ('indexData.json', 'etfData.json', 'fundData.json'):
    _d = jload(_fn) or []
    _bad = [x.get('name') for x in _d if x.get('yieldNum') and not (0.5 <= x['yieldNum'] <= 30)]
    check('yieldNum 单位(' + _fn + ')', not _bad, '异常: ' + str(_bad[:5]) if _bad else '百分数口径 ✅')

# 15. cnEtfData feeNum 单位校验（小数约定 0.0015=0.15%，2026-09-13 新增，防 sync_new_etf 写入百分数）
_cn = jload('cnEtfData.json') or []
_bad_fee = [x.get('code') for x in _cn
            if isinstance(x.get('feeNum'), (int, float)) and x['feeNum']
            and not (0.0005 <= x['feeNum'] <= 0.02)]
check('cnEtfData feeNum 单位(小数 0.0015=0.15%)', not _bad_fee,
      '异常: ' + str(_bad_fee[:5]) if _bad_fee else '小数口径 ✅')

# 16. dailyData 正文不含【】强调符号（2026-09-20 用户要求：今后不再添加；消费端已在 sync_daily.py 归一化）
_dd = jload('dailyData.json') or []
_marked = []
for _d in (_dd if isinstance(_dd, list) else []):
    for _it in (_d.get('items') or []):
        if isinstance(_it.get('text'), str) and ('【' in _it['text'] or '】' in _it['text']):
            _marked.append(_it.get('id'))
check('dailyData 正文无【】符号', not _marked,
      '异常条目: ' + str(_marked[:5]) if _marked else '无【】✅')

# 17. 指数币种变体归并（2026-09-20 用户要求 · 数据治理）
#     站内任何 trackCode 都不得是「变体版」（港币/人民币折算版），一律须为「基准版」
#     —— 同一指数的两个币种版本不得在站内并列出现（映射见 index_variants.py）
try:
    from index_variants import VARIANT_TO_BASE
    _bad_var = []
    for _fn in ('cnEtfData.json', 'etfData.json', 'fundData.json', 'hkEtfData.json', 'indexData.json'):
        for _x in (jload(_fn) or []):
            _tc = str(_x.get('trackCode') or '')
            if _tc in VARIANT_TO_BASE:
                _bad_var.append('%s:%s(%s→%s)' % (_fn.split('.')[0], _x.get('code'), _tc, VARIANT_TO_BASE[_tc]))
    check('指数币种变体已归并(无港币/人民币重复版)', not _bad_var,
          '未归并: ' + str(_bad_var[:5]) if _bad_var else '%d 组映射生效 ✅' % len(VARIANT_TO_BASE))
except ImportError as _e:
    check('指数币种变体已归并(无港币/人民币重复版)', False, 'index_variants.py 缺失: %s' % _e)

# 18. 前端 JS 语法（防「字符串字面替换引入引号错误」类回归）
#     2026-10-04：v0.1.96 空格治理曾把 mobile.js 的字符串多写一个引号 → mobile.js 解析失败
#     → 移动层（汉堡/抽屉/卡片）整层不初始化、手机端回退桌面导航。
#     本项用 node --check 校验 mobile.js 与 index.html 的全部内联 <script>。
import subprocess, re as _re, tempfile


def _js_syntax_ok(code):
    fd, p = tempfile.mkstemp(suffix='.js')
    os.close(fd)
    try:
        with io.open(p, 'w', encoding='utf-8') as f:
            f.write(code)
        r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
        return (r.returncode == 0), (r.stderr or '').strip()
    except FileNotFoundError:
        return True, 'node 不可用，跳过'
    finally:
        try:
            os.remove(p)
        except OSError:
            pass


_js_errs = []
try:
    with io.open(os.path.join(BASE, 'mobile.js'), encoding='utf-8') as _f:
        _ok, _e = _js_syntax_ok(_f.read())
        if not _ok:
            _js_errs.append('mobile.js: ' + (_e.splitlines()[0] if _e else ''))
except Exception as _e:
    _js_errs.append('mobile.js 读取失败: %s' % _e)
try:
    with io.open(os.path.join(BASE, 'index.html'), encoding='utf-8') as _f:
        _html = _f.read()
    for _i, _m in enumerate(_re.finditer(r'<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>', _html, _re.I), 1):
        _code = _m.group(1)
        if not _code.strip():
            continue
        _ok, _e = _js_syntax_ok(_code)
        if not _ok:
            _js_errs.append('index.html inline #%d: %s' % (_i, (_e.splitlines()[0] if _e else '')))
except Exception as _e:
    _js_errs.append('index.html 读取失败: %s' % _e)
check('前端 JS 语法(mobile.js + index.html 内联)', not _js_errs,
      ' | '.join(_js_errs[:3]) if _js_errs else '全部通过 ✅')

# 19. 红利机会值（A股）数据（2026-10-08 模块并入主站）：页面由 #subOpportunity + opportunity-page.js 渲染，
#     数据由 opportunity_engine.py 生成（周更）。此处校验结构完整性；新鲜度只提示、不判失败（周更节奏下滞后属正常）。
_op = jload('opportunity.json')
if _op is not None:
    _o_ser = _op.get('series') or {}
    _o_d = _o_ser.get('d') or []
    _o_v = _o_ser.get('v') or []
    _o_p = _o_ser.get('p') or []
    check('opportunity.json schema', _op.get('schema') == 'dividend-opportunity/v1', str(_op.get('schema')))
    _o_asof_ok = False
    try:
        datetime.date.fromisoformat(str(_op.get('asof'))[:10])
        _o_asof_ok = True
    except Exception:
        pass
    check('opportunity.json asof 有效日期', _o_asof_ok, str(_op.get('asof')))
    check('opportunity.json 机会值 0–100',
          isinstance(_op.get('score'), (int, float)) and 0 <= _op['score'] <= 100, str(_op.get('score')))
    check('opportunity.json 序列完整(周频)',
          len(_o_d) >= 50 and len(_o_d) == len(_o_v) == len(_o_p), '周数=%d' % len(_o_d))
    _o_keys = ('schema', 'index', 'score', 'compare', 'core', 'bands', 'observe', 'method', 'series')
    _o_miss = [k for k in _o_keys if k not in _op]
    check('opportunity.json 字段齐备', not _o_miss, ('缺: %s' % _o_miss) if _o_miss else 'ok')
    if _op.get('asof') and CN_LATEST:
        print('ℹ️ opportunity.json 数据截至 {}（较 A 股最新交易日 {} 滞后 {} 天；周更节奏下滞后属正常）'.format(
            _op['asof'], CN_LATEST, _behind(_op['asof'], CN_LATEST)))

print('\n===== 结果 =====')
if FAIL:
    print('❌ {} 项未通过：'.format(len(FAIL)))
    for f in FAIL:
        print('  -', f)
    sys.exit(1)
else:
    print('✅ 全部通过，可以部署')

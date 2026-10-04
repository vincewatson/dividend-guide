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

import datetime

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

def check(tag, ok, detail):
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
        else:
            missing.append(x.get('name', '?'))
    latest = max(dates) if dates else ''
    check('divHistory 最新日期', bool(latest), latest or '无数据')
    check('divHistory 缺失指数', len(missing) <= 3, f'{len(missing)} 个: {missing[:5]}')

# 3. assetData 红利指数 == divHistory 最新
ad = jload('assetData.json')
if ad and dates:
    red_dates = [x['date'] for x in ad if x.get('type') == '红利' and x.get('date')]
    red_ok = all(days_between(d, latest) <= 2 for d in red_dates)   # 股息率非每日更新，允许滞后≤2天（2026-08-19 调整）
    check('assetData 红利指数 date == divHistory 最新(允许滞后≤2天)', red_ok,
          f'{sorted(set(red_dates))} vs divHistory {latest}')

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
for fn, th in [('fundData.json', 25), ('etfData.json', 14), ('cnEtfData.json', 50)]:
    d = jload(fn)
    if d is not None:
        n = len([x for x in d if x.get('divDate')])
        check(f'{fn} divDate 覆盖率', n >= th, f'{n}/{len(d)}')

# 8. dailyChange 日期
if idx:
    dc_dates = [x.get('dailyDate', '') for x in idx if x.get('dailyDate')]
    dc_latest = max(dc_dates) if dc_dates else ''
    check('dailyChange 最新日期', dc_latest == latest, f'{dc_latest} vs divHistory {latest}')

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
        dt2 = datetime.datetime.strptime(latest[:10], '%Y-%m-%d')
        yh_ok = 0 <= (dt2 - dt1).days <= 3
    except Exception:
        pass
    check('yuebaoHistory 最新日期(允许滞后≤3天)', yh_ok, f'{yh_latest} vs divHistory {latest}')
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

# 10. divHistory 全覆盖：所有有 divHistory 的指数最后日期 == 最新交易日（防单指数滞后漏检，2026-08-16 新增）
if idx and dates:
    lag_div = [(x.get('name', '?'), x['divHistory'][-1].get('date', '')) for x in idx
               if x.get('divHistory') and days_between(x['divHistory'][-1].get('date', ''), latest) > 2]
    check('divHistory 全覆盖(允许滞后≤2天)', len(lag_div) == 0,
          f'{len(lag_div)} 个滞后: {lag_div[:5]}' if lag_div else f'{len(idx) - len(missing)} 个指数均到 {latest}')

# 11. dailyChange 全覆盖：所有有 divHistory 的指数 dailyDate 应达最新交易日（允许滞后≤2天）
#     2026-09-26 调整：跨市场日历周（如 A股中秋休市、港股照常开市）两市场最新交易日相差 1 天属正常，
#     原「== latest」会把 A股指数（09-24）全部误判为滞后；改为与 divHistory 一致的 ≤2 天容差（仍可拦截 932584 类多日停滞）。
if idx and dates:
    lag_dc = [(x.get('name', '?'), x.get('dailyDate') or '—') for x in idx
              if x.get('divHistory') and days_between(x.get('dailyDate') or '', latest) > 2]
    check('dailyChange 全覆盖(允许滞后≤2天)', len(lag_dc) == 0,
          f'{len(lag_dc)} 个滞后: {lag_dc[:5]}' if lag_dc else f'{len(idx) - len(missing)} 个指数均到 {latest}')

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
    for _k in ('3年期国债', '5年期国债', '天弘余额宝', 'REITs产权类', 'REITs特许经营权类'):
        _v = ah.get(_k)
        if not isinstance(_v, list) or not _v:
            continue
        _last = _v[-1].get('date', '') if isinstance(_v[-1], dict) else str(_v[-1])[:10]
        if _k.endswith('国债'):
            _exp = _last_friday(latest)
            _ok = _exp is not None and str(_last)[:10] == _exp
            check(f'assetHistory {_k} 最新日期(周频·最近周五)', _ok, f'{_last} vs 期望周五 {_exp}')
            continue
        _ok = False
        try:
            _ok = 0 <= (datetime.datetime.strptime(latest[:10], '%Y-%m-%d')
                        - datetime.datetime.strptime(str(_last)[:10], '%Y-%m-%d')).days <= 3
        except Exception:
            pass
        check(f'assetHistory {_k} 最新日期', _ok, f'{_last} vs divHistory {latest}')

# 13. reitsDaily 每只 REITs 最后日期（日频缓存全覆盖，允许 ≤5 只滞后；停牌/无成交豁免，2026-08-16 新增）
rd = jload('reitsDaily.json')
if rd and isinstance(rd, dict):
    codes = rd.get('codes') or {}
    lag_r = []
    for code, info in codes.items():
        ser = info.get('series') or {}
        if ser and days_between(max(ser.keys()), latest) > 2:
            lag_r.append((code, max(ser.keys())))
    check('reitsDaily 全覆盖(允许滞后≤2天)', len(lag_r) <= 5,
          f'{len(lag_r)}/{len(codes)} 只滞后: {lag_r[:5]}' if lag_r else f'{len(codes)} 只均到 {latest}')

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

print('\n===== 结果 =====')
if FAIL:
    print('❌ {} 项未通过：'.format(len(FAIL)))
    for f in FAIL:
        print('  -', f)
    sys.exit(1)
else:
    print('✅ 全部通过，可以部署')

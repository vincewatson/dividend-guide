#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
食息指南 数据重建脚本（原 sync_excel；excel-exit P3 后更名为 build_lists）
====================================
从 data/curation/*.json（清单 + 标注）+ 其它 data/*.json 重建 8 个站点数据文件。
脚本**不读任何 Excel**（excel-exit P0→P3 已完成；原 xlsx 已归档 archive/excel-baseline-*）。

用法:
    python3 build_lists.py     # 由 auto_sync_deploy.sh 步骤 4 / 11 调用

数据源（仓库内、git 版本化；本脚本不再读任何 xlsx）:
    data/curation/assets.json                             → assetData（首页总表）
    data/curation/indices_pro.json                        → indexData（境内红利指数清单）
    data/curation/indices_main.json                        → indexData（主表红利指数补充）
    data/curation/indices_feishu_info.json / _yield.json   → indexData（用户标注：详情页/加权/调整周期/税系数…）
    data/curation/cn_etf.json                              → cnEtfData
    data/curation/hk_etf_pro.json                          → hkEtfData（清单）
    data/curation/hk_etf_feishu.json                       → hkEtfData（用户标注：详情页/互联互通）
    data/curation/monthly_etf.json                         → etfData
    data/curation/monthly_fund.json                        → fundData
    data/curation/money_fund.json                          → moneyFundData
    data/curation/reits_equity.json / reits_concession.json→ reitsData

用户标注优先机制（重要）:
    curation 里的「用户标注」（indices_feishu_info / indices_feishu_yield / hk_etf_feishu）优先于
    Wind 清单值：详情页、加权方式（附加条件）、样本调整周期/生效日、目标市场、成分个数、股息率、
    港股红利税系数、互联互通、跟踪指数… 以标注为准；清单表仅补充标注没有的字段/标的。

港股红利税系数规则（重要）:
    优先读标注「红利指数股息率」的税系数列（手动整理，可信）；
    标注没有的按名称智能识别：名称含「港股」或「沪港深」→ 0.8，其他 → 1.0。

输出:
    data/*.json    (index.html 通过 fetch 加载)
"""
import os, io, json, math, datetime

# 指数币种变体归并（数据治理 · 单一事实来源；见 index_variants.py 顶部说明）
# 用户口径（2026-09-20）：同一指数的港币/人民币两版站内只保留一条，取「基准版」，不并列。
from index_variants import normalize as iv_norm

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')

# ── 清单 + 标注来源：data/curation/*.json（excel-exit P2，2026-10-06）────────────────
# 本脚本不再读任何 xlsx：清单与用户「个性化标注 / 口径修正」统一来自仓库内、git 版本化的
# curation JSON（由一次性迁移工具 export_curation.py 从原 Excel 冻结而来，之后手工维护）。
# 各 builder 按【列名】取值 —— 消除「按列下标取值」的隐性契约（backlog B-1）。
CURATION_DIR = os.path.join(DATA_DIR, 'curation')


def load_curation(name):
    """读取 data/curation/<name>.json（整个对象）。缺失/损坏返回 None。"""
    path = os.path.join(CURATION_DIR, name)
    if not os.path.exists(path):
        print('[WARN] curation 文件缺失:', name)
        return None
    try:
        with io.open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('[WARN] curation 读取失败 %s: %s' % (name, e))
        return None


def curation_rows(name):
    """返回 curation JSON 的行列表（dict 列表，键=列名）。"""
    obj = load_curation(name)
    return (obj or {}).get('rows') or []


def curation_cols(name):
    """返回 curation JSON 的列名列表（用于动态列检测）。"""
    obj = load_curation(name)
    return (obj or {}).get('columns') or []


def curation_snapshot_date(name):
    """curation 来源快照日期（= 原 xlsx mtime 的日期部分 YYYY-MM-DD），用于 sizeDate。"""
    obj = load_curation(name) or {}
    sm = str(obj.get('sourceMtime') or '')[:10]
    return sm or None


def _find_col(cols, names):
    """按列名查找列（动态检测 curation 列），找不到返回 None。"""
    for c in cols:
        for n in names:
            if c and n in str(c):
                return c
    return None


# 「停用名单」（excel-exit 机制 B，2026-10-06）：sync_lifecycle.py 依 Wind「基金到期日」
#   （≤ 今天 = 已结束）写入 data/curation/_retired.json；重建时跳过这些 code（历史数据不删）。
#   适用于：境内红利ETF / 港交所红利ETF / REITs / 货币基金。
_RETIRED_KEYS = ('cnEtfData', 'hkEtfData', 'reitsData', 'moneyFundData')


def load_retired_codes():
    """读取 data/curation/_retired.json 的 stopped code 集合。缺失/损坏 → 空集合。"""
    try:
        with io.open(os.path.join(CURATION_DIR, '_retired.json'), 'r', encoding='utf-8') as f:
            obj = json.load(f)
        return set((obj.get('retired') or {}).keys())
    except Exception:
        return set()


# 「规模 as-of 日期」的来源 curation 文件（= 原 Excel 快照的等价物）：
# 用于 sizeDate —— 清单来源快照日期（冻结在 curation 的 sourceMtime）。
_SIZE_ASOF = {
    'cnEtfData': 'cn_etf.json',
    'hkEtfData': 'hk_etf_pro.json',
    'etfData': 'monthly_etf.json',
    'fundData': 'monthly_fund.json',
    'moneyFundData': 'money_fund.json',
}


def load_user_index_info():
    """加载用户标注「红利指数信息表 / 红利指数股息率」：以指数代码为键，用户标注优先。
    来源：data/curation/indices_feishu_info.json + indices_feishu_yield.json（原飞书表）。"""
    info, div = {}, {}   # code -> {字段: 值}
    # ① 指数股息率表（股息率/港股红利税系数/每月千元分红需总投入）—— 先加载，供 ② 并入
    for row in curation_rows('indices_feishu_yield.json'):
        code = clean_code(row.get('指数代码'))
        if not code:
            continue
        _im = clean_num(row.get('每月千元分红需总投入（万元）'))
        div[code] = {
            'yieldNum': round(clean_num(row.get('股息率')), 4) if clean_num(row.get('股息率')) else 0.0,
            'taxRate': clean_num(row.get('港股红利税系数'), 1),
            'investMonthly': round(_im, 2) if _im else 0.0,
        }
    # ② 指数信息表（全称/发布机构/发布日期/成分个数/目标市场/加权方式/加权附加条件/调整周期/
    #    调整生效日/股息率/详情页）—— 详情页在原 Excel 里是 HYPERLINK 公式，导出时已解析为 URL。
    for row in curation_rows('indices_feishu_info.json'):
        code = clean_code(row.get('指数代码'))
        if not code:
            continue
        info[code] = {
            'name': clean_str(row.get('指数名称')) or '',
            'fullname': clean_str(row.get('指数全称')) or '',
            'publisher': clean_str(row.get('发布机构')) or '',
            'listedDate': date_str(row.get('发布日期')),
            'components': int(clean_num(row.get('成分个数'))) if clean_num(row.get('成分个数')) else 0,
            'market': clean_str(row.get('目标市场')) or '',
            'weight': clean_str(row.get('加权方式')),
            'weightExtra': clean_str(row.get('加权方式（附加条件）')),
            'adjustCycle': clean_str(row.get('样本调整周期')),
            'adjustDate': clean_str(row.get('样本调整生效日')),
            'yieldNum': round(clean_num(row.get('股息率')), 4) if clean_num(row.get('股息率')) else 0.0,
            'detailUrl': clean_str(row.get('详情页')) or '',
        }
        if code in div:              # 与迁移前一致：股息率表字段并入 info（税系数/每月投入）
            info[code].update(div[code])
    print('[INFO] 用户标注已加载(curation): 红利指数信息表 {} 条, 股息率 {} 条'.format(len(info), len(div)))
    return info, div



# 常用繁转简映射（Wind 源数据为繁体，网站统一显示简体）
TRAD2SIMPLE = {
    '紅': '红', '綠': '绿', '藍': '蓝', '恆': '恒', '證': '证', '務': '务',
    '幣': '币', '際': '际', '項': '项', '資': '资', '產': '产', '規': '规',
    '滙': '汇', '環': '环', '經': '经', '營': '营', '聯': '联', '費': '费',
    '報': '报', '過': '过', '門': '门', '戶': '户', '網': '网', '國': '国',
    '亞': '亚', '灣': '湾', '總': '总', '淨': '净', '額': '额', '億': '亿',
    '萬': '万', '數': '数', '據': '据', '業': '业', '績': '绩', '專': '专',
    '條': '条', '約': '约', '質': '质', '優': '优', '選': '选', '動': '动',
    '態': '态', '從': '从', '來': '来', '東': '东', '華': '华', '時': '时',
    '電': '电', '視': '视', '訊': '讯', '聞': '闻', '賣': '卖', '買': '买',
    '託': '托', '價': '价', '單': '单', '雙': '双', '統': '统', '計': '计',
    '標': '标', '識': '识', '風': '风', '險': '险', '評': '评', '級': '级',
    '貨': '货', '責': '责', '權': '权', '應': '应', '當': '当', '發': '发',
    '佈': '布', '稱': '称', '於': '于', '與': '与', '為': '为', '匯': '汇',
    '優': '优', '質': '质', '庫': '库', '倉': '仓', '賬': '账', '戶': '户',
    '顯': '显', '示': '示', '幣': '币', '淨': '净', '產': '产', '務': '务',
    '導': '导', '航': '航', '頁': '页', '欄': '栏', '資': '资', '訊': '讯',
}

def to_simple(s):
    """繁转简（对名称/文本字段应用，Wind 源数据为繁体）"""
    if s is None:
        return s
    t = str(s)
    for k, v in TRAD2SIMPLE.items():
        t = t.replace(k, v)
    return t


def norm_hk_name(s):
    """港交所ETF名称繁简归一化（飞书表用户可能用简体，Wind 用繁体）"""
    return to_simple(s).strip() if s else ''


def load_user_hk_etf():
    """加载用户标注「港交所红利ETF」：以ETF简称为键（归一化后）。
    来源：data/curation/hk_etf_feishu.json（原飞书表）。"""
    out = {}
    for row in curation_rows('hk_etf_feishu.json'):
        name = norm_hk_name(clean_str(row.get('ETF简称')))
        if not name:
            continue
        out[name] = {
            'fullname': clean_str(row.get('ETF全称')) or '',
            'detailUrl': clean_str(row.get('详情页')),          # 官方详情页（curation 第3列）
            'connect': clean_str(row.get('互联互通ETF')) == '是',
            'trackCode': clean_code(row.get('跟踪指数代码')),
            'trackName': clean_str(row.get('跟踪指数名称')),
            'manager': clean_str(row.get('基金管理人')),
            'listedDate': date_str(row.get('成立日期')),
            'fee': clean_num(row.get('管理费率')),
            'size': round(clean_num(row.get('管理规模(亿港元)')), 2),
            'divDate': date_str(row.get('最近分红日期')),
        }
    print('[INFO] 用户标注已加载(curation): 港交所红利ETF {} 条'.format(len(out)))
    return out


def clean_code(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip().replace('\t', '').replace('\u3000', '').upper()
    return s if s else None


def clean_str(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip().replace('\t', '').replace('\u3000', '')
    return s if s else None


def clean_num(v, default=0):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def pct_str(v, default='0.00%'):
    try:
        f = float(v)
        if math.isnan(f):
            return default
        return '{:.2f}%'.format(f * 100)
    except (ValueError, TypeError):
        return default


def date_str(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    if hasattr(v, 'strftime'):  # pd.Timestamp / datetime.datetime / datetime.date
        return v.strftime('%Y-%m-%d')
    if isinstance(v, str):
        v = v.strip()
        if not v or v == 'nan':
            return None
        return v[:10]
    return None


def smart_tax_rate(name):
    """按名称智能识别港股红利税系数：含「港股」/「沪港深」→ 0.8，其余 → 1.0"""
    s = clean_str(name) or ''
    if ('港股' in s) or ('沪港深' in s):
        return 0.8
    return 1.0


# 非指数类资产的指标详情介绍（静态说明，不随行情变化）
ASSET_DESC = {
    '5年期LPR': '贷款市场报价利率，由报价行报价计算得出，是银行对最优质客户贷款利率的基准，每月20日公布。',
    '3年期储蓄国债': '财政部面向个人发行的储蓄国债（凭证式/电子式），3年期，票面利率在发行时确定、存续期内固定不变，按年付息、到期还本，是风险极低的固定收益品种。',
    '5年期储蓄国债': '财政部面向个人发行的储蓄国债（凭证式/电子式），5年期，票面利率在发行时确定、存续期内固定不变，按年付息、到期一次还本，适合长期稳健配置。',
    '1年期整存整取': '银行整存整取定期存款，1年期，到期一次性还本付息，受存款保险制度保障，收益稳定。',
    '3年期整存整取': '银行整存整取定期存款，3年期，到期一次性还本付息，利率高于1年期，流动性相对较低。',
    '人身保险产品预定利率研究值': '监管部门发布的人身保险产品预定利率研究参考值，用于引导年金险、增额寿险等产品的预定利率定价。',
    '中证同业存单AAA指数': '中证同业存单AAA指数（931059.CSI）月度年化收益率。同业存单为银行在银行间市场发行的短期存款凭证，AAA 级为最高信用等级，波动小、流动性好，收益贴近货币市场利率水平。',
    '重点50城租金率': '重点50个大中城市二手住宅租金回报率，即年租金与房价之比，反映房产长期持有的现金流收益水平。',
    'REITs特许经营权类': '以高速公路、新能源、生态环保、水利等基础设施为底层资产的特许经营权类公募REITs，现金流为有限期经营权属性，派息含资产摊销对应的本金返还。该指标取自Wind月度名义派息率，用全部特许经营权类REITs的中位数表示，反映该类资产的整体派息水平。',
    'REITs产权类': '以园区、仓储物流、消费、保障房等不动产为底层资产的产权类公募REITs，持有资产产权，收益来自租金及运营收入。该指标取自Wind月度名义派息率，用全部产权类REITs的中位数表示，反映该类资产的整体派息水平。',
    '天弘余额宝': '天弘基金管理的货币市场基金，对接支付宝余额宝，资金灵活可取，收益随市场利率浮动。',
}


# 国债条目覆盖：Excel 里是旧的「储蓄国债」票息（财政部），
# 网站改用 Wind（万得）债券发行记录的储蓄国债票面利率（sync_asset_macro.py fetch_bond_savings，周频）。
# 同步时用 assetHistory.json 最新值覆盖，避免 Excel 旧数据回退覆盖。
# 来源统一标注 Wind（2026-10-04 用户要求：数据每次只从一个源取，不再写「Wind/iFind」）。
BOND_OVERRIDE = {
    '3年期储蓄国债': ('3年期储蓄国债', '1.63%', '2026-10-02', '储蓄国债票面利率', 'Wind'),
    '5年期储蓄国债': ('5年期储蓄国债', '1.70%', '2026-10-02', '储蓄国债票面利率', 'Wind'),
}


# 通用覆盖名单：列表值取 assetHistory 最新（2026-08-15 用户确认，Excel 快照旧值不覆盖）
# 不含：国债(BOND_OVERRIDE)/红利指数(divHistory)/货币基金(moneyFundData)/REITs(日频)/重点50城租金率(用户手动维护)
HIST_COVER_NAMES = {'5年期LPR', '3年期整存整取', '1年期整存整取',
                    '人身保险产品预定利率研究值', '中证同业存单AAA指数'}
# 指标说明覆盖：Excel 备注列不准确时强制（2026-08-15）
NOTE_OVERRIDE = {'中证同业存单AAA指数': '中证同业存单AAA指数月度年化收益率'}


# 手工补加资产（用户在对话中告知，登记于 docs/data-governance/manual-overrides.md）。
# 这些条目不在 Excel 总表内；重建时按 type 追加到同组末尾，数值取 indexData divHistory 最新值。
# 落地方式 = B（代码硬编码），保证每周整表重建不被冲掉。
# 2026-10-06：加「红利低波」（H30269.CSI，中证红利低波动指数），与既有 5 条红利指数并列。
EXTRA_ASSETS = [
    {'type': '红利', 'name': '红利低波', 'note': '近12个月股息率'},
]



def build_asset_data():
    rows = []
    # 尝试从 assetHistory.json 读取国债最新值（更准确）
    bond_latest = {}
    hist_path = os.path.join(DATA_DIR, 'assetHistory.json')
    if os.path.exists(hist_path):
        try:
            with io.open(hist_path, 'r', encoding='utf-8') as f:
                hist = json.load(f)
            for k in ['3年期储蓄国债', '5年期储蓄国债']:
                h = hist.get(k) or []
                if h:
                    bond_latest[k] = (h[-1]['date'], round(h[-1]['yield'], 4))
        except Exception:
            pass
    # assetData 名称 → indexData 名称 显式映射（名称不一致但指向同一指数）
    ASSET_INDEX_NAME_MAP = {
        '上证国企红利': '上国红利',
        '香港银行': 'HK银行(HKD)',
        '港股通央企红利': '港股通央企红利',
        '中证红利': '中证红利',
        '中证银行': '中证银行',
    }
    # 红利指数股息率覆盖：优先 indexData.json divHistory 最新值（Wind 口径最新）
    index_latest = {}
    index_path = os.path.join(DATA_DIR, 'indexData.json')
    if os.path.exists(index_path):
        try:
            with io.open(index_path, 'r', encoding='utf-8') as f:
                idata = json.load(f)
            for item in idata:
                h = item.get('divHistory') or []
                if h and h[-1].get('yield'):
                    index_latest[item['name']] = (h[-1]['date'], float(h[-1]['yield']))
        except Exception:
            pass
    # 货币基金（天弘余额宝）覆盖：moneyFundData.json 由 sync_money_fund.py 实时更新（Wind），
    # Excel 快照里的 7 日年化是导出时旧值（会滞后）。date 优先 yieldDate，缺省用 yuebaoHistory 最新日期。
    money_latest = {}
    mf_path = os.path.join(DATA_DIR, 'moneyFundData.json')
    if os.path.exists(mf_path):
        try:
            with io.open(mf_path, 'r', encoding='utf-8') as f:
                for mf in json.load(f):
                    if mf.get('yield7dNum'):
                        money_latest[mf['name']] = mf
        except Exception:
            pass
    # assetHistory 最新值覆盖：REITs（日频中位数） + 通用序列（2026-08-15 用户确认）
    reits_latest = {}
    hist_latest = {}
    if os.path.exists(hist_path):
        try:
            with io.open(hist_path, 'r', encoding='utf-8') as f:
                hist = json.load(f)
            for k in ['REITs产权类', 'REITs特许经营权类']:
                h = hist.get(k) or []
                if h:
                    reits_latest[k] = (h[-1]['date'], round(h[-1]['yield'], 4))
            # 通用序列：整存整取/LPR/预定利率/同业存单 列表值取 assetHistory 最新（用户确认，2026-08-15）
            for k in HIST_COVER_NAMES:
                h = hist.get(k) or []
                if h:
                    hist_latest[k] = (h[-1]['date'], round(h[-1]['yield'], 4))
        except Exception:
            pass
    yuebao_latest_date = ''
    yh_path = os.path.join(DATA_DIR, 'yuebaoHistory.json')
    if os.path.exists(yh_path):
        try:
            with io.open(yh_path, 'r', encoding='utf-8') as f:
                yh = json.load(f)
            s = yh.get('series') or []
            if s:
                yuebao_latest_date = s[-1]['date']
        except Exception:
            pass
    for row in curation_rows('assets.json'):
        t = clean_str(row.get('资产类型')); name = clean_str(row.get('资产/指数名称'))
        if not t or not name:
            continue
        # 国债条目覆盖（储蓄国债票面利率；原注明「iFind 中债收益率」有误，2026-10-05 更正）
        if name in BOND_OVERRIDE:
            new_name, fallback_yield, fallback_date, note, source = BOND_OVERRIDE[name]
            latest = bond_latest.get(new_name)
            if latest:
                y = '{:.2f}%'.format(latest[1])
                d = latest[0]
            else:
                y, d = fallback_yield, fallback_date
            rows.append({
                'type': t, 'name': new_name, 'yield': y, 'date': d,
                'note': note, 'source': source,
                'desc': ASSET_DESC.get(new_name, '')
            })
            continue
        # 红利指数覆盖：divHistory 最新值优先（Wind 口径，Excel 旧值不覆盖最新）
        # 名称精确匹配失败时尝试包含匹配（如 assetData"上证国企红利" vs indexData"上国红利"）
        _match = None
        _map_name = ASSET_INDEX_NAME_MAP.get(name)
        if _map_name and _map_name in index_latest:
            latest_date, latest_yield = index_latest[_map_name]
        elif name in index_latest:
            latest_date, latest_yield = index_latest[name]
        else:
            for _k, _v in index_latest.items():
                if (_k in name or name in _k) and len(_k) >= 2 and len(name) >= 2:
                    _match = (_k, _v)
                    break
            if _match:
                latest_date, latest_yield = _match[1]
        if _map_name and _map_name in index_latest or name in index_latest or _match:
            rows.append({
                'type': t, 'name': name, 'yield': '{:.2f}%'.format(latest_yield),
                'date': latest_date, 'note': clean_str(row.get('利率说明')) or '',
                'source': 'Wind', 'desc': ASSET_DESC.get(name, '')
            })
            continue
        # 货币基金覆盖：余额宝 7 日年化取 moneyFundData 最新（Wind 实时，Excel 旧值不覆盖）
        if name in money_latest:
            _mf = money_latest[name]
            _yb_date = _mf.get('yieldDate') or yuebao_latest_date or ''
            rows.append({
                'type': t, 'name': name,
                'yield': '{:.2f}%'.format(_mf['yield7dNum'] * 100),  # 余额宝统一 2 位小数（数据规则）
                'date': _yb_date, 'note': clean_str(row.get('利率说明')) or '7日年化收益率',
                'source': 'Wind', 'desc': ASSET_DESC.get(name, '')
            })
            continue
        note = clean_str(row.get('利率说明')) or ''
        # REITs 口径统一为"名义派息率（中位数）"（2026-08-11 用户指定，不随 Excel 变更）
        if name in ('REITs产权类', 'REITs特许经营权类'):
            note = '名义派息率（中位数）'
        # REITs 覆盖：取 assetHistory 最新中位数（Wind 日频，Excel 快照不覆盖最新）
        if name in reits_latest:
            _d, _y = reits_latest[name]
            rows.append({
                'type': t, 'name': name, 'yield': '{:.2f}%'.format(_y),
                'date': _d, 'note': '名义派息率（中位数）',
                'source': 'Wind', 'desc': ASSET_DESC.get(name, '')
            })
            continue
        # 通用覆盖：整存整取/LPR/预定利率/同业存单 取 assetHistory 最新（2026-08-15 用户确认）
        # 来源统一 Wind（2026-10-04 用户要求：这些序列均由 sync_asset_macro.py 经 Wind MCP 取得，原「Wind/iFind」有误）
        if name in hist_latest:
            _d, _y = hist_latest[name]
            _note = NOTE_OVERRIDE.get(name) or clean_str(row.get('利率说明')) or ''
            rows.append({
                'type': t, 'name': name, 'yield': '{:.2f}%'.format(_y),
                'date': _d, 'note': _note,
                'source': 'Wind', 'desc': ASSET_DESC.get(name, '')
            })
            continue
        rows.append({
            'type': t, 'name': name, 'yield': pct_str(row.get('食息率')),
            'date': date_str(row.get('更新日期')) or '', 'note': note,
            'source': clean_str(row.get('数据来源')) or 'Wind',
            'desc': ASSET_DESC.get(name, '')
        })
    # 手工补加资产（EXTRA_ASSETS，2026-10-06）：不在 Excel 总表内，按 type 追加到同组末尾；
    # 数值取 indexData divHistory 最新值；已存在则跳过（Excel 若将来收录则不重复）。
    _names = {r.get('name') for r in rows}
    for ea in EXTRA_ASSETS:
        nm = ea['name']
        if nm in _names:
            continue
        latest = index_latest.get(nm)
        if not latest:
            print('[WARN] EXTRA_ASSETS 未在 indexData 找到 divHistory: {}'.format(nm))
            continue
        _d, _y = latest
        _row = {
            'type': ea['type'], 'name': nm, 'yield': '{:.2f}%'.format(_y),
            'date': _d, 'note': ea.get('note', '') or '',
            'source': 'Wind', 'desc': ASSET_DESC.get(nm, '')
        }
        _ins = None
        for _i, _r in enumerate(rows):
            if _r.get('type') == ea['type']:
                _ins = _i + 1
        if _ins is None:
            rows.append(_row)
        else:
            rows.insert(_ins, _row)
    # 首页「红利」组默认按股息率从高到低排名（2026-10-06 用户要求）：
    #   站点为静态更新，每次更新数据后红利组须保持「股息率由高到低」的默认顺序。
    #   仅重排 type=='红利' 的行（按出现位置原地替换），保持各分组位置与其它组内部顺序不变。
    def _yield_val(_s):
        try:
            return float(str(_s).replace('%', '').strip())
        except (TypeError, ValueError):
            return -1.0
    _red = [r for r in rows if r.get('type') == '红利']
    if _red:
        _it = iter(sorted(_red, key=lambda x: _yield_val(x.get('yield')), reverse=True))
        rows = [next(_it) if r.get('type') == '红利' else r for r in rows]
    return rows


def norm_market(v):
    """规范化目标市场：A股->沪深, 港->港股, 沪->沪市, 深->深市, 沪港深/沪深港->沪港深"""
    s = clean_str(v) or ''
    if not s:
        return ''
    if s == 'A股':
        return '沪深'
    if s == '港':
        return '港股'
    if s == '沪':
        return '沪市'
    if s == '深':
        return '深市'
    if '沪港深' in s or '沪深港' in s:
        return '沪港深'
    return s


def build_index_data():
    """红利指数：curation 用户标注（原飞书表）字段优先，清单补充缺失字段。
    来源：indices_pro.json（境内红利指数清单）+ indices_main.json（主表红利指数补充）。"""
    user_info, user_div = load_user_index_info()
    out = {}
    for row in curation_rows('indices_pro.json'):
        code = clean_code(row.get('指数代码'))
        if not code:
            continue
        # 基础字段先取清单（列名见 data/curation/indices_pro.json）
        item = {
            'code': code, 'name': clean_str(row.get('指数名称')) or '',
            'fullname': clean_str(row.get('指数全称')) or '',
            'publisher': clean_str(row.get('发布机构')) or '',
            'listedDate': date_str(row.get('发布日期')) or '',
            'market': norm_market(row.get('目标市场')),
            'components': int(clean_num(row.get('成分个数'))) if clean_num(row.get('成分个数')) else 0,
            'currency': clean_str(row.get('交易币种')) or '', 'weight': clean_str(row.get('加权方式')) or '',
            'fundCount': int(clean_num(row.get('跟踪标的基金数量'))) if clean_num(row.get('跟踪标的基金数量')) else 0,
            'yield': pct_str(row.get('股息率TTM')),
            'yieldNum': round(clean_num(row.get('股息率TTM')), 4) if clean_num(row.get('股息率TTM')) else 0.0,
            'yrChange': clean_num(row.get('年涨跌幅')) if clean_num(row.get('年涨跌幅')) else 0.0,
            'fullReturn': clean_str(row.get('全收益指数')) or '',
        }
        # 用户表字段覆盖（用户手动修订优先）
        if code in user_info:
            u = user_info[code]
            if u.get('name'): item['name'] = u['name']
            if u.get('fullname'): item['fullname'] = u['fullname']
            if u.get('publisher'): item['publisher'] = u['publisher']
            if u.get('listedDate'): item['listedDate'] = u['listedDate']
            if u.get('components'): item['components'] = u['components']
            if u.get('market'): item['market'] = norm_market(u['market'])
            if u.get('weight'): item['weight'] = u['weight']
            # 用户表独有的字段
            if u.get('detailUrl'): item['detailUrl'] = u['detailUrl']
            if u.get('weightExtra'): item['weightExtra'] = u['weightExtra']
            if u.get('adjustCycle'): item['adjustCycle'] = u['adjustCycle']
            if u.get('adjustDate'): item['adjustDate'] = u['adjustDate']
            if u.get('yieldNum'): item['yieldNum'] = u['yieldNum']
        # 股息率表字段覆盖（税系数/每月投入）
        if code in user_div:
            ud = user_div[code]
            if ud.get('yieldNum'): item['yieldNum'] = ud['yieldNum']
            item['taxRate'] = ud.get('taxRate', 1.0)
            if ud.get('investMonthly'): item['investMonthly'] = ud['investMonthly']
        else:
            # 用户股息率表没有该指数时，给默认税系数（A股1.0）
            item.setdefault('taxRate', 1.0)
            item.setdefault('investMonthly', 0.0)
        out[code] = item

    # 补：清单「主表红利指数」里有、境内红利指数表没有的指数（如港股指数的股息率/税系数）
    for row in curation_rows('indices_main.json'):
        code = clean_code(row.get('指数代码'))
        if not code:
            continue
        if code in out:
            item = out[code]
            # 未覆盖的字段补默认（列名见 data/curation/indices_main.json）
            item.setdefault('taxRate', 1.0)
            item.setdefault('investMonthly', 0.0)
            if item['yieldNum'] == 0 and clean_num(row.get('股息率')):
                item['yieldNum'] = round(clean_num(row.get('股息率')), 4)
                item['yield'] = pct_str(row.get('股息率'))
            if item['yrChange'] == 0 and clean_num(row.get('年涨跌幅')):
                item['yrChange'] = round(clean_num(row.get('年涨跌幅')), 4)
            if not item.get('name'):
                item['name'] = clean_str(row.get('指数简称')) or ''
            if not item.get('fullname'):
                item['fullname'] = clean_str(row.get('指数全称')) or ''
            if not item.get('components'):
                item['components'] = int(clean_num(row.get('成分股数量')))
            if not item.get('market'):
                hk = 'HK' in code or code.endswith('.HI')
                item['market'] = '港股' if hk else ''
            if not item.get('currency'):
                hk = 'HK' in code or code.endswith('.HI')
                item['currency'] = 'HKD' if hk else 'CNY'
        else:
            hk = 'HK' in code or code.endswith('.HI')
            item = {
                'code': code, 'name': clean_str(row.get('指数简称')) or '',
                'fullname': clean_str(row.get('指数全称')) or '',
                'publisher': '', 'listedDate': '', 'market': '港股' if hk else '',
                'components': int(clean_num(row.get('成分股数量'))),
                'currency': 'HKD' if hk else 'CNY', 'weight': '',
                'fundCount': 0, 'yield': pct_str(row.get('股息率')),
                'yieldNum': round(clean_num(row.get('股息率')), 4),
                'yrChange': round(clean_num(row.get('年涨跌幅')), 4),
                'fullReturn': '', 'taxRate': 1.0,
                'investMonthly': 0.0,
            }
            # 用户股息率表覆盖
            if code in user_div:
                ud = user_div[code]
                if ud.get('yieldNum'): item['yieldNum'] = ud['yieldNum']
                item['taxRate'] = ud.get('taxRate', 1.0)
                if ud.get('investMonthly'): item['investMonthly'] = ud['investMonthly']
            # 用户信息表覆盖（详情页/加权/调整周期等）
            if code in user_info:
                u = user_info[code]
                if u.get('name'): item['name'] = u['name']
                if u.get('fullname'): item['fullname'] = u['fullname']
                if u.get('publisher'): item['publisher'] = u['publisher']
                if u.get('listedDate'): item['listedDate'] = u['listedDate']
                if u.get('components'): item['components'] = u['components']
                if u.get('market'): item['market'] = norm_market(u['market'])
                if u.get('weight'): item['weight'] = u['weight']
                if u.get('detailUrl'): item['detailUrl'] = u['detailUrl']
                if u.get('weightExtra'): item['weightExtra'] = u['weightExtra']
                if u.get('adjustCycle'): item['adjustCycle'] = u['adjustCycle']
                if u.get('adjustDate'): item['adjustDate'] = u['adjustDate']
                if u.get('yieldNum'): item['yieldNum'] = u['yieldNum']
            out[code] = item
    return list(out.values())


def build_cn_etf_data():
    # 取「ETF扩位场内简称」为站点 ETF 简称唯一口径（2026-09-20 用户要求，取自 Wind）。
    # 列名见 data/curation/cn_etf.json（按名取值，挪列不再受影响）。
    rows = []
    for row in curation_rows('cn_etf.json'):
        code = clean_code(row.get('ETF代码'))
        if not code:
            continue
        fee = clean_num(row.get('管理费率'))
        rows.append({
            'code': code, 'name': clean_str(row.get('ETF扩位场内简称')) or '',
            'trackCode': clean_code(row.get('跟踪指数代码')) or '',
            'trackName': clean_str(row.get('跟踪指数名称')) or '',
            'manager': clean_str(row.get('基金管理人')) or '',
            'listedDate': date_str(row.get('成立日期')),
            'listedMarketDate': date_str(row.get('上市日期')),
            'fee': '{:.2f}%'.format(fee * 100) if fee else '0.00%',
            'feeNum': round(fee, 4) if fee else 0.0,
            'divCount': int(clean_num(row.get('年度分红次数(2026)'))),
            'size': round(clean_num(row.get('管理规模(最新,亿元)')), 2),
            'shares': round(clean_num(row.get('场内流通份额(亿份)')), 2),
            'holders': round(clean_num(row.get('持有人户数(2025,万)')), 2),
            'divDate': date_str(row.get('最近分红日期')),
        })
    return rows


def build_hk_etf_data():
    """港交所红利ETF：curation 用户标注优先，清单补充缺失。
    来源：hk_etf_pro.json（清单）+ hk_etf_feishu.json（标注）。"""
    user_hk = load_user_hk_etf()
    rows = []
    for row in curation_rows('hk_etf_pro.json'):
        code = clean_code(row.get('ETF代码'))
        if not code:
            continue
        name = to_simple(clean_str(row.get('ETF简称')) or '')  # 统一显示简体（源为繁体）
        name_key = norm_hk_name(name)  # 匹配标注时繁简归一化
        fee = clean_num(row.get('管理费率'))
        connect = clean_str(row.get('是否互联互通ETF'))
        item = {
            'code': code, 'name': name, 'fullname': clean_str(row.get('ETF全称')) or '',
            'connect': connect == '是',
            'trackCode': clean_code(row.get('跟踪指数代码')),
            'trackName': clean_str(row.get('跟踪指数名称')),
            'manager': clean_str(row.get('基金管理人')),
            'listedDate': date_str(row.get('成立日期')),
            'fee': '{:.2f}%'.format(fee * 100) if fee else '0.00%',
            'feeNum': round(fee, 4) if fee else 0.0,
            'size': round(clean_num(row.get('管理规模(亿港元)')), 2),
            'divDate': date_str(row.get('最近分红日期')),
        }
        # 用户表覆盖（用户手动修订：互联互通、跟踪指数等）
        if name_key in user_hk:
            u = user_hk[name_key]
            if u.get('fullname'): item['fullname'] = u['fullname']
            if u.get('detailUrl'): item['detailUrl'] = u['detailUrl']
            if u.get('connect'): item['connect'] = u['connect']
            if u.get('trackCode'): item['trackCode'] = u['trackCode']
            if u.get('trackName'): item['trackName'] = u['trackName']
            if u.get('manager'): item['manager'] = u['manager']
            if u.get('listedDate'): item['listedDate'] = u['listedDate']
            if u.get('fee'): item['fee'] = '{:.2f}%'.format(u['fee'] * 100)
            if u.get('fee'): item['feeNum'] = round(u['fee'], 4)
            if u.get('size'): item['size'] = u['size']
            if u.get('divDate'): item['divDate'] = u['divDate']
        rows.append(item)
    return rows


def build_etf_data():
    # 取「ETF扩位场内简称」为站点 ETF 简称唯一口径（2026-09-20 用户要求）。
    # 列名见 data/curation/monthly_etf.json。
    rows = []
    _div_col = _find_col(curation_cols('monthly_etf.json'), ['最近分红日期', '最近分红'])
    for row in curation_rows('monthly_etf.json'):
        code = clean_code(row.get('ETF代码'))
        if not code:
            continue
        fee = clean_num(row.get('管理费率'))
        _div_date = date_str(row.get(_div_col)) if _div_col else ''
        rows.append({
            'code': code, 'name': clean_str(row.get('ETF扩位场内简称')) or '',
            'fundCompany': clean_str(row.get('基金公司')) or '',
            'listedDate': date_str(row.get('上市日期')),
            'divDate': _div_date,
            'fee': '{:.2f}%'.format(fee * 100) if fee else '0.00%',
            'feeNum': round(fee, 4) if fee else 0.0,
            'totalDiv': int(clean_num(row.get('累计分红次数'))),
            'annualDiv': int(clean_num(row.get('年度分红次数'))),
            'annualDivAmt': round(clean_num(row.get('年度单位分红')), 4),
            'monthlyDivAmt': round(clean_num(row.get('年度月均分红')), 4),
            'price': round(clean_num(row.get('当前场内价格')), 3),
            'cumDiv': round(clean_num(row.get('单位累计分红')), 4),
            'trackCode': clean_code(row.get('对应指数代码')),
            'trackName': clean_str(row.get('对应指数简称')),
            'divTotalAmt': round(clean_num(row.get('累计分红总额')), 2),
            'yield': pct_str(row.get('对应指数股息率')),
            'yieldNum': round(clean_num(row.get('对应指数股息率')), 4),
            'taxRate': smart_tax_rate(clean_str(row.get('ETF扩位场内简称'))),
            'investMonthly': round(clean_num(row.get('每月千元收益需总投入')), 2),
        })
    return rows


def build_fund_data():
    # 列名见 data/curation/monthly_fund.json。
    rows = []
    _div_col = _find_col(curation_cols('monthly_fund.json'), ['最近分红日期', '最近分红'])
    for row in curation_rows('monthly_fund.json'):
        code = clean_code(row.get('基金代码'))
        if not code:
            continue
        fee = clean_num(row.get('管理费率'))
        _div_date = date_str(row.get(_div_col)) if _div_col else ''
        rows.append({
            'code': code, 'name': clean_str(row.get('基金简称')) or '',
            'fundCompany': clean_str(row.get('基金公司')),
            'establishDate': date_str(row.get('成立日期')),
            'divDate': _div_date,
            'fee': '{:.2f}%'.format(fee * 100) if fee else '0.00%',
            'feeNum': round(fee, 4) if fee else 0.0,
            'annualDiv': int(clean_num(row.get('年度分红次数'))),
            'annualDivAmt': round(clean_num(row.get('单位年度分红')), 4),
            'monthlyDivAmt': round(clean_num(row.get('年度月均分红')), 4),
            'nav': round(clean_num(row.get('最新净值')), 4),
            'trackCode': clean_code(row.get('对应指数代码')),
            'trackName': clean_str(row.get('对应指数简称')),
            'fundSize': round(clean_num(row.get('基金规模')), 2),
            'divTotalAmt': round(clean_num(row.get('年度分红总额')), 2),
            'yield': pct_str(row.get('对应指数股息率')),
            'yieldNum': round(clean_num(row.get('对应指数股息率')), 4),
            'taxRate': smart_tax_rate(clean_str(row.get('基金简称'))),
            'investMonthly': round(clean_num(row.get('每月千元收益需总投入')), 2),
        })
    return rows


def build_money_fund_data():
    # 列名见 data/curation/money_fund.json。
    rows = []
    # 保留已有「Wind 实时」字段（sync_money_fund.py 写入，清单无 yieldDate 列）：
    #   有 yieldDate 即说明该行是 Wind 实时值 —— 值(yield7d/yield7dNum/dailyWan)必须与日期
    #   成对保留。2026-09-27 修复：此前只保留 yieldDate，值被快照旧值覆盖 → 出现
    #   「日期是 Wind 的、数值是快照的」口径不一致（每周把 Wind 的有效收益率冲掉）。
    old_wind = {}
    old_path = os.path.join(DATA_DIR, 'moneyFundData.json')
    if os.path.exists(old_path):
        try:
            with io.open(old_path, 'r', encoding='utf-8') as f:
                for _m in json.load(f):
                    if _m.get('yieldDate'):
                        old_wind[_m['code']] = {
                            'yield7d': _m.get('yield7d', ''),
                            'yield7dNum': _m.get('yield7dNum'),
                            'dailyWan': _m.get('dailyWan'),
                            'yieldDate': _m['yieldDate'],
                        }
        except Exception:
            pass
    for row in curation_rows('money_fund.json'):
        code = clean_code(row.get('基金代码'))
        if not code:
            continue
        fee = clean_num(row.get('管理费率'))
        _r = {
            'code': code, 'name': clean_str(row.get('基金简称')) or '',
            'size': round(clean_num(row.get('基金规模')), 2),
            'fee': '{:.2f}%'.format(fee * 100) if fee else '0.00%',
            'feeNum': round(fee, 4) if fee else 0.0,
            'yield7d': pct_str(row.get('7日年化收益率')),
            'yield7dNum': round(clean_num(row.get('7日年化收益率')), 4),
            'dailyWan': round(clean_num(row.get('日万份收益')), 4),
            'yieldDate': '',
        }
        # Wind 实时值优先于清单快照（与 yieldDate 一并保留）
        if code in old_wind:
            _r.update(old_wind[code])
        rows.append(_r)
    return rows


def build_reits_data():
    # 列名见 data/curation/reits_equity.json / reits_concession.json。
    rows = []
    for _f in ['reits_equity.json', 'reits_concession.json']:
        for row in curation_rows(_f):
            code = clean_code(row.get('REITs代码'))
            if not code:
                continue
            rows.append({
                'code': code, 'name': clean_str(row.get('REITs简称')) or '',
                'assetType': clean_str(row.get('资产类型')) or '',
                'listedDate': date_str(row.get('上市日期')),
                'totalDiv': int(clean_num(row.get('累计分红次数'))),
                'annualDiv': round(clean_num(row.get('年化分红次数')), 2),
                'cumDivAmt': round(clean_num(row.get('单位累计分红')), 4),
                'annualDivAmt': round(clean_num(row.get('单位年化分红')), 4),
                'yield': pct_str(row.get('年化派息率')),
                'yieldNum': round(clean_num(row.get('年化派息率')), 4),
                'volatility': round(clean_num(row.get('年化波动率')), 4),
                'shortName': clean_str(row.get('REITs场内简称')),
                'projectType': clean_str(row.get('项目属性')),
                'prevClose': round(clean_num(row.get('前收盘价')), 3),
            })
    return rows


def main():
    # P2（2026-10-06）：不再依赖 Excel 快照 —— 改为校验 curation 清单/标注是否齐备。
    _need = ['assets.json', 'indices_pro.json', 'indices_main.json', 'cn_etf.json',
             'hk_etf_pro.json', 'monthly_etf.json', 'monthly_fund.json',
             'money_fund.json', 'reits_equity.json', 'reits_concession.json',
             'indices_feishu_info.json', 'indices_feishu_yield.json', 'hk_etf_feishu.json']
    _miss = [n for n in _need if not os.path.exists(os.path.join(CURATION_DIR, n))]
    if _miss:
        print('[ERROR] data/curation/ 清单文件缺失，无法重建：', _miss)
        print('  （应从 git 拉取 data/curation/；如需从旧 Excel 重新冻结，运行 export_curation.py）')
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    # 保留旧的手动修订字段（用户手动输入，清单/Wind 不应覆盖）+ divHistory/dailyChange
    # 手动字段清单：publisher(指数公司)、listedDate(发布日期)、weight(加权方式)、
    #   weightExtra(加权附加条件)、yield/yieldNum(股息率，以 Wind divHistory 最新值或用户修正为准)、
    #   components、market、currency、fullReturn
    MANUAL_FIELDS = ['publisher', 'listedDate', 'weight', 'weightExtra',
                     'yield', 'yieldNum', 'components', 'market', 'currency', 'fullReturn']
    # 权威手动值（用户确认/页面标准）：sync 时强制固定，不随清单/Wind 覆盖。
    # 这些是用户手动核对的字段，尤其针对 Wind 缺失的小众指数。
    AUTHORITATIVE_MANUAL = {
        '000922.CSI': {'listedDate': '2008-05-09'},
        '930917.CSI': {'components': 99},
        'SPCADMCP.SPI': {'components': 100, 'weight': '因子加权'},
        '995128.SSI': {'components': 50, 'market': '沪港深'},
        '995127.SSI': {'components': 100, 'market': '沪港深'},
        '995082.SSI': {'components': 50},
    }
    old_hist = {}
    old_daily = {}
    old_manual = {}
    old_yr = {}
    idx_path_old = os.path.join(DATA_DIR, 'indexData.json')
    if os.path.exists(idx_path_old):
        try:
            with io.open(idx_path_old, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    if item.get('divHistory'):
                        old_hist[item['code']] = item['divHistory']
                    if item.get('dailyChange') is not None:
                        old_daily[item['code']] = {'dailyChange': item['dailyChange'], 'dailyDate': item.get('dailyDate', '')}
                    if item.get('yrChange'):
                        old_yr[item['code']] = item['yrChange']
                    # 保存手动修订字段（旧值非空才保护；标普中国A股红利100 的 yield 为空 → 不覆盖为 0）
                    manual = {}
                    for k in MANUAL_FIELDS:
                        if item.get(k) is not None and item.get(k) != '' and item.get(k) != 0:
                            manual[k] = item[k]
                    old_manual[item['code']] = manual
        except Exception:
            pass
    # 指数 yieldNum 映射（百分数口径，用于 etf/fund 股息率校正，2026-08-22）
    idx_yield = {}
    try:
        with io.open(idx_path_old, 'r', encoding='utf-8') as f:
            for _it in json.load(f):
                _yn = _it.get('yieldNum')
                if _yn:
                    idx_yield[_it['code']] = _yn
    except Exception:
        pass
    builders = {
        'assetData': ('assetData.json', build_asset_data),
        'indexData': ('indexData.json', build_index_data),
        'cnEtfData': ('cnEtfData.json', build_cn_etf_data),
        'hkEtfData': ('hkEtfData.json', build_hk_etf_data),
        'etfData': ('etfData.json', build_etf_data),
        'fundData': ('fundData.json', build_fund_data),
        'moneyFundData': ('moneyFundData.json', build_money_fund_data),
        'reitsData': ('reitsData.json', build_reits_data),
    }
    _retired_codes = load_retired_codes()
    for key, (fname, fn) in builders.items():
        data = fn()
        # 指数币种变体归并（2026-09-20 用户要求 · 数据治理）：
        # 同一指数的港币/人民币两版站内只保留一条 —— 任何 builder 产出的 trackCode
        # 若为「变体版」一律改写为「基准版」（映射见 index_variants.py）。
        # 放在这里是为了先归并、再走下面 etfData/fundData 的「按跟踪指数股息率校正」，
        # 保证取到的是基准版指数的股息率。
        for _it in data:
            if isinstance(_it, dict) and _it.get('trackCode'):
                _nc, _nn = iv_norm(_it['trackCode'], _it.get('trackName') or '')
                if _nc != _it['trackCode']:
                    print('  [币种变体归并] %s: %s → %s' % (
                        _it.get('code', '?'), _it['trackCode'], _nc))
                    _it['trackCode'] = _nc
                    if _nn:
                        _it['trackName'] = _nn
        if key == 'cnEtfData':
            # 保留 Wind 自动补充的新 ETF（sync_new_etf.py，2026-08-15 规则）：
            # Excel 重建不删除不在 Excel 表中的自动发现标的
            try:
                _old_path = os.path.join(DATA_DIR, 'cnEtfData.json')
                if os.path.exists(_old_path):
                    with io.open(_old_path, 'r', encoding='utf-8') as _f:
                        _old = json.load(_f)
                    _exist = {x['code'] for x in data}
                    _old_names = {x['code']: (x.get('name') or '') for x in _old}
                    for _x in _old:
                        if _x['code'] not in _exist:
                            data.append(_x)
                    # N 前缀保护（2026-08-16 用户要求）：上市临时 N 摘除后，Excel 快照残留的 N 不恢复
                    for _item in data:
                        _code = _item.get('code', '')
                        _on = _old_names.get(_code)
                        if _on and not _on.startswith('N') and (_item.get('name') or '').startswith('N'):
                            _item['name'] = _on
                    data.sort(key=lambda x: x['code'])
            except Exception:
                pass
        if key == 'hkEtfData':
            # 保留人工补充、Excel/用户修订表外的港股 ETF（2026-10-05 新增，与 cnEtfData 新 ETF 护栏同理）：
            #   Excel 整表重建不得删除不在「港交所红利ETF」表内的标的（如主动管理ETF 3555.HK）。
            try:
                _old_hk_path = os.path.join(DATA_DIR, 'hkEtfData.json')
                if os.path.exists(_old_hk_path):
                    with io.open(_old_hk_path, 'r', encoding='utf-8') as _f:
                        _old_hk = json.load(_f)
                    _exist_hk = {x.get('code') for x in data}
                    _kept_hk = [x for x in _old_hk if isinstance(x, dict) and x.get('code') and x['code'] not in _exist_hk]
                    if _kept_hk:
                        data.extend(_kept_hk)
                        print('  [合并] hkEtfData 保留 Excel/用户表外的 ETF {} 只'.format(len(_kept_hk)))
            except Exception:
                pass
            # 人工补充字段保护（Excel 表无此列，旧值非空才保留）：active(主动管理ETF 标记)/shares(份额)
            try:
                with io.open(os.path.join(DATA_DIR, 'hkEtfData.json'), 'r', encoding='utf-8') as _f:
                    _prev_hk = {x.get('code'): x for x in json.load(_f) if isinstance(x, dict)}
            except Exception:
                _prev_hk = {}
            for _it in data:
                _p = _prev_hk.get(_it.get('code'))
                if not _p:
                    continue
                for _k in ('active', 'shares', 'sharesUnit'):
                    if _p.get(_k) is not None:
                        _it[_k] = _p[_k]
        if key == 'indexData':
            # 保留 Wind 自动补充的新指数（sync_new_etf.py，2026-09-27 加固）：
            # Excel/用户修订表重建不删除不在表内的自动发现指数（与 cnEtfData 新 ETF 保护同理）。
            # 否则 step 12 补入的指数会在下一轮 step 11 被整表重建丢掉，只能靠检索窗口再次发现。
            try:
                _old_idx_path = os.path.join(DATA_DIR, fname)
                if os.path.exists(_old_idx_path):
                    with io.open(_old_idx_path, 'r', encoding='utf-8') as _f:
                        _old_idx = json.load(_f)
                    _exist_idx = {x.get('code') for x in data}
                    _kept_idx = [x for x in _old_idx if x.get('code') not in _exist_idx]
                    if _kept_idx:
                        data.extend(_kept_idx)
                        print('  [合并] indexData 保留 Excel/用户表外的指数 {} 个'.format(len(_kept_idx)))
            except Exception:
                pass
            for item in data:
                if item['code'] in old_hist:
                    item['divHistory'] = old_hist[item['code']]
                if item['code'] in old_daily:
                    item['dailyChange'] = old_daily[item['code']]['dailyChange']
                    item['dailyDate'] = old_daily[item['code']]['dailyDate']
                # yrChange 保护：Wind 实时值优先（sync_daily_change 更新），Excel 快照旧值仅兜底（2026-08-16）
                if old_yr.get(item['code']):
                    item['yrChange'] = old_yr[item['code']]
                # 手动修订字段保护：旧值非空则保留，避免 Excel 的 0/缺失覆盖
                old_m = old_manual.get(item['code'], {})
                for k, v in old_m.items():
                    item[k] = v
                # 权威手动值优先：用户确认的标准值强制固定
                for k, v in AUTHORITATIVE_MANUAL.get(item['code'], {}).items():
                    item[k] = v
                # 股息率校正：以 Wind divHistory 最新值为准（统一 Wind 口径，避免 Excel 错误值）
                hist = item.get('divHistory') or []
                if hist and hist[-1].get('yield'):
                    # divHistory 的 yield 已是百分数（4.2756 = 4.28%），转小数后 pct_str 格式化
                    pct_val = float(hist[-1]['yield'])
                    item['yieldNum'] = round(pct_val, 4)
                    item['yield'] = pct_str(pct_val / 100.0)
                elif item.get('yieldNum') in (0, 0.0, None, '') or not item.get('yield'):
                    # 无历史数据且无有效股息率 → 置空（前端显示 —），禁止 0.00%
                    item['yield'] = ''
                    item['yieldNum'] = None
        if key in ('etfData', 'fundData'):
            # 股息率口径校正（2026-08-22 防复发，见 docs/reference/data-format-rules.md「数据源口径统一」）：
            # yieldNum 统一为百分数（4.2756=4.28%）；trackCode 在 indexData → 用跟踪指数股息率；
            # 否则 Excel 快照小数值（<1，Wind 导出格式不一）→ ×100 转百分数
            for it in data:
                tc = it.get('trackCode') or ''
                yn = it.get('yieldNum') or 0
                if tc and tc in idx_yield and idx_yield[tc]:
                    it['yieldNum'] = round(idx_yield[tc], 4)
                    it['yield'] = pct_str(it['yieldNum'] / 100.0)
                elif 0 < yn < 1:
                    it['yieldNum'] = round(yn * 100, 4)
                    it['yield'] = pct_str(it['yieldNum'] / 100.0)
        if key in ('etfData', 'fundData'):
            # 保留「月月名单」自动补入的表外行（sync_new_monthly.py，2026-10-06 新增）：
            #   Excel 整表重建不得删除不在 Excel 表内的自动发现成员（与 cnEtfData 新 ETF / reitsData 新 REITs 同理）。
            #   ⚠️ 成员「移出」由步骤 14 sync_fund_divdate.prune_stale_monthly 负责（真正从 json 删除）——
            #   此处只保留「当前 json 里存在、但 Excel 表没有」的行，故已被移出的成员不会被复活。
            try:
                _old_m_path = os.path.join(DATA_DIR, fname)
                if os.path.exists(_old_m_path):
                    with io.open(_old_m_path, 'r', encoding='utf-8') as _f:
                        _old_m = json.load(_f)
                    _exist_m = {x.get('code') for x in data}
                    _kept_m = [x for x in _old_m
                               if isinstance(x, dict) and x.get('code') and x['code'] not in _exist_m]
                    if _kept_m:
                        data.extend(_kept_m)
                        print('  [合并] {} 保留 Excel/用户表外的月月成员 {} 只'.format(key, len(_kept_m)))
            except Exception:
                pass
        # 合并而不是覆盖（2026-09-26）：Excel 快照是手动导出的，往往比 Wind 取到的数据旧。
        #   ① reitsData：保留 sync_new_reits.py 补入、Excel 里没有的新 REITs（与 cnEtfData 的新 ETF 保护同理）
        #   ② 规模：旧文件里 Wind 取到的规模若比 Excel 快照新（sizeDate 更晚），保留 Wind 的规模与日期
        _mkey = {'cnEtfData': 'size', 'hkEtfData': 'size', 'etfData': 'fundSize',
                 'fundData': 'fundSize', 'moneyFundData': 'size', 'reitsData': None}
        if key in _mkey:
            try:
                with io.open(os.path.join(DATA_DIR, fname), 'r', encoding='utf-8') as _f:
                    _prev = {x.get('code'): x for x in json.load(_f) if isinstance(x, dict)}
            except Exception:
                _prev = {}
            if key == 'reitsData' and _prev:
                _in_excel = {x.get('code') for x in data}
                _kept = [x for c, x in _prev.items() if c and c not in _in_excel]
                if _kept:
                    data.extend(_kept)
                    data.sort(key=lambda x: x.get('code') or '')
                    print('  [合并] reitsData 保留 Excel 外的 REITs {} 只'.format(len(_kept)))
            _sk = _mkey[key]
            if _sk and _prev:
                _snap_date = curation_snapshot_date(_SIZE_ASOF[key]) or ''
                _n = 0
                for _it in data:
                    _o = _prev.get(_it.get('code')) or {}
                    if _o.get('sizeDate') and _o['sizeDate'] > _snap_date and _o.get(_sk) not in (None, ''):
                        _it[_sk], _it['sizeDate'] = _o[_sk], _o['sizeDate']
                        _n += 1
                if _n:
                    print('  [合并] {} 保留比 curation 清单更新的 Wind 规模 {} 条'.format(key, _n))
        # 规模日期（2026-09-26，中央数据库 data_center 要求：规模必须带日期，前端不展示）：
        # 清单来源（curation sourceMtime）里的规模用快照日期；之后 sync_wind_fields.py 取到 Wind 规模时会改成 Wind 取数日期
        _size_key = {'cnEtfData': 'size', 'hkEtfData': 'size', 'etfData': 'fundSize',
                     'fundData': 'fundSize', 'moneyFundData': 'size'}.get(key)
        if _size_key:
            _snap_date = curation_snapshot_date(_SIZE_ASOF[key])
            for _it in data:
                if isinstance(_it, dict) and _it.get(_size_key) and not _it.get('sizeDate'):
                    _it['sizeDate'] = _snap_date
        # 停用名单（excel-exit 机制 B）：已清盘/结束的标的（Wind「基金到期日」已过）
        #   在此统一剔除 —— 置于所有「表外行护栏」之后，确保被停用的标的不会被重新并入。
        if key in _RETIRED_KEYS and _retired_codes:
            _n_before = len(data)
            data = [x for x in data if not (isinstance(x, dict) and x.get('code') in _retired_codes)]
            if len(data) != _n_before:
                print('  [停用] {} 剔除已结束标的 {} 只（curation/_retired.json）'.format(
                    key, _n_before - len(data)))
        path = os.path.join(DATA_DIR, fname)
        # 原子写入：先写临时文件再替换，避免坚果云盘对目标文件加锁导致 EPERM
        import tempfile
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        print('{:<14} {:>4} 条 -> {}'.format(key, len(data), fname))


if __name__ == '__main__':
    main()

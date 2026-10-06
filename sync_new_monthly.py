#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月月分红名单「自动补入」（2026-10-06 用户规则固化）
============================================================
用户口径（2026-10-06 确认）：
  1. 检索范围：**全市场口径**（不预设「红利主题」白名单，在全市场范围内筛）。
  2. 纳入阈值：Wind「近 1 年分红次数」**≥ 11 次**。
  3. 份额去重：同一产品的多个份额类别（A/C/E/I/Y）**只保留 A 类**（无 A 类则保留检出的一个）。
  4. 归类写入：
       - Wind 代码 .SH / .SZ（场内 ETF）→ `data/etfData.json`（月月分红 ETF）
       - Wind 代码 .OF（场外）        → `data/fundData.json`（指数基金月月分红）
     站点 `code` 一律写 `base + '.OF'`（与 build_lists 口径一致）。
  5. 仅纳入**指数产品**（ETF / 指数基金，Wind 返回「跟踪指数代码」）：主动管理基金
     （如超短债、量化选股，无跟踪指数）不纳入月月分红名单——名单两个板块固有语义为
     「ETF 月月分红 / 指数基金月月分红」。
  6. **自动加入，不人工确认**；**移出**由 `sync_fund_divdate.prune_stale_monthly`
     自动完成（最近一次分红早于「上一个月」即移出，见步骤 14）。

联动与防回退：
  - 本脚本产出的是「curation 表外行」→ 必须由 `build_lists.py` 的 etfData/fundData
    「表外行保留护栏」保住，否则每周整表重建会冲掉（同 cnEtfData 新 ETF / reitsData 新 REITs）。
  - 流水线位置：**build_lists(2)（步骤 11）之后、sync_fund_divdate（步骤 14）之前**
    （编号外步骤）——便于同轮紧接的 step 14 刷新 divDate 并做月月连续性校验。
  - 字段填充：本脚本只写「身份 / 结构」字段（code/name/company/成立日/费率/跟踪指数…）；
    数值类字段与跟踪指数规范名由后续 `sync_wind_fields.py`（步骤 15）Wind 化补齐。

用法：python3 sync_new_monthly.py [--dry-run]
      --dry-run 只打印候选与拟加入清单，**不写文件**（先核对再正式运行）。
"""
import json, os, subprocess, sys, io, time, tempfile

# 指数币种变体归并（单一事实来源，见 index_variants.py）
from index_variants import normalize as iv_norm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
ETF = os.path.join(DATA_DIR, 'etfData.json')
FUND = os.path.join(DATA_DIR, 'fundData.json')
CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wind_guard_cli.mjs')  # Wind 额度守卫包装器（2026-10-06；真实 cli.mjs 见 SX_WIND_CLI_REAL）
SKILL_DIR = os.path.expanduser('~/.agents/skills/wind-mcp-skill')

THRESHOLD = 11
QUERY = '筛选近1年分红次数大于等于{}次的基金'.format(THRESHOLD)
# 份额类别优先度（数值越小越优先）：A 类优先，其次无类别（ETF），再 C/E/I/Y
CLASS_PRIORITY = {'A': 0, '': 1, 'C': 2, 'E': 3, 'I': 4, 'Y': 5}
SLEEP = float(os.environ.get('SX_NM_SLEEP', '0.4'))


def ts():
    return time.strftime('%H:%M:%S')


def _wind_env():
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    return env


def call_wind_tbl(server, tool, question):
    """Wind 查询，返回 [(columns, rows), ...]（3 次重试 + 6s 退避 + 代理变量清理）。失败返回 []。"""
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', server, tool,
                 json.dumps({'question': question}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=int(os.environ.get('SX_WIND_TIMEOUT', '45')),
                env=_wind_env(), cwd=SKILL_DIR)
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


def short_company(s):
    """Wind「基金管理人」全称 → 站点简称（如 中欧基金管理有限公司 → 中欧基金）。
    注：sync_wind_fields 的 fundData 分支请求字段名「基金公司名称」，Wind 实际返回列名为
    「基金管理人」→ 列名不匹配，故其并不会覆盖 fundData.fundCompany；本函数结果即最终值。"""
    s = (s or '').strip()
    for suf in ('管理有限公司', '股份有限公司', '基金有限公司', '有限公司'):
        if s.endswith(suf):
            s = s[:-len(suf)]
            break
    if s.endswith('基金管理'):
        s = s[:-2]
    return s


def smart_tax_rate(name):
    """港股红利税系数：含「港股」/「沪港深」→ 0.8，其余 → 1.0（与 build_lists 一致）。"""
    s = name or ''
    return 0.8 if ('港股' in s or '沪港深' in s) else 1.0


def _col_idx(cols, *keys):
    names = [(c.get('name') or '') if isinstance(c, dict) else str(c) for c in cols]
    for i, n in enumerate(names):
        if any(k in n for k in keys):
            return i
    return -1


def discover():
    """全市场检索近 1 年分红次数 ≥ THRESHOLD 的基金 → [(windCode, name, count)]。"""
    out = []
    for cols, rows in call_wind_tbl('fund_data', 'search_funds', QUERY):
        ci_code = _col_idx(cols, 'Wind代码', '代码')
        ci_name = _col_idx(cols, '证券简称', '简称', '名称')
        ci_cnt = _col_idx(cols, '分红次数')
        if ci_code < 0 or ci_name < 0:
            continue
        for r in rows:
            if ci_code >= len(r) or ci_name >= len(r) or not r[ci_code]:
                continue
            try:
                cnt = int(float(r[ci_cnt])) if 0 <= ci_cnt < len(r) and r[ci_cnt] is not None else 0
            except (TypeError, ValueError):
                cnt = 0
            out.append((str(r[ci_code]), str(r[ci_name] or ''), cnt))
    return out


def split_class(name):
    """拆分「名称 + 份额类别」：末位 ∈ {A,C,E,I,Y} 且前一位非数字 → (base, class)；否则 (name, '')。"""
    n = name or ''
    if len(n) > 1 and n[-1] in CLASS_PRIORITY and not n[-2].isdigit():
        return n[:-1], n[-1]
    return n, ''


def dedup_share_classes(rows):
    """同 base 名称只保留优先度最高的一份；返回 [(windCode, name, count)]。"""
    best = {}
    for code, name, cnt in rows:
        base, cls = split_class(name)
        cur = best.get(base)
        if cur is None or CLASS_PRIORITY[cls] < CLASS_PRIORITY[cur[2]]:
            best[base] = (code, name, cls, cnt)
    return [(v[0], v[1], v[3]) for v in best.values()]


def classify(wind_code):
    """按 Wind 代码后缀归类：.SH/.SZ → 场内 ETF；其余（.OF）→ 场外。"""
    return 'etf' if wind_code.upper().endswith(('.SH', '.SZ')) else 'fund'


def fetch_detail(wind_code):
    """取候选详情（跟踪指数 / 管理人 / 费率 / 成立日 / 上市日 / 扩位简称）。取不到返回 None。"""
    q = ('{} 跟踪指数代码 跟踪指数名称 基金管理人 管理费率 '
         '基金成立日 上市日期 基金扩位场内简称 基金简称').format(wind_code)
    for cols, rows in call_wind_tbl('fund_data', 'get_fund_info', q):
        for r in rows:
            if not r or str(r[0]) != wind_code:
                continue

            def g(*keys):
                i = _col_idx(cols, *keys)
                return r[i] if 0 <= i < len(r) else None

            def num(*keys):
                try:
                    return float(g(*keys))
                except (TypeError, ValueError):
                    return 0.0

            return {
                'trackCode': str(g('跟踪指数代码') or '').strip(),
                'trackName': str(g('跟踪指数名称') or '').strip(),
                'company': short_company(str(g('基金管理人') or '')),
                'fee': num('管理费率'),
                'found': str(g('基金成立日') or '')[:10],
                'listed': str(g('上市日期') or '')[:10],
                'extName': str(g('基金扩位场内简称') or '').strip(),
                'shortName': str(g('基金简称') or '').strip(),
            }
    return None


def build_row(kind, code_store, name, detail):
    """按站点 schema 构造最小可用行；数值/规范名由后续 sync_wind_fields 补齐。"""
    fee = detail.get('fee') or 0.0
    fee_str = '{:.2f}%'.format(fee) if fee else '0.00%'
    fee_num = round(fee / 100.0, 4) if fee else 0.0
    row = {
        'code': code_store,
        'name': name,
        'fundCompany': detail.get('company', ''),
    }
    if kind == 'etf':
        row.update({
            'listedDate': detail.get('found', ''),
            'divDate': '',
            'fee': fee_str, 'feeNum': fee_num,
            'totalDiv': 0, 'annualDiv': 0, 'annualDivAmt': 0.0, 'monthlyDivAmt': 0.0,
            'price': 0.0, 'cumDiv': 0.0,
            'trackCode': detail.get('trackCode', ''), 'trackName': detail.get('trackName', ''),
            'divTotalAmt': 0.0, 'yield': '', 'yieldNum': None,
            'taxRate': smart_tax_rate(name), 'investMonthly': 0.0,
        })
    else:
        row.update({
            'establishDate': detail.get('found', ''),
            'divDate': '',
            'fee': fee_str, 'feeNum': fee_num,
            'annualDiv': 0, 'annualDivAmt': 0.0, 'monthlyDivAmt': 0.0, 'nav': 0.0,
            'trackCode': detail.get('trackCode', ''), 'trackName': detail.get('trackName', ''),
            'fundSize': 0.0, 'divTotalAmt': 0.0, 'yield': '', 'yieldNum': None,
            'taxRate': smart_tax_rate(name), 'investMonthly': 0.0, 'sizeDate': None,
        })
    return row


def main():
    dry = '--dry-run' in sys.argv
    print('[月月名单自动补入] [%s] Wind 全市场检索：%s' % (ts(), QUERY), flush=True)
    raw = discover()
    print('  Wind 返回 %d 只（含各份额类别）' % len(raw), flush=True)
    if not raw:
        print('  [⚠️] 未取得候选（Wind 抖动？）→ 本次不新增，保留现有名单', flush=True)
        return
    kept = dedup_share_classes(raw)
    print('  份额去重后 %d 只（A 类优先）' % len(kept), flush=True)

    etf = load_json(ETF)
    fund = load_json(FUND)
    exist = {x.get('code', '').split('.')[0] for x in etf} | {x.get('code', '').split('.')[0] for x in fund}

    adds_etf, adds_fund, skipped = [], [], []
    for wind_code, name, cnt in kept:
        base = wind_code.split('.')[0]
        kind = classify(wind_code)
        store = base + '.OF'          # 站点 code 统一 base + '.OF'
        if base in exist:
            continue
        detail = fetch_detail(wind_code)
        if not detail:
            skipped.append((wind_code, name, '详情拉取失败'))
            continue
        tc = detail.get('trackCode', '')
        if not tc:
            skipped.append((wind_code, name, '非指数产品（无跟踪指数）'))
            continue
        tc_n, tc_name = iv_norm(tc, detail.get('trackName', ''))
        if tc_n and tc_n != tc:
            detail['trackCode'] = tc_n
            detail['trackName'] = tc_name or detail.get('trackName', '')
        disp = name
        if kind == 'etf' and detail.get('extName'):
            disp = detail['extName']          # ETF 简称唯一口径 = 基金扩位场内简称
        row = build_row(kind, store, disp, detail)
        (adds_etf if kind == 'etf' else adds_fund).append(
            (store, disp, cnt, detail.get('trackCode', ''), detail.get('trackName', '')))
        if not dry:
            (etf if kind == 'etf' else fund).append(row)
        time.sleep(SLEEP)

    print('\n  === 拟新增 %d 只 ===' % (len(adds_etf) + len(adds_fund)), flush=True)
    for store, disp, cnt, tc, tn in adds_etf:
        print('    [场内ETF] %s %s（近1年分红 %d 次，跟踪 %s %s）' % (store, disp, cnt, tc, tn), flush=True)
    for store, disp, cnt, tc, tn in adds_fund:
        print('    [场外基金] %s %s（近1年分红 %d 次，跟踪 %s %s）' % (store, disp, cnt, tc, tn), flush=True)
    if skipped:
        print('  === 未纳入 %d 只（非指数 / 拉取失败）===' % len(skipped), flush=True)
        for c, n, why in skipped:
            print('    - %s %s：%s' % (c, n, why), flush=True)

    if dry:
        print('\n[dry-run] 未写文件。去掉 --dry-run 正式加入。', flush=True)
        return
    if adds_etf or adds_fund:
        save_json(ETF, etf)
        save_json(FUND, fund)
        print('\n[完成] [%s] 已写入 etfData(+%d) / fundData(+%d)；'
              '随后由步骤 14 刷 divDate、步骤 15 Wind 化补齐字段。'
              % (ts(), len(adds_etf), len(adds_fund)), flush=True)
    else:
        print('\n[完成] [%s] 无新增，名单不变' % ts(), flush=True)


if __name__ == '__main__':
    main()

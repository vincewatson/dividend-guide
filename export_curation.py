#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【一次性 · 迁移工具，不入流水线】Excel 快照 → data/curation/*.json（excel-exit P0）

背景：见 docs/data-governance/excel-exit-plan.md。本站要「摆脱 Excel 依赖」，把当前 Excel
里的**清单 + 标注**冻结为仓库内、git 版本化的单一 JSON 来源（data/curation/）。

本脚本**只读 Excel、只写 JSON**，不改动任何站点数据文件、不参与 auto_sync_deploy.sh。
用途：① 生成迁移基线；② 日后需要核对「Excel 里原本写了什么」时可重跑。

用法：python3 export_curation.py
"""
import glob, io, json, os, datetime
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(BASE, 'data', 'user')
OUT_DIR = os.path.join(BASE, 'data', 'curation')


def find_snapshot(prefix):
    """与 sync_excel.find_snapshot 同口径：data/ 与 data/user/ 取 mtime 最新。"""
    files = glob.glob(os.path.join(BASE, 'data', prefix + '*.xlsx'))
    files += glob.glob(os.path.join(USER_DIR, prefix + '*.xlsx'))
    files = [f for f in files if not os.path.basename(f).startswith('~$')]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


SNAPS = {
    'main':   find_snapshot('食息指南(EXCEL-Wind)'),
    'pro':    find_snapshot('食息指南PRO(EXCEL-Wind)'),
    'feishu': find_snapshot('食息指南Pro-飞书'),
}

# domain, source_key, sheet, out_json
EXPORTS = [
    ('indices',      'pro',    '境内红利指数',      'indices_pro.json'),
    ('indices',      'feishu', '红利指数信息表',    'indices_feishu_info.json'),
    ('indices',      'feishu', '红利指数股息率',    'indices_feishu_yield.json'),
    ('indices',      'main',   '红利指数',          'indices_main.json'),
    ('cn_etf',       'pro',    '境内红利ETF',       'cn_etf.json'),
    ('hk_etf',       'pro',    '港交所红利ETF',     'hk_etf_pro.json'),
    ('hk_etf',       'feishu', '港交所红利ETF',     'hk_etf_feishu.json'),
    ('monthly_etf',  'main',   '月月可分红ETF',     'monthly_etf.json'),
    ('monthly_fund', 'main',   '月月可分红（场外）', 'monthly_fund.json'),
    ('money_fund',   'main',   '货币基金',          'money_fund.json'),
    ('reits',        'main',   'REITs（产权类）',   'reits_equity.json'),
    ('reits',        'main',   'REITs（经营权类）', 'reits_concession.json'),
    ('assets',       'main',   '总表',              'assets.json'),
]


def cell(v):
    """单元格 → JSON 友好值：NaN→None；日期→YYYY-MM-DD；numpy 标量→原生。"""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp, datetime.datetime, datetime.date)):
        return v.strftime('%Y-%m-%d')
    if hasattr(v, 'item'):
        try:
            return v.item()
        except Exception:
            pass
    if isinstance(v, str):
        return v.strip()
    return v


def uniq(names):
    """表头可能重名（如两张表里的「每月千元收益需总投入」）→ 追加 #2/#3。"""
    seen, out = {}, []
    for n in names:
        n = ('' if n is None or (isinstance(n, float) and pd.isna(n)) else str(n)).strip() or 'col'
        if n in seen:
            seen[n] += 1
            out.append('%s #%d' % (n, seen[n]))
        else:
            seen[n] = 1
            out.append(n)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = []
    for domain, src_key, sheet, out_name in EXPORTS:
        path = SNAPS.get(src_key)
        if not path:
            print('[WARN] 快照缺失:', src_key)
            continue
        try:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
        except Exception as e:
            print('[WARN] 读取失败 %s/%s: %s' % (src_key, sheet, e))
            continue
        cols = uniq(df.iloc[0].tolist())
        rows = []
        for i in range(2, len(df)):          # 与 sync_excel builder 一致：0=表头、1=单位、2 起为数据
            vals = df.iloc[i].tolist()
            if all(cell(v) is None for v in vals):
                continue                     # 全空行跳过
            rows.append({cols[j]: cell(vals[j]) for j in range(min(len(cols), len(vals)))})
        obj = {
            'domain': domain,
            'source': os.path.basename(path),
            'sourceMtime': datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M'),
            'sheet': sheet,
            'headerRow': 0,
            'unitsRow': 1,
            'exportedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'columns': cols,
            'rows': rows,
        }
        with io.open(os.path.join(OUT_DIR, out_name), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        manifest.append({'file': out_name, 'domain': domain, 'source': obj['source'],
                         'sheet': sheet, 'rows': len(rows), 'columns': len(cols)})
        print('  %-28s %-22s rows=%d' % (out_name, sheet, len(rows)))

    with io.open(os.path.join(OUT_DIR, '_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'exportedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   'snapshots': {k: (os.path.basename(v) if v else None) for k, v in SNAPS.items()},
                   'snapshotMtimes': {k: (datetime.datetime.fromtimestamp(os.path.getmtime(v)).strftime('%Y-%m-%d %H:%M') if v else None)
                                      for k, v in SNAPS.items()},
                   'exports': manifest}, f, ensure_ascii=False, indent=1)
    print('已写 %d 个 JSON → data/curation/' % len(manifest))


if __name__ == '__main__':
    main()

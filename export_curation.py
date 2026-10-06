#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【一次性 · 迁移工具，不入流水线】Excel 快照 → data/curation/*.json（excel-exit P0）

背景：见 docs/data-governance/excel-exit-plan.md。本站要「摆脱 Excel 依赖」，把当前 Excel
里的**清单 + 标注**冻结为仓库内、git 版本化的单一 JSON 来源（data/curation/）。

本脚本**只读 Excel、只写 JSON**，不改动任何站点数据文件、不参与 auto_sync_deploy.sh。
用途：① 生成迁移基线；② 日后需要核对「Excel 里原本写了什么」时可重跑。

excel-exit P3（2026-10-06）：原 xlsx 已从 data/user、user_upload **移入 archive/excel-baseline-20261006/**；
本脚本会自动到该归档目录下检索（见 _xlsx_dirs），因此仍可对归档的 Excel 重跑核对。

用法：python3 export_curation.py
"""
import glob, io, json, os, re, datetime
import pandas as pd
import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(BASE, 'data', 'user')
OUT_DIR = os.path.join(BASE, 'data', 'curation')


def _xlsx_dirs():
    """检索 xlsx 的目录：现行目录 + excel-exit P3 归档目录（archive/excel-baseline-*）。"""
    dirs = [os.path.join(BASE, 'data'), USER_DIR,
            os.path.join(BASE, 'user_upload')]
    for d in sorted(glob.glob(os.path.join(BASE, 'archive', 'excel-baseline-*'))):
        if os.path.isdir(d):
            dirs.append(d)
            dirs.append(os.path.join(d, 'user_upload'))
    return dirs


def find_snapshot(prefix):
    """同原 sync_excel.find_snapshot 口径：在 _xlsx_dirs() 各目录取 mtime 最新的快照。"""
    files = []
    for d in _xlsx_dirs():
        files += glob.glob(os.path.join(d, prefix + '*.xlsx'))
    files = [f for f in files if not os.path.basename(f).startswith('~$')]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


SNAPS = {
    'main':   find_snapshot('食息指南(EXCEL-Wind)'),
    'pro':    find_snapshot('食息指南PRO(EXCEL-Wind)'),
    'feishu': find_snapshot('食息指南Pro-飞书'),
}

# domain, source_key, sheet, out_json, data_start_row
#   data_start_row 必须与 build_lists.py 各 builder（原 sync_excel）的 `for i in range(N, len(df))` 一致：
#   飞书/PRO/总表 = 1；主表的 红利指数/月月ETF/月月场外/货币基金/REITs = 2（这些表第 1 行是单位行）。
EXPORTS = [
    ('indices',      'pro',    '境内红利指数',      'indices_pro.json',           1),
    ('indices',      'feishu', '红利指数信息表',    'indices_feishu_info.json',   1),
    ('indices',      'feishu', '红利指数股息率',    'indices_feishu_yield.json',  1),
    ('indices',      'main',   '红利指数',          'indices_main.json',          2),
    ('cn_etf',       'pro',    '境内红利ETF',       'cn_etf.json',                1),
    ('hk_etf',       'pro',    '港交所红利ETF',     'hk_etf_pro.json',            1),
    ('hk_etf',       'feishu', '港交所红利ETF',     'hk_etf_feishu.json',         1),
    ('monthly_etf',  'main',   '月月可分红ETF',     'monthly_etf.json',           2),
    ('monthly_fund', 'main',   '月月可分红（场外）', 'monthly_fund.json',          2),
    ('money_fund',   'main',   '货币基金',          'money_fund.json',            2),
    ('reits',        'main',   'REITs（产权类）',   'reits_equity.json',          2),
    ('reits',        'main',   'REITs（经营权类）', 'reits_concession.json',      2),
    ('assets',       'main',   '总表',              'assets.json',                1),
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


def fill_formula_links(path, sheet, cols, rows, code_col, link_col='详情页', data_start=1):
    """补全 Excel 里的 HYPERLINK 公式列（pandas 读不到缓存值 → 返回 None）。

    与原 sync_excel.load_user_index_info（P2 起改读 curation）的解析口径一致：
      data_only=False 保留公式，正则抓取 HYPERLINK("<url>",...) 的第 1 个参数。
    背景：飞书表「红利指数信息表」的「详情页」整列都是 =HYPERLINK("…","链接") 公式，
    pandas/openpyxl(data_only=True) 会读到 None；「港交所红利ETF」的「详情页」是纯文本不受影响。
    """
    if link_col not in cols or code_col not in cols:
        return 0
    ci, li = cols.index(code_col), cols.index(link_col)
    filled = 0
    try:
        wb = openpyxl.load_workbook(path, data_only=False, read_only=True)
        ws = wb[sheet]
        by_key = {str(r.get(code_col)).strip().upper(): r for r in rows if r.get(code_col)}
        # openpyxl 第 r 行 == pandas 索引 r-1；数据从 data_start(0-based) → openpyxl data_start+1
        for row in ws.iter_rows(min_row=data_start + 1, max_col=max(ci, li) + 1, values_only=True):
            v = row[li] if li < len(row) else None
            if not v:
                continue
            m = re.search(r'HYPERLINK\(\s*"([^"]+)"', str(v))
            if not m:
                continue
            key = str(row[ci]).strip().upper() if ci < len(row) and row[ci] is not None else ''
            r = by_key.get(key)
            if r is not None and not r.get(link_col):
                r[link_col] = m.group(1)
                filled += 1
        wb.close()
    except Exception as e:
        print('[WARN] HYPERLINK 解析失败 %s/%s: %s' % (os.path.basename(path), sheet, e))
    return filled


# 各 domain 的「实体主键列」——用于 HYPERLINK 解析时定位到具体行（无 详情页 列时自然跳过）
CODE_COL = {'indices': '指数代码', 'hk_etf': 'ETF简称', 'cn_etf': 'ETF代码',
            'monthly_etf': 'ETF代码', 'monthly_fund': '基金代码', 'money_fund': '基金代码',
            'reits': 'REITs代码', 'assets': '资产类型'}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = []
    for domain, src_key, sheet, out_name, data_start in EXPORTS:
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
        for i in range(data_start, len(df)):   # 与 build_lists builder 的行偏移一致
            vals = df.iloc[i].tolist()
            if all(cell(v) is None for v in vals):
                continue                     # 全空行跳过
            rows.append({cols[j]: cell(vals[j]) for j in range(min(len(cols), len(vals)))})
        # 补全 HYPERLINK 公式列（如飞书「红利指数信息表」的 详情页）
        nlink = fill_formula_links(path, sheet, cols, rows,
                                   code_col=CODE_COL.get(domain, cols[0]), data_start=data_start)
        obj = {
            'domain': domain,
            'source': os.path.basename(path),
            'sourceMtime': datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M'),
            'sheet': sheet,
            'headerRow': 0,
            'unitsRow': (data_start - 1) if data_start > 1 else None,
            'dataStartRow': data_start,
            'exportedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'columns': cols,
            'rows': rows,
        }
        with io.open(os.path.join(OUT_DIR, out_name), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        manifest.append({'file': out_name, 'domain': domain, 'source': obj['source'],
                         'sheet': sheet, 'rows': len(rows), 'columns': len(cols),
                         'formulaLinksFilled': nlink})
        print('  %-28s %-22s rows=%d%s' % (out_name, sheet, len(rows),
              ('  HYPERLINK补全=%d' % nlink) if nlink else ''))

    with io.open(os.path.join(OUT_DIR, '_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'exportedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   'snapshots': {k: (os.path.basename(v) if v else None) for k, v in SNAPS.items()},
                   'snapshotMtimes': {k: (datetime.datetime.fromtimestamp(os.path.getmtime(v)).strftime('%Y-%m-%d %H:%M') if v else None)
                                      for k, v in SNAPS.items()},
                   'exports': manifest}, f, ensure_ascii=False, indent=1)
    print('已写 %d 个 JSON → data/curation/' % len(manifest))
    export_blog()


# ── 博客：文章清单 + 标注（user_upload/*.xlsx）→ data/curation/（excel-exit P1）──────
# 与 sync_blog.py 完全同口径（同款全角/半角空格规范 + 相关指数分隔）。
BLOG_CJK = '\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
_BR1 = re.compile(r'(?<=[' + BLOG_CJK + r']) +(?=[0-9A-Za-z])')
_BR2 = re.compile(r'(?<=[0-9A-Za-z]) +(?=[' + BLOG_CJK + r'])')
def _bnorm(s):
    return _BR2.sub('', _BR1.sub('', s)) if isinstance(s, str) else s
def _bsplit(v):
    if v is None:
        return []
    s = str(v).strip()
    if not s:
        return []
    out = []
    for p in re.split(r"[,，、;；/\n\r]+", s):
        p = _bnorm(p).strip(" ,，、")
        if p and p not in out:
            out.append(p)
    return out


def export_blog():
    """导出 ① 文章清单（公众号历史文章*.xlsx）② 标注（博客文章标注表*.xlsx）。"""
    # ① 文章清单
    srcs = []
    for d in _xlsx_dirs():
        srcs += glob.glob(os.path.join(d, '公众号历史文章*.xlsx'))
    srcs = [f for f in srcs if not os.path.basename(f).startswith('~$')]
    if srcs:
        src = max(srcs, key=os.path.getmtime)
        wb = openpyxl.load_workbook(src, data_only=True)
        ws = wb.active
        rows = []
        for i in range(2, ws.max_row + 1):
            d = ws.cell(i, 1).value
            title = ws.cell(i, 2).value or ''
            url = ws.cell(i, 3).value or ''
            col = ws.cell(i, 4).value
            title = title.strip() if isinstance(title, str) else str(title)
            url = url.strip() if isinstance(url, str) else str(url)
            col = (col.strip() if isinstance(col, str) else (str(col) if col else ''))
            if not title and not url and not d:
                continue
            rows.append({
                'date': d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else (str(d).strip() if d else ''),
                'title': _bnorm(title),
                'url': url,
                'column': _bnorm(col),
            })
        obj = {
            'domain': 'blog_articles',
            'source': os.path.basename(src),
            'sourceMtime': datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime('%Y-%m-%d %H:%M'),
            'exportedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'note': '子弹列车公众号文章清单（date/title/url/column）。由 export_curation.py 从用户导出的 Excel 冻结；'
                    '此后手工维护，sync_blog.py 只读不写。',
            'columns': ['date', 'title', 'url', 'column'],
            'rows': rows,
        }
        with io.open(os.path.join(OUT_DIR, 'blog_articles.json'), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        print('  %-28s %-22s rows=%d' % ('blog_articles.json', '公众号历史文章', len(rows)))
    else:
        print('[WARN] 未找到 user_upload/公众号历史文章*.xlsx，跳过博客清单导出')

    # ② 标注表 → url -> {direction, indexes}
    annts = []
    for d in _xlsx_dirs():
        annts += glob.glob(os.path.join(d, '博客文章标注表*.xlsx'))
    annts = [f for f in annts if not os.path.basename(f).startswith('~$')]
    if annts:
        ax = max(annts, key=os.path.getmtime)
        wb = openpyxl.load_workbook(ax, data_only=True)
        ws = wb[wb.sheetnames[0]]
        annotations = {}
        for i in range(2, ws.max_row + 1):
            u = ws.cell(i, 3).value
            u = u.strip() if isinstance(u, str) else (str(u).strip() if u else '')
            if not u:
                continue
            d = ws.cell(i, 5).value
            d = _bnorm(str(d).strip()) if d else ''
            ix = _bsplit(ws.cell(i, 6).value)
            if d or ix:
                annotations[u] = {'direction': d, 'indexes': ix}
        obj = {
            'domain': 'blog_annotations',
            'source': os.path.basename(ax),
            'sourceMtime': datetime.datetime.fromtimestamp(os.path.getmtime(ax)).strftime('%Y-%m-%d %H:%M'),
            'exportedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'schema': 'url -> {direction, indexes}',
            'note': '博客文章标注（内容标签 direction / 相关指数 indexes）。由 export_curation.py 从用户维护的标注表冻结；'
                    '此后手工维护，sync_blog.py 只读不写。',
            'annotations': annotations,
        }
        with io.open(os.path.join(OUT_DIR, 'blog_annotations.json'), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        print('  %-28s %-22s entries=%d' % ('blog_annotations.json', '博客文章标注表', len(annotations)))
    else:
        print('[WARN] 未找到 user_upload/博客文章标注表*.xlsx，跳过博客标注导出')


if __name__ == '__main__':
    main()

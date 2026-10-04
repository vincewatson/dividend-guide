#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""博客（子弹列车公众号文章目录）数据生成 —— 手动维护，不参与自动流水线。
============================================================
输入：① user_upload/公众号历史文章(20240123-20260919).xlsx
         （列：发表日期 / 标题 / 文章链接 / 所属栏目）
      ② user_upload/博客文章标注表*.xlsx（用户自行维护的标注表，取最新一份）
         （列：发表日期 / 标题 / 文章链接 / 所属栏目 / 内容标签 / 相关指数 / 付费文章）
输出：data/blogData.json
      字段：date / title / url / column / direction / indexes[] / paid

说明（2026-10-04）：
  - 文章清单 = 「公众号历史文章」表（289 篇，权威清单，含「所属栏目」）；
  - 「内容标签」（direction）与「相关指数」（indexes）优先取自用户维护的
    「博客文章标注表*.xlsx」（按文章链接 url 合并；取 mtime 最新的一份），
    历史兜底 data/blogAnnotations.json（xlsx 未覆盖到的条目才用）；
  - 「付费文章」为作者标注的所属栏目之一（2 篇）→ paid=true。
  - 按链接去重、按发表日期倒序；应用全站空格规范。

用法：python3 sync_blog.py   （生成后需 python3 embed_data.py 刷新内嵌兜底）
"""
import glob, io, json, os, re
import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = sorted(glob.glob(os.path.join(BASE, "user_upload/公众号历史文章*.xlsx")))[-1]
OUT = os.path.join(BASE, "data/blogData.json")
ANNOT_PATH = os.path.join(BASE, "data/blogAnnotations.json")   # url -> {direction, indexes}（历史兜底）
ANNOT_XLSX_GLOB = os.path.join(BASE, "user_upload/博客文章标注表*.xlsx")   # 用户维护的标注表（优先）

# 「付费文章」作为所属栏目值时，同时标记 paid（前端「文章属性」筛选承载）
PAID_COL = "付费文章"

CJK = '\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
R1 = re.compile(r'(?<=[' + CJK + r']) +(?=[0-9A-Za-z])')
R2 = re.compile(r'(?<=[0-9A-Za-z]) +(?=[' + CJK + r'])')


def norm(s):
    return R2.sub('', R1.sub('', s)) if isinstance(s, str) else s


def split_indexes(v):
    """相关指数：多个指数用「, 」「、」「;」「/」等分隔 → 名称列表（去重）"""
    if v is None:
        return []
    s = str(v).strip()
    if not s:
        return []
    out = []
    for p in re.split(r"[,，、;；/\n\r]+", s):
        p = norm(p).strip(" ,，、")
        if p and p not in out:
            out.append(p)
    return out


def load_annot():
    """标注来源：① 用户维护的「博客文章标注表*.xlsx」（最新）→ ② data/blogAnnotations.json 兜底。
    返回 url -> {direction, indexes}"""
    annot = {}
    covered = set()          # 标注表中出现过的 url（即使两个字段为空也算已覆盖 → 该 url 以标注表为准）
    xlsx = sorted(glob.glob(ANNOT_XLSX_GLOB), key=os.path.getmtime)
    if xlsx:
        wb = openpyxl.load_workbook(xlsx[-1], data_only=True)
        ws = wb[wb.sheetnames[0]]
        for r in range(2, ws.max_row + 1):
            u = ws.cell(r, 3).value
            u = u.strip() if isinstance(u, str) else (str(u).strip() if u else "")
            if not u:
                continue
            covered.add(u)
            d = ws.cell(r, 5).value
            d = norm(str(d).strip()) if d else ""
            ix = split_indexes(ws.cell(r, 6).value)
            if d or ix:
                annot[u] = {"direction": d, "indexes": ix}
        print("标注表:", os.path.basename(xlsx[-1]), "| 覆盖 url:", len(covered), "| 有条目:", len(annot))
    if os.path.exists(ANNOT_PATH):
        with io.open(ANNOT_PATH, encoding="utf-8") as f:
            for u, a in json.load(f).items():
                if u not in covered:    # 仅兜底标注表未覆盖到的 url（防止旧值把已清空的值又填回来）
                    annot[u] = a
    return annot


def main():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    ws = wb.active
    recs = []
    for r in range(2, ws.max_row + 1):
        d = ws.cell(r, 1).value
        title = (ws.cell(r, 2).value or '')
        url = (ws.cell(r, 3).value or '')
        col = ws.cell(r, 4).value
        title = title.strip() if isinstance(title, str) else str(title)
        url = url.strip() if isinstance(url, str) else str(url)
        col = (col.strip() if isinstance(col, str) else (str(col) if col else ''))
        if not title and not url and not d:
            continue
        recs.append({
            "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else (str(d).strip() if d else ""),
            "title": norm(title),
            "url": url,
            "column": norm(col),
            "direction": "",      # 内容标签：本表缺 → 留空
            "indexes": [],        # 相关指数：本表缺 → 留空
        })

    # 按链接去重（同一篇只保留一条；合并日期/栏目）
    by_url = {}
    for r in recs:
        k = r["url"] or (r["date"] + "|" + r["title"])
        if k not in by_url:
            by_url[k] = r
        else:
            a = by_url[k]
            if not a["column"] and r["column"]:
                a["column"] = r["column"]
            if not a["title"] and r["title"]:
                a["title"] = r["title"]
            if r["date"] and (not a["date"] or r["date"] > a["date"]):
                a["date"] = r["date"]

    # 补录：内容标签（direction）/ 相关指数（indexes）——按 url 从标注表合并（见 load_annot）
    annot = load_annot()
    for r in by_url.values():
        a = annot.get(r["url"])
        if a:
            if a.get("direction"):
                r["direction"] = norm(a["direction"])
            if a.get("indexes"):
                r["indexes"] = [norm(x) for x in a["indexes"]]

    out = sorted(by_url.values(), key=lambda x: x["date"], reverse=True)
    for r in out:
        r["paid"] = (r["column"] == PAID_COL)

    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    # 同步刷新历史兜底标注库（= 当前合并结果），防止标注表文件丢失后回退到旧值
    ann_out = {r["url"]: {"direction": r["direction"], "indexes": r["indexes"]}
               for r in out if (r["direction"] or r["indexes"])}
    with io.open(ANNOT_PATH, "w", encoding="utf-8") as f:
        json.dump(ann_out, f, ensure_ascii=False)

    from collections import Counter
    print("来源:", os.path.basename(SRC))
    print("文章:", len(out), "| 付费:", sum(1 for x in out if x["paid"]),
          "| 有内容标签:", sum(1 for x in out if x["direction"]),
          "| 有相关指数:", sum(1 for x in out if x["indexes"]))
    print("年份:", dict(sorted(Counter(x["date"][:4] for x in out).items())))
    print("所属栏目:", dict(Counter(x["column"] for x in out).most_common()))
    print("写入", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()

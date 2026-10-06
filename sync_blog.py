#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""博客（子弹列车公众号文章目录）数据生成 —— 手动维护，不参与自动流水线。
============================================================
输入（均为仓库内、git 版本化的 curation JSON，**不再依赖任何 Excel**）：
  ① data/curation/blog_articles.json     文章清单（date/title/url/column）
  ② data/curation/blog_annotations.json  标注（url -> {direction, indexes}）
输出：data/blogData.json
      字段：date / title / url / column / direction / indexes[] / paid

说明（2026-10-06 · excel-exit P1）：
  - 文章清单 = 「公众号历史文章」表（289 篇，权威清单，含「所属栏目」），
    已由 export_curation.py 从用户 xlsx 冻结为 curation/blog_articles.json；
  - 「内容标签」（direction）与「相关指数」（indexes）取自 curation/blog_annotations.json
    （原「博客文章标注表*.xlsx」，按文章链接 url 合并）；
  - 「付费文章」为作者标注的所属栏目之一（2 篇）→ paid=true。
  - 按链接去重、按发表日期倒序；应用全站空格规范。
  - ⚠️ 本脚本**只读** curation、只写 data/blogData.json（不再回写标注文件）。
    要改标注：直接编辑 data/curation/blog_annotations.json，然后重跑本脚本 + embed_data.py。

用法：python3 sync_blog.py   （生成后需 python3 embed_data.py 刷新内嵌兜底）
"""
import io, json, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
CURATION_DIR = os.path.join(BASE, "data/curation")
ARTICLES_PATH = os.path.join(CURATION_DIR, "blog_articles.json")     # 文章清单
ANNOT_PATH = os.path.join(CURATION_DIR, "blog_annotations.json")     # 标注（direction / indexes）
OUT = os.path.join(BASE, "data/blogData.json")

# 「付费文章」作为所属栏目值时，同时标记 paid（前端「文章属性」筛选承载）
PAID_COL = "付费文章"

CJK = '\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
R1 = re.compile(r'(?<=[' + CJK + r']) +(?=[0-9A-Za-z])')
R2 = re.compile(r'(?<=[0-9A-Za-z]) +(?=[' + CJK + r'])')


def norm(s):
    return R2.sub('', R1.sub('', s)) if isinstance(s, str) else s


def split_indexes(v):
    """相关指数：列表原样返回；若为字符串（用户手改）则按「, 、 ; / 换行」拆分（去重）。"""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            p = norm(str(x).strip())
            if p and p not in out:
                out.append(p)
        return out
    s = str(v).strip()
    if not s:
        return []
    out = []
    for p in re.split(r"[,，、;；/\n\r]+", s):
        p = norm(p).strip(" ,，、")
        if p and p not in out:
            out.append(p)
    return out


def load_articles():
    """读取文章清单：data/curation/blog_articles.json。返回 [{date,title,url,column}]。"""
    with io.open(ARTICLES_PATH, encoding="utf-8") as f:
        obj = json.load(f)
    rows = obj["rows"]
    print("文章清单:", os.path.basename(ARTICLES_PATH), "| 行:", len(rows))
    return rows


def load_annot():
    """读取标注：data/curation/blog_annotations.json。返回 url -> {direction, indexes}。"""
    if not os.path.exists(ANNOT_PATH):
        print("[WARN] 标注文件缺失:", ANNOT_PATH)
        return {}
    with io.open(ANNOT_PATH, encoding="utf-8") as f:
        obj = json.load(f)
    annot = {}
    for u, a in (obj.get("annotations") or {}).items():
        d = norm(a.get("direction") or "")
        ix = split_indexes(a.get("indexes"))
        if d or ix:
            annot[u] = {"direction": d, "indexes": ix}
    print("标注:", os.path.basename(ANNOT_PATH), "| 条目:", len(annot))
    return annot


def main():
    recs = []
    for row in load_articles():
        date = row.get("date") or ""
        title = row.get("title") or ""
        url = row.get("url") or ""
        column = row.get("column") or ""
        if not title and not url and not date:
            continue
        recs.append({
            "date": str(date).strip(),
            "title": norm(str(title)),
            "url": str(url).strip(),
            "column": norm(str(column)),
            "direction": "",
            "indexes": [],
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

    # 补录：内容标签（direction）/ 相关指数（indexes）——按 url 合并标注（见 load_annot）
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

    from collections import Counter
    print("来源:", os.path.basename(ARTICLES_PATH))
    print("文章:", len(out), "| 付费:", sum(1 for x in out if x["paid"]),
          "| 有内容标签:", sum(1 for x in out if x["direction"]),
          "| 有相关指数:", sum(1 for x in out if x["indexes"]))
    print("年份:", dict(sorted(Counter(x["date"][:4] for x in out).items())))
    print("所属栏目:", dict(Counter(x["column"] for x in out).most_common()))
    print("写入", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""博客（子弹列车公众号文章目录）数据生成 —— 手动维护，不参与自动流水线。
============================================================
输入：user_upload/子弹列车公众号历史内容目录（不完整）.xlsx
      （列：发布日期 / 文章链接[标题+超链接] / 投资方向 / 涉及指数）
输出：data/blogData.json
      字段：date / title / url / direction / indexes[] / paid

规则：
  - 按链接去重（同一篇文章只保留一条，合并字段、保留信息更全者）
  - 按发布日期倒序
  - 应用全站空格规范（中英文 / 中文数字之间不留空格）
  - EXTRA：xlsx 遗漏、由用户口头补录的文章
  - PAID_URLS：付费文章（列表标题后加金色「✦」）

用法：python3 sync_blog.py   （生成后需 python3 embed_data.py 刷新内嵌兜底）
"""
import io, json, os, re
import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "user_upload/子弹列车公众号历史内容目录（不完整）.xlsx")
OUT = os.path.join(BASE, "data/blogData.json")

CJK = '\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
R1 = re.compile(r'(?<=[' + CJK + r']) +(?=[0-9A-Za-z])')
R2 = re.compile(r'(?<=[0-9A-Za-z]) +(?=[' + CJK + r'])')


def norm(s):
    return R2.sub('', R1.sub('', s)) if isinstance(s, str) else s


# 用户补录（xlsx 中缺失）——付费文章「红利四大金刚」
EXTRA = [
    {"date": "2026-01-05",
     "title": "子弹列车版“红利四大金刚”",
     "url": "https://mp.weixin.qq.com/s/bSyegtCHH4YoOy7krLys2A",
     "direction": "红利",
     "indexes": []},
]

# 付费文章（用户标注，共 2 篇）
PAID_URLS = {
    "https://mp.weixin.qq.com/s/R2JEMADrlrTcUqtRrGIDOA",  # 标普生物科技：荒原之上，再育繁花（2026-02-02）
    "https://mp.weixin.qq.com/s/bSyegtCHH4YoOy7krLys2A",  # 子弹列车版“红利四大金刚”（2026-01-05）
}


def main():
    wb = openpyxl.load_workbook(SRC)
    ws = wb.active
    recs = []
    for r in range(2, ws.max_row + 1):
        d = ws.cell(r, 1).value
        bc = ws.cell(r, 2)
        c = ws.cell(r, 3).value
        ix = ws.cell(r, 4).value
        title = (bc.value or '').strip() if bc.value else ''
        url = bc.hyperlink.target if bc.hyperlink else None
        if not title and not url and not d:
            continue
        parts = []
        if ix:
            for seg in re.split(r'[，,、]\s*', str(ix)):
                seg = seg.strip()
                if seg:
                    parts.append(seg)
        recs.append({
            "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else (str(d) if d else ""),
            "title": norm(title),
            "url": url or "",
            "direction": norm(str(c).strip()) if c else "",
            "indexes": [norm(x) for x in parts],
        })

    for e in EXTRA:
        if not any(r["url"] and r["url"] == e["url"] for r in recs):
            recs.append(dict(e))

    by_url = {}
    for r in recs:
        k = r["url"] or (r["date"] + "|" + r["title"])
        if k not in by_url:
            by_url[k] = r
        else:
            a = by_url[k]
            if not a["direction"] and r["direction"]:
                a["direction"] = r["direction"]
            if len(r["indexes"]) > len(a["indexes"]):
                a["indexes"] = r["indexes"]
            if not a["date"] and r["date"]:
                a["date"] = r["date"]
            if r["date"] and a["date"] and r["date"] > a["date"]:
                a["date"] = r["date"]

    out = sorted(by_url.values(), key=lambda x: x["date"], reverse=True)
    for r in out:
        r["paid"] = r["url"] in PAID_URLS

    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    from collections import Counter
    print("文章:", len(out), "| 付费:", sum(1 for x in out if x["paid"]),
          "| 年份:", dict(Counter(x["date"][:4] for x in out)))
    print("写入", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()

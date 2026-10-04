#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
食息资讯（日报）同步脚本 · 消费端
====================================
只读 digest-db.json（坚果云同步目录内的稳定机器接口），生成网站数据文件。

⛔ 消费方约定（见同目录 DATA-SCHEMA.md）：
   1. 只读 digest-db.json，**不解析** yield-guide-daily-digest.html
      （HTML 只是同一份数据的视图，结构随改版变动；两者不一致时以 JSON 为准）
   2. **不执行** yield-guide-daily-digest-skill.md 里的采集流程
      （那是 Windows 生成端的事；消费方只读、不采集、不写入）
   3. 字段定义 / 使用示例 / 配色复用方式 → 同目录 DATA-SCHEMA.md

产出（网站 data/）：
   - dailyData.json      : db["digests"]（按期倒序；item 含 id/tags/time/source/text/url）
   - dailyTagColors.json : db["meta"]["tagColors"]（10 个标签的浅底/深字配色，供前端直接复用）

用法:
    python3 sync_daily.py
"""
import glob
import io
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
OUT_DATA = os.path.join(DATA_DIR, 'dailyData.json')
OUT_COLORS = os.path.join(DATA_DIR, 'dailyTagColors.json')

# digest-db.json 的候选位置（坚果云同步目录；跨设备时自动探测）
CANDIDATES = [
    '~/Library/CloudStorage/坚果云-vincent.watson@live.com/Codes/workbuddy/'
    'dividend-guide-digest-workbuddy/digest-db.json',
    '~/Nutstore Files/Codes/workbuddy/dividend-guide-digest-workbuddy/digest-db.json',
    'D:/Codes/workbuddy/dividend-guide-digest-workbuddy/digest-db.json',
]
GLOBS = [
    '~/Library/CloudStorage/*/Codes/workbuddy/*/digest-db.json',
    '~/Library/CloudStorage/*/**/dividend-guide-digest-workbuddy/digest-db.json',
    '~/坚果云/**/dividend-guide-digest-workbuddy/digest-db.json',
]

# 正文中禁止出现的强调符号（2026-09-20 用户要求：「今后也不要加这些符号了」）
#   生成端规范见 yield-guide-daily-digest-workbuddy/yield-guide-daily-digest-skill.md「改写规范」
#   （以及该工作区的 .workbuddy/memory/MEMORY.md「内容质量标准」）：
#   主体要自然写进句子，❌ 不用【央行】这类括号标注式写法。
#   此处做**消费端归一化兜底**——即便上游仍带【】，站点数据也保证干净，同时打印告警以便发现生成端回归。
MARKS = '【】'


def strip_marks(s):
    """去掉【】等强调符号，只删符号本身、保留符号内的文字（'【央行】'→'央行'）。"""
    if s is None:
        return s
    return ''.join(ch for ch in str(s) if ch not in MARKS)


def find_db():
    """定位 digest-db.json；多个命中时取修改时间最新的那个。

    性能：GLOBS 中的 `~/Library/CloudStorage/*/**/...` 会对整个坚果云目录树做递归 glob，
    当目录树巨大时可达 ~19 分钟（2026-10-01 实测 1122s）。因此：稳定位置（CANDIDATES）一旦命中
    即短路返回，仅在无候选命中时才退回落盘 glob（跨设备探测语义保留）。
    """
    hits = [os.path.expanduser(p) for p in CANDIDATES if os.path.exists(os.path.expanduser(p))]
    if not hits:
        for pat in GLOBS:
            hits += glob.glob(os.path.expanduser(pat), recursive=True)
    hits = sorted({os.path.realpath(h) for h in hits if os.path.isfile(h)})
    if not hits:
        return None
    return max(hits, key=os.path.getmtime)


def main():
    db_path = find_db()
    if not db_path:
        print('[WARN] 未找到 digest-db.json（坚果云同步目录）。现有 data/ 保持不变。')
        return
    print('数据源:', db_path)

    with io.open(db_path, 'r', encoding='utf-8') as fh:
        db = json.load(fh)

    if not isinstance(db, dict) or not isinstance(db.get('digests'), list):
        print('[ERROR] digest-db.json 结构异常：缺少 digests 数组')
        return

    meta = db.get('meta') or {}
    digests = db['digests']
    primary = set((meta.get('taxonomy') or {}).get('primary') or [])
    tag_colors = meta.get('tagColors') or {}

    # 轻量校验（宽容：字段不认识就忽略，不因多余字段报错）
    for d in digests:
        assert 'date' in d and isinstance(d.get('items'), list), 'digest 结构异常: %s' % str(d)[:80]
        for it in d['items']:
            assert 'tags' in it and 'text' in it, 'item 结构异常: %s' % str(it)[:80]
            if primary:
                stray = [t for t in it['tags'] if t not in primary]
                if stray:
                    print('[WARN] %s 含体系外标签 %s' % (it.get('id', '?'), stray))

    digests = sorted(digests, key=lambda d: d.get('date', ''), reverse=True)

    # 归一化：正文去掉【】强调符号（消费端兜底，2026-09-20 用户要求）
    marked = 0
    for d in digests:
        for it in d['items']:
            if isinstance(it.get('text'), str) and any(m in it['text'] for m in MARKS):
                marked += 1
                it['text'] = strip_marks(it['text'])
    if marked:
        print('[WARN] 正文含【】符号 %d 条，已在写入前剥离 —— 生成端应已停止使用该符号'
              '（见 digest-workbuddy/MEMORY.md「内容质量标准」），请检查上游是否回归' % marked)
    else:
        print('正文检查: 无【】符号 ✅')

    os.makedirs(DATA_DIR, exist_ok=True)
    with io.open(OUT_DATA, 'w', encoding='utf-8') as f:
        json.dump(digests, f, ensure_ascii=False, indent=1)
    with io.open(OUT_COLORS, 'w', encoding='utf-8') as f:
        json.dump(tag_colors, f, ensure_ascii=False, indent=1)

    total = sum(len(d.get('items', [])) for d in digests)
    print('dailyData 生成: %d 期 / %d 条 -> %s' % (len(digests), total, OUT_DATA))
    print('dailyTagColors 生成: %d 个标签 -> %s' % (len(tag_colors), OUT_COLORS))
    for d in digests:
        print('  %s | %d 条' % (d.get('date'), len(d.get('items', []))))


if __name__ == '__main__':
    main()

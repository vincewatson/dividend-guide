#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
食息指南 · 内嵌兜底数据刷新脚本
====================================
从 data/*.json 生成 index.html 中内嵌兜底数组（离线兜底）的最新版本，
确保即使 data/*.json 无法加载（断网/CDN 失效），页面也能展示最近一次的数据。

用法:
    python3 embed_data.py            # 刷新 index.html 内嵌数据（自动备份 + 语法验证）
    python3 embed_data.py --preview  # 预览将要替换的数组大小（不写入）

安全机制:
    - 括号平衡定位数组边界（不用正则非贪婪，避免误匹配嵌套数组）
    - 替换后自动用 node 做 JS 语法验证，失败则自动回滚并报错
    - 替换前自动备份 index.html → index.html.bak-<日期>
"""
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
HTML_PATH = os.path.join(BASE, 'index.html')

MAP = {
    'assetData.json': 'assetData',
    'indexData.json': 'indexData',
    'cnEtfData.json': 'cnEtfData',
    'hkEtfData.json': 'hkEtfData',
    'etfData.json': 'etfData',
    'fundData.json': 'fundData',
    'moneyFundData.json': 'moneyFundData',
    'reitsData.json': 'reitsData',
    'dailyData.json': 'dailyData',
}

INDEX_KEEP_FIELDS = [
    'code', 'name', 'fullname', 'publisher', 'listedDate', 'market',
    'components', 'currency', 'weight', 'weightExtra', 'fundCount',
    'yield', 'yieldNum', 'yrChange', 'dailyChange', 'dailyDate',
    'fullReturn', 'adjustCycle', 'adjustDate',
]


def load_json(fname):
    p = os.path.join(DATA_DIR, fname)
    if not os.path.exists(p):
        return None
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def find_array(html, var_name):
    """括号平衡定位 const varName = [...] 的精确边界，返回 (start, end) 或 None"""
    m = re.search(r'const\s+' + re.escape(var_name) + r'\s*=\s*\[', html)
    if not m:
        return None
    depth = 1
    i = m.end()
    while i < len(html):
        if html[i] == '[':
            depth += 1
        elif html[i] == ']':
            depth -= 1
            if depth == 0:
                return m.start(), i + 1
        i += 1
    return None


def verify_js(html):
    """用 node 验证所有 <script> 语法，返回 (ok, error)"""
    try:
        r = subprocess.run(
            ['node', '-e', """
const fs = require('fs');
const html = fs.readFileSync(process.argv[1], 'utf-8');
const scripts = [...html.matchAll(/<script>([\\s\\S]*?)<\\/script>/g)];
for (const s of scripts) { try { new Function(s[1]); } catch(e) { console.error(e.message.slice(0,200)); process.exit(1); } }
console.log('OK');
""", HTML_PATH],
            capture_output=True, text=True, timeout=30)
        return r.returncode == 0, r.stderr.strip()
    except Exception as e:
        return False, str(e)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', action='store_true', help='仅预览不写入')
    args = ap.parse_args()

    html = io.open(HTML_PATH, 'r', encoding='utf-8').read()
    report = {}
    changes = 0
    skipped = []

    for fname, var_name in MAP.items():
        data = load_json(fname)
        if data is None:
            skipped.append((fname, '数据文件缺失'))
            continue
        if not isinstance(data, list):
            skipped.append((fname, '非数组结构，跳过'))
            continue
        if fname == 'indexData.json':
            data = [{k: x[k] for k in INDEX_KEEP_FIELDS if k in x} for x in data]
        new_js = json.dumps(data, ensure_ascii=False)
        loc = find_array(html, var_name)
        if not loc:
            skipped.append((fname, 'index.html 中未找到内嵌数组'))
            continue
        start, end = loc
        old_text = html[start:end]
        new_text = 'const ' + var_name + ' = ' + new_js + ';'
        old_size = len(old_text)
        new_size = len(new_text)
        report[var_name] = {'old_chars': old_size, 'new_chars': new_size, 'records': len(data)}
        if args.preview:
            flag = ' [有变化]' if old_text != new_text else ' [无变化]'
            print('{}: {}字符 -> {}字符 ({}条){}'.format(
                var_name, old_size, new_size, len(data), flag))
            continue
        if old_text != new_text:
            html = html[:start] + new_text + html[end:]
            changes += 1

    if args.preview:
        print('\n预览完成。{} 个数组有变化，跳过 {} 个'.format(changes, len(skipped)))
        return

    if changes == 0:
        print('无变化，未写入')
        return

    # 备份原文件
    bak = HTML_PATH + '.bak-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy2(HTML_PATH, bak)
    print('已备份原文件: {}'.format(bak))

    # 写入
    io.open(HTML_PATH, 'w', encoding='utf-8').write(html)

    # 语法验证，失败自动回滚
    ok, err = verify_js(html)
    if not ok:
        shutil.copy2(bak, HTML_PATH)
        print('❌ JS 语法验证失败，已自动回滚: {}'.format(err))
        sys.exit(1)

    report_path = os.path.join(BASE, 'backup', 'embed_report.json')
    io.open(report_path, 'w', encoding='utf-8').write(
        json.dumps({'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'arrays': report, 'skipped': skipped}, ensure_ascii=False, indent=1))
    print('✅ 已刷新 {} 个内嵌数组（JS 验证通过）'.format(changes))
    for name, r in report.items():
        print('  {}: {} 字符 -> {} 字符 ({}条)'.format(name, r['old_chars'], r['new_chars'], r['records']))
    if skipped:
        print('跳过:')
        for s in skipped:
            print('  -', s)


if __name__ == '__main__':
    main()

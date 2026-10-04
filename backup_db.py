#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
食息指南 · 本地数据库备份脚本
====================================
把网站全部数据（data/*.json + Excel 源文件）打包为本地数据库快照，
确保即使某天无法再拉取 Wind / iFind 在线数据，现有数据也完整可用。

功能:
    1. 快照目录备份: 备份到 backup/<YYYY-MM-DD>_<HHMM>/（完整复制所有数据文件）
    2. 单一离线归档: 生成 backup/offline-db-<日期>.json（所有数据合并为一个文件，含元数据）
    3. 自动清理: 只保留最近 KEEP_DAYS 天（默认 30）的快照，更早的自动删除
    4. 验证: 备份后校验 JSON 完整性，输出统计

用法:
    python3 backup_db.py                # 执行备份
    python3 backup_db.py --check        # 仅校验现有数据完整性（不备份）
    python3 backup_db.py --list         # 列出已有快照

说明:
    - 快照目录中的文件是"最后已知良好"数据，任何时刻都可直接拷回 data/ 恢复。
    - offline-db-<日期>.json 是单一归档文件，包含全部数据，便于整体迁移/导入。
"""
import argparse
import datetime
import io
import json
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
BACKUP_DIR = os.path.join(BASE, 'backup')
KEEP_DAYS = 30  # 快照保留天数

# 需要纳入备份的数据文件（data/ 下）
DATA_FILES = [
    'assetData.json', 'assetHistory.json', 'cnEtfData.json', 'dailyData.json',
    'dailyTagColors.json', 'divNoRecord.json', 'etfData.json', 'fundData.json',
    'hkEtfData.json', 'indexData.json', 'moneyFundData.json', 'reitsData.json',
    'yuebaoHistory.json',
]
# Excel 源文件（data/ 根目录 + data/user/ 子目录）
EXCEL_FILES = [
    '食息指南(EXCEL-Wind)-快照2.xlsx',
    '食息指南PRO(EXCEL-Wind)-快照2.xlsx',
    '食息指南Pro-飞书.xlsx',
]


def validate_data():
    """校验 data/*.json 完整性，返回 (ok_count, total, errors)"""
    errors = []
    ok = 0
    total = 0
    for f in DATA_FILES:
        p = os.path.join(DATA_DIR, f)
        if not os.path.exists(p):
            errors.append(f + ': 文件缺失')
            continue
        total += 1
        try:
            with io.open(p, 'r', encoding='utf-8') as fh:
                json.load(fh)
            ok += 1
        except Exception as e:
            errors.append(f + ': JSON 损坏 (' + str(e) + ')')
    return ok, total, errors


def build_offline_db():
    """把所有数据合并为一个离线归档字典"""
    db = {
        '_meta': {
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'note': '食息指南 离线数据库归档（Wind/iFind 断源后仍可完整使用）',
            'files': DATA_FILES,
        },
        'data': {},
    }
    for f in DATA_FILES:
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            with io.open(p, 'r', encoding='utf-8') as fh:
                db['data'][f] = json.load(fh)
    return db


def do_backup():
    print('===== 食息指南 · 本地数据库备份 =====')
    ok, total, errors = validate_data()
    print('数据校验: {}/{} 个 JSON 正常'.format(ok, total))
    if errors:
        print('[WARN] 以下文件异常（仍会备份现有内容）:')
        for e in errors:
            print('  -', e)

    ts = datetime.datetime.now().strftime('%Y-%m-%d_%H%M')
    snap_dir = os.path.join(BACKUP_DIR, ts)
    os.makedirs(snap_dir, exist_ok=True)

    # 1. 复制 JSON 数据
    copied = 0
    for f in DATA_FILES:
        src = os.path.join(DATA_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(snap_dir, f))
            copied += 1
    # 2. 复制 Excel 源文件
    for f in EXCEL_FILES:
        for sub in ['', 'user']:
            src = os.path.join(DATA_DIR, sub, f) if sub else os.path.join(DATA_DIR, f)
            if os.path.exists(src):
                dst = os.path.join(snap_dir, sub) if sub else snap_dir
                os.makedirs(dst, exist_ok=True)
                shutil.copy2(src, os.path.join(dst, f))
                break
    print('快照已保存: {}（{} 个 JSON + Excel 源）'.format(snap_dir, copied))

    # 3. 生成单一离线归档
    db = build_offline_db()
    archive_path = os.path.join(BACKUP_DIR, 'offline-db-' + ts[:10] + '.json')
    with io.open(archive_path, 'w', encoding='utf-8') as fh:
        json.dump(db, fh, ensure_ascii=False, indent=1)
    print('离线归档已生成: {}（{:.1f}KB）'.format(archive_path, os.path.getsize(archive_path) / 1024))

    # 4. 清理过期快照
    cleaned = 0
    cutoff = datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)
    for name in sorted(os.listdir(BACKUP_DIR)):
        d = os.path.join(BACKUP_DIR, name)
        if not os.path.isdir(d):
            continue
        try:
            d_date = datetime.datetime.strptime(name[:10], '%Y-%m-%d').date()
            if d_date < cutoff:
                shutil.rmtree(d)
                cleaned += 1
        except (ValueError, IndexError):
            continue
    print('清理过期快照: {} 个（保留最近 {} 天）'.format(cleaned, KEEP_DAYS))
    print('✅ 备份完成')


def list_backups():
    if not os.path.isdir(BACKUP_DIR):
        print('暂无备份')
        return
    for name in sorted(os.listdir(BACKUP_DIR)):
        d = os.path.join(BACKUP_DIR, name)
        if os.path.isdir(d):
            n = len([x for x in os.listdir(d) if x.endswith('.json')])
            print('  {}: {} 个数据文件'.format(name, n))
        else:
            print('  {}: 归档'.format(name))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='仅校验数据完整性')
    ap.add_argument('--list', action='store_true', help='列出已有快照')
    args = ap.parse_args()
    if args.check:
        ok, total, errors = validate_data()
        print('数据校验: {}/{} 个 JSON 正常'.format(ok, total))
        for e in errors:
            print('  -', e)
    elif args.list:
        list_backups()
    else:
        do_backup()


if __name__ == '__main__':
    main()

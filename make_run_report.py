#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行报告生成器（2026-10-07 · 重构阶段：每次运行留一份报告）

读取本次运行落盘的：
  - `.run_report.jsonl`      每步事件 {label,status,reason}（run_py / skip 分支写入）
  - `.run_timings.jsonl`     每步耗时 {label,sec,rc}
  - `.run_usage_baseline.json` 运行开始时的 .wind_usage 快照（用于算「本次」增量）
  - `.wind_usage/<date>.json`  当日累计（含本次）
  - `.wind_pending.json`     额度不足待补
输出：
  - `logs/update-YYYYMMDD-HHMM.md`

用法（auto_sync_deploy.sh 末尾）：
    python3 make_run_report.py --mode daily --deploy skipped
"""
import argparse
import datetime
import io
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
import wind_client  # noqa  提供 load()/used_mode()/MODE/BUDGET/load_pending()
import lifecycle_common as lc  # 清单进出机制 · 共享工具（.list_changes.json 读取）

REPORT_JSONL = os.path.join(BASE, '.run_report.jsonl')
BASELINE = os.path.join(BASE, '.run_usage_baseline.json')
LOGS_DIR = os.path.join(BASE, 'logs')


def _read_jsonl(p):
    out = []
    try:
        with io.open(p, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        pass
    return out


def _baseline():
    try:
        with io.open(BASELINE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"total": 0, "by_step": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='daily')
    ap.add_argument('--reason', default='')     # 本次档位说明（auto_sync_deploy.sh 传入 MODE_REASON）
    ap.add_argument('--deploy', default='skipped')
    ap.add_argument('--rc-checks', default='')
    args = ap.parse_args()

    now = datetime.datetime.now()
    events = _read_jsonl(REPORT_JSONL)
    timings = {r.get('label'): r for r in _read_jsonl(os.path.join(BASE, '.run_timings.jsonl'))}
    cur = wind_client.load()
    base = _baseline()
    pend = wind_client.load_pending()

    cur_by_step = cur.get('by_step') or {}
    base_by_step = base.get('by_step') or {}

    def delta_n(label):
        return int(cur_by_step.get(label, {}).get('n', 0)) - int(base_by_step.get(label, {}).get('n', 0))

    run_total = int(cur.get('total', 0)) - int(base.get('total', 0))
    # 档位名（--mode 值可能是 daily / weekly / daily+weekly）
    mode_name = {'daily': '日更', 'weekly': '周更', 'daily+weekly': '日更+周更'}.get(args.mode, args.mode)
    budget = wind_client.BUDGET

    lines = []
    lines.append('# 食息指南 · 数据更新运行报告\n')
    lines.append('- 生成时间：%s' % now.strftime('%Y-%m-%d %H:%M:%S'))
    lines.append('- 档位：**%s**（`SX_WIND_MODE=%s`）' % (mode_name, args.mode))
    lines.append('- 本次档位：**%s**%s' % (mode_name, ('（%s）' % args.reason) if args.reason else ''))
    lines.append('- Wind 调用：**本次 %d 次**；当日该档位累计 %d / 预算 %d；当日合计 %d / 硬上限 %d'
                 % (run_total, wind_client.used_mode(), budget,
                    int(cur.get('total', 0)), wind_client.CAP))
    if pend:
        lines.append('- 待补（额度不足，下次先跑）：%s' % '、'.join(pend))
    else:
        lines.append('- 待补：无')
    lines.append('- 部署：%s' % ('跳过（SX_NO_DEPLOY=1）' if args.deploy == 'skipped' else '已执行'))
    lines.append('')
    lines.append('| 步骤/脚本 | 结果 | 说明 | Wind | 耗时(s) |')
    lines.append('|---|---|---|---:|---:|')
    STATUS = {'ran': '✅ 已更新', 'fail': '❌ 失败（保留旧值）', 'skip': '⏭ 本次不跑'}
    for e in events:
        label = e.get('label', '?')
        st = e.get('status', '')
        reason = e.get('reason', '') or ''
        sec = timings.get(label, {}).get('sec', '')
        if st == 'skip':
            lines.append('| %s | %s | %s | — | — |' % (label, STATUS['skip'], reason))
        else:
            lines.append('| %s | %s | %s | %d | %s |'
                         % (label, STATUS.get(st, st), reason, delta_n(label),
                            sec if sec != '' else '—'))

    # 汇总
    ok = sum(1 for e in events if e.get('status') == 'ran')
    fail = sum(1 for e in events if e.get('status') == 'fail')
    skip = sum(1 for e in events if e.get('status') == 'skip')
    lines.append('')
    lines.append('**汇总**：已更新 %d 步、失败 %d 步、本次不跑 %d 步；本次 Wind %d 次。'
                 % (ok, fail, skip, run_total))
    lines.append('')
    lines.append('> 说明：「本次不跑」的原因包括 **非本档位步骤**（如周更不含日更步骤）与 **预检判定已是最新交易日**（无新数据）。')

    # 清单变动（2026-10-07）：列出 .list_changes.json 中 date==今天 的条目（无则写「无」）
    lines.append('')
    lines.append('## 清单变动')
    _ACT = {'add': '自动补入', 'retire': '移出', 'observe': '待观察'}
    _LIST = {'cnEtf': '境内红利ETF', 'hkEtf': '港交所红利ETF', 'reits': 'REITs',
             'etf': '月月分红ETF', 'fund': '月月分红基金', 'money': '货币基金'}
    _chg = lc.today_events()
    if not _chg:
        lines.append('无')
    else:
        lines.append('| 动作 | 清单 | 代码 | 名称 | 原因 | 来源 |')
        lines.append('|---|---|---|---|---|---|')
        for e in _chg:
            lines.append('| %s | %s | %s | %s | %s | %s |' % (
                _ACT.get(e.get('action'), e.get('action') or ''),
                _LIST.get(e.get('list'), e.get('list') or ''),
                e.get('code') or '', e.get('name') or '',
                e.get('reason') or '', e.get('source') or ''))

    # 月月名单空日期补查（2026-10-08）：列出 etfData/fundData 中 divDate 为空/缺失的成员
    #   （无论上面「清单变动」是否为「无」，都输出本小节）
    lines.append('')
    lines.append('### 月月名单中分红日期为空（需补查）')
    _empty = []
    for _fn, _lbl in (('etfData.json', '月月分红ETF'), ('fundData.json', '月月分红基金')):
        try:
            with io.open(os.path.join(BASE, 'data', _fn), encoding='utf-8') as _f:
                _rows = json.load(_f)
        except Exception:
            _rows = []
        for _it in (_rows or []):
            if not isinstance(_it, dict):
                continue
            if not _it.get('divDate'):
                _empty.append((_lbl, _it.get('code') or '', _it.get('name') or ''))
    if _empty:
        lines.append('| 清单 | 代码 | 名称 |')
        lines.append('|---|---|---|')
        for _lbl, _code, _name in _empty:
            lines.append('| %s | %s | %s |' % (_lbl, _code, _name))
    else:
        lines.append('（无）')

    # 港ETF 行情快照覆盖（2026-10-08）：日更 sync_product_quotes 应给全部港ETF 取到行情。
    #   背景：港股代码 4→5 位后未转回 4 位调 Wind → 全部取不到；本次修复后此处应「全覆盖」。
    lines.append('')
    lines.append('### 港ETF 行情快照覆盖（productQuotes）')
    _hkcodes = []
    try:
        with io.open(os.path.join(BASE, 'data', 'hkEtfData.json'), encoding='utf-8') as _f:
            _hkcodes = [x.get('code') for x in (json.load(_f) or [])
                        if isinstance(x, dict) and x.get('code')]
    except Exception:
        _hkcodes = []
    _q = {}
    try:
        with io.open(os.path.join(BASE, 'data', 'productQuotes.json'), encoding='utf-8') as _f:
            _q = (json.load(_f) or {}).get('quotes') or {}
    except Exception:
        _q = {}
    _last = {c: ((_q.get(c) or [{}])[-1].get('date') or '') for c in _hkcodes}
    _maxd = max(_last.values()) if _last and any(_last.values()) else ''
    _cov = [c for c in _hkcodes if _last.get(c) == _maxd and _maxd]
    _miss = [c for c in _hkcodes if c not in _cov]
    if not _hkcodes:
        lines.append('- （未找到 hkEtfData.json）')
    else:
        lines.append('- 港ETF **%d/%d** 只有最新快照（最新快照日 %s）%s' % (
            len(_cov), len(_hkcodes), _maxd or '—',
            '' if not _miss else '；缺：' + '、'.join(_miss)))

    os.makedirs(LOGS_DIR, exist_ok=True)
    out = os.path.join(LOGS_DIR, 'update-%s.md' % now.strftime('%Y%m%d-%H%M'))
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).encode('utf-8', 'replace').decode('utf-8') + '\n')
    print('[运行报告] 已生成：%s' % os.path.relpath(out, BASE))
    return 0


if __name__ == '__main__':
    sys.exit(main())

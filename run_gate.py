#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日整跑闸（2026-10-06 新增）—— 防止同日重复整跑耗尽 Wind 额度。

事故复盘：2026-10-06 因多次整跑 `auto_sync_deploy.sh`（外加零散单项验证）把 Wind 当日
2000 次额度耗尽。本闸在流水线**开始时**记录当日整跑次数；当日已达上限则拒绝启动
（退出码 3），避免「跑一半没额度」的尴尬与浪费。

- 状态文件：`.run_state.json`（{date, count, lastStart}）
- 上限：`SX_MAX_FULL_RUNS`（默认 1）
- 强制再跑：`SX_FORCE_RUN=1`
- 顺带打印今日 Wind 调用用量（读 `.wind_calls_<date>`，由 wind_guard_cli.mjs 记录）

用法（auto_sync_deploy.sh 开头）：
    python3 run_gate.py || { echo "被额度闸拦截"; exit 0; }
"""
import datetime
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, ".run_state.json")
MAX = int(os.environ.get("SX_MAX_FULL_RUNS", "1"))
CAP = int(os.environ.get("SX_WIND_DAILY_CAP", "2000"))

today = datetime.date.today().isoformat()

rec = {}
try:
    with open(STATE, encoding="utf-8") as f:
        rec = json.load(f)
except Exception:
    rec = {}

n = rec.get("count", 0) if rec.get("date") == today else 0

# 今日 Wind 调用用量（读守卫计数文件）
used = 0
try:
    with open(os.path.join(BASE, ".wind_calls_%s" % today), encoding="utf-8") as f:
        used = sum(1 for line in f if line.strip())
except Exception:
    used = 0

print("[额度闸] 今日 Wind 已用 %d/%d 次；今日已整跑 %d 次（上限 %d）。" % (used, CAP, n, MAX))

if n >= MAX and os.environ.get("SX_FORCE_RUN") != "1":
    print("[额度闸] ⛔ 今日整跑已达标，拒绝再跑。如确需再跑：设 SX_FORCE_RUN=1 后重试。")
    sys.exit(3)

rec = {
    "date": today,
    "count": n + 1,
    "lastStart": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
}
try:
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
except Exception:
    pass

print("[额度闸] ✅ 今日第 %d 次整跑（上限 %d）——开始。" % (rec["count"], MAX))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 Wind 调用客户端（2026-10-06 · 阶段 0：只计数、不改逻辑）

本模块是数据更新流程重构的**唯一 Wind 调用入口**，设计以
`docs/data-governance/update-redesign.md` 为准。

阶段 0（本版）只做一件事：**给每次 Wind 调用计数**，为后续「预算 + 断点续跑」提供依据，
**不改变任何查询逻辑、措辞、重试与并发**。

用法（各脚本）：
    import wind_client
    ...
    cp = wind_client.run(['node', wind_client.CLI, 'call', server, tool, q], ...)  # 与 subprocess.run 同形

计数：
    `.wind_usage/YYYY-MM-DD.json` -> {"date", "total", "by_step": {步骤: {"n": 次数, "sec": 累计秒}}}
    步骤名取自环境变量 `SX_WIND_STEP`（由 auto_sync_deploy.sh 的 run_py 设为该步 label，
    与 `.run_timings.jsonl` 的 label 对齐，便于把「次数」与「耗时」合成一张表）；
    未设置时回退为 `sys.argv[0]` 文件名。

说明：真实 CLI 经 `wind_guard_cli.mjs`（每日硬上限，独立于本模块的逐步计数）。
阶段 1 将在此处加入「日/周预算、额度用尽即停、pending 续跑」。

自测：`python3 wind_client.py` 打印当日用量与按步明细（report）。
"""
import datetime
import json
import os
import subprocess
import sys
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
USAGE_DIR = os.path.join(BASE, ".wind_usage")
# 真实 CLI 经「额度守卫」包装器（每日硬上限；见 wind_guard_cli.mjs）
CLI = os.path.join(BASE, "wind_guard_cli.mjs")
# 当日硬上限（阶段 0 仅记录，不拦截；拦截在阶段 1）
CAP = int(os.environ.get("SX_WIND_DAILY_CAP", "2000"))

_LOCK = threading.Lock()


def _today():
    return datetime.date.today().isoformat()


def _step():
    """当前步骤名：优先 SX_WIND_STEP（流水线 run_py 注入），否则用脚本文件名。"""
    return os.environ.get("SX_WIND_STEP") or os.path.basename(sys.argv[0] or "unknown")


def _path(day):
    return os.path.join(USAGE_DIR, "%s.json" % day)


def load(day=None):
    """读取某日用量（默认今天）；无文件返回空结构。"""
    day = day or _today()
    try:
        with open(_path(day), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"date": day, "total": 0, "by_step": {}}


def _save(obj):
    try:
        os.makedirs(USAGE_DIR, exist_ok=True)
        with open(_path(obj["date"]), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    except Exception:
        pass  # 计数失败绝不阻断取数


def record(n=1, sec=0.0, step=None):
    """记 n 次调用、耗时 sec 秒到当日用量。线程安全（并发脚本安全）。"""
    step = step or _step()
    with _LOCK:
        obj = load()
        obj["total"] = int(obj.get("total", 0)) + n
        bs = obj.setdefault("by_step", {})
        e = bs.setdefault(step, {"n": 0, "sec": 0.0})
        e["n"] = int(e.get("n", 0)) + n
        e["sec"] = round(float(e.get("sec", 0.0)) + float(sec), 1)
        _save(obj)


def run(cmd, **kwargs):
    """透传 `subprocess.run`，并把本次 Wind 调用计入当日用量。

    参数/返回值与 `subprocess.run` **完全一致**（返回 CompletedProcess），
    因此调用方无需改动解析逻辑。
    """
    t0 = time.time()
    cp = subprocess.run(cmd, **kwargs)
    try:
        record(1, time.time() - t0)
    except Exception:
        pass
    return cp


def report(day=None):
    """返回「步骤 → 次数/累计耗时」的可读文本（按首次调用顺序，即流水线顺序）。"""
    obj = load(day)
    out = ["日期: %s    合计: %d 次" % (obj.get("date"), int(obj.get("total", 0)))]
    for step, e in (obj.get("by_step") or {}).items():
        out.append("  %-40s %4d 次   %6.1f s" % (step, int(e.get("n", 0)), float(e.get("sec", 0.0))))
    return "\n".join(out)


if __name__ == "__main__":
    print(report())

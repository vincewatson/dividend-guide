#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 Wind 调用客户端 —— 数据更新流程重构的唯一 Wind 入口

以 `docs/data-governance/update-redesign.md` 为准。

阶段 0（2026-10-06）：只计数（`.wind_usage/YYYY-MM-DD.json`，按日 + 步骤）。
阶段 1（2026-10-07）：加每日预算 + 额度用尽优雅停止 + pending 续补。

预算（按「运行档位」的当日调用数）：
    - 日更（SX_WIND_MODE=daily，默认）：SX_WIND_BUDGET 默认 300
    - 周更（SX_WIND_MODE=weekly）      ：SX_WIND_BUDGET 默认 650
    - 当天合计软上限 SX_WIND_DAY_CAP（默认 1600，账号 A 规则）
    当日该档位的调用数达到预算 → **拒绝**后续调用（返回 rc=3 的合成结果），
    并把当前步骤记入 `.wind_pending.json`；调用方视 rc≠0 为失败 → 走既有「重试/保留旧值」逻辑，
    安全降级、绝不误改数据（额度不足不失败）。下次运行先补 pending（见 auto_sync_deploy.sh）。

用法（各脚本）：
    import wind_client
    cp = wind_client.run(['node', wind_client.CLI, 'call', server, tool, q], ...)  # 与 subprocess.run 同形

计数：`.wind_usage/YYYY-MM-DD.json` -> {"date","total","by_step":{...},"by_mode":{...}}
步骤名：环境变量 `SX_WIND_STEP`（run_py 注入，与 `.run_timings.jsonl` 的 label 对齐）。

自测：`python3 wind_client.py`（用量/预算报表）；`--pending`（打印待补步骤）；`--clear-pending`。
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
PENDING_PATH = os.path.join(BASE, ".wind_pending.json")
# 真实 CLI 经「额度守卫」包装器（每日硬上限 2000；见 wind_guard_cli.mjs）
CLI = os.path.join(BASE, "wind_guard_cli.mjs")

# 运行档位：daily（默认）/ weekly
_MODE_RAW = (os.environ.get("SX_WIND_MODE") or "daily").strip().lower()
MODE = "weekly" if _MODE_RAW.startswith("w") else "daily"
_DEFAULT_BUDGET = {"daily": 300, "weekly": 650}   # 2026-10-07：周更 800→650（规则：日更≤300 / 周更≤650）
BUDGET = int(os.environ.get("SX_WIND_BUDGET", str(_DEFAULT_BUDGET[MODE])))
# 全局每日硬上限（守卫层 2000）与「当天合计」软上限（账号 A 规则：当天合计 ≤1600）
CAP = int(os.environ.get("SX_WIND_DAILY_CAP", "2000"))
DAY_CAP = int(os.environ.get("SX_WIND_DAY_CAP", "1600"))

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
            obj = json.load(f)
        obj.setdefault("by_mode", {})
        return obj
    except Exception:
        return {"date": day, "total": 0, "by_step": {}, "by_mode": {}}


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
        bm = obj.setdefault("by_mode", {})
        bm[MODE] = int(bm.get(MODE, 0)) + n
        _save(obj)


def used_today():
    """当日总调用数（跨档位）。"""
    return int(load().get("total", 0))


def used_mode():
    """当日「本档位」调用数（预算基准）。"""
    return int(load().get("by_mode", {}).get(MODE, 0))


def remaining():
    return max(0, BUDGET - used_mode())


# ---------------------------------------------------------------------------
# pending（额度不足待补）
# ---------------------------------------------------------------------------
def _load_pending_file():
    try:
        with open(PENDING_PATH, encoding="utf-8") as f:
            obj = json.load(f)
    except Exception:
        obj = {}
    obj.setdefault("steps", [])
    return obj


def _save_pending(obj):
    try:
        with open(PENDING_PATH, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def add_pending(step=None):
    step = step or _step()
    with _LOCK:
        obj = _load_pending_file()
        if step not in obj["steps"]:
            obj["steps"].append(step)
        obj["updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        obj["mode"] = MODE
        _save_pending(obj)


def load_pending():
    return _load_pending_file().get("steps", [])


def clear_pending():
    _save_pending({"steps": [], "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})


# ---------------------------------------------------------------------------
# 调用
# ---------------------------------------------------------------------------
def _refused(cmd, kwargs):
    """预算用尽时的合成结果（rc=3），stdout/stderr 类型与 kwargs 的 text 设置一致。"""
    msg = ("[wind_client] %s 档位今日调用 %d/%d、当日合计 %d/%d → 已达上限，拒绝本次调用并记入 pending。"
           % (MODE, used_mode(), BUDGET, used_today(), DAY_CAP))
    text = bool(kwargs.get("text") or kwargs.get("encoding") or kwargs.get("universal_newlines"))
    return subprocess.CompletedProcess(cmd, 3,
                                       "" if text else b"",
                                       (msg + "\n") if text else (msg + "\n").encode("utf-8"))


def run(cmd, **kwargs):
    """透传 `subprocess.run`，并把本次 Wind 调用计入当日用量。

    额度用尽（本档位当日调用 ≥ 预算）时 **不再发起真实调用**：记入 pending 并返回 rc=3 的
    合成 CompletedProcess，使调用方按既有「失败/保留旧值」路径安全降级。
    参数/返回值其余与 `subprocess.run` 一致。
    """
    if used_mode() >= BUDGET or used_today() >= DAY_CAP:
        add_pending()
        return _refused(cmd, kwargs)
    t0 = time.time()
    cp = subprocess.run(cmd, **kwargs)
    try:
        record(1, time.time() - t0)
    except Exception:
        pass
    return cp


def report(day=None):
    """返回「档位/预算/用量 + 步骤明细」的可读文本。"""
    obj = load(day)
    out = ["日期: %s" % obj.get("date")]
    out.append("档位: %s    预算: %d 次/日    本档已用: %d    剩余: %d"
               % (MODE, BUDGET, used_mode(), remaining()))
    out.append("当日合计: %d 次（硬上限 %d）" % (int(obj.get("total", 0)), CAP))
    bm = obj.get("by_mode") or {}
    if bm:
        out.append("按档位: " + "  ".join("%s=%d" % (k, v) for k, v in bm.items()))
    for step, e in (obj.get("by_step") or {}).items():
        out.append("  %-40s %4d 次   %6.1f s" % (step, int(e.get("n", 0)), float(e.get("sec", 0.0))))
    pend = load_pending()
    if pend:
        out.append("待补(pending): " + " ".join(pend))
    return "\n".join(out)


def main():
    argv = sys.argv[1:]
    if "--pending" in argv:
        print(" ".join(load_pending()))
        return
    if "--clear-pending" in argv:
        clear_pending()
        print("[wind_client] pending 已清空")
        return
    print(report())


if __name__ == "__main__":
    main()

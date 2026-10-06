#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易日历（A股 / 港股）—— 单一真实来源

- 数据源：`market_calendar.json`（各年『工作日休市』）。
- **收盘时间（北京时间）**：A股 **15:30**、港股 **16:30**。
  若「今天」是交易日但**尚未到该市场的收盘时点**，则今天**还不算**最新交易日，应取**上一交易日**
  （当天数据尚未生成）。这解决了「凌晨/盘中运行」时把今天误当作最新交易日的问题。

被 `sync_div_history.py` / `sync_daily_change.py` / `preflight.py` / `check_data.py` 共同引用。
"""
import datetime
import io
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CAL_PATH = os.path.join(BASE, 'market_calendar.json')
CN, HK = 'CN', 'HK'
# 各市场「数据可用」的收盘时点（北京时间，含）；可用环境变量覆盖
CLOSE = {
    CN: datetime.time(15, 30),
    HK: datetime.time(16, 30),
}

try:
    with io.open(CAL_PATH, encoding='utf-8') as _f:
        _CAL = json.load(_f)
except Exception:
    _CAL = {}


def covered(mkt, year):
    return str(year) in _CAL.get(mkt, {})


def is_trading_day(mkt, dd):
    if dd.weekday() >= 5:
        return False
    return dd.isoformat() not in set(_CAL.get(mkt, {}).get(str(dd.year), []))


def last_trading_day(mkt, dd):
    """≤ dd 的最近交易日（纯日期口径，不考虑收盘时间；用于历史日期）。"""
    x = dd
    for _ in range(40):
        if is_trading_day(mkt, x):
            return x
        x -= datetime.timedelta(days=1)
    return None


def latest_trading_day(mkt, now=None):
    """当前应已可用的「最新交易日」——**考虑收盘时间**：
    今天若为交易日且已过收盘时点（CN 15:30 / HK 16:30）→ 今天；
    否则（非交易日 / 尚未收盘）→ 上一交易日。`now` 取本地（北京）时间。"""
    now = now or datetime.datetime.now()
    d = now.date()
    if is_trading_day(mkt, d) and now.time() >= CLOSE.get(mkt, datetime.time(23, 59)):
        return d
    return last_trading_day(mkt, d - datetime.timedelta(days=1))


def market_of(item):
    """指数所属日历市场：'港股' → HK；其余（沪深/沪市/深市/沪港深/未知）→ CN；未知按代码后缀兜底。"""
    m = str(item.get('market') or '')
    if m == '港股':
        return HK
    if m:
        return CN
    return HK if str(item.get('code') or '').endswith('.HI') else CN

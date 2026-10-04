#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
货币基金收益率实时更新脚本
====================================
Wind 快照 Excel 里的货币基金收益率是导出时的旧值，
本脚本用 Wind MCP 实时拉取天弘余额宝（及其他头部货基）的最新 7 日年化，
更新 data/moneyFundData.json。

用法:
    python3 sync_money_fund.py
"""
import io, json, os, subprocess, time, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
MONEY_JSON = os.path.join(DATA_DIR, 'moneyFundData.json')

WIND_SKILL = os.path.expanduser('~/.agents/skills/wind-mcp-skill')
CLI = os.path.join(WIND_SKILL, 'scripts', 'cli.mjs')

# 需要实时更新的货基代码（Excel 里 43 只全量太长，只更新头部+展示需要的）
# 当前详情页图表只用天弘余额宝；后续可扩展
TARGET_CODES = ['000198.OF']  # 天弘余额宝


def call_wind_price(code):
    """查基金 7 日年化收益率（含最新交易日）。
    2026-09-19 优化：加入 3 次重试 + 代理变量清理，失败返回 None（不再抛异常中断整脚本）。"""
    env = dict(os.environ)
    env['NODE_EXTRA_CA_CERTS'] = '/etc/ssl/cert.pem'
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NODE_USE_ENV_PROXY'):
        env.pop(k, None)
    for attempt in range(3):
        try:
            r = subprocess.run(
                ['node', CLI, 'call', 'fund_data', 'get_fund_price_indicators',
                 json.dumps({'windcode': code, 'indexes': '七日年化收益率,万份基金收益,最新交易日'}, ensure_ascii=False)],
                capture_output=True, text=True, timeout=90, env=env, cwd=WIND_SKILL)
        except Exception:
            time.sleep(4); continue
        if r.returncode != 0:
            time.sleep(4); continue
        try:
            outer = json.loads(r.stdout)
            text = outer['content'][0]['text']
            if '没找到' in text:
                return None
            inner = json.loads(text)
            cols = [x['name'] for x in inner['data']['columns']]
            rows = inner['data']['rows']
            if not rows:
                return None
            row = rows[0]
            yi = cols.index('七日年化收益率') if '七日年化收益率' in cols else 0
            di = cols.index('万份基金收益') if '万份基金收益' in cols else 1
            ti = cols.index('最新交易日') if '最新交易日' in cols else -1
            out = {'yield7d': float(row[yi]) / 100.0 if row[yi] else 0,
                   'dailyWan': float(row[di]) if row[di] else 0}
            if ti >= 0 and row[ti]:
                d = str(row[ti])[:8]
                out['yieldDate'] = '{}-{}-{}'.format(d[:4], d[4:6], d[6:8])
            return out
        except Exception:
            time.sleep(4)
    return None


def atomic_write_json(path, obj):
    """原子写入（临时文件 + os.replace），避免坚果云同步锁导致半截文件。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def main():
    print('===== 货币基金收益率实时更新 =====', flush=True)
    if not os.path.exists(CLI):
        print('[ERROR] wind-mcp-skill 未找到:', WIND_SKILL, flush=True)
        return
    with io.open(MONEY_JSON, 'r', encoding='utf-8') as f:
        funds = json.load(f)

    for code in TARGET_CODES:
        data = call_wind_price(code)
        if not data:
            print('[WARN] {} 实时数据获取失败（保留原值）'.format(code), flush=True)
            continue
        for fund in funds:
            if fund['code'] == code:
                fund['yield7dNum'] = data['yield7d']
                fund['yield7d'] = '{:.3f}%'.format(data['yield7d'] * 100)
                fund['dailyWan'] = round(data['dailyWan'], 4)
                if data.get('yieldDate'):
                    fund['yieldDate'] = data['yieldDate']
                print('[OK] {} ({}) -> 7日年化 {:.2f}% (数据日期 {})'.format(
                    fund['name'], code, data['yield7d'] * 100, data.get('yieldDate', '?')), flush=True)
                break

    atomic_write_json(MONEY_JSON, funds)
    print('已更新', MONEY_JSON, flush=True)


if __name__ == '__main__':
    main()

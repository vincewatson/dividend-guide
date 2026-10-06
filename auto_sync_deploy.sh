#!/usr/bin/env bash
# ============================================================
# 食息指南 · 每周同步部署脚本（2026-08-11 定稿；2026-09-19 修订：编号统一为连续 1..20）
#   2026-09-26 修订：新增 [13/21] sync_new_reits.py（新 REITs 自动发现），原 13–20 步顺延为 14–21，总步数 21
#   ↑ 步骤编号：[3/21] 语法预检 + [4..21/21]；步骤 1–2（修订文档 / 确认任务逻辑）由任务层在上游完成
# 顺序关键点（防复发）：
#   - 步骤 3：全部 .py 语法预检（防 // 注释类错误）
#   - build_lists（原 sync_excel）跑两次：第二次在 div_history/daily_change/money_fund/yuebao 之后，
#     build_asset_data 才能取到最新 divHistory（红利指数）与 moneyFundData.yieldDate（余额宝）
#   - sync_fund_divdate 必须在最后一次 build_lists 之后（build_lists 重建会覆盖 divDate）
#   - build_lists.py 自 2026-10-06（excel-exit P2）起**不再读 Excel**，清单/标注一律来自 data/curation/*.json
#     2026-10-06（excel-exit P3）：由 sync_excel.py 更名为 build_lists.py；xlsx 已归档 archive/excel-baseline-*
#   - 2026-10-06 新增清单「进出」两处（均编号外）：[生命周期体检] sync_lifecycle.py（「出」= 清盘/退市/终止）、
#     [港ETF·进] sync_new_hk_etf.py（「进」= 新上市红利类港ETF，自动补入 hkEtfData）——数据源均为
#     data/curation/_hk_etf_universe.json（中央数据库导出，与「策略魔方」同源）
#   - check_data.py 验证全部 ✅ 才允许部署（硬门槛）
# 三条铁律：写回绝不删除旧数据；历史序列起点早于图表起点；check_data 必须全 ✅
# ============================================================
set -e
cd "$(dirname "$0")"

# Cloudflare Pages 部署凭据（2026-10-03 由 Vercel 迁移）
#   从项目外的文件读取：~/.config/dividend-guide/cloudflare-token（一行 API token）
#                       ~/.config/dividend-guide/cloudflare-account（一行 Account ID）
#   也可用环境变量 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID
#   放在开头检查，避免跑完 20 分钟取数才发现无法部署
CF_DIR="$HOME/.config/dividend-guide"
if [ -z "$CLOUDFLARE_API_TOKEN" ] && [ -f "$CF_DIR/cloudflare-token" ]; then
  CLOUDFLARE_API_TOKEN="$(tr -d '[:space:]' < "$CF_DIR/cloudflare-token")"
fi
if [ -z "$CLOUDFLARE_ACCOUNT_ID" ] && [ -f "$CF_DIR/cloudflare-account" ]; then
  CLOUDFLARE_ACCOUNT_ID="$(tr -d '[:space:]' < "$CF_DIR/cloudflare-account")"
fi
if [ -z "$CLOUDFLARE_API_TOKEN" ] || [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
  echo "[ERROR] 未找到 Cloudflare 凭据：请写入 $CF_DIR/cloudflare-token 与 $CF_DIR/cloudflare-account（各一行），或设置环境变量 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID"
  exit 1
fi
export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID

# ------------------------------------------------------------
# [额度闸] 每日整跑闸（2026-10-06 新增）
#   防止同日重复整跑耗尽 Wind 额度（2026-10-06 事故复盘：多轮整跑 + 零散单项验证把 2000 次/日额度用尽）。
#   默认每天最多整跑 1 次；已达上限则直接退出（不启动流水线，避免「跑一半没额度」）。
#   覆盖：SX_FORCE_RUN=1 强制再跑；上限：SX_MAX_FULL_RUNS（默认 1）。
#   同时打印今日 Wind 调用用量（由 wind_guard_cli.mjs 记入 .wind_calls_<date>）。
# ------------------------------------------------------------
if ! python3 run_gate.py; then
  echo "⛔ 本次整跑被额度闸拦截。如确需再跑：SX_FORCE_RUN=1 bash auto_sync_deploy.sh"
  exit 0
fi

# 强制 Python 无缓冲输出：重定向/管道时避免 stdout 块缓冲导致"长时间无进展、像卡住"（2026-09-19 优化）
export PYTHONUNBUFFERED=1

# ------------------------------------------------------------
# 计时 + 心跳辅助（2026-09-19 优化）
#   目的：每个 Python 步骤打印「开始/结束 + 耗时」；单步运行超过 30s 时每 30s 打一次心跳，
#   避免长时间无输出被误判为"卡死"。兼容 macOS 自带 bash 3.2（不使用 wait -n / wait -p）。
# ------------------------------------------------------------
# 每步耗时落盘（2026-10-06 新增）：此前耗时只打印、不留存，无法事后定位瓶颈。
#   每次运行清空重建；格式 = 每行一个 JSON {label,sec,rc}。流水线末尾打印降序汇总。
TIMINGS_FILE=".run_timings.jsonl"
: > "$TIMINGS_FILE"

run_py() {
  local label="$1"; shift
  local t0=$(date +%s)
  echo "  ⏱  [$(date '+%H:%M:%S')] 开始：$label"
  # 后台运行以便心跳探测；PYTHONUNBUFFERED=1 已导出，脚本自身输出实时可见
  python3 "$@" &
  local pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    local i=0
    while [ $i -lt 6 ]; do
      sleep 5
      kill -0 "$pid" 2>/dev/null || break
      i=$((i + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "     … [$(date '+%H:%M:%S')] $label 仍在运行（已 $(( $(date +%s) - t0 ))s）"
    fi
  done
  local rc=0
  wait "$pid" || rc=$?
  local dur=$(( $(date +%s) - t0 ))
  printf '{"label":"%s","sec":%s,"rc":%s}\n' "$label" "$dur" "$rc" >> "$TIMINGS_FILE"
  if [ $rc -eq 0 ]; then
    echo "  ✅ [$(date '+%H:%M:%S')] 完成：$label（耗时 ${dur}s）"
  else
    echo "  ❌ [$(date '+%H:%M:%S')] 失败：$label（耗时 ${dur}s，退出码 $rc）"
  fi
  return $rc
}

# ------------------------------------------------------------
# [预检] 更新前体检（2026-10-04 新增）
#   判断今天 A股/港股是否开盘、哪些数据域已覆盖到最新交易日、建议跑/跳过哪些步骤。
#   只读，不修改数据。默认仅报告。按建议跳过步骤有两种方式：
#     ① 显式指定：SKIP_STEPS="5 6 7 8 9 10 16" bash auto_sync_deploy.sh
#     ② 自动采纳：PREFLIGHT_AUTO=1 bash auto_sync_deploy.sh
#   （保守：仅跳过纯 Wind 日频 + 资讯步骤；build_lists/校验/部署等一律保留）
# ------------------------------------------------------------
echo "===== [预检] 更新前体检（preflight.py）====="
if [ -z "$SKIP_STEPS" ] && [ "$PREFLIGHT_AUTO" = "1" ]; then
  SKIP_STEPS="$(python3 preflight.py --emit-skip 2>/dev/null || true)"
fi
python3 preflight.py || echo "（预检失败，忽略，继续执行完整流水线）"
if [ -n "$SKIP_STEPS" ]; then
  echo "⏭ 本次将跳过步骤：$SKIP_STEPS （如非预期，请检查 SKIP_STEPS / PREFLIGHT_AUTO）"
fi
should_skip() { case " $SKIP_STEPS " in *" $1 "*) return 0 ;; esac; return 1; }

echo "===== [3/21] 脚本语法预检（全部 .py；步骤 1–2 修订文档/确认逻辑由任务层完成）====="
for f in *.py; do
  python3 -c "import ast; ast.parse(open('$f', encoding='utf-8').read())" || { echo "[ERROR] $f 语法错误"; exit 1; }
done
echo "✅ 全部 $(ls *.py | wc -l | tr -d ' ') 个脚本语法 OK"

echo ""
echo "===== [编号外] 生命周期体检：停用已清盘/结束标的（Wind「基金到期日」）====="
# 停用机制（excel-exit 机制 B）：境内红利ETF/港交所红利ETF/REITs/货币基金的「出」= 基金已结束。
#   判据：Wind「基金到期日」≤ 今天 → 已结束 → 写入 data/curation/_retired.json；build_lists 重建时跳过（历史数据不删，删条目即恢复）。
#   频率：清盘罕见，脚本自带约 28 天节流（SX_LIFECYCLE_DAYS），平时秒退；Wind 抖动不阻断。
run_py "sync_lifecycle.py" sync_lifecycle.py || echo "  ⚠ 生命周期体检失败（Wind 抖动），保留现有停用名单，下次重试"

echo "===== [4/21] 从 curation 重建数据（第一次；原 sync_excel，现 build_lists，不读 Excel）====="
run_py "build_lists.py（第一次）" build_lists.py

echo ""
if should_skip 5; then echo "===== [5/21] 同步股息率历史（Wind）— ⏭ 跳过（预检：已是最新交易日）====="; else
echo "===== [5/21] 同步股息率历史（Wind）====="
run_py "sync_div_history.py" sync_div_history.py
run_py "fix_laggard_indexes.py" fix_laggard_indexes.py
fi

echo ""
if should_skip 6; then echo "===== [6/21] 同步每日涨跌幅（Wind）— ⏭ 跳过（预检：已是最新交易日）====="; else
echo "===== [6/21] 同步每日涨跌幅（Wind）====="
run_py "sync_daily_change.py" sync_daily_change.py
fi

echo ""
if should_skip 7; then echo "===== [7/21] 同步货币基金实时收益率（Wind）— ⏭ 跳过（预检：已是最新交易日）====="; else
echo "===== [7/21] 同步货币基金实时收益率（Wind）====="
run_py "sync_money_fund.py" sync_money_fund.py
fi

echo ""
if should_skip 8; then echo "===== [8/21] 同步余额宝7日年化历史（Wind）— ⏭ 跳过（预检：已是最新交易日）====="; else
echo "===== [8/21] 同步余额宝7日年化历史（Wind）====="
run_py "sync_yuebao_history.py" sync_yuebao_history.py
fi

echo ""
if should_skip 9; then echo "===== [9/21] 同步宏观资产历史（Wind）— ⏭ 跳过（预检：已是最新交易日）====="; else
echo "===== [9/21] 同步宏观资产历史（Wind）====="
run_py "sync_asset_macro.py" sync_asset_macro.py
fi

echo ""
if should_skip 10; then echo "===== [10/21] 同步 REITs 日频增量 — ⏭ 跳过（预检：已是最新交易日）====="; else
echo "===== [10/21] 同步 REITs 日频增量（asset_macro 不覆盖 REITs）====="
run_py "sync_reits_daily.py" sync_reits_daily.py
fi

echo ""
echo "===== [11/21] 从 curation 重建数据（第二次！assetData 取最新 divHistory/yieldDate）====="
run_py "build_lists.py（第二次）" build_lists.py

echo ""
echo "===== [12/21] 新 ETF/新指数自动发现（Wind）====="
run_py "sync_new_etf.py" sync_new_etf.py

echo ""
echo "===== [港ETF·进] 新港交所红利ETF 自动补入（中央数据库名单；2026-10-06 新增·编号外，不影响 1..21 计数）====="
# 数据源 = data/curation/_hk_etf_universe.json 的 dividend_funds（中央数据库导出，与「策略魔方」同源）。
# 关键词筛红利类 + 排除 REIT + 按全称归并多柜台 → 与 hkEtfData 对照；新标的用 --add 拉 Wind 详情自动补入
# （表外行护栏保证重建不丢）。已收录的不会重复补；行缺 trackCode/detailUrl 须人工补。
run_py "sync_new_hk_etf.py --add" sync_new_hk_etf.py --add || echo "  ⚠ 港ETF 自动补入失败（Wind 抖动），保留现有清单，下次重试"

echo ""
echo "===== [13/21] 新 REITs 自动发现（Wind；2026-09-26 新增）====="
run_py "sync_new_reits.py" sync_new_reits.py

echo ""
echo "===== [月月名单] 自动补入（Wind；2026-10-06 新增·编号外，不影响 1..21 计数）====="
# 全市场检索「近1年分红次数 ≥ 11」的指数产品（A 类去重）→ 自动补入月月分红名单（etfData/fundData）。
# 位置关键：必须在 step 11 build_lists(2) 之后（产出的是 curation 表外行，靠 build_lists 表外行护栏保留）、
#           且在 step 14 之前（同轮紧接刷 divDate + prune_stale_monthly 剔除超期成员）。Wind 抖动失败不阻断。
run_py "sync_new_monthly.py" sync_new_monthly.py || echo "  ⚠ 月月名单自动补入失败（Wind 抖动），保留现有名单，下次重试"

echo ""
echo "===== [产品行情] 快照入库（Wind；2026-10-05 新增·编号外，不影响 1..21 计数）====="
# 拉取各 ETF/基金【当日涨跌幅】【今年以来回报】，按日期打标签【追加】到 data/productQuotes.json
# （只追加不覆盖：历史快照永久保留；产品回报绝不跨取跟踪指数）。Wind 抖动失败不阻断后续步骤。
# ⚠️ 位置（2026-10-06 调整）：必须放在「月月名单自动补入」**之后** —— 补入的新产品才能在同轮拿到行情快照。
run_py "sync_product_quotes.py" sync_product_quotes.py || echo "  ⚠ 产品行情快照失败（Wind 抖动），保留已有快照，下次重试"

echo ""
echo "===== [14/21] 恢复基金最近分红日期（Wind，覆盖被 curation 重建覆盖的 divDate）====="
run_py "sync_fund_divdate.py all --force" sync_fund_divdate.py all --force

echo ""
echo "===== [15/21] 字段级 Wind 化（fundCount/ETF字段/月月分红字段，2026-08-16）====="
run_py "sync_wind_fields.py all" sync_wind_fields.py all

echo ""
if should_skip 16; then echo "===== [16/21] 同步食息资讯（日报）— ⏭ 跳过（预检：digest 源无新日期）====="; else
echo "===== [16/21] 同步食息资讯（日报；只读 digest-db.json）====="
run_py "sync_daily.py" sync_daily.py
fi

echo ""
echo "===== [17/21] 备份本地数据库（离线保障）====="
run_py "backup_db.py" backup_db.py

echo ""
echo "===== [18/21] 数据一致性验证（失败即中止部署）====="
run_py "check_data.py" check_data.py

echo ""
echo "===== [19/21] 刷新内嵌兜底数据 ====="
run_py "embed_data.py" embed_data.py

echo ""
echo "===== [20/21] 部署到 Cloudflare Pages ====="
# 2026-10-03 迁移：原 Vercel 直传 → Cloudflare Pages 直传（含 functions/ 与 _redirects/_headers）
bash "$(pwd)/deploy_cloudflare.sh"

echo ""
echo "===== [21/21] 线上验证（最多等待 20 秒，避免网络被拦截时无限挂起）====="
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u NODE_USE_ENV_PROXY \
  curl -s --connect-timeout 10 --max-time 20 "https://divlab.net/?cmp=$(date +%s)" | grep -o '数据更新于[^<]*' | head -1 || echo "（线上验证被网络拦截或页面文案已改版，请手动确认）"

echo ""
echo "===== [耗时汇总] 本次各步耗时（降序 · 供优化定位）====="
python3 - "$TIMINGS_FILE" <<'PY'
import json, sys
p = sys.argv[1]
rows = []
try:
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
except Exception:
    pass
if rows:
    for r in sorted(rows, key=lambda x: -x.get('sec', 0)):
        print("  %6ds  %s%s" % (r.get('sec', 0), r.get('label', '?'),
                                '' if r.get('rc', 0) == 0 else '   <-- 失败 rc=%s' % r.get('rc')))
    tot = sum(r.get('sec', 0) for r in rows)
    print("  ------ 合计 %ds（约 %.1f 分钟，共 %d 步）；已写入 %s" % (tot, tot / 60.0, len(rows), p))
else:
    print("  （无耗时记录）")
PY

echo ""
echo "✅ 同步完成！请访问 https://divlab.net"

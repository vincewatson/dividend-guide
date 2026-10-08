#!/usr/bin/env bash
# ============================================================
# 食息指南 · 同步部署脚本（2026-08-11 定稿；2026-09-19 编号 1..20；2026-09-26 增步骤 → 1..21）
#   2026-10-07 重构阶段2/3：分「日更 / 周更」两档；重建数据只跑一次；分红日期等移周更。
#   2026-10-07 入口档位改按【星期】（北京时间）自动判定，并新增 --daily（详见下方 [档位] 段）。
#   ↑ 步骤编号：[3/21] 语法预检 + [5..21/21]；步骤 1–2（修订文档/确认逻辑）由任务层完成；
#     原 [4/21] build_lists(1) 与 [11/21] build_lists(2) 合并为**一次** build_lists（置于原第 11 步位置，
#     以确保 assetData 取到当日最新 divHistory，同时「新名单/分红日期/字段」等仍在其后更新）。
#     ⚠️ 打印标签沿用历史 [N/21]（原第 4 步已取消、无第 11 步标签；实际编号步骤 17 个）；
#        连续重编号见 docs/backlog.md B-5。fix_laggard_indexes.py 已删除（逻辑并入 sync_div_history.py）。
# 顺序关键点（防复发）：
#   - 步骤 3：全部 .py 语法预检（防 // 注释类错误）
#   - build_lists **只跑一次**（原第 11 步位置）：在 div_history/daily_change 之后、rebuild 后 assetData 取最新 divHistory/yieldDate；
#     其后 new_etf/new_reits/new_monthly/fund_divdate/wind_fields 再更新；build_lists 重建已改为**保留** divDate/size/divHistory/dailyChange/yrChange（合并写入）
#   - sync_fund_divdate 在（唯一一次）build_lists 之后
#   - build_lists.py 自 2026-10-06 起**不再读 Excel**，清单/标注一律来自 data/curation/*.json
#   - check_data.py 验证全部 ✅ 才允许部署（硬门槛）
# 三条铁律：写回绝不删除旧数据；历史序列起点早于图表起点；check_data 必须全 ✅
# ============================================================
set -e
cd "$(dirname "$0")"

# Cloudflare Pages 部署凭据（2026-10-03 由 Vercel 迁移）
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
#   默认每天最多整跑 1 次；已达上限则直接退出。覆盖：SX_FORCE_RUN=1；上限：SX_MAX_FULL_RUNS。
# ------------------------------------------------------------
if ! python3 run_gate.py; then
  echo "⛔ 本次整跑被额度闸拦截。如确需再跑：SX_FORCE_RUN=1 bash auto_sync_deploy.sh"
  exit 0
fi

export PYTHONUNBUFFERED=1
export PYTHONUTF8=1   # 强制 Python UTF-8（2026-10-07）：避免中文经 argv 传入时被按 ascii 解码成代理字符

# ------------------------------------------------------------
# 计时 + 心跳 + 运行报告（2026-09-19 / 2026-10-06 / 2026-10-07）
# ------------------------------------------------------------
TIMINGS_FILE=".run_timings.jsonl"
: > "$TIMINGS_FILE"
# 运行报告事件流（每次运行清空重建；末尾 make_run_report.py 汇总为 logs/update-*.md）
RUN_REPORT=".run_report.jsonl"
: > "$RUN_REPORT"
report_event() { printf '{"label":"%s","status":"%s","reason":"%s"}\n' "$1" "$2" "$3" >> "$RUN_REPORT"; }
# 本次运行起点用量快照（用于报告里的「本次」增量）
python3 -c "import json,wind_client; json.dump(wind_client.load(), open('.run_usage_baseline.json','w',encoding='utf-8'))" 2>/dev/null || true

run_py() {
  local label="$1"; shift
  local t0=$(date +%s)
  echo "  ⏱  [$(date '+%H:%M:%S')] 开始：$label"
  export SX_WIND_STEP="$label"
  if is_weekly_step "$label"; then export SX_WIND_MODE="weekly"; else export SX_WIND_MODE="daily"; fi
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
    report_event "$label" ran ""
  else
    echo "  ❌ [$(date '+%H:%M:%S')] 失败：$label（耗时 ${dur}s，退出码 $rc）"
    report_event "$label" fail "退出码 $rc"
  fi
  return $rc
}

# ------------------------------------------------------------
# [档位] 自动判档（2026-10-07 · 按星期 · 北京时间）
#   - 周一至周五：只跑日更；
#   - 周六 / 周日：同一次运行里「日更 + 周更」，部署只做一次；
#     但同一个周末只跑一次周更——若本周六 0 点后已跑过周更（.run_state.json:lastWeekly ≥ 本周六）→ 再点只跑日更；
#   - 兜底：距上次周更 > 13 天，不论周几都补跑周更（日更 + 周更）；
#   - --weekly：手动强制「只跑周更」；--daily：手动强制「只跑日更」（手动优先于自动判档）。
#   上次周更日期记在 .run_state.json:lastWeekly（初始 2026-10-07；测量日已跑过周更）。
# ------------------------------------------------------------
MANUAL_WEEKLY=0
MANUAL_DAILY=0
for _a in "$@"; do
  case "$_a" in
    --weekly) MANUAL_WEEKLY=1 ;;
    --daily)  MANUAL_DAILY=1 ;;
  esac
done

# ---- 本地开发模式（2026-10-08 用户要求）----------------------------------------------
# 本地模式只管「代码/样式等手工改动」：改完不单独部署，记进 deploy/待部署清单.md。
# 【数据更新（日更/周更）照常部署】——部署会把整个目录一起传上线，所以清单里已完成的本地改动也会随之上线；
# 部署成功后，本脚本把清单内容记入 docs/changelog 当月文件并删除清单（见下方部署步骤）。

# 输出一行：lastWeekly  距今天数  中文星期  是否周末(0/1)  本周末是否已跑过周更(0/1)
_TIER="$(python3 -c '
import json, datetime
try:
    rec = json.load(open(".run_state.json", encoding="utf-8"))
except Exception:
    rec = {}
last = str(rec.get("lastWeekly") or "2026-10-07")[:10]
try:
    lastd = datetime.date.fromisoformat(last)
except Exception:
    lastd = datetime.date(2026, 10, 7)
try:
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
except Exception:
    now = datetime.datetime.now()
today = now.date()
wd = today.weekday()                                 # 周一=0 … 周日=6
days = (today - lastd).days
cn = "周" + "一二三四五六日"[wd]
is_weekend = 1 if wd >= 5 else 0
if wd >= 5:
    sat = today - datetime.timedelta(days=(wd - 5))  # 本周六（周六=当天、周日=昨天）
else:
    sat = today + datetime.timedelta(days=(5 - wd))  # 本周六（未来）
ran_weekend = 1 if lastd >= sat else 0
print(last, days, cn, is_weekend, ran_weekend)
')"
read -r LAST_WEEKLY DAYS_SINCE_WEEKLY WD_CN IS_WEEKEND RAN_WEEKEND <<< "$_TIER"

if [ "$MANUAL_WEEKLY" = "1" ]; then
  RUN_DAILY=0; RUN_WEEKLY=1; MODE="weekly"
  MODE_REASON="--weekly 手动强制：只跑周更"
elif [ "$MANUAL_DAILY" = "1" ]; then
  RUN_DAILY=1; RUN_WEEKLY=0; MODE="daily"
  MODE_REASON="--daily 手动强制：只跑日更"
elif [ "${DAYS_SINCE_WEEKLY:-0}" -gt 13 ]; then
  RUN_DAILY=1; RUN_WEEKLY=1; MODE="daily+weekly"
  MODE_REASON="兜底：距上次周更（$LAST_WEEKLY）已 $DAYS_SINCE_WEEKLY 天（>13），不论周几补跑周更 → 日更 + 周更"
elif [ "$IS_WEEKEND" = "1" ]; then
  if [ "$RAN_WEEKEND" = "1" ]; then
    RUN_DAILY=1; RUN_WEEKLY=0; MODE="daily"
    MODE_REASON="$WD_CN（北京）默认日更+周更；但本周六 0 点后已跑过周更（lastWeekly=$LAST_WEEKLY）→ 仅日更"
  else
    RUN_DAILY=1; RUN_WEEKLY=1; MODE="daily+weekly"
    MODE_REASON="$WD_CN（北京）：周末首跑、本周末尚未跑过周更 → 日更 + 周更（只部署一次）"
  fi
else
  RUN_DAILY=1; RUN_WEEKLY=0; MODE="daily"
  MODE_REASON="$WD_CN（北京）：工作日 → 仅日更"
fi
MODE_LABEL="$MODE"
export MODE MODE_LABEL MODE_REASON RUN_DAILY RUN_WEEKLY

WEEKLY_NUMS="12 13 14"                                   # 周更「编号」步骤：new_etf / new_reits / fund_divdate
is_weekly_num() { case " $WEEKLY_NUMS " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
is_weekly_step() {   # 按 label 判定是否周更档步骤
  case "$1" in
    *sync_fund_divdate.py*--monthly-empty*) return 1 ;;   # 月月空日期补查：日更步骤（须排在下方 fund_divdate 分支之前）
    *sync_new_etf.py*|*sync_new_reits.py*|*sync_fund_divdate.py*|*sync_lifecycle.py*|*sync_new_hk_etf.py*|*sync_new_monthly.py*)
      return 0 ;;
    *) return 1 ;;
  esac
}

PENDING="$(python3 wind_client.py --pending 2>/dev/null || true)"
if [ -n "$PENDING" ]; then
  echo "🔁 上次额度不足待补（本次先跑）：$PENDING"
  python3 wind_client.py --clear-pending >/dev/null 2>&1 || true
fi
pending_has() { case "$PENDING" in *"$1"*) return 0 ;; esac; return 1; }

# 编号步骤是否执行：pending 强制 > 「17/18/19 两档都跑」> 档位
step_on() {   # $1=步骤号  $2=代表 label 关键字
  pending_has "$2" && return 0
  case " 17 18 19 " in *" $1 "*) return 0 ;; esac
  if is_weekly_num "$1"; then
    [ "$RUN_WEEKLY" = "1" ] && return 0 || return 1
  else
    [ "$RUN_DAILY" = "1" ] && return 0 || return 1
  fi
}
label_on() {  # 编号外步骤是否执行：$1=代表 label 关键字
  pending_has "$1" && return 0
  if is_weekly_step "$1"; then
    [ "$RUN_WEEKLY" = "1" ] && return 0 || return 1
  else
    [ "$RUN_DAILY" = "1" ] && return 0 || return 1
  fi
}
echo "===== 本次档位：$MODE_LABEL（$MODE_REASON）====="

# ------------------------------------------------------------
# [预检] 更新前体检（2026-10-04 新增）。日更下可按建议跳过已是最新步骤（PREFLIGHT_AUTO=1）。
# ------------------------------------------------------------
echo "===== [预检] 更新前体检（preflight.py）====="
PF_ARGS=""; [ "$MODE" = "weekly" ] && PF_ARGS="--weekly"
if [ "$RUN_DAILY" = "1" ] && [ -z "$SKIP_STEPS" ] && [ "$PREFLIGHT_AUTO" = "1" ]; then
  SKIP_STEPS="$(python3 preflight.py --emit-skip 2>/dev/null || true)"
fi
python3 preflight.py $PF_ARGS || echo "（预检失败，忽略，继续执行完整流水线）"
if [ -n "$SKIP_STEPS" ]; then
  echo "⏭ 本次将跳过步骤：$SKIP_STEPS （如非预期，请检查 SKIP_STEPS / PREFLIGHT_AUTO）"
fi
should_skip() { case " $SKIP_STEPS " in *" $1 "*) return 0 ;; esac; return 1; }

echo "===== [3/21] 脚本语法预检（全部 .py）====="
for f in *.py; do
  python3 -c "import ast; ast.parse(open('$f', encoding='utf-8').read())" || { echo "[ERROR] $f 语法错误"; exit 1; }
done
echo "✅ 全部 $(ls *.py | wc -l | tr -d ' ') 个脚本语法 OK"

echo ""
if label_on "sync_lifecycle.py"; then
echo "===== [编号外] 生命周期体检：停用已清盘/结束标的（Wind「基金到期日」）====="
run_py "sync_lifecycle.py" sync_lifecycle.py || echo "  ⚠ 生命周期体检失败（Wind 抖动），保留现有停用名单，下次重试"
else
echo "===== [编号外] 生命周期体检 — ⏭ 跳过 ====="
report_event "sync_lifecycle.py" skip "周更步骤（本次日更不跑）"
fi

echo ""
if step_on 5 "sync_div_history.py" && ! should_skip 5; then
echo "===== [5/21] 同步股息率历史（Wind，只补缺口）====="
run_py "sync_div_history.py" sync_div_history.py
else
echo "===== [5/21] 同步股息率历史 — ⏭ 跳过 ====="
report_event "sync_div_history.py" skip "$([ "$MODE" = "weekly" ] && echo '日更步骤（本次周更不跑）' || echo '预检：已是最新交易日')"
fi

echo ""
if step_on 6 "sync_daily_change.py" && ! should_skip 6; then
echo "===== [6/21] 同步每日涨跌幅（Wind）====="
run_py "sync_daily_change.py" sync_daily_change.py
else
echo "===== [6/21] 同步每日涨跌幅 — ⏭ 跳过 ====="
report_event "sync_daily_change.py" skip "$([ "$MODE" = "weekly" ] && echo '日更步骤（本次周更不跑）' || echo '预检：已是最新交易日')"
fi

echo ""
if step_on 7 "sync_money_fund.py" && ! should_skip 7; then
echo "===== [7/21] 同步货币基金实时收益率（Wind）====="
run_py "sync_money_fund.py" sync_money_fund.py
else
echo "===== [7/21] 同步货币基金实时收益率 — ⏭ 跳过 ====="
report_event "sync_money_fund.py" skip "$([ "$MODE" = "weekly" ] && echo '日更步骤（本次周更不跑）' || echo '预检：已是最新交易日（A股休市，无新数据）')"
fi

echo ""
if step_on 8 "sync_yuebao_history.py" && ! should_skip 8; then
echo "===== [8/21] 同步余额宝7日年化历史（Wind）====="
run_py "sync_yuebao_history.py" sync_yuebao_history.py
else
echo "===== [8/21] 同步余额宝7日年化历史 — ⏭ 跳过 ====="
report_event "sync_yuebao_history.py" skip "$([ "$MODE" = "weekly" ] && echo '日更步骤（本次周更不跑）' || echo '预检：已是最新交易日（A股休市，无新数据）')"
fi

echo ""
if step_on 9 "sync_asset_macro.py" && ! should_skip 9; then
echo "===== [9/21] 同步宏观资产历史（Wind）====="
run_py "sync_asset_macro.py" sync_asset_macro.py
else
echo "===== [9/21] 同步宏观资产历史 — ⏭ 跳过 ====="
report_event "sync_asset_macro.py" skip "$([ "$MODE" = "weekly" ] && echo '日更步骤（本次周更不跑）' || echo '预检：已是最新交易日（A股休市，无新数据）')"
fi

echo ""
if step_on 10 "sync_reits_daily.py" && ! should_skip 10; then
echo "===== [10/21] 同步 REITs 日频增量（Wind）====="
run_py "sync_reits_daily.py" sync_reits_daily.py
else
echo "===== [10/21] 同步 REITs 日频增量 — ⏭ 跳过 ====="
report_event "sync_reits_daily.py" skip "$([ "$MODE" = "weekly" ] && echo '日更步骤（本次周更不跑）' || echo '预检：已是最新交易日（A股休市，无新数据）')"
fi

echo ""
echo "===== [重建] 从 curation 重建数据（唯一一次；assetData 取最新 divHistory/yieldDate）====="
run_py "build_lists.py" build_lists.py

echo ""
if step_on 12 "sync_new_etf.py"; then
echo "===== [12/21] 新 ETF/新指数自动发现（Wind）====="
run_py "sync_new_etf.py" sync_new_etf.py
else
echo "===== [12/21] 新 ETF/新指数自动发现 — ⏭ 跳过 ====="
report_event "sync_new_etf.py" skip "周更步骤（本次日更不跑）"
fi

echo ""
if label_on "sync_new_hk_etf.py"; then
echo "===== [港ETF·进] 新港交所红利ETF 自动补入（中央数据库名单·编号外）====="
run_py "sync_new_hk_etf.py --add" sync_new_hk_etf.py --add || echo "  ⚠ 港ETF 自动补入失败（Wind 抖动），保留现有清单，下次重试"
else
echo "===== [港ETF·进] 新港交所红利ETF 自动补入 — ⏭ 跳过 ====="
report_event "sync_new_hk_etf.py --add" skip "周更步骤（本次日更不跑）"
fi

echo ""
if step_on 13 "sync_new_reits.py"; then
echo "===== [13/21] 新 REITs 自动发现（Wind）====="
run_py "sync_new_reits.py" sync_new_reits.py
else
echo "===== [13/21] 新 REITs 自动发现 — ⏭ 跳过 ====="
report_event "sync_new_reits.py" skip "周更步骤（本次日更不跑）"
fi

echo ""
if label_on "sync_new_monthly.py"; then
echo "===== [月月名单] 自动补入（Wind·编号外）====="
run_py "sync_new_monthly.py" sync_new_monthly.py || echo "  ⚠ 月月名单自动补入失败（Wind 抖动），保留现有名单，下次重试"
else
echo "===== [月月名单] 自动补入 — ⏭ 跳过 ====="
report_event "sync_new_monthly.py" skip "周更步骤（本次日更不跑）"
fi

echo ""
if label_on "sync_product_quotes.py"; then
echo "===== [产品行情] 快照入库（Wind·编号外）====="
run_py "sync_product_quotes.py" sync_product_quotes.py || echo "  ⚠ 产品行情快照失败（Wind 抖动），保留已有快照，下次重试"
else
echo "===== [产品行情] 快照入库 — ⏭ 跳过 ====="
report_event "sync_product_quotes.py" skip "日更步骤（本次周更不跑）"
fi

echo ""
if step_on 14 "sync_fund_divdate.py"; then
echo "===== [14/21] 恢复基金最近分红日期（Wind）====="
run_py "sync_fund_divdate.py all --force" sync_fund_divdate.py all --force
else
echo "===== [14/21] 恢复基金最近分红日期 — ⏭ 跳过 ====="
report_event "sync_fund_divdate.py all --force" skip "周更步骤（本次日更不跑）"
fi

echo ""
# 编号外·日更：月月名单空日期补查（2026-10-08）——只把 etfData/fundData 中 divDate 为空的成员补查；
#   label 同时含 sync_fund_divdate.py 与 --monthly-empty → is_weekly_step 判为「非周更」（走 daily 额度）；
#   失败不阻断（保留原值）。
if [ "$RUN_DAILY" = "1" ]; then
echo "===== [编号外] 月月名单空日期补查（Wind，仅日更）====="
run_py "sync_fund_divdate.py --monthly-empty" sync_fund_divdate.py monthly --monthly-empty || echo "  ⚠ 月月名单空日期补查失败（Wind 抖动），保留原值，下次重试"
else
echo "===== [编号外] 月月名单空日期补查 — ⏭ 跳过 ====="
report_event "sync_fund_divdate.py --monthly-empty" skip "月月空日期补查：仅日更"
fi

echo ""
if step_on 15 "sync_wind_fields.py"; then
echo "===== [15/21] 字段级 Wind 化（fundCount/ETF字段/月月分红字段）====="
run_py "sync_wind_fields.py all" sync_wind_fields.py all
else
echo "===== [15/21] 字段级 Wind 化 — ⏭ 跳过 ====="
report_event "sync_wind_fields.py all" skip "日更步骤（本次周更不跑）"
fi

echo ""
if step_on 16 "sync_daily.py" && ! should_skip 16; then
echo "===== [16/21] 同步食息资讯（日报）====="
run_py "sync_daily.py" sync_daily.py
else
echo "===== [16/21] 同步食息资讯（日报）— ⏭ 跳过 ====="
report_event "sync_daily.py" skip "$([ "$MODE" = "weekly" ] && echo '日更步骤（本次周更不跑）' || echo '预检：digest 源无新日期')"
fi

echo ""
echo "===== [17/21] 备份本地数据库（离线保障）====="
run_py "backup_db.py" backup_db.py

echo ""
echo "===== [18/21] 数据一致性验证（失败即中止部署）====="
run_py "check_data.py" check_data.py

# 周更档成功跑完 → 记录 lastWeekly（供下次判档）
if [ "$RUN_WEEKLY" = "1" ]; then
  python3 - <<'PY'
import json, datetime
p = ".run_state.json"
try:
    rec = json.load(open(p, encoding="utf-8"))
except Exception:
    rec = {}
try:
    from zoneinfo import ZoneInfo
    today = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).date()
except Exception:
    today = datetime.date.today()
rec["lastWeekly"] = today.isoformat()
json.dump(rec, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[档位] 已记录本次周更日期 lastWeekly=%s" % rec["lastWeekly"])
PY
fi

echo ""
echo "===== [19/21] 刷新内嵌兜底数据 ====="
run_py "embed_data.py" embed_data.py

echo ""
if [ "$SX_NO_DEPLOY" = "1" ]; then
  echo "===== [20/21] 部署到 Cloudflare Pages — ⏭ 跳过（SX_NO_DEPLOY=1）====="
  report_event "部署 deploy_cloudflare" skip "SX_NO_DEPLOY=1（只跑数据）"
else
  echo "===== [20/21] 部署到 Cloudflare Pages ====="
  PENDING_MD="deploy/待部署清单.md"
  if [ -f "$PENDING_MD" ]; then
    echo "[待部署清单] 以下本地改动将随本次数据更新一起上线："
    grep '^| 20' "$PENDING_MD" || true
  fi
  if bash "$(pwd)/deploy_cloudflare.sh"; then
    report_event "部署 deploy_cloudflare" ran ""
    if [ -f "$PENDING_MD" ]; then
      CL="docs/changelog/$(date +%Y-%m).md"
      { echo ""; echo "<!-- $(date '+%Y-%m-%d %H:%M') 随数据更新上线的本地改动（原 deploy/待部署清单.md） -->"; grep '^| 20' "$PENDING_MD" | sed 's/^| /| 已上线·/' ; } >> "$CL"
      rm -f "$PENDING_MD" && echo "[待部署清单] 已随部署上线，内容记入 $CL，清单已删除"
      report_event "待部署清单" ran "随本次部署上线，已记入 changelog 并删除"
    fi
  else
    report_event "部署 deploy_cloudflare" fail "deploy_cloudflare.sh 失败（待部署清单保留）"
  fi
fi

echo ""
if [ "$SX_NO_DEPLOY" = "1" ]; then
  echo "===== [21/21] 线上验证 — ⏭ 跳过（SX_NO_DEPLOY=1）====="
  report_event "线上验证" skip "SX_NO_DEPLOY=1"
else
  echo "===== [21/21] 线上验证（最多等待 20 秒）====="
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u NODE_USE_ENV_PROXY \
    curl -s --connect-timeout 10 --max-time 20 "https://divlab.net/?cmp=$(date +%s)" | grep -o '数据更新于[^<]*' | head -1 || echo "（线上验证被网络拦截或页面文案已改版，请手动确认）"
  report_event "线上验证" ran ""
fi

echo ""
echo "===== [耗时汇总] 本次各步耗时（降序）====="
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
echo "===== [运行报告] 生成 logs/update-YYYYMMDD-HHMM.md ====="
python3 make_run_report.py --mode "$MODE_LABEL" --reason "$MODE_REASON" --deploy "$([ "$SX_NO_DEPLOY" = "1" ] && echo skipped || echo done)" || echo "（运行报告生成失败，忽略）"

echo ""
echo "✅ 同步完成！请访问 https://divlab.net"

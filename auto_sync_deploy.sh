#!/usr/bin/env bash
# ============================================================
# 食息指南 · 每周同步部署脚本（2026-08-11 定稿；2026-09-19 修订：编号统一为连续 1..20）
#   2026-09-26 修订：新增 [13/21] sync_new_reits.py（新 REITs 自动发现），原 13–20 步顺延为 14–21，总步数 21
#   ↑ 步骤编号：[3/21] 语法预检 + [4..21/21]；步骤 1–2（修订文档 / 确认任务逻辑）由任务层在上游完成
# 顺序关键点（防复发）：
#   - 步骤 3：全部 .py 语法预检（防 // 注释类错误）
#   - sync_excel 跑两次：第二次在 div_history/daily_change/money_fund/yuebao 之后，
#     build_asset_data 才能取到最新 divHistory（红利指数）与 moneyFundData.yieldDate（余额宝）
#   - sync_fund_divdate 必须在最后一次 sync_excel 之后（sync_excel 会用 Excel 覆盖 divDate）
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

# 强制 Python 无缓冲输出：重定向/管道时避免 stdout 块缓冲导致"长时间无进展、像卡住"（2026-09-19 优化）
export PYTHONUNBUFFERED=1

# ------------------------------------------------------------
# 计时 + 心跳辅助（2026-09-19 优化）
#   目的：每个 Python 步骤打印「开始/结束 + 耗时」；单步运行超过 30s 时每 30s 打一次心跳，
#   避免长时间无输出被误判为"卡死"。兼容 macOS 自带 bash 3.2（不使用 wait -n / wait -p）。
# ------------------------------------------------------------
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
  if [ $rc -eq 0 ]; then
    echo "  ✅ [$(date '+%H:%M:%S')] 完成：$label（耗时 $(( $(date +%s) - t0 ))s）"
  else
    echo "  ❌ [$(date '+%H:%M:%S')] 失败：$label（耗时 $(( $(date +%s) - t0 ))s，退出码 $rc）"
  fi
  return $rc
}

echo "===== [3/21] 脚本语法预检（全部 .py；步骤 1–2 修订文档/确认逻辑由任务层完成）====="
for f in *.py; do
  python3 -c "import ast; ast.parse(open('$f', encoding='utf-8').read())" || { echo "[ERROR] $f 语法错误"; exit 1; }
done
echo "✅ 全部 $(ls *.py | wc -l | tr -d ' ') 个脚本语法 OK"

echo "===== [4/21] 同步 Excel 数据（第一次）====="
run_py "sync_excel.py（第一次）" sync_excel.py

echo ""
echo "===== [5/21] 同步股息率历史（Wind）====="
run_py "sync_div_history.py" sync_div_history.py
run_py "fix_laggard_indexes.py" fix_laggard_indexes.py

echo ""
echo "===== [6/21] 同步每日涨跌幅（Wind）====="
run_py "sync_daily_change.py" sync_daily_change.py

echo ""
echo "===== [7/21] 同步货币基金实时收益率（Wind）====="
run_py "sync_money_fund.py" sync_money_fund.py

echo ""
echo "===== [8/21] 同步余额宝7日年化历史（Wind）====="
run_py "sync_yuebao_history.py" sync_yuebao_history.py

echo ""
echo "===== [9/21] 同步宏观资产历史（Wind）====="
run_py "sync_asset_macro.py" sync_asset_macro.py

echo ""
echo "===== [10/21] 同步 REITs 日频增量（asset_macro 不覆盖 REITs）====="
run_py "sync_reits_daily.py" sync_reits_daily.py

echo ""
echo "===== [11/21] 同步 Excel 数据（第二次！assetData 取最新 divHistory/yieldDate）====="
run_py "sync_excel.py（第二次）" sync_excel.py

echo ""
echo "===== [12/21] 新 ETF/新指数自动发现（Wind）====="
run_py "sync_new_etf.py" sync_new_etf.py

echo ""
echo "===== [13/21] 新 REITs 自动发现（Wind；2026-09-26 新增）====="
run_py "sync_new_reits.py" sync_new_reits.py

echo ""
echo "===== [14/21] 恢复基金最近分红日期（Wind，覆盖被 Excel 覆盖的 divDate）====="
run_py "sync_fund_divdate.py all --force" sync_fund_divdate.py all --force

echo ""
echo "===== [15/21] 字段级 Wind 化（fundCount/ETF字段/月月分红字段，2026-08-16）====="
run_py "sync_wind_fields.py all" sync_wind_fields.py all

echo ""
echo "===== [16/21] 同步食息资讯（日报；只读 digest-db.json）====="
run_py "sync_daily.py" sync_daily.py

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
echo "✅ 同步完成！请访问 https://divlab.net"

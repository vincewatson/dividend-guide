#!/usr/bin/env bash
# ============================================================
# 部署「食息指南」到 Cloudflare Pages（2026-10-03 新增；替代原 Vercel 部署）
#   对应位置：原 auto_sync_deploy.sh 第 20 步 / 原 deploy_now.sh
#   方式：本地同步 → 组装干净目录 → wrangler 直传（Direct Upload，含 functions/）
#
# 凭据（按优先级）：
#   1) 环境变量：CLOUDFLARE_API_TOKEN、CLOUDFLARE_ACCOUNT_ID
#   2) 文件：$HOME/.config/dividend-guide/cloudflare-token（一行 token）
#            $HOME/.config/dividend-guide/cloudflare-account（一行 account id）
#
# 用法：bash deploy_cloudflare.sh
# ============================================================
set -e
cd "$(dirname "$0")"

PROJECT="${CF_PAGES_PROJECT:-dividend-guide}"
CF_DIR="$HOME/.config/dividend-guide"

# --- 凭据 ---
if [ -z "$CLOUDFLARE_API_TOKEN" ] && [ -f "$CF_DIR/cloudflare-token" ]; then
  CLOUDFLARE_API_TOKEN="$(tr -d '[:space:]' < "$CF_DIR/cloudflare-token")"
fi
if [ -z "$CLOUDFLARE_ACCOUNT_ID" ] && [ -f "$CF_DIR/cloudflare-account" ]; then
  CLOUDFLARE_ACCOUNT_ID="$(tr -d '[:space:]' < "$CF_DIR/cloudflare-account")"
fi
[ -z "$CLOUDFLARE_API_TOKEN" ] && { echo "[ERROR] 未找到 Cloudflare API token（环境变量 CLOUDFLARE_API_TOKEN 或 $CF_DIR/cloudflare-token）"; exit 1; }
[ -z "$CLOUDFLARE_ACCOUNT_ID" ] && { echo "[ERROR] 未找到 Cloudflare Account ID（环境变量 CLOUDFLARE_ACCOUNT_ID 或 $CF_DIR/cloudflare-account）"; exit 1; }
export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID

# --- 组装部署目录（保留 functions/ 与 _redirects / _headers；排除非上线文件）---
DEPLOY_DIR="$HOME/.trae/work/6a4132f2b99c56d056553a09/deploy-cf"
rm -rf "$DEPLOY_DIR"; mkdir -p "$DEPLOY_DIR"
rsync -a \
  --exclude='.DS_Store' --exclude='.git' --exclude='.vercel' --exclude='.trae' \
  --exclude='node_modules' --exclude='__pycache__' \
  --exclude='*.xlsx' --exclude='*.py' --exclude='*.sh' --exclude='*.bak' --exclude='*.bak-*' --exclude='*.tmp' \
  --exclude='archive' --exclude='backup' --exclude='docs' --exclude='/api' \
  --exclude='prototype' \
  --exclude='data/user' --exclude='user_upload' \
  --exclude='vercel.json' --exclude='.vercelignore' --exclude='.gitignore' --exclude='/*.md' \
  "./" "$DEPLOY_DIR/"

echo "== 部署目录抽查 =="
ls "$DEPLOY_DIR" | head -30
echo "-- functions --"; find "$DEPLOY_DIR/functions" -type f 2>/dev/null

# --- wrangler CLI（优先工作区缓存安装）---
WRANGLER=""
WORK="$HOME/.trae/work/6a4132f2b99c56d056553a09"
for cand in "$WORK/node_modules/.bin/wrangler" "$WORK/wrangler-cli/node_modules/.bin/wrangler" "$(command -v wrangler 2>/dev/null)"; do
  if [ -n "$cand" ] && [ -x "$cand" ]; then WRANGLER="$cand"; break; fi
done
if [ -z "$WRANGLER" ]; then
  echo "[INFO] 未找到 wrangler，正在安装到工作区缓存…"
  WDIR="$WORK/wrangler-cli"
  mkdir -p "$WDIR"
  # --prefix 固定安装位置；--cache 指到可写目录，规避系统 npm 全局缓存权限问题
  (cd "$WDIR" && npm install wrangler@latest --no-audit --no-fund --prefix "$WDIR" --cache "$WORK/npm-cache") || true
  WRANGLER="$WDIR/node_modules/.bin/wrangler"
fi
[ -x "$WRANGLER" ] || { echo "[ERROR] wrangler 不可用"; exit 3; }

# --- 首次部署：创建 Pages 项目（已存在则忽略）---
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u NODE_USE_ENV_PROXY \
  NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem \
  "$WRANGLER" pages project create "$PROJECT" --production-branch=main </dev/null 2>&1 | tail -3 || true

# --- 部署（Direct Upload：上传整目录，含 functions/）---
cd "$DEPLOY_DIR"
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u NODE_USE_ENV_PROXY \
  NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem \
  "$WRANGLER" pages deploy "$DEPLOY_DIR" --project-name="$PROJECT" --branch=main --commit-dirty=true 2>&1 | tail -15

echo ""
echo "✅ 已部署到 Cloudflare Pages 项目：$PROJECT"

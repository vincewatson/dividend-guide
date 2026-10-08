#!/bin/bash
# 食息指南 · 本地预览：双击运行，自动在浏览器打开本地网站（关闭这个终端窗口即停止预览）
cd "$(dirname "$0")/.." || exit 1
PORT=8090
while lsof -i :$PORT >/dev/null 2>&1; do PORT=$((PORT+1)); done
echo "本地预览地址：http://localhost:$PORT/"
echo "看完直接关闭这个窗口即可。"
( sleep 1; open "http://localhost:$PORT/" ) &
python3 -m http.server $PORT

#!/bin/bash
set -e
cd "$(dirname "$0")"

if ! command -v npm >/dev/null 2>&1; then
  osascript -e 'display dialog "未检测到 npm，请先安装 Node.js (https://nodejs.org)" buttons {"好的"} default button "好的"'
  exit 1
fi

if [ ! -d "node_modules" ]; then
  npm install
fi

npm start

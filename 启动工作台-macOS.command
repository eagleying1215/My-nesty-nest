#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo '请先从 python.org 安装 Python 3.10 或更新版本。'
  read -r -p '按回车退出……'
  exit 1
fi
python3 启动工作台.py

#!/bin/sh
# 安装仓库的 Git 钩子（当前只有 pre-push：交接文档与数据不一致时拒绝推送）
# 用法：sh tools/install_git_hooks.sh
set -e
ROOT=$(git rev-parse --show-toplevel)
for f in tools/git-hooks/*; do
  name=$(basename "$f")
  cp "$f" "$ROOT/.git/hooks/$name"
  chmod +x "$ROOT/.git/hooks/$name"
  echo "已安装钩子: $name"
done

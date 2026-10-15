#!/bin/sh
# 本机开发用：改完 skills/ 之后运行，让 Skills Manager 从 skills/<名字>/ 重新导入。
# 已部署的 agent（pi、Claude Code）通过软链接指向 Skills Manager 的库，导入后立即生效。
set -e
cd "$(dirname "$0")/.."
python3 tools/sync_shared.py --check
python3 tools/portability_check.py --strict
SM="$HOME/.skills-manager/bin/skills-manager-cli"
[ -x "$SM" ] || SM="$(command -v skills-manager-cli)"
for s in zh-ladder-writing zh-ladder-diagram zh-ladder-page; do
  "$SM" --json skills update "$s" | grep -q '"refreshed":true' && echo "已同步 $s"
done

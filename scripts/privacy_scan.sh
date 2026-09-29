#!/usr/bin/env bash
# 推送前隐私扫描：零命中才算过。命中就逐个修，别加白名单绕过。
# 通用规则写在这里；只属于作者本人的关键词（用户名、邮箱前缀、表 ID、签名 ID 等）
# 放在仓库外的本机文件里，一行一个正则：~/.config/daniel-tools/private_patterns.txt
set -u
cd "$(dirname "$0")/.."
generic='/Users/[A-Za-z]|/home/[a-z]+/|@gmail\.com|@qq\.com|@163\.com|SESSDATA|bili_jct|sk-[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|BEGIN (RSA|OPENSSH) PRIVATE|DEVELOPMENT_TEAM = [A-Z0-9]{10}|1[3-9][0-9]{9}'
private_file="${PRIVATE_PATTERNS:-$HOME/.config/daniel-tools/private_patterns.txt}"
pat="$generic"
if [ -f "$private_file" ]; then
  extra=$(grep -v '^\s*#' "$private_file" | grep -v '^\s*$' | paste -sd'|' -)
  [ -n "$extra" ] && pat="$pat|$extra"
else
  echo "提示：没找到 $private_file，只跑了通用规则。"
fi
hits=$(grep -rInE --exclude-dir=.git --exclude=privacy_scan.sh "$pat" . || true)
big=$(find . -path ./.git -prune -o -type f -size +2M -print)
if [ -n "$hits" ] || [ -n "$big" ]; then
  [ -n "$hits" ] && { echo "== 命中敏感模式："; echo "$hits"; }
  [ -n "$big" ] && { echo "== 超过 2MB 的文件："; echo "$big"; }
  exit 1
fi
echo "隐私扫描通过：0 命中"

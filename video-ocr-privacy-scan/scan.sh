#!/usr/bin/env bash
# 成片隐私扫描：抽帧 → 逐帧识别文字 → 搜路名、门牌、电话这类会暴露住址的字。
# 用法：bash scan.sh 成片.mp4 [每秒抽几帧，默认 10]
# 输出：命中的行打到屏幕；全部识别结果留在 成片.ocr.txt，方便回头细看。
# 只读视频，不改原文件。抽出来的帧放临时目录，跑完删掉。
set -euo pipefail
[ $# -ge 1 ] || { echo "用法：bash scan.sh 成片.mp4 [fps]"; exit 2; }
video="$1"; fps="${2:-10}"
here="$(cd "$(dirname "$0")" && pwd)"
[ -x "$here/ocr_scan" ] || swiftc -O "$here/ocr_scan.swift" -o "$here/ocr_scan"
frames="$(mktemp -d)"; trap 'rm -rf "$frames"' EXIT
ffmpeg -loglevel error -i "$video" -vf "fps=$fps" -q:v 2 "$frames/f%05d.jpg"
out="${video%.*}.ocr.txt"
"$here/ocr_scan" "$frames" > "$out"
# 想加词就改这一行。数字门槛是 5 位以上，避开字幕里常见的年份和小数字。
pattern="${OCR_PATTERN:-路|Road|Rd\.|街|弄|巷|号楼|小区|电话|Tel|[0-9]{5,}}"
echo "共 $(ls "$frames" | wc -l | tr -d ' ') 帧，有文字的 $(wc -l < "$out" | tr -d ' ') 帧。全部结果：$out"
# 只搜帧文件名后面识别出来的字（文件名 f00226.jpg 本身就带 5 位数字）
if grep -E "^[^ ]+ .*($pattern)" "$out"; then
  echo "== 上面这些帧可能露了位置信息，回去看一眼，需要就补遮。"
else
  echo "== 没搜到路名、门牌、电话。"
fi

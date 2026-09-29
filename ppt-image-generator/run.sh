#!/bin/bash
# 本地 PPT 出图脚本
# 使用 Gemini API 生成渐变毛玻璃风格的 PPT 图片
#
# 使用方法:
#   1. 确保已安装 Python 3.8+
#   2. export GEMINI_API_KEY='replace-with-your-key'
#   3. chmod +x run.sh && ./run.sh [slides.json]

set -euo pipefail

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "请先设置 GEMINI_API_KEY 环境变量"
  echo "export GEMINI_API_KEY='replace-with-your-key'"
  exit 1
fi

# 安装依赖
pip install google-genai pillow python-dotenv

# 运行生成（不传参数时使用 example_slides.json）
python generate_slides.py "$@"

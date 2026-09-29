#!/bin/bash

# 检查 Python 环境
if [ ! -d "venv" ]; then
    echo "正在创建 Python 虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 启动 Web 分析器
echo "正在启动文章分析器..."
python tools/web_analyzer.py 
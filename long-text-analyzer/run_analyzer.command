#!/bin/bash

echo "正在启动文章分析器..."

# 切换到程序目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "切换到程序目录: $SCRIPT_DIR"
cd "$SCRIPT_DIR"

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "正在创建 Python 虚拟环境..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "错误：创建虚拟环境失败"
        read -p "按任意键退出..."
        exit 1
    fi
fi

# 激活 Python 虚拟环境
echo "正在激活 Python 虚拟环境..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "错误：激活虚拟环境失败"
    read -p "按任意键退出..."
    exit 1
fi

# 安装依赖
echo "正在检查依赖..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "错误：安装依赖失败"
    read -p "按任意键退出..."
    exit 1
fi

# 启动程序
echo "正在启动 Web 服务..."
# 在后台运行 Flask 服务
python tools/web_analyzer.py &
# 保存进程 ID
FLASK_PID=$!

# 等待服务启动
echo "等待服务启动..."
sleep 3

# 打开浏览器
echo "正在打开浏览器..."
open "http://127.0.0.1:5000"

# 等待用户按 Ctrl+C
echo "程序已启动！按 Ctrl+C 停止服务..."
wait $FLASK_PID 
#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify
from article_analyzer import ArticleAnalyzer
import os
from pathlib import Path
from dotenv import load_dotenv
import argparse

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-me')

# 加载环境变量
load_dotenv()

# 确保模板目录存在
template_dir = Path(__file__).parent / 'templates'
static_dir = Path(__file__).parent / 'static'
template_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    text = request.json.get('text', '')
    if not text:
        return jsonify({'error': '请输入要分析的文本'}), 400
    
    try:
        # 使用环境变量中的默认提供商
        provider = os.getenv('DEFAULT_LLM_PROVIDER', 'anthropic')
        analyzer = ArticleAnalyzer(provider=provider)
        result = analyzer.analyze_text(text)
        formatted_result = analyzer.format_analysis_result(result)
        return jsonify({'result': formatted_result})
    except Exception as e:
        return jsonify({'error': f'分析过程中出现错误：{str(e)}'}), 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='启动文章分析器 Web 服务')
    parser.add_argument('--port', type=int, default=5000, help='服务器端口号')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='服务器主机地址')
    args = parser.parse_args()
    
    app.run(debug=True, host=args.host, port=args.port) 
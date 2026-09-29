# 长文自动分析器

一篇很长的文章或者一整段多轮对话记录，想知道讲了什么、谁说了什么关键观点、有哪些值得深挖的问题，从头读一遍太花时间，所以写了这个：调用 LLM 自动分段分析，再把各段结果合并成一份结构化总结（概述、主要话题、发言者分析、背景信息、问题讨论、独特见解）。

- 形态：Python 命令行 + 本地网页（Flask）
- 状态：已停
- 最后改动：2026-03-07

## 怎么用

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入你要用的 provider 的 API key
```

命令行方式：

```bash
python3 tools/article_analyzer.py --input your_article.txt
# 或者从标准输入读，输入完按 Ctrl+D 结束
python3 tools/article_analyzer.py

# 换 provider / 模型 / 输出到文件
python3 tools/article_analyzer.py --input your_article.txt --provider anthropic --output result.txt
```

网页方式：

```bash
./start_analyzer.sh
# 或者双击 run_analyzer.command（macOS，会自动建虚拟环境、装依赖、开浏览器）
```

启动后访问 `http://127.0.0.1:5000`，粘贴文本点分析即可。

## 依赖

- Python 3.6+
- `openai`、`anthropic`、`google-generativeai`（按用哪个 provider 装哪个，任选其一即可跑通）
- `python-dotenv`、`flask`（网页模式需要）

支持的 provider：`openai`（默认）、`anthropic`、`deepseek`、`azure`、`gemini`，命令行加 `--provider` 切换；网页模式用 `.env` 里的 `DEFAULT_LLM_PROVIDER`（默认 `anthropic`）。

## 风险与边界

- 长文本会被自动分段发给 LLM，段与段之间没有上下文共享，分析结果靠后处理合并，超长文章的跨段关联可能丢失。
- 依赖 LLM 返回严格 JSON 格式，遇到格式不对会自动尝试修复/重试，仍失败则报错退出，不会返回错误的半截结果。
- 网页模式没有做任何鉴权，只适合本机使用，不要部署到公网。
- 文本内容会发送给你选择的 LLM provider，处理机密/敏感文本前自己判断是否合适。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：这个项目原来是从 devin.cursorrules 模板 fork 出来的，仓库根目录的 README、requirements.txt、.env、.env.example 都是模板自带的通用内容（且 `.env`/`.env.example` 里都留了真实的 OpenAI API key，一个都没有带过来）；只留了真正被这个工具用到的 `tools/article_analyzer.py`、`tools/web_analyzer.py`、`tools/llm_api.py`（分析逻辑依赖它做多 provider 调用）、`tools/templates/index.html`，以及两个启动脚本（跳过了写死本机绝对路径的 `start_analyzer.applescript`）；`requirements.txt` 换成了这几个脚本实际用到的库（原来是模板的网页抓取/搜索引擎相关依赖，跟本工具无关）；`web_analyzer.py` 里硬编码的 Flask `SECRET_KEY` 占位符改成了从环境变量读（`FLASK_SECRET_KEY`，仍有默认占位值方便本机直接跑）；`llm_api.py` 的 shebang 从模板残留的 `/workspace/tmp_windsurf/...` 改成了通用的 `#!/usr/bin/env python3`。新写了 `.env.example`（全假值）。迁移时只做了静态检查（`python3 -m py_compile`），没有重新运行。

# 技术讲义 PPT 生成

领域专家有大纲和旧课件，但没时间从头排版一份技术讲义 PPT，所以写了这个：大纲 markdown → 自动分版式 → 自动配图匹配 → 自动出 PPTX，再跑一轮自动审改，人工只需要在 PowerPoint 里微调 10-20%。

- 形态：Python 命令行（多个独立脚本，可单独跑也可串成 pipeline）
- 状态：已停（原型验证完成后没再继续投入）
- 最后改动：2026-07-08

## 怎么用

```bash
pip install -e .

# 新建一个项目（生成 outline.md 模板 + 目录结构）
python3 new_project.py --name "我的讲义"

# 或者直接用仓库自带的假内容示例跑一遍，看看效果
python3 -m src.core.pipeline --base examples/demo-deck
# → examples/demo-deck/output.pptx（主交付）
# → examples/demo-deck/output-preview.html（跑 render_html 单独生成，见下）

# 单独生成 HTML 预览（不用打开 PowerPoint 就能看效果）
python3 -m src.render_html --base examples/demo-deck

# 跑一轮自动审改（规则版，不需要 API key）
python3 -m src.reviewer_agent --base examples/demo-deck

# 完整审改闭环（reviewer → contributor → 再审，直到收敛或到轮次上限）
python3 -m src.run_review_loop --base examples/demo-deck --max-iter 3

# 加 Claude 一起审（需要 ANTHROPIC_API_KEY，规则版之外再补语义判断）
python3 -m src.run_review_loop --base examples/demo-deck --max-iter 3 --llm
```

用自己的大纲：把 `outline.md` 换成你自己的内容（格式见 `examples/demo-deck/outline.md`，`##` 是章、`### 第N页：标题` 是页、`- ` 是要点、`> 配图建议：` 是配图描述），如果有旧 PPT 素材，先跑 `python3 -m src.extract_images 旧课件.pptx --base 你的项目目录` 把图提取到 `extracted/` 目录，再跑 pipeline。

## 工作原理

大纲解析 → 版式分类（12 种 layout，规则版）→ 本地图片关键词匹配 → 生成结构化 actions.json（中间产物）→ 渲染成 PPTX / HTML → 规则版 Reviewer 挑问题（可选加 Claude 语义审稿）→ Contributor 按问题自动改一轮 → 再审，直到收敛。

## 依赖

- Python 3.11+
- `python-pptx`、`pillow`
- 可选：`anthropic`（只有用 `--llm` 时才需要，见 `.env.example`）

## 跟原始项目相比，这份公开版少了什么

原项目是围绕一个真实客户项目做的原型验证，这份公开版只留了跟"输入大纲 → 输出 PPT"这条主线直接相关的生成代码，去掉了：
- 网页审改面板（FastAPI + 浏览器 UI）
- 大规模网络采图编排（`web_sourcer.py` / `run_web_sourcing.py`）——这部分设计是给 sub-agent 分发采图任务，没有全部跑通验证过，公开版没有必要背这个复杂度
- AI 交叉验证（调 API 逐张核对图文是否匹配）
- 针对原项目的命中率评测脚本

`reviewer_agent.py` 和 `run_review_loop.py` 里保留了一个通用的"跟人工反馈对照算召回率"功能（`--eval-feedback`），如果你有一份专家驳回反馈（格式见代码里 `evaluate_recall_against_feedback` 的 docstring），可以自己接上用来评估 Reviewer 效果。

## 风险与边界

- `slide_cover()`（`src/export_pptx.py`）和 `render_cover()` 的 eyebrow 文字、`slide_agenda()` 的目录卡片，目前是**写死的示例常量**，不会读 `outline.md` 里封面页/目录页的实际文字。跑自己的项目最简单的办法是直接改 `export_pptx.py` 顶部的 `COVER_TITLE_LINE1` / `COVER_TITLE_LINE2` / `COVER_SUBTITLE` / `AGENDA_CARDS` 等几个常量；更彻底的做法是把这两个函数也改成从 `Page`/`DeckActions` 读数据（跟其余 10 种 layout 一致）。
- `src/reviewer_llm.py` 里的 few-shot 示例反馈是占位内容，实际使用时建议换成你自己领域、自己专家的真实驳回反馈原话，效果会明显更好（system prompt 里有说明）。
- 图片匹配（`source_images.py`）是本地关键词打分，不接任何外部图库，效果上限取决于 `extracted/` 里有多少图、大纲里的"配图建议"写得够不够具体。
- 12 种 layout 的分类是规则版（关键词/正则命中），不是训练过的分类器，遇到大纲写法差异较大的项目命中率会下降。
- `--llm` 相关功能会真实调用 Anthropic API，产生费用。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。迁移时做了：只保留大纲解析、风格提取、版式规划、本地图片匹配、actions 中间产物、PPTX/HTML 渲染、规则版+LLM 版审改闭环这条主线的代码；网页审改面板、大规模网络采图、AI 交叉验证、针对真实客户项目的命中率评测脚本都没有搬。

代码里原本嵌着一个真实项目的具体内容：写死在渲染代码里的封面标题、页脚文字、目录结构，审稿提示词里的示例反馈原话，还有排版规则里那个行业的专业词表。这些都换成了占位内容或改成从数据读取，专业词表改成了「按你的领域填」的示例。原项目的真实大纲、真实反馈和评测结果都没有搬，示例用的是 `examples/demo-deck/outline.md`，内容全部是占位。

迁移时用示例大纲实际跑通了一遍完整流程（`pipeline.py` 生成 PPTX、`render_html.py` 生成 HTML 预览、`reviewer_agent.py` 规则版审稿、`run_review_loop.py` 两轮闭环，全部跑通无报错），确认改动后代码仍然可用；`--llm` 相关路径（需要 API key）和 `extract_images.py`（需要真实 PPTX 输入）没有实跑，只做了 `python3 -m py_compile` 静态检查。

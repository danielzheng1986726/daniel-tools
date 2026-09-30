# 小红书卡片渲染

小红书知识笔记要出好看的图文卡片，手动截图排版太麻烦，所以写了这个 Markdown 转卡片图的渲染器。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-08-08

## 怎么用

Markdown 文件用 `---` 分页，文件开头可选 YAML 头定义封面（`title`/`subtitle`/`emoji`）：

```markdown
---
title: 示例标题
subtitle: 副标题
emoji: "🌱"
---

## 第一页标题

正文内容，支持 **加粗**、*斜体*、`代码`、列表、引用。

#标签1 #标签2

---

## 第二页标题

...
```

渲染：

```bash
python3 render_xhs_cards.py notes.md -o ./xhs-cards/
python3 render_xhs_cards.py notes.md -o ./xhs-cards/ --accent "#0F766E" --accent2 "#14B8A6"
```

换主题色要两个参数一起给：`--accent` 管标题、分隔线和标签文字，`--accent2` 管列表圆点、封面渐变的后半段和侧边色条。只给 `--accent` 的话，圆点和封面渐变还是默认的靛蓝，两种颜色会混在一起（2026-09-30 实测）。

输出 1080x1440 的 PNG：有 `title` 就先出一张 `cover.png` 封面，再按分页出 `card_1.png`、`card_2.png`……

也可以当模块调用：

```python
from render_xhs_cards import render_cards
files = render_cards("notes.md", "./xhs-cards/", accent="#4338CA")
```

## 依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

即 `pyyaml` 和 `playwright`（用无头 Chromium 截图）。渲染时会加载 Google Fonts 的 Noto Sans SC，需要联网；断网会退回系统里的 `PingFang SC` / `Hiragino Sans GB` 等中文字体。

## 风险与边界

不删改任何已有文件，只在指定输出目录写 PNG。渲染逻辑是自己写的一个极简 Markdown 子集解析器（标题/列表/引用/加粗/斜体/行内代码/`#标签`），不是完整 CommonMark，复杂 Markdown（嵌套列表、表格等）不保证排版正确。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：新增 `requirements.txt`；README 里的输出目录示例从系统临时目录 `/tmp/xhs-cards/` 换成相对路径 `./xhs-cards/`。代码本身没有改动（没有本机路径、密钥或个人信息需要清理）。迁移时只做了静态检查（`py_compile`），没有重新跑 Playwright 渲染。

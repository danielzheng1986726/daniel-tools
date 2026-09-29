# Markdown 转公众号样式

公众号编辑器会把 `<style>` 块和 class 选择器全丢掉，只认标签上的 `style=""` 属性，直接把 Markdown 渲染出的裸 HTML 粘进去就是零样式的白板文章，太麻烦，所以写了这个工具把样式一个个内联到标签上。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-07-15

## 怎么用

```bash
python3 md_to_wechat_html.py article.md -o out.html
```

从 stdin 读也行：

```bash
cat article.md | python3 md_to_wechat_html.py -
```

常用参数：
- `--theme plain`：样式主题，目前只有一套 `plain`。
- `--link-mode footnote|inline|keep`：公众号正文里的超链接对订阅号是失效的，默认 `footnote`（正文留 `文字[1]`，文末生成参考链接清单）；`inline` 把链接写成「文字（https://...）」；`keep` 原样保留 `<a>`，知道自己在干什么时再用。
- `--strip-h1`：摘掉正文里第一个 H1（标题应该走公众号自己的标题字段，不该在正文里重复一遍）。
- `--footnote-heading`：脚注区标题，默认「参考链接」。
- `--stats`：把标题/字数/链接统计打到 stderr，方便核对。

输出的 HTML 可以直接粘进公众号编辑器，或者喂给别的发布工具（比如 `multipost-draft-filler`）。

## 依赖

```bash
pip install -r requirements.txt
```

即 `beautifulsoup4` 和 `markdown-it-py`。

## 风险与边界

不删改任何本地文件，只读输入、写输出。公众号编辑器实测能保留的 CSS 属性有限（`font-size`/`line-height`/`color`/`margin`/`padding`/`background`/`border`/`text-align`/`font-weight`），样式表是按这个边界写的，公众号后台改版后可能需要重新核对。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：把 usage 示例里的 `tools/md_to_wechat_html.py` 路径改成脚本自身文件名（搬出来后不再有 `tools/` 子目录）；模块开头注释里提到具体测试日期和「传给 MultiPost」的实现细节，改写成更通用的描述；新增 `requirements.txt`。代码逻辑本身没有改动。迁移时只做了静态检查（`py_compile`），没有重新跑一遍转换。

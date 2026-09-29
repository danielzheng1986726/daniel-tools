# 多平台灌草稿

写完一篇文章要挨个打开公众号、知乎、小红书的编辑器手动粘贴排版，太麻烦，所以写了这个脚本，一条命令把 Markdown 灌进 MultiPost 桌面客户端已登录的各平台编辑器草稿箱。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-09-28

## 怎么用

前提：装好 [MultiPost](https://github.com/leaperone/MultiPost) 桌面客户端，登录好要发的平台账号，并在「设置 → 外部 API」里打开外部 API 开关。

```bash
python3 multipost_publish.py article.md --platforms zhihu,wechat
```

默认只灌草稿，不点发布（`autoSubmit=false`）。想直接发布要显式加 `--submit`——别轻易开。

常用参数：
- `--content-type ARTICLE|DYNAMIC|VIDEO`：文章、图文动态、视频，默认 `ARTICLE`。
- `--platforms`：逗号分隔的平台名，默认 `zhihu,wechat`。
- `--title`：不给就取正文首个 H1。
- `--digest` / `--read-original`：公众号摘要和「阅读原文」链接，MultiPost 的 API 管不到这两个字段，脚本会在填完后用 MCP 的 `execute_script` 直接补 DOM。
- `--cover`：封面图路径；公众号必须有封面，不给会自动调用 `make_cover.py` 生成一张（可以 `--no-auto-cover` 关掉）。
- `--dry-run`：只打印将要发送的内容，不真调接口。
- `--list-accounts`：列出 MultiPost 里已登录的账号。

图文动态和视频模式：

```bash
python3 multipost_publish.py note.md --content-type DYNAMIC --platforms xiaohongshu --images a.jpg,b.jpg
python3 multipost_publish.py script.md --content-type VIDEO --platforms shipinhao --video clip.mp4
```

## 依赖

无第三方 pip 依赖，只用标准库，但**依赖同一个 `daniel-tools` 仓库里两个相邻的工具文件夹**：
- `../md-to-wechat-html/md_to_wechat_html.py`（公众号内容转内联样式 HTML）
- `../wechat-text-cover/make_cover.py`（自动生成封面时调用）

三个文件夹要放在同一层级（都在 `daniel-tools/` 下）才能找到彼此；`md-to-wechat-html` 自己的依赖（`beautifulsoup4`、`markdown-it-py`）也要装好，见它自己的 README。

还依赖：
- MultiPost 桌面客户端本身在跑，且已在设置里打开外部 API。
- Token 从 MultiPost 客户端的本机配置目录里自动读；也可以用环境变量 `MULTIPOST_TOKEN` 覆盖（比如客户端换了存储位置，或想手动指定）。

抖音等平台的「话题标签」需要专门的适配脚本（比如把标签做成真正可点击的话题），这类脚本不在本仓库范围内，脚本只会提示你另外处理，不会瞎填。

## 风险与边界

- **默认只灌草稿。`--submit` 会真的点发布，发布前务必去 MultiPost 里肉眼核对一遍标题、封面、正文、标签。**
- 会调用本机正在运行的 MultiPost 桌面客户端的 REST API 和 MCP 接口（默认 `http://127.0.0.1:19528`），只在本机通信，不经过公网。
- 补摘要/阅读原文那步是靠 JS 直接操作公众号编辑器页面的 DOM（通过 MultiPost 的 `execute_script`），公众号编辑器改版可能导致选择器失效，届时这两个字段会静默填不进去（脚本会打印「没找到摘要框/阅读原文框」）。
- 平台支持的内容类型（ARTICLE/DYNAMIC/VIDEO）会实时查询 MultiPost 的 `/v1/platforms`，不信写死的表；查不到时才退回内置的兜底判断。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：`sys.path` 插入和封面生成的 `subprocess` 调用从「同一个 `tools/` 目录下」改成「相邻的两个工具文件夹」（`../md-to-wechat-html/` 和 `../wechat-text-cover/make_cover.py`），并在找不到时给出明确报错提示两个文件夹要在同一层级；文档字符串和 `--brand` 示例里的真实个人品牌名换成占位「示例公众号」；模块开头注释里的具体测试日期去掉。Token 读取路径（`~/Library/Application Support/multipost-desktop/app-settings.json`）本身是 MultiPost 客户端固定的存储位置，不是 Daniel 专属路径，原样保留，代码里用 `Path.home()` 动态取，不含任何用户名。迁移时只做了静态检查（`py_compile`），没有真的连 MultiPost 客户端跑一遍（跑这个脚本必然会联网调用本机客户端接口，按迁移规矩不实跑）。

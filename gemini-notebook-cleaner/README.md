# Gemini Notebook 批量清理

Gemini 的 Notebook（notebook.google.com）攒多了，一个个点删除太麻烦，写了这个浏览器脚本批量删。

- 形态：浏览器脚本（Chrome DevTools Console）
- 状态：用过一次（2026-09-28 删了 260 个）
- 最后改动：2026-09-29

## 怎么用

1. Chrome 打开 `https://notebook.google.com/?authuser=0`，停在「My notebooks」列表视图。
2. `Cmd+Option+J` 打开 Console，粘贴 `notebook_bulk_delete.js` 全文，回车。
3. 默认 `DRY_RUN = true`，只会打印将要删除的清单（`console.table`），不会真删。确认清单没问题后，把脚本里的 `DRY_RUN` 改成 `false` 再跑一次，会弹确认框二次确认。
4. 中途想停：在 Console 里输入 `window.__stopNbDelete = true`。
5. `KEEP` 数组填想保留的标题关键词（标题包含即保留），例如 `['会议记录', '读书']`。

## 依赖

无。纯浏览器脚本，不需要安装任何东西，但依赖 Gemini Notebook 网页当前的 DOM 结构（class 名、按钮 aria-label）。

## 风险与边界

- **会永久删除 Notebook，不可恢复。** 务必先用默认的 `DRY_RUN = true` 看一遍清单，确认没有误删范围再改成 `false`。
- Google 改版后页面选择器（`tr.mat-mdc-row`、`button[aria-label="Project Actions Menu"]` 等）可能失效，脚本会找不到按钮而报错停止，不会误删别的东西。
- 脚本按行删除，每删一个等 5 秒、每次点击间隔 1 秒，连续失败 5 次会自动停止，不会无限重试。
- 只在你自己登录的账号页面里跑，脚本本身不上传任何数据。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。迁移时做了：去掉文件名里的编号前缀（改成 `notebook_bulk_delete.js`）；`DRY_RUN` 默认值从 `false` 改成 `true`；`KEEP` 注释里的示例从个人化的例子换成中性示例（`['会议记录', '读书']`）；README 补充风险说明。迁移时只做了静态检查（读代码确认逻辑），没有重新在浏览器里跑一遍。

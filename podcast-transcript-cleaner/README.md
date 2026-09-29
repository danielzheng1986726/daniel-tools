# 播客 ASR 稿清洗

ASR 转写稿的说话人分不清、专名听成同音字、断句乱七八糟，每次都要手动整理太麻烦，所以写了这个脚本调 Claude Code 自动清洗。

- 形态：zsh 命令行脚本
- 状态：在用
- 最后改动：2026-04-16

## 怎么用

```bash
clean-podcast                       # 自动列出 ~/Downloads 里最近的 .md 文件，选一个
clean-podcast <输入文件>            # 指定文件，输出名自动取文件名
clean-podcast <输入文件> <输出名>   # 指定文件和输出名
```

跑起来之后会调用 `claude -p` 执行清洗（首次调用可能要一两分钟），清洗结果写到输出目录，同时在终端打印说话人识别结论、术语修正清单，以及最重要的——一份「需要人工确认的存疑项」清单（标记为 `[?]` 的地方）。**这份存疑清单是你唯一需要人工审阅的部分，务必看一遍再用。**

装好之后可以把它放进 `PATH`（比如软链到 `~/.local/bin/clean-podcast`）就能直接当命令用。

## 依赖

- [Claude Code](https://claude.com/claude-code) CLI，且能不带确认地跑 `claude -p`（非交互模式）。
- `podcast-transcript-editor` 这个 skill 要能被 Claude Code 找到（放在 `~/.claude/skills/` 或项目 `.claude/skills/` 下）。这个脚本本身只是个调用壳，清洗逻辑（怎么判断说话人、怎么修正术语、怎么标存疑项）全在这个 skill 里。
- zsh（用了 zsh 特有的数组语法 `${(@f)...}`，不能直接拿 bash 跑）。

## 风险与边界

- 输出目录默认 `~/MyVault/podcasts/`，可以用环境变量 `CLEAN_PODCAST_OUTPUT_DIR` 改成别的路径。
- 目标文件已存在会先问要不要覆盖，不会静默覆盖。
- 这是机器清洗稿，清洗质量取决于 `podcast-transcript-editor` skill 本身和调用的模型；存疑项列表已经是脚本能给到的最强提示，但不代表清洗结果 100% 准确，引用原话前建议回听音频核对。
- 不会自动处理版权或隐私内容，清洗对象是你自己拥有或有权处理的转写稿。

## 迁移说明

2026-09-29 从 Daniel 本机的 `~/.local/bin/clean-podcast` 复制过来（不带原 git 历史）。迁移时做了：输出目录从写死的 `$HOME/MyVault/podcasts` 改成可用环境变量 `CLEAN_PODCAST_OUTPUT_DIR` 覆盖（默认值不变）。脚本本身不含用户名、邮箱等敏感信息（用的都是 `$HOME` 相对路径）。迁移时只做了语法检查（`zsh -n`），没有真的跑一遍清洗（那需要联网调用 Claude Code 且依赖具体的转写稿文件）。

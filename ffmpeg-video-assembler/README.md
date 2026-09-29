# FFmpeg 视频自动拼接

手剪短视频时，转场、配乐淡入淡出、片尾文字这些每次都要重新调 FFmpeg 参数，太麻烦，所以写了这个：写一份 JSON 配置（片段顺序、转场、配乐、字幕、文字条），脚本自动拼出一条 `filter_complex` 命令并渲染。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-04-09

## 怎么用

```bash
# 只打印生成的 FFmpeg 命令，不实际渲染
python3 video_assembler.py example_config.json --dry-run

# 实际渲染
python3 video_assembler.py example_config.json
```

配置字段见 `example_config.json`：
- `clips`：按顺序排列的视频片段，每条可单独指定 `transition`（覆盖全局 `transition_type`）
- `output` / `resolution` / `transition_duration` / `transition_type`：整体输出设置
- `audio`：可选背景音乐（音量、淡入淡出秒数）
- `subtitles`：可选字幕文件（ASS/SRT，走 FFmpeg 的 `subtitles` 滤镜）
- `text_overlays`：可选文字叠加（比如片尾标题），可设开始/结束时间、位置、字号颜色

## 依赖

- FFmpeg / ffprobe（需要能在 PATH 里直接跑通）
- Python 3，标准库即可，无第三方包

## 风险与边界

- 会直接覆盖 `output` 指定的文件（`ffmpeg -y`），先用 `--dry-run` 确认命令再跑。
- 字体路径写的是 macOS 系统字体（`Heiti SC` / `STHeiti Medium.ttc`），换系统要自己改 `font` 参数。
- 没有输入校验之外的容错：某个片段读不出时长、字幕文件路径带特殊字符等情况可能直接让 FFmpeg 报错退出。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：直接复制脚本（内容本身不含真实路径、密钥或项目信息，未改动逻辑），新增 `example_config.json` 示例配置（假素材名）和本 README。迁移时只做了 `python3 -m py_compile` 静态检查，没有重新运行。

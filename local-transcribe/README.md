# 本机转写

播客/视频转写要么要传去云端不放心，要么按分钟收费，太麻烦，所以写了这个全在本机跑的转写工具。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-09-21

## 怎么用

```bash
python3 transcribe_link.py "https://www.xiaoyuzhoufm.com/episode/xxxxx" \
  --context "示例节目 示例嘉宾 具身智能"
```

也支持 B 站/YouTube 链接、音频直链、本地音视频文件：

```bash
python3 transcribe_link.py ~/Downloads/interview.mp3
```

常用参数：
- `--context`：热词，空格分隔，写完整搭配（比如「示例节目」而不是「示例」），是软偏置不是强制词表。
- `--out`：成稿目录，默认脚本同级的 `./transcripts`（建议加进 `.gitignore`，转写稿不入库）。
- `--keep-audio`：保留下载的音频和中间文件，默认转完就删。
- `--max-seconds N`：只转前 N 秒，试跑用。

## 依赖

- `ffmpeg` / `ffprobe`
- `yt-dlp`（转 B 站/YouTube 等非小宇宙链接时用）
- `mlx-qwen3-asr`（本机 MLX 版 Qwen3-ASR-1.7B 推理，需要自行安装并保证在 `PATH` 里，或用环境变量 `QWEN_ASR_BIN` 指到可执行文件路径）
- 环境变量（都可选）：
  - `QWEN_ASR_BIN`：`mlx-qwen3-asr` 可执行文件路径，不设默认从 `PATH` 找
  - `QWEN_ASR_MODEL`：默认 `Qwen/Qwen3-ASR-1.7B`

只依赖 Python 标准库，不需要额外装 pip 包。

## 风险与边界

- 音频全程留在本机，不上传任何第三方服务，免费。
- 机器稿质量有限：不分说话人；专名可能被听成同音字；引用原话前建议回听音频核对。成稿仅自用，不建议直接外发或公开转贴完整逐字稿。
- 小宇宙付费单集拿不到音频直链会直接报错；Spotify 等加密平台不支持；视频号、抖音等未验证过，遇到会在 yt-dlp 这一步报错。
- 一小时节目在 M1 芯片上大约十几到二十几分钟转完（约 3–5 倍实时），建议放后台跑，不要干等。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：去掉 `mlx-qwen3-asr` 默认路径里的本机绝对路径（原来兜底指向私有仓库下的一个 venv），改成优先读环境变量、其次从 `PATH` 里找；输出目录默认值从原仓库的 `contexts/transcripts` 改成脚本同级的 `./transcripts`；工作目录基准从"仓库根目录"改成"脚本所在目录"，因为搬出来之后不再有上层仓库结构。迁移时只做了静态检查（`py_compile`），没有重新运行（没联网下载、没调用本机 ASR）。

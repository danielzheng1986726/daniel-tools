# 播客精华片段剪辑

一整期播客几十分钟，想剪出两分钟的精华片段发小红书/朋友圈预热，手动听完再剪太花时间，所以写了这几个脚本试着自动化。

- 形态：Python 命令行（多个独立脚本，不同思路）
- 状态：已停
- 最后改动：2026-03-07

## 里面有什么

这个文件夹其实是几次不同尝试的合集，没有统一成一个工具，谁用谁选：

- `simple_audio_trim.py`：最简单，直接截取音频中间 2 分钟。
- `advanced_audio_trim.py`：升级版，支持开头/中间/结尾/混合四种截取策略，参数可调。
- `podcast_highlight.py`：基于静音检测（`pydub.silence`）切分片段，再挑一组拼成目标时长的集锦，会顺手画一张分析图。
- `process_audio.py` / `process_audio_new.py`：先用 Whisper 转写全文，再按转写内容选片段（两个版本用了不同的音频解码方式：一个走 `ffmpeg-python`，一个走 `librosa`），是最接近「按内容选精华」的思路，但没有做完（没有真正基于内容质量打分，选段逻辑还很粗）。

## 怎么用

### 简单/进阶截取（不涉及转写，跑得快）

```bash
python3 simple_audio_trim.py   # 默认读 output.mp3，输出 highlight.wav

python3 advanced_audio_trim.py --input output.mp3 --output highlight.wav \
    --duration 120 --strategy mix   # strategy: beginning / middle / end / mix
```

### 基于静音检测的精彩集锦

```bash
python3 podcast_highlight.py <音频文件路径>
```

### 基于 Whisper 转写选段（最慢，效果也最粗糙）

```bash
python3 process_audio_new.py   # 或 process_audio.py，默认读 output.mp3
```

## 依赖

见 `requirements.txt`（按脚本分组，用哪个装哪组）。所有依赖音频解码的脚本都需要系统装好 `ffmpeg`（`brew install ffmpeg`）。

## 风险与边界

- 都是只读输入、写新文件，不会删除或覆盖原始音频。
- `simple_audio_trim.py` / `advanced_audio_trim.py` 纯粹按时间位置截取，跟内容质量无关，选出来的片段可能正好卡在一句话中间。
- `podcast_highlight.py` 和 `process_audio*.py` 是更早期的实验性尝试，没有做到「自动挑出真正精彩的内容」，效果有限，更多是留作以后继续做的起点。
- Whisper 转写在本机跑，不上传音频；模型固定用的 `base`，速度和准确度是个折中。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：删掉了仓库里的真实音频/输出文件（`output.mp3`、`highlight*.wav`）、删掉了含真实 OpenAI API key 的 `.env`、删掉了跟这几个脚本无关的 devin.cursorrules 模板文件（`tools/llm_api.py` 等——这几个脚本都不引用它们）；`requirements.txt` 原来是模板自带的通用依赖列表（网页抓取/搜索引擎相关，跟本工具无关），换成了脚本实际 `import` 用到的库。迁移时只做了静态检查（`python3 -m py_compile`），没有重新运行。

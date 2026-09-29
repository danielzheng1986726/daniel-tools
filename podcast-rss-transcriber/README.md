# 播客 RSS 转写

自己播客的每一期都要一段段听、一段段整理文字稿，纯手工太慢，所以写了这个：给一个播客 RSS 地址，自动抓全部剧集、下载音频、用 Whisper 转成文字。

- 形态：Python 命令行
- 状态：已停（已被更完整的本地转写流程取代，见下方说明）
- 最后改动：2026-03-07

**这是旧版转录入口，已停。** 后来的转写改用本仓库的 [local-transcribe](../local-transcribe/)：来源不止 RSS（B 站、YouTube、本地文件都行），用的是更快的本机模型。这里留着，是因为它是一个独立能跑的最小实现，只想按 RSS 批量转写时可以参考。

## 怎么用

```bash
pip install -r requirements.txt
python3 podcast_transcrib.py --feed https://example.com/rss/your-feed-id
```

不传 `--feed` 就用脚本里 `RSS_FEED_URL` 的默认值，记得改成自己的播客 RSS 地址。程序会先抓取剧集列表并生成 `podcast_data/metadata.json` 和 `播客内容汇总.md`，然后询问是否下载音频并转录；转录结果保存在 `podcast_data/transcripts/`。

## 依赖

- Python 3
- `feedparser`（RSS 解析）、`requests`（下载音频）
- `openai-whisper` + `torch`（本地语音转文字，首次运行会自动下载模型）

## 风险与边界

- 音频和转录文本会下载/生成到本机 `podcast_data/` 目录，注意磁盘空间；这些内容不在仓库里维护（`.gitignore` 已排除）。
- Whisper 在本地跑，转录质量和 `WHISPER_MODEL` 选的模型大小有关（脚本默认 `small`），不分说话人，专有名词容易转成同音字，引用原话前建议回听核对。
- 没有做增量/去重之外的容错，网络中断或 RSS 格式异常时建议重新运行，已下载/已转录的文件会自动跳过。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：把脚本里硬编码的真实播客 RSS 地址和节目名换成了占位符 `https://example.com/rss/your-feed-id`，改用 `--feed` 命令行参数传入；去掉了原 README 里指向内部资产库项目的具体路径，改成文字描述。迁移时只做了静态检查（`python3 -m py_compile podcast_transcrib.py`），没有重新运行。

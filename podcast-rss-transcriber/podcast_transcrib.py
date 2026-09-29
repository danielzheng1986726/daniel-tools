#!/usr/bin/env python3
"""
播客转录工具
功能：从 RSS feed 获取所有剧集，下载音频，转录成文字

使用前请先安装依赖：
pip install feedparser requests openai-whisper torch

如果你的电脑有 NVIDIA GPU，Whisper 会自动使用 GPU 加速。
如果没有 GPU，也可以运行，只是会慢一些。

使用方法：
python3 podcast_transcrib.py --feed https://example.com/rss/your-feed-id
（不传 --feed 就用下面 RSS_FEED_URL 的默认值，记得改成你自己的播客 RSS 地址）
"""

import argparse
import feedparser
import requests
import os
import json
from pathlib import Path
from datetime import datetime
import re

# ============ 配置区域 ============
RSS_FEED_URL = "https://example.com/rss/your-feed-id"
OUTPUT_DIR = Path("./podcast_data")
AUDIO_DIR = OUTPUT_DIR / "audio"
TRANSCRIPT_DIR = OUTPUT_DIR / "transcripts"

# Whisper 模型大小选择：
# - "tiny": 最快，准确度一般，适合测试
# - "base": 较快，准确度尚可
# - "small": 平衡速度和准确度（推荐）
# - "medium": 较慢，准确度较高
# - "large": 最慢，准确度最高（需要较大显存）
WHISPER_MODEL = "small"
# =================================


def setup_directories():
    """创建必要的目录"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    AUDIO_DIR.mkdir(exist_ok=True)
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    print(f"✓ 目录已创建: {OUTPUT_DIR}")


def fetch_rss_feed(feed_url):
    """获取 RSS feed 并解析"""
    print(f"正在获取 RSS feed: {feed_url}")
    feed = feedparser.parse(feed_url)

    if feed.bozo:
        print(f"⚠ RSS 解析警告: {feed.bozo_exception}")

    podcast_info = {
        "title": feed.feed.get("title", "未知播客"),
        "description": feed.feed.get("description", ""),
        "author": feed.feed.get("author", ""),
        "link": feed.feed.get("link", ""),
        "episodes": []
    }

    print(f"✓ 播客: {podcast_info['title']}")
    print(f"  共 {len(feed.entries)} 期节目")

    for entry in feed.entries:
        # 获取音频链接
        audio_url = None
        for link in entry.get("links", []):
            if link.get("type", "").startswith("audio/"):
                audio_url = link.get("href")
                break

        # 如果没在 links 里找到，尝试 enclosures
        if not audio_url:
            for enclosure in entry.get("enclosures", []):
                if enclosure.get("type", "").startswith("audio/"):
                    audio_url = enclosure.get("href")
                    break

        episode = {
            "title": entry.get("title", "未知标题"),
            "description": entry.get("description", entry.get("summary", "")),
            "published": entry.get("published", ""),
            "audio_url": audio_url,
            "duration": entry.get("itunes_duration", ""),
        }
        podcast_info["episodes"].append(episode)

    # 保存元数据
    metadata_path = OUTPUT_DIR / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(podcast_info, f, ensure_ascii=False, indent=2)
    print(f"✓ 元数据已保存: {metadata_path}")

    return podcast_info


def sanitize_filename(name):
    """清理文件名，移除不合法字符"""
    # 移除或替换不合法字符
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip()
    # 限制长度
    if len(name) > 100:
        name = name[:100]
    return name


def download_audio(episode, index):
    """下载单个音频文件"""
    if not episode["audio_url"]:
        print(f"  ⚠ 第 {index} 期没有音频链接，跳过")
        return None

    filename = f"{index:03d}_{sanitize_filename(episode['title'])}.mp3"
    filepath = AUDIO_DIR / filename

    if filepath.exists():
        print(f"  ✓ 已存在，跳过: {filename}")
        return filepath

    print(f"  ↓ 下载中: {episode['title'][:50]}...")

    try:
        response = requests.get(episode["audio_url"], stream=True, timeout=60)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  ✓ 下载完成: {filename}")
        return filepath

    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        return None


def download_all_audio(podcast_info):
    """下载所有音频"""
    print("\n开始下载音频文件...")

    audio_files = []
    for i, episode in enumerate(podcast_info["episodes"], 1):
        filepath = download_audio(episode, i)
        audio_files.append({
            "episode": episode,
            "index": i,
            "audio_path": filepath
        })

    return audio_files


def transcribe_audio(audio_path, episode_info, index):
    """使用 Whisper 转录单个音频"""
    import whisper

    transcript_filename = f"{index:03d}_{sanitize_filename(episode_info['title'])}.txt"
    transcript_path = TRANSCRIPT_DIR / transcript_filename

    if transcript_path.exists():
        print(f"  ✓ 已存在，跳过: {transcript_filename}")
        return transcript_path

    print(f"  🎙 转录中: {episode_info['title'][:50]}...")

    try:
        # 加载模型（首次会自动下载）
        model = whisper.load_model(WHISPER_MODEL)

        # 转录
        result = model.transcribe(
            str(audio_path),
            language="zh",  # 指定中文
            verbose=False
        )

        # 保存转录结果
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"标题: {episode_info['title']}\n")
            f.write(f"发布日期: {episode_info['published']}\n")
            f.write(f"时长: {episode_info['duration']}\n")
            f.write("=" * 50 + "\n\n")
            f.write(result["text"])

        print(f"  ✓ 转录完成: {transcript_filename}")
        return transcript_path

    except Exception as e:
        print(f"  ✗ 转录失败: {e}")
        return None


def transcribe_all(audio_files):
    """转录所有音频"""
    print("\n开始转录音频...")
    print(f"使用 Whisper 模型: {WHISPER_MODEL}")
    print("（首次运行会自动下载模型，请耐心等待）\n")

    for item in audio_files:
        if item["audio_path"]:
            transcribe_audio(
                item["audio_path"],
                item["episode"],
                item["index"]
            )


def generate_summary_doc(podcast_info):
    """生成汇总文档"""
    summary_path = OUTPUT_DIR / "播客内容汇总.md"

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# {podcast_info['title']}\n\n")
        f.write(f"**简介**: {podcast_info['description'][:500]}...\n\n")
        f.write(f"**作者**: {podcast_info['author']}\n\n")
        f.write(f"---\n\n")
        f.write(f"## 剧集列表\n\n")

        for i, ep in enumerate(podcast_info["episodes"], 1):
            f.write(f"### {i}. {ep['title']}\n")
            f.write(f"- 发布日期: {ep['published']}\n")
            f.write(f"- 时长: {ep['duration']}\n")
            # 清理 HTML 标签
            desc = re.sub(r'<[^>]+>', '', ep['description'])
            if len(desc) > 300:
                desc = desc[:300] + "..."
            f.write(f"- 简介: {desc}\n\n")

    print(f"\n✓ 汇总文档已生成: {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="播客转录工具：从 RSS feed 抓取剧集并转录")
    parser.add_argument("--feed", default=RSS_FEED_URL, help="播客 RSS feed 地址")
    args = parser.parse_args()

    print("=" * 50)
    print("播客转录工具")
    print("=" * 50 + "\n")

    # 1. 设置目录
    setup_directories()

    # 2. 获取 RSS feed
    podcast_info = fetch_rss_feed(args.feed)

    # 3. 生成汇总文档（即使不下载也有用）
    generate_summary_doc(podcast_info)

    # 4. 询问是否继续下载和转录
    print("\n" + "-" * 50)
    print("接下来可以：")
    print("  1. 下载所有音频并转录（可能需要较长时间）")
    print("  2. 只查看元数据（已保存在 metadata.json）")
    print("-" * 50)

    choice = input("\n是否下载并转录所有音频？(y/n): ").strip().lower()

    if choice == 'y':
        # 5. 下载音频
        audio_files = download_all_audio(podcast_info)

        # 6. 转录
        transcribe_all(audio_files)

        print("\n" + "=" * 50)
        print("✓ 全部完成！")
        print(f"  - 元数据: {OUTPUT_DIR / 'metadata.json'}")
        print(f"  - 音频文件: {AUDIO_DIR}")
        print(f"  - 转录文本: {TRANSCRIPT_DIR}")
        print(f"  - 汇总文档: {OUTPUT_DIR / '播客内容汇总.md'}")
        print("=" * 50)
    else:
        print("\n已跳过下载和转录。")
        print(f"元数据和汇总文档已保存在: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

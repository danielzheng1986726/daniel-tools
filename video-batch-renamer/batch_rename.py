#!/usr/bin/env python3
"""
批量给 MP4 视频文件名加上时长后缀，如 my_video_2m8s.mp4。

默认是 DRY_RUN：只打印「会改成什么样」，不真的重命名。
确认清单没问题后加 --apply 才会真正执行。

用法：
    python3 batch_rename.py --dir /path/to/videos --prefix "my_video_"
    python3 batch_rename.py --dir /path/to/videos --prefix "my_video_" --apply
"""

import argparse
import os
import subprocess


def get_duration(filepath):
    """用 ffprobe 获取视频时长（秒）"""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", filepath
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        seconds = float(result.stdout.strip())
        return int(seconds)
    except Exception:
        return None


def format_duration(seconds):
    """格式化时长为 8s 或 2m8s"""
    if seconds < 60:
        return f"{seconds}s"
    else:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m{s}s" if s else f"{m}m"


def batch_rename(video_dir, prefix, apply):
    if not os.path.isdir(video_dir):
        print(f"目录不存在: {video_dir}")
        return

    planned = []
    for filename in sorted(os.listdir(video_dir)):
        if not filename.lower().endswith(".mp4"):
            continue
        filepath = os.path.join(video_dir, filename)
        seconds = get_duration(filepath)
        if seconds is None:
            print(f"无法获取 {filename} 的时长，跳过。")
            continue
        duration_str = format_duration(seconds)
        new_name = f"{prefix}{duration_str}.mp4"
        new_path = os.path.join(video_dir, new_name)
        if os.path.exists(new_path):
            print(f"{new_name} 已存在，跳过。")
            continue
        planned.append((filepath, new_path, filename, new_name))

    if not planned:
        print("没有可重命名的 .mp4 文件。")
        return

    print(f"计划重命名 {len(planned)} 个文件：")
    for _, _, old_name, new_name in planned:
        print(f"  {old_name} -> {new_name}")

    if not apply:
        print("\n当前是 DRY_RUN 模式，以上重命名没有真的执行。确认无误后加 --apply 重新运行。")
        return

    for filepath, new_path, old_name, new_name in planned:
        os.rename(filepath, new_path)
        print(f"{old_name} -> {new_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量给 MP4 文件名加上时长后缀")
    parser.add_argument("--dir", required=True, help="视频所在文件夹")
    parser.add_argument("--prefix", default="video_", help="文件名前缀，默认 video_")
    parser.add_argument("--apply", action="store_true", help="真正执行重命名；不加则只打印计划")
    args = parser.parse_args()

    batch_rename(args.dir, args.prefix, args.apply)

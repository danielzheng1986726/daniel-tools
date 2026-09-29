#!/usr/bin/env python3
"""
video_assembler.py — AI Agent 驱动的自动视频剪辑工具

接受 JSON 配置文件，调用 FFmpeg 自动拼接视频片段，添加转场、背景音乐和字幕。

用法：
    python video_assembler.py config.json
    python video_assembler.py config.json --dry-run   # 只打印命令不执行
"""

import json
import subprocess
import sys
import os
from pathlib import Path


def get_video_duration(path: str) -> float:
    """用 ffprobe 获取视频时长"""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def build_ffmpeg_command(config: dict) -> list[str]:
    """根据 JSON 配置生成 FFmpeg 命令"""

    clips = config["clips"]
    output = config["output"]
    transition_duration = config.get("transition_duration", 0.5)
    transition_type = config.get("transition_type", "fade")
    resolution = config.get("resolution", "720x1280")
    w, h = resolution.split("x")

    # 获取每个片段时长
    durations = []
    for clip in clips:
        dur = clip.get("duration") or get_video_duration(clip["path"])
        durations.append(dur)

    # === 构建输入 ===
    inputs = []
    for clip in clips:
        inputs.extend(["-i", clip["path"]])

    # 背景音乐输入
    bgm = config.get("audio")
    if bgm:
        inputs.extend(["-i", bgm["path"]])
    bgm_input_idx = len(clips)

    # === 构建 filter_complex ===
    filters = []
    n = len(clips)

    # 统一分辨率和帧率
    for i in range(n):
        filters.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{i}]"
        )

    if n == 1:
        # 单片段，无需转场
        video_out = "v0"
    else:
        # 逐段 xfade 转场
        td = transition_duration
        prev = "v0"
        for i in range(1, n):
            # 计算 offset：前面所有片段时长之和 - 已有转场时长 - 当前转场时长
            offset = sum(durations[:i]) - td * i
            if offset < 0:
                offset = 0
            out_label = f"xf{i}"
            t = clips[i].get("transition", transition_type)
            filters.append(
                f"[{prev}][v{i}]xfade=transition={t}:duration={td}:offset={offset:.3f}[{out_label}]"
            )
            prev = out_label
        video_out = prev

    # 字幕
    subtitles = config.get("subtitles")
    if subtitles:
        sub_file = subtitles["path"].replace("\\", "/").replace(":", "\\:")
        font = subtitles.get("font", "Heiti SC")
        size = subtitles.get("size", 28)
        color = subtitles.get("color", "&Hffffff")
        filters.append(
            f"[{video_out}]subtitles={sub_file}:"
            f"force_style='FontName={font},FontSize={size},PrimaryColour={color},"
            f"Outline=2,Shadow=1,MarginV=30'[vsub]"
        )
        video_out = "vsub"

    # 文字叠加（片尾标题等）
    text_overlays = config.get("text_overlays", [])
    for idx, overlay in enumerate(text_overlays):
        text = overlay["text"]
        start = overlay.get("start", 0)
        end = overlay.get("end", 3)
        font_size = overlay.get("font_size", 48)
        font_color = overlay.get("font_color", "white")
        position = overlay.get("position", "center")
        font = overlay.get("font", "/System/Library/Fonts/STHeiti Medium.ttc")

        if position == "center":
            x, y = "(w-text_w)/2", "(h-text_h)/2"
        elif position == "bottom":
            x, y = "(w-text_w)/2", "h-text_h-60"
        elif position == "top":
            x, y = "(w-text_w)/2", "60"
        else:
            x, y = position.split(",")

        out_label = f"vtxt{idx}"
        filters.append(
            f"[{video_out}]drawtext="
            f"fontfile='{font}':"
            f"text='{text}':"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}:"
            f"x={x}:y={y}:"
            f"enable='between(t,{start},{end})':"
            f"borderw=2:bordercolor=black@0.6"
            f"[{out_label}]"
        )
        video_out = out_label

    # 音频处理
    audio_filters = []
    if bgm:
        vol = bgm.get("volume", 0.3)
        fade_in = bgm.get("fade_in", 2)
        fade_out = bgm.get("fade_out", 3)

        # 总视频时长
        total_dur = sum(durations) - transition_duration * max(0, n - 1)
        fade_out_start = max(0, total_dur - fade_out)

        audio_filters.append(
            f"[{bgm_input_idx}:a]"
            f"afade=t=in:d={fade_in},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out},"
            f"volume={vol},"
            f"atrim=0:{total_dur:.3f}"
            f"[bgm]"
        )
        audio_out = "bgm"
    else:
        audio_out = None

    # 组合 filter_complex
    filter_complex = ";".join(filters)
    if audio_filters:
        filter_complex += ";" + ";".join(audio_filters)

    # === 构建完整命令 ===
    cmd = ["ffmpeg", "-y"]
    cmd.extend(inputs)
    cmd.extend(["-filter_complex", filter_complex])
    cmd.extend(["-map", f"[{video_out}]"])

    if audio_out:
        cmd.extend(["-map", f"[{audio_out}]"])
    else:
        cmd.extend(["-an"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
    ])

    if audio_out:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.append(output)
    return cmd


def main():
    if len(sys.argv) < 2:
        print("用法: python video_assembler.py config.json [--dry-run]")
        sys.exit(1)

    config_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    with open(config_path) as f:
        config = json.load(f)

    # 验证输入文件存在
    for clip in config["clips"]:
        if not Path(clip["path"]).exists():
            print(f"错误: 视频文件不存在: {clip['path']}")
            sys.exit(1)

    if config.get("audio") and not Path(config["audio"]["path"]).exists():
        print(f"错误: 音频文件不存在: {config['audio']['path']}")
        sys.exit(1)

    cmd = build_ffmpeg_command(config)

    if dry_run:
        print("FFmpeg 命令 (dry-run):")
        print(" ".join(cmd))
    else:
        print(f"开始渲染: {config['output']}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"渲染完成: {config['output']}")
        else:
            print(f"渲染失败:")
            print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

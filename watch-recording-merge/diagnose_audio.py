#!/usr/bin/env python3
"""
音频诊断工具 - 看看你的音频到底怎么了
"""

import subprocess
import sys
from pathlib import Path

# 安装依赖
try:
    from pydub import AudioSegment
    import numpy as np
except ImportError:
    print("安装依赖...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pydub", "numpy"])
    from pydub import AudioSegment
    import numpy as np

def diagnose_audio(file_path):
    """诊断音频文件"""
    print(f"🔍 诊断音频: {file_path}\n")
    
    # 加载音频
    audio = AudioSegment.from_file(file_path)
    
    # 基本信息
    duration = len(audio) / 1000  # 秒
    print(f"时长: {duration:.1f} 秒 ({duration/60:.1f} 分钟)")
    print(f"采样率: {audio.frame_rate} Hz")
    print(f"声道数: {audio.channels}")
    print(f"位深: {audio.sample_width * 8} bit\n")
    
    # 分析每30秒的音量
    print("📊 音量分析（每30秒）：")
    print("-" * 50)
    
    chunk_duration = 30000  # 30秒
    for i in range(0, len(audio), chunk_duration):
        chunk = audio[i:i+chunk_duration]
        
        # 计算RMS（音量）
        rms = chunk.rms
        max_possible = chunk.max_possible_amplitude
        volume_percent = (rms / max_possible) * 100 if max_possible > 0 else 0
        
        # 计算动态范围（判断是否是单调噪音）
        samples = np.array(chunk.get_array_of_samples())
        if len(samples) > 0:
            dynamic_range = np.std(samples)
        else:
            dynamic_range = 0
        
        start_time = i / 1000
        end_time = min((i + chunk_duration) / 1000, duration)
        
        # 判断内容类型
        if volume_percent < 1:
            content = "🔇 静音"
        elif volume_percent < 5 and dynamic_range < 100:
            content = "🎵 极低噪音"
        elif dynamic_range < 500:
            content = "📢 单调噪音（可能是风扇/摩擦声）"
        elif volume_percent > 15:
            content = "🎤 可能有语音"
        else:
            content = "🔊 背景噪音"
        
        print(f"{start_time:6.1f}s - {end_time:6.1f}s: {content} (音量:{volume_percent:4.1f}%)")
    
    print("-" * 50)
    
    # 检测实际有内容的部分
    from pydub.silence import detect_nonsilent
    
    print("\n🎯 检测可能的语音段：")
    nonsilent = detect_nonsilent(audio, 
                                 min_silence_len=2000,
                                 silence_thresh=-40,
                                 seek_step=100)
    
    if nonsilent:
        print(f"找到 {len(nonsilent)} 个非静音段：")
        for i, (start, end) in enumerate(nonsilent[:10], 1):  # 只显示前10个
            print(f"  {i}. {start/1000:.1f}s - {end/1000:.1f}s ({(end-start)/1000:.1f}秒)")
        
        if len(nonsilent) > 10:
            print(f"  ... 还有 {len(nonsilent)-10} 个片段")
    else:
        print("⚠️ 没有检测到明显的语音内容！")
    
    return nonsilent

# 运行诊断
if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = input("请输入音频文件路径: ").strip()
    
    diagnose_audio(file_path)

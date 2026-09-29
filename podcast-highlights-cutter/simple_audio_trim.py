import librosa
import soundfile as sf
import numpy as np
import json
import os
from datetime import timedelta

def load_audio(file_path):
    """加载音频文件"""
    print(f"正在加载音频文件 {file_path}...")
    try:
        y, sr = librosa.load(file_path, sr=None)  # 保持原始采样率
        duration = librosa.get_duration(y=y, sr=sr)
        print(f"音频加载成功，时长: {timedelta(seconds=duration)}")
        return y, sr, duration
    except Exception as e:
        print(f"加载音频时出错: {str(e)}")
        raise

def trim_audio(y, sr, start_time, end_time):
    """截取音频的指定部分"""
    start_sample = int(start_time * sr)
    end_sample = int(end_time * sr)
    
    # 确保索引不超出范围
    if end_sample > len(y):
        end_sample = len(y)
    
    if start_sample >= len(y):
        raise ValueError(f"起始时间 {start_time} 秒超出了音频长度")
    
    return y[start_sample:end_sample]

def select_highlights(duration, target_duration=120):
    """选择最有价值的时间段
    
    由于没有转写内容，我们将简单地选择音频的中间部分
    以此作为示例，实际应用中可以根据需要修改
    """
    if duration <= target_duration:
        # 如果音频长度不超过目标长度，返回整个音频
        return [(0, duration)]
    
    # 选择中间部分
    middle = duration / 2
    half_target = target_duration / 2
    start = middle - half_target
    end = middle + half_target
    
    # 确保不超出范围
    if start < 0:
        start = 0
        end = target_duration
    elif end > duration:
        end = duration
        start = duration - target_duration
    
    return [(start, end)]

def main():
    input_file = "output.mp3"
    output_file = "highlight.wav"
    target_duration = 120  # 2分钟
    
    # 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"错误：找不到文件 {input_file}")
        return
    
    try:
        # 加载音频
        y, sr, duration = load_audio(input_file)
        
        # 选择片段
        highlights = select_highlights(duration, target_duration)
        
        # 剪辑音频
        print("正在剪辑音频...")
        output = np.array([])
        
        for start, end in highlights:
            print(f"剪辑时间段: {timedelta(seconds=start)} - {timedelta(seconds=end)}")
            chunk = trim_audio(y, sr, start, end)
            output = np.concatenate((output, chunk)) if len(output) > 0 else chunk
        
        # 检查剪辑后的长度
        output_duration = len(output) / sr
        print(f"剪辑后音频长度: {timedelta(seconds=output_duration)}")
        
        # 导出剪辑后的音频
        print(f"正在保存到 {output_file}...")
        sf.write(output_file, output, sr)
        print(f"精华片段已保存为 {output_file}")
        
    except Exception as e:
        print(f"处理过程中出现错误：{str(e)}")

if __name__ == "__main__":
    main() 
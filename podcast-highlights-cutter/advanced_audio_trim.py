import librosa
import soundfile as sf
import numpy as np
import os
import argparse
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

def select_highlights(duration, strategy, target_duration=120):
    """根据不同策略选择音频的重要部分
    
    策略:
    - 'beginning': 选择开始的2分钟
    - 'middle': 选择中间的2分钟
    - 'end': 选择结束的2分钟
    - 'mix': 选择开始、中间和结束的片段
    """
    if duration <= target_duration:
        # 如果音频长度不超过目标长度，返回整个音频
        return [(0, duration)]
    
    if strategy == 'beginning':
        # 选择开始的部分
        return [(0, target_duration)]
    
    elif strategy == 'middle':
        # 选择中间部分
        middle = duration / 2
        half_target = target_duration / 2
        start = middle - half_target
        end = middle + half_target
        return [(start, end)]
    
    elif strategy == 'end':
        # 选择结束部分
        return [(duration - target_duration, duration)]
    
    elif strategy == 'mix':
        # 混合策略：开始、中间和结束各取一部分
        segment_duration = target_duration / 3
        
        # 开始部分
        start_segment = (0, segment_duration)
        
        # 中间部分
        middle = duration / 2
        half_segment = segment_duration / 2
        middle_segment = (middle - half_segment, middle + half_segment)
        
        # 结束部分
        end_segment = (duration - segment_duration, duration)
        
        return [start_segment, middle_segment, end_segment]
    
    else:
        # 默认选择中间部分
        print(f"未知策略 '{strategy}'，使用默认的 'middle' 策略")
        middle = duration / 2
        half_target = target_duration / 2
        start = middle - half_target
        end = middle + half_target
        return [(start, end)]

def save_audio(output, sr, output_file):
    """保存音频文件"""
    print(f"正在保存到 {output_file}...")
    sf.write(output_file, output, sr)
    print(f"音频已保存为 {output_file}")
    
    # 计算时长
    duration = len(output) / sr
    print(f"输出音频时长: {timedelta(seconds=duration)}")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='音频剪辑工具')
    parser.add_argument('--input', default='output.mp3', help='输入音频文件路径')
    parser.add_argument('--output', default='highlight.wav', help='输出音频文件路径')
    parser.add_argument('--duration', type=int, default=120, help='目标时长（秒）')
    parser.add_argument('--strategy', choices=['beginning', 'middle', 'end', 'mix'], 
                        default='middle', help='选择策略')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.input):
        print(f"错误：找不到文件 {args.input}")
        return
    
    try:
        # 加载音频
        y, sr, duration = load_audio(args.input)
        
        # 选择片段
        print(f"使用 '{args.strategy}' 策略选择片段...")
        highlights = select_highlights(duration, args.strategy, args.duration)
        
        # 剪辑音频
        print("正在剪辑音频...")
        output = np.array([])
        
        for i, (start, end) in enumerate(highlights):
            print(f"片段 {i+1}: {timedelta(seconds=start)} - {timedelta(seconds=end)}")
            chunk = trim_audio(y, sr, start, end)
            output = np.concatenate((output, chunk)) if len(output) > 0 else chunk
        
        # 保存音频
        save_audio(output, sr, args.output)
        
    except Exception as e:
        print(f"处理过程中出现错误：{str(e)}")

if __name__ == "__main__":
    main() 
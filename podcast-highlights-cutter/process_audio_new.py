import librosa
import soundfile as sf
import numpy as np
import json
import os
import whisper
from datetime import timedelta

def transcribe_audio(audio_path):
    """使用 Whisper 转写音频"""
    print("正在加载 Whisper 模型...")
    model = whisper.load_model("base")
    
    print("开始转写音频...")
    result = model.transcribe(audio_path)
    
    # 保存转写结果
    with open("transcription.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result

def select_segments(transcription, target_duration=120):
    """从转写结果中选择最佳片段"""
    segments = transcription["segments"]
    
    # 按照时间顺序排序片段
    sorted_segments = sorted(segments, key=lambda x: x["start"])
    
    # 寻找最佳的连续片段组合
    best_segments = []
    current_duration = 0
    
    for segment in sorted_segments:
        segment_duration = segment["end"] - segment["start"]
        if current_duration + segment_duration <= target_duration:
            best_segments.append(segment)
            current_duration += segment_duration
        
        if current_duration >= target_duration:
            break
    
    # 打印选择的片段及总时长
    total_duration = sum(segment["end"] - segment["start"] for segment in best_segments)
    print(f"已选择 {len(best_segments)} 个片段，总时长: {timedelta(seconds=total_duration)}")
    
    # 打印选择的文本内容
    for i, segment in enumerate(best_segments):
        print(f"片段 {i+1}: {segment['text']}")
    
    return best_segments

def cut_audio(audio_path, segments):
    """根据选定的片段剪辑音频"""
    print("正在加载音频文件...")
    y, sr = librosa.load(audio_path, sr=None)  # 保持原始采样率
    
    print("正在剪辑音频...")
    output = np.array([])
    
    for segment in segments:
        start_sample = int(segment["start"] * sr)
        end_sample = int(segment["end"] * sr)
        
        # 确保索引不超出范围
        if end_sample > len(y):
            end_sample = len(y)
        
        if start_sample < len(y):
            chunk = y[start_sample:end_sample]
            output = np.concatenate((output, chunk)) if len(output) > 0 else chunk
    
    # 导出剪辑后的音频
    print("正在保存精华片段...")
    sf.write("highlight.wav", output, sr)
    print("精华片段已保存为 highlight.wav")

def main():
    input_file = "output.mp3"
    
    # 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"错误：找不到文件 {input_file}")
        return
    
    try:
        # 转写音频
        transcription = transcribe_audio(input_file)
        
        # 选择片段
        selected_segments = select_segments(transcription)
        
        # 保存选定片段的信息
        with open("selected_segments.json", "w", encoding="utf-8") as f:
            json.dump(selected_segments, f, ensure_ascii=False, indent=2)
        
        # 剪辑音频
        cut_audio(input_file, selected_segments)
        
    except Exception as e:
        print(f"处理过程中出现错误：{str(e)}")

if __name__ == "__main__":
    main() 
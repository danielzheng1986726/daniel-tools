import whisper
import ffmpeg
import json
import os
import numpy as np
from pydub import AudioSegment

def load_audio(file_path):
    """使用 ffmpeg-python 加载音频"""
    try:
        out, _ = (
            ffmpeg.input(file_path)
            .output('pipe:', format='wav', acodec='pcm_s16le', ac=1, ar=16000)
            .run(capture_stdout=True, capture_stderr=True)
        )
        return np.frombuffer(out, np.int16).astype(np.float32) / 32768.0
    except ffmpeg.Error as e:
        print('Error:', e.stderr.decode())
        raise

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
    
    return best_segments

def cut_audio(audio_path, segments):
    """根据选定的片段剪辑音频"""
    print("正在加载音频文件...")
    audio = AudioSegment.from_mp3(audio_path)
    
    print("正在剪辑音频...")
    output = AudioSegment.empty()
    
    for segment in segments:
        start_ms = int(segment["start"] * 1000)
        end_ms = int(segment["end"] * 1000)
        chunk = audio[start_ms:end_ms]
        output += chunk
    
    # 导出剪辑后的音频
    output.export("highlight.mp3", format="mp3")
    print("精华片段已保存为 highlight.mp3")

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
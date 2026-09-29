#!/usr/bin/env python3
"""
Apple Watch 录音智能拼接工具 v2.2
修复：确保进度显示在所有终端都能工作
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple

def install_requirements():
    """安装依赖"""
    print("正在检查依赖库...")
    required = ['pydub', 'openai-whisper', 'numpy', 'torch']
    
    import subprocess
    for package in required:
        try:
            if package == 'openai-whisper':
                __import__('whisper')
            else:
                __import__(package)
        except ImportError:
            print(f"正在安装 {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_requirements()

import whisper
from pydub import AudioSegment
import numpy as np

class WhisperDrivenMerger:
    def __init__(self, model_size="base", language="zh"):
        """初始化"""
        print(f"\n{'='*60}")
        print(f"🤖 正在加载 Whisper {model_size} 模型...")
        print(f"{'='*60}")
        
        start_time = time.time()
        self.model = whisper.load_model(model_size)
        load_time = time.time() - start_time
        
        print(f"✅ 模型加载完成 (耗时 {load_time:.1f} 秒)\n")
        
        self.language = language
        self.min_speech_duration = 1.0
        self.merge_gap = 2.0
        self.padding = 0.5
        
    def show_progress_bar(self, current, total, prefix='进度', suffix='', length=40):
        """显示简单进度条"""
        percent = current / total if total > 0 else 0
        filled = int(length * percent)
        bar = '█' * filled + '░' * (length - filled)
        
        # 计算剩余时间
        if hasattr(self, '_progress_start_time'):
            elapsed = time.time() - self._progress_start_time
            if current > 0:
                total_time = elapsed * total / current
                remaining = total_time - elapsed
                time_str = f" | 剩余: {int(remaining)}秒"
            else:
                time_str = ""
        else:
            self._progress_start_time = time.time()
            time_str = ""
        
        print(f'\r{prefix}: [{bar}] {percent*100:.1f}%{time_str} {suffix}', end='', flush=True)
        
        if current >= total:
            print()  # 完成后换行
            
    def analyze_with_whisper(self, audio_file: Path, file_index: int, total_files: int) -> Tuple[AudioSegment, List[dict]]:
        """使用Whisper分析音频"""
        print(f"\n{'─'*60}")
        print(f"📁 处理文件 [{file_index}/{total_files}]: {audio_file.name}")
        print(f"{'─'*60}")
        
        # 加载音频
        print("⏳ 加载音频文件...")
        audio = AudioSegment.from_file(audio_file)
        duration_sec = len(audio) / 1000
        duration_min = duration_sec / 60
        print(f"   ✓ 时长: {duration_min:.1f} 分钟 ({duration_sec:.0f} 秒)")
        
        # 临时文件
        temp_file = Path("temp_audio.wav")
        print("⏳ 导出临时文件...")
        audio.export(temp_file, format="wav")
        print("   ✓ 临时文件已创建")
        
        # Whisper转写
        print(f"🎯 开始Whisper转写 (语言: {self.language or '自动检测'})...")
        
        # 估算时间（base模型约为音频时长的1/10）
        estimated_time = duration_sec / 10
        print(f"   预计需要: {estimated_time:.0f} 秒")
        
        # 开始转写
        start_time = time.time()
        print("   转写中", end="")
        
        # 创建一个简单的动画效果
        def show_processing():
            symbols = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            i = 0
            while not hasattr(self, '_transcribe_done'):
                print(f'\r   转写中 {symbols[i % len(symbols)]}', end='', flush=True)
                time.sleep(0.1)
                i += 1
        
        # 启动动画（简化版，不用线程）
        result = self.model.transcribe(
            str(temp_file),
            language=self.language,
            word_timestamps=True,
            verbose=False,
            fp16=False
        )
        
        process_time = time.time() - start_time
        speed_ratio = duration_sec / process_time if process_time > 0 else 0
        
        print(f"\r   ✓ 转写完成！(耗时: {process_time:.1f}秒, 速度: {speed_ratio:.1f}x)")
        
        # 清理
        temp_file.unlink()
        
        # 提取有效片段
        print("⏳ 分析转写结果...")
        valid_segments = []
        
        for segment in result['segments']:
            text = segment['text'].strip()
            if self._is_meaningful(text):
                valid_segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': text
                })
        
        # 合并相近片段
        merged_segments = self._merge_close_segments(valid_segments)
        print(f"   ✓ 找到 {len(merged_segments)} 个有效片段")
        
        return audio, merged_segments
    
    def _is_meaningful(self, text: str) -> bool:
        """判断文本是否有意义"""
        if not text:
            return False
            
        # 清理文本
        clean_text = text.replace(' ', '').replace('，', '').replace('。', '')
        if len(clean_text) < 2:
            return False
        
        # 过滤纯语气词
        meaningless = ['嗯', '啊', '呃', '哦', '哎', 'uh', 'um', 'ah']
        if text.lower().strip() in meaningless:
            return False
        
        # 检查重复字符
        if len(set(clean_text)) == 1:
            return False
        
        # 检查是否有实质内容
        import re
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        has_english = bool(re.search(r'\b[a-zA-Z]{2,}\b', text))
        
        return has_chinese or has_english
    
    def _merge_close_segments(self, segments: List[dict]) -> List[dict]:
        """合并相近片段"""
        if not segments:
            return []
        
        merged = []
        current = segments[0].copy()
        
        for segment in segments[1:]:
            if segment['start'] - current['end'] < self.merge_gap:
                current['end'] = segment['end']
                current['text'] += ' ' + segment['text']
            else:
                merged.append(current)
                current = segment.copy()
        
        merged.append(current)
        return merged
    
    def extract_segments(self, audio: AudioSegment, segments: List[dict]) -> List[AudioSegment]:
        """提取音频片段"""
        extracted = []
        
        for seg in segments:
            start_ms = max(0, int((seg['start'] - self.padding) * 1000))
            end_ms = min(len(audio), int((seg['end'] + self.padding) * 1000))
            
            if end_ms - start_ms > self.min_speech_duration * 1000:
                extracted.append(audio[start_ms:end_ms])
        
        return extracted
    
    def process_folder(self, input_folder: str, output_file: str = None):
        """处理文件夹"""
        input_path = Path(input_folder)
        
        # 扫描文件
        print("\n🔍 扫描音频文件...")
        audio_files = []
        for ext in ['*.m4a', '*.mp3', '*.wav', '*.aac', '*.webm']:
            files = list(input_path.glob(ext))
            audio_files.extend(files)
            if files:
                print(f"   找到 {len(files)} 个 {ext[1:]} 文件")
        
        if not audio_files:
            print("❌ 没有找到音频文件")
            return
        
        # 排序
        audio_files.sort(key=lambda x: x.stat().st_mtime)
        
        # 显示文件列表
        print(f"\n{'='*60}")
        print(f"📊 待处理文件列表 (共 {len(audio_files)} 个)")
        print(f"{'='*60}")
        
        total_size = 0
        for i, file in enumerate(audio_files, 1):
            size_mb = file.stat().st_size / (1024 * 1024)
            total_size += size_mb
            mtime = datetime.fromtimestamp(file.stat().st_mtime).strftime("%H:%M:%S")
            
            # 截断长文件名
            name = file.name
            if len(name) > 35:
                name = name[:32] + "..."
            
            print(f"  {i:2d}. {name:<35} ({size_mb:6.1f} MB) [{mtime}]")
        
        print(f"{'─'*60}")
        print(f"  总计: {total_size:.1f} MB")
        print(f"{'='*60}")
        
        # 确认
        input("\n按回车键开始处理...")
        
        # 开始处理
        print(f"\n{'='*60}")
        print("🚀 开始处理音频文件")
        print(f"{'='*60}")
        
        all_audio_segments = []
        all_text_segments = []
        total_duration = 0
        valid_duration = 0
        
        overall_start = time.time()
        
        # 处理每个文件
        for i, audio_file in enumerate(audio_files, 1):
            # 显示总进度
            print(f"\n总进度: {i-1}/{len(audio_files)} 完成", end="")
            if i > 1:
                elapsed = time.time() - overall_start
                avg_time = elapsed / (i - 1)
                remaining = avg_time * (len(audio_files) - i + 1)
                print(f" | 预计剩余: {str(timedelta(seconds=int(remaining)))}", end="")
            print()
            
            # 处理文件
            audio, segments = self.analyze_with_whisper(audio_file, i, len(audio_files))
            total_duration += len(audio) / 1000
            
            if segments:
                extracted = self.extract_segments(audio, segments)
                all_audio_segments.extend(extracted)
                
                for seg in segments:
                    all_text_segments.append({
                        'file': audio_file.name,
                        'time': f"{seg['start']:.1f}-{seg['end']:.1f}",
                        'text': seg['text']
                    })
                    valid_duration += seg['end'] - seg['start']
        
        if not all_audio_segments:
            print("\n❌ 没有找到有意义的对话内容")
            return
        
        # 合并音频
        print(f"\n{'='*60}")
        print(f"🔧 合并音频片段 (共 {len(all_audio_segments)} 个)")
        print(f"{'='*60}")
        
        print("合并中", end="")
        merged = all_audio_segments[0]
        
        for j, segment in enumerate(all_audio_segments[1:], 1):
            if j % 10 == 0:
                print(".", end="", flush=True)
            silence = AudioSegment.silent(duration=500)
            merged = merged + silence + segment
        
        print(" ✓")
        
        # 生成输出文件名
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"merged_recording_{timestamp}.m4a"
        
        output_path = Path(output_file)
        
        # 导出
        print("\n💾 导出文件...")
        merged.export(output_path, format="mp4", codec="aac", bitrate="128k")
        print(f"   ✓ 音频: {output_path}")
        
        # 导出文本
        text_file = output_path.with_suffix('.txt')
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(f"录音转写记录\n")
            f.write(f"生成时间: {datetime.now()}\n")
            f.write("="*50 + "\n\n")
            
            for seg in all_text_segments:
                f.write(f"[{seg['file']} @ {seg['time']}s]\n")
                f.write(f"{seg['text']}\n\n")
        
        print(f"   ✓ 文本: {text_file}")
        
        # 统计
        total_time = time.time() - overall_start
        
        print(f"\n{'='*60}")
        print("✨ 处理完成！")
        print(f"{'='*60}")
        print(f"📊 统计信息:")
        print(f"   • 原始总时长: {total_duration/60:.1f} 分钟")
        print(f"   • 有效内容: {valid_duration/60:.1f} 分钟")
        print(f"   • 压缩率: {(1 - valid_duration/total_duration)*100:.1f}%")
        print(f"   • 处理耗时: {str(timedelta(seconds=int(total_time)))}")
        print(f"   • 找到片段: {len(all_text_segments)} 个")
        print(f"{'='*60}")

def main():
    # 标题
    os.system('clear' if os.name == 'posix' else 'cls')
    print("╔" + "═"*58 + "╗")
    print("║" + " "*18 + "🚀 Apple Watch 录音拼接 v2.2" + " "*11 + "║")
    print("║" + " "*15 + "使用 Whisper AI 智能识别有效内容" + " "*11 + "║")
    print("╚" + "═"*58 + "╝")
    
    # 选择模型
    print("\n🤖 选择 Whisper 模型:")
    print("  1. tiny   (39M)  - 最快，准确度较低")
    print("  2. base   (74M)  - 平衡选择 ⭐推荐")
    print("  3. small  (244M) - 较准确")
    print("  4. medium (769M) - 很准确")
    print("  5. large  (1.5G) - 最准确但很慢")
    
    choice = input("\n选择 (1-5) [默认: 2]: ").strip() or "2"
    model_map = {"1": "tiny", "2": "base", "3": "small", "4": "medium", "5": "large"}
    model_size = model_map.get(choice, "base")
    print(f"✓ 已选择: {model_size}")
    
    # 选择语言
    print("\n🌍 选择语言:")
    print("  1. 中文 ⭐推荐")
    print("  2. 英文")
    print("  3. 自动检测")
    
    lang_choice = input("\n选择 (1-3) [默认: 1]: ").strip() or "1"
    lang_map = {"1": "zh", "2": "en", "3": None}
    language = lang_map.get(lang_choice, "zh")
    print(f"✓ 已选择: {language or '自动检测'}")
    
    # 获取文件夹
    if len(sys.argv) > 1:
        input_folder = sys.argv[1]
    else:
        input_folder = input("\n📁 请输入录音文件夹路径: ").strip()
        input_folder = input_folder.replace('\\ ', ' ').strip()
    
    if not os.path.exists(input_folder):
        print(f"❌ 文件夹不存在: {input_folder}")
        return
    
    # 处理
    merger = WhisperDrivenMerger(model_size, language)
    merger.process_folder(input_folder)
    
    print("\n💡 使用提示:")
    print("  • 音频文件可用于进一步处理")
    print("  • 文本文件包含完整转写内容")
    print("  • 如需更高准确度，可尝试更大的模型")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
播客精彩集锦生成器
从播客音频中提取关键片段，创建精彩集锦
"""

import os
import sys
import json
import librosa
import numpy as np
import matplotlib.pyplot as plt
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_silence
import logging
import matplotlib as mpl

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置matplotlib使用不需要特定字体的配置
mpl.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
mpl.rcParams['axes.unicode_minus'] = False

class PodcastHighlightGenerator:
    """播客精彩集锦生成器"""
    
    def __init__(self, audio_path, target_duration=120, min_segment_duration=5, max_segment_duration=20):
        """
        初始化播客精彩集锦生成器
        
        参数:
            audio_path (str): 音频文件路径
            target_duration (int): 目标集锦时长(秒)
            min_segment_duration (int): 最小片段时长(秒)
            max_segment_duration (int): 最大片段时长(秒)
        """
        self.audio_path = audio_path
        self.target_duration = target_duration
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.audio = None
        self.sample_rate = None
        self.segments = []
        
    def load_audio(self):
        """加载音频文件"""
        logger.info(f"正在加载音频文件: {self.audio_path}")
        try:
            self.audio = AudioSegment.from_file(self.audio_path)
            logger.info(f"音频长度: {len(self.audio) / 1000:.2f}秒, 声道数: {self.audio.channels}, 采样率: {self.audio.frame_rate}Hz")
            return True
        except Exception as e:
            logger.error(f"加载音频文件失败: {e}")
            return False
    
    def analyze_audio(self):
        """分析音频，提取潜在的精彩片段"""
        logger.info("正在分析音频...")
        
        # 转换为单声道便于分析
        mono_audio = self.audio.set_channels(1)
        
        # 检测静音段落，用于找到句子边界
        logger.info("正在检测静音段落...")
        silence_ranges = detect_silence(
            mono_audio, 
            min_silence_len=500,  # 最小静音时长(毫秒)
            silence_thresh=-40    # 静音阈值(dB)
        )
        
        # 根据静音段落分割句子
        sentence_ranges = []
        start = 0
        
        for silence_start, silence_end in silence_ranges:
            # 只有当静音足够长时，才认为是句子的边界
            if silence_end - silence_start >= 300:  # 300毫秒以上的静音视为句子边界
                if silence_start - start >= self.min_segment_duration * 1000:
                    sentence_ranges.append((start, silence_start))
                start = silence_end
        
        # 添加最后一个句子
        if len(mono_audio) - start >= self.min_segment_duration * 1000:
            sentence_ranges.append((start, len(mono_audio)))
        
        logger.info(f"检测到 {len(sentence_ranges)} 个潜在句子")
        
        # 提取句子片段并计算特征
        sentences = []
        for i, (start, end) in enumerate(sentence_ranges):
            duration = (end - start) / 1000  # 转换为秒
            
            # 跳过过长或过短的句子
            if not (self.min_segment_duration <= duration <= self.max_segment_duration):
                continue
                
            # 提取句子音频
            sentence_audio = mono_audio[start:end]
            
            # 计算特征
            samples = np.array(sentence_audio.get_array_of_samples())
            
            # 1. 能量特征 - 音量变化
            energy = np.sum(samples.astype(np.float32)**2) / len(samples)
            energy_score = min(energy / 1e7, 10)  # 归一化能量分数
            
            # 2. 音高变化 - 使用样本标准差作为简单的音高变化指标
            pitch_variation = np.std(samples.astype(np.float32)) / 1000
            pitch_score = min(pitch_variation, 5)
            
            # 3. 时长得分 - 适中的时长更好
            duration_score = 0
            if 8 <= duration <= 15:  # 理想时长
                duration_score = 3
            elif 5 <= duration < 8 or 15 < duration <= 20:  # 次理想时长
                duration_score = 2
            else:
                duration_score = 1
                
            # 计算总分
            total_score = energy_score + pitch_score + duration_score
            
            sentences.append({
                'index': i,
                'start': start,
                'end': end,
                'start_time': self._format_time(start / 1000),
                'end_time': self._format_time(end / 1000),
                'duration': duration,
                'audio': sentence_audio,
                'energy_score': energy_score,
                'pitch_score': pitch_score,
                'duration_score': duration_score,
                'total_score': total_score
            })
            
            logger.debug(f"句子 {i}: 时长={duration:.2f}秒, 能量={energy_score:.2f}, 音高变化={pitch_score:.2f}, 总分={total_score:.2f}")
        
        logger.info(f"提取了 {len(sentences)} 个有效句子")
        
        # 按分数降序排序
        sentences.sort(key=lambda x: x['total_score'], reverse=True)
        
        # 选择最佳句子，同时考虑时间顺序
        selected_sentences = []
        total_duration = 0
        
        # 首先选择得分最高的前N个句子
        top_sentences = sentences[:min(len(sentences), int(self.target_duration / 10) + 5)]
        
        # 按原始顺序重新排序
        top_sentences.sort(key=lambda x: x['index'])
        
        # 选择句子，确保总时长不超过目标时长
        for sentence in top_sentences:
            if total_duration + sentence['duration'] <= self.target_duration:
                selected_sentences.append(sentence)
                total_duration += sentence['duration']
                logger.info(f"选择句子 {sentence['index']}: 时长={sentence['duration']:.2f}秒, 分数={sentence['total_score']:.2f}, 时间范围: {sentence['start_time']} - {sentence['end_time']}")
            
            if total_duration >= self.target_duration:
                break
                
        logger.info(f"已选择 {len(selected_sentences)} 个句子，总时长 {total_duration:.2f}秒")
        
        # 保存选定的句子
        self.segments = selected_sentences
    
    def _format_time(self, seconds):
        """将秒数格式化为时:分:秒格式"""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
        
    def generate_highlight(self, output_path):
        """生成精彩集锦"""
        if not self.segments:
            logger.error("没有可用的音频片段")
            return False
            
        logger.info(f"正在生成精彩集锦: {output_path}")
        
        # 创建用于过渡的短淡入淡出效果
        crossfade_duration = 300  # 毫秒
        
        # 组合所有选定的片段
        highlight = self.segments[0]['audio']
        
        # 添加剩余片段，带有交叉淡化
        for i in range(1, len(self.segments)):
            # 为了更平滑的过渡，对每个片段应用淡入淡出
            next_segment = self.segments[i]['audio']
            next_segment = next_segment.fade_in(100).fade_out(100)
            
            # 添加片段，使用交叉淡化
            highlight = highlight.append(next_segment, crossfade=crossfade_duration)
        
        # 确保时长符合要求
        if len(highlight) > self.target_duration * 1000:
            highlight = highlight[:self.target_duration * 1000]
            
        # 添加淡入淡出效果
        fade_duration = 1000  # 毫秒
        highlight = highlight.fade_in(fade_duration).fade_out(fade_duration)
        
        # 保存到文件
        try:
            highlight.export(output_path, format="wav")
            logger.info(f"精彩集锦已保存: {output_path}, 时长: {len(highlight) / 1000:.2f}秒")
            return True
        except Exception as e:
            logger.error(f"保存精彩集锦失败: {e}")
            return False
    
    def export_segments_info(self, output_path):
        """导出片段信息到JSON文件"""
        if not self.segments:
            logger.error("没有可用的片段信息")
            return False
            
        # 准备导出数据
        export_data = {
            "source_audio": self.audio_path,
            "total_duration": float(len(self.audio) / 1000),
            "highlight_duration": float(sum(segment['duration'] for segment in self.segments)),
            "segments": []
        }
        
        # 添加片段信息
        for segment in self.segments:
            segment_info = {
                "index": int(segment['index']),
                "start_time": segment['start_time'],
                "end_time": segment['end_time'],
                "duration": float(segment['duration']),
                "start_ms": int(segment['start']),
                "end_ms": int(segment['end']),
                "score": float(segment['total_score'])
            }
            export_data["segments"].append(segment_info)
            
        # 保存到文件
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            logger.info(f"片段信息已保存: {output_path}")
            return True
        except Exception as e:
            logger.error(f"保存片段信息失败: {e}")
            return False
    
    def visualize_waveform(self, output_path=None):
        """可视化音频波形和选定的片段"""
        if not self.audio or not self.segments:
            logger.error("没有可用的音频或片段")
            return
            
        logger.info("正在生成波形可视化...")
        
        # 将AudioSegment转换为numpy数组
        samples = np.array(self.audio.get_array_of_samples())
        
        # 创建图形
        plt.figure(figsize=(15, 6))
        
        # 绘制完整波形
        time = np.linspace(0, len(self.audio) / 1000, len(samples))
        plt.plot(time, samples, color='gray', alpha=0.5)
        
        # 高亮显示选定的片段
        for segment in self.segments:
            start_time = segment['start'] / 1000
            end_time = segment['end'] / 1000
            
            # 获取片段对应的样本索引
            start_idx = int(start_time * self.audio.frame_rate)
            end_idx = int(end_time * self.audio.frame_rate)
            
            # 确保索引在有效范围内
            start_idx = max(0, min(start_idx, len(samples) - 1))
            end_idx = max(0, min(end_idx, len(samples) - 1))
            
            # 高亮显示片段
            segment_time = np.linspace(start_time, end_time, end_idx - start_idx)
            if start_idx < end_idx and start_idx < len(samples) and end_idx <= len(samples):
                plt.plot(segment_time, samples[start_idx:end_idx], color='red', linewidth=1)
        
        # 设置图形属性
        plt.title('Podcast Audio Waveform and Highlights')
        plt.xlabel('Time (seconds)')
        plt.ylabel('Amplitude')
        plt.grid(True, alpha=0.3)
        
        # 保存或显示图形
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"波形图已保存: {output_path}")
        else:
            plt.show()
            
        plt.close()
            
    def process(self, output_path, visualize=False, export_info=False):
        """处理完整的精彩集锦生成流程"""
        if not self.load_audio():
            return False
            
        self.analyze_audio()
        success = self.generate_highlight(output_path)
        
        if success and visualize:
            viz_path = os.path.splitext(output_path)[0] + "_waveform.png"
            self.visualize_waveform(viz_path)
            
        if success and export_info:
            info_path = os.path.splitext(output_path)[0] + "_segments.json"
            self.export_segments_info(info_path)
            
        return success

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <音频文件路径> [输出文件路径]")
        return 1
        
    audio_path = sys.argv[1]
    if not os.path.exists(audio_path):
        print(f"错误: 找不到音频文件 '{audio_path}'")
        return 1
        
    # 设置默认输出文件路径
    output_path = sys.argv[2] if len(sys.argv) > 2 else "highlight.wav"
    
    # 创建生成器实例并处理音频
    generator = PodcastHighlightGenerator(audio_path)
    if generator.process(output_path, visualize=True, export_info=True):
        print(f"精彩集锦生成成功: {output_path}")
        return 0
    else:
        print("精彩集锦生成失败")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
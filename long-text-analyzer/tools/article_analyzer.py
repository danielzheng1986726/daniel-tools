#!/usr/bin/env python3

import argparse
import json
import sys
from typing import List, Optional, Dict, Any
from pathlib import Path

from llm_api import query_llm, create_llm_client

class ArticleAnalyzer:
    """文章分析器类，用于处理和分析文章内容"""
    
    def __init__(self, provider: str = "openai", model: Optional[str] = None, max_tokens_per_chunk: int = 4000):
        """
        初始化文章分析器
        
        Args:
            provider: LLM提供商，默认为"openai"
            model: 模型名称，默认为None（将使用提供商的默认模型）
            max_tokens_per_chunk: 每个分段的最大token数，默认4000
        """
        self.provider = provider
        self.model = model
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.client = create_llm_client(provider)
        self.conversation_history: List[Dict[str, str]] = []
        
    def _split_text(self, text: str) -> List[str]:
        """
        将长文本分割成合适的段落
        
        Args:
            text: 要分割的文本内容
            
        Returns:
            List[str]: 分割后的文本段落列表
        """
        # 首先按段落分割
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            # 粗略估计token数（中文每个字约2个token，英文每个单词约1.3个token）
            para_length = len(para) * 2  # 保守估计
            
            if current_length + para_length > self.max_tokens_per_chunk and current_chunk:
                # 当前段落加入会超出限制，先保存当前chunk
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_length = para_length
            else:
                # 当前段落可以加入
                current_chunk.append(para)
                current_length += para_length
        
        # 处理最后一个chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            
        return chunks
        
    def _merge_analysis_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        合并多个分析结果
        
        Args:
            results: 多个分段的分析结果列表
            
        Returns:
            Dict[str, Any]: 合并后的分析结果
        """
        merged = {
            "summary": "",
            "main_topics": [],
            "speakers_analysis": [],
            "background_info": [],
            "questions_and_discussions": [],
            "unique_insights": []
        }
        
        # 用于去重的集合
        topics_set = set()
        speakers_set = set()
        background_topics = set()
        questions_set = set()
        insights_set = set()
        
        for result in results:
            # 合并摘要
            if merged["summary"]:
                merged["summary"] += "\n" + result["summary"]
            else:
                merged["summary"] = result["summary"]
            
            # 合并主题（去重）
            for topic in result["main_topics"]:
                if topic not in topics_set:
                    topics_set.add(topic)
                    merged["main_topics"].append(topic)
            
            # 合并发言者分析（去重并合并关键点）
            for speaker in result["speakers_analysis"]:
                existing_speaker = None
                for s in merged["speakers_analysis"]:
                    if s["speaker"] == speaker["speaker"]:
                        existing_speaker = s
                        break
                
                if existing_speaker:
                    # 合并已存在发言者的关键点
                    existing_speaker["key_points"].extend(speaker["key_points"])
                    existing_speaker["logic_analysis"] += "\n" + speaker["logic_analysis"]
                else:
                    # 添加新发言者
                    merged["speakers_analysis"].append(speaker)
            
            # 合并背景信息（按话题合并）
            for info in result["background_info"]:
                if info["topic"] not in background_topics:
                    background_topics.add(info["topic"])
                    merged["background_info"].append(info)
                else:
                    # 找到已存在的话题并合并信息
                    for existing_info in merged["background_info"]:
                        if existing_info["topic"] == info["topic"]:
                            existing_info["explanation"] += "\n" + info["explanation"]
                            if info.get("source"):
                                if existing_info.get("source"):
                                    existing_info["source"] += "; " + info["source"]
                                else:
                                    existing_info["source"] = info["source"]
            
            # 合并问题讨论（去重）
            for question in result["questions_and_discussions"]:
                if question["question"] not in questions_set:
                    questions_set.add(question["question"])
                    merged["questions_and_discussions"].append(question)
            
            # 合并独特见解（去重）
            for insight in result["unique_insights"]:
                if insight["insight"] not in insights_set:
                    insights_set.add(insight["insight"])
                    merged["unique_insights"].append(insight)
        
        # 对合并后的结果进行去重和清理
        # 1. 去除重复的关键点
        for speaker in merged["speakers_analysis"]:
            speaker["key_points"] = list(dict.fromkeys(speaker["key_points"]))
        
        return merged
        
    def _create_analysis_prompt(self, text: str) -> str:
        """
        创建分析提示
        
        Args:
            text: 要分析的文本内容
            
        Returns:
            str: 分析提示
        """
        return f"""请分析以下文本，并以JSON格式返回分析结果。注意：
1. 必须返回严格的JSON格式
2. 不要添加任何JSON之外的文本
3. 所有字符串必须使用双引号
4. 确保所有JSON语法正确

请分析以下内容：

{text}

请按照以下JSON格式返回分析结果：

{{
    "summary": "对话的简要概述，突出关键信息",
    "main_topics": ["主要话题1", "主要话题2"],
    "speakers_analysis": [
        {{
            "speaker": "发言者标识（如需要则匿名化）",
            "role": "发言者的角色或背景（如有）",
            "key_points": ["关键点1", "关键点2"],
            "logic_analysis": "观点背后的逻辑分析",
            "authority_source": "专业权威性来源（如有）"
        }}
    ],
    "background_info": [
        {{
            "topic": "相关话题",
            "explanation": "背景信息说明",
            "source": "信息来源（如有）"
        }}
    ],
    "questions_and_discussions": [
        {{
            "question": "问题或争议点",
            "analysis": "深入思考和讨论",
            "assumptions": "潜在假设或动机分析"
        }}
    ],
    "unique_insights": [
        {{
            "insight": "独特见解",
            "value": "价值评估",
            "application": "适用场景",
            "innovation_point": "创新价值点"
        }}
    ]
}}"""

    def _validate_and_fix_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证并修复分析结果的数据结构
        
        Args:
            result: 原始分析结果
            
        Returns:
            Dict[str, Any]: 修复后的分析结果
        """
        template = {
            "summary": "",
            "main_topics": [],
            "speakers_analysis": [],
            "background_info": [],
            "questions_and_discussions": [],
            "unique_insights": []
        }
        
        fixed = template.copy()
        
        # 修复 summary
        if isinstance(result.get("summary"), str):
            fixed["summary"] = result["summary"]
            
        # 修复 main_topics
        if isinstance(result.get("main_topics"), list):
            fixed["main_topics"] = [str(topic) for topic in result["main_topics"] if isinstance(topic, (str, int, float))]
            
        # 修复 speakers_analysis
        if isinstance(result.get("speakers_analysis"), list):
            for speaker in result["speakers_analysis"]:
                if isinstance(speaker, dict):
                    fixed_speaker = {
                        "speaker": str(speaker.get("speaker", "")),
                        "role": str(speaker.get("role", "")),
                        "key_points": [],
                        "logic_analysis": str(speaker.get("logic_analysis", "")),
                        "authority_source": str(speaker.get("authority_source", ""))
                    }
                    if isinstance(speaker.get("key_points"), list):
                        fixed_speaker["key_points"] = [str(point) for point in speaker["key_points"] if isinstance(point, (str, int, float))]
                    fixed["speakers_analysis"].append(fixed_speaker)
                    
        # 修复 background_info
        if isinstance(result.get("background_info"), list):
            for info in result["background_info"]:
                if isinstance(info, dict):
                    fixed_info = {
                        "topic": str(info.get("topic", "")),
                        "explanation": str(info.get("explanation", "")),
                        "source": str(info.get("source", ""))
                    }
                    fixed["background_info"].append(fixed_info)
                elif isinstance(info, (str, int, float)):
                    # 处理旧格式
                    fixed_info = {
                        "topic": "背景信息",
                        "explanation": str(info),
                        "source": ""
                    }
                    fixed["background_info"].append(fixed_info)
                    
        # 修复 questions_and_discussions
        if isinstance(result.get("questions_and_discussions"), list):
            for qd in result["questions_and_discussions"]:
                if isinstance(qd, dict):
                    fixed_qd = {
                        "question": str(qd.get("question", "")),
                        "analysis": str(qd.get("analysis", "")),
                        "assumptions": str(qd.get("assumptions", ""))
                    }
                    fixed["questions_and_discussions"].append(fixed_qd)
                elif isinstance(qd, (str, int, float)):
                    # 处理旧格式
                    fixed_qd = {
                        "question": str(qd),
                        "analysis": "",
                        "assumptions": ""
                    }
                    fixed["questions_and_discussions"].append(fixed_qd)
                    
        # 修复 unique_insights
        if isinstance(result.get("unique_insights"), list):
            for insight in result["unique_insights"]:
                if isinstance(insight, dict):
                    fixed_insight = {
                        "insight": str(insight.get("insight", "")),
                        "value": str(insight.get("value", "")),
                        "application": str(insight.get("application", "")),
                        "innovation_point": str(insight.get("innovation_point", ""))
                    }
                    fixed["unique_insights"].append(fixed_insight)
                elif isinstance(insight, (str, int, float)):
                    # 处理旧格式
                    fixed_insight = {
                        "insight": str(insight),
                        "value": "",
                        "application": "",
                        "innovation_point": ""
                    }
                    fixed["unique_insights"].append(fixed_insight)
                    
        return fixed

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        分析文本内容
        
        Args:
            text: 要分析的文本内容
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        # 分割文本
        chunks = self._split_text(text)
        print(f"文本已分割为 {len(chunks)} 个部分进行分析...", file=sys.stderr)
        
        # 分析每个分段
        results = []
        for i, chunk in enumerate(chunks, 1):
            print(f"正在分析第 {i}/{len(chunks)} 部分...", file=sys.stderr)
            try:
                prompt = self._create_analysis_prompt(chunk)
                response = query_llm(
                    prompt=prompt,
                    client=self.client,
                    model=self.model,
                    provider=self.provider
                )
                
                if not response:
                    print(f"警告：第 {i} 部分未获得响应，尝试重试...", file=sys.stderr)
                    # 重试一次
                    response = query_llm(
                        prompt=prompt,
                        client=self.client,
                        model=self.model,
                        provider=self.provider
                    )
                    
                if not response:
                    raise Exception(f"未能获取到第 {i} 部分的LLM响应")
                    
                try:
                    result = json.loads(response)
                    # 验证和修复数据结构
                    fixed_result = self._validate_and_fix_result(result)
                    results.append(fixed_result)
                except json.JSONDecodeError as e:
                    print(f"警告：第 {i} 部分的LLM响应不是有效的JSON格式。尝试修复...", file=sys.stderr)
                    try:
                        # 1. 首先尝试找到最外层的花括号
                        start = response.find('{')
                        end = response.rfind('}') + 1
                        if start >= 0 and end > start:
                            # 2. 提取可能的JSON字符串
                            json_str = response[start:end]
                            # 3. 清理可能的格式问题
                            json_str = json_str.replace("'", '"')  # 替换单引号为双引号
                            json_str = json_str.replace('\n', '\\n')  # 处理换行符
                            json_str = json_str.replace('\r', '\\r')  # 处理回车符
                            # 4. 尝试解析
                            result = json.loads(json_str)
                            # 5. 验证和修复数据结构
                            fixed_result = self._validate_and_fix_result(result)
                            results.append(fixed_result)
                            print(f"成功修复第 {i} 部分的JSON格式", file=sys.stderr)
                        else:
                            raise Exception("无法从响应中提取JSON结构")
                    except Exception as e:
                        print(f"错误：无法解析第 {i} 部分的LLM响应：{e}", file=sys.stderr)
                        print(f"原始响应：{response}", file=sys.stderr)
                        # 6. 如果还是失败，尝试重新请求
                        print(f"尝试重新请求第 {i} 部分...", file=sys.stderr)
                        response = query_llm(
                            prompt=prompt,
                            client=self.client,
                            model=self.model,
                            provider=self.provider
                        )
                        if not response:
                            raise Exception(f"重试后仍未能获取到第 {i} 部分的有效响应")
                        try:
                            result = json.loads(response)
                            # 7. 验证和修复数据结构
                            fixed_result = self._validate_and_fix_result(result)
                            results.append(fixed_result)
                            print(f"重试成功：获取到第 {i} 部分的有效JSON响应", file=sys.stderr)
                        except json.JSONDecodeError:
                            raise Exception(f"重试后仍未能获取到有效的JSON格式响应")
            except Exception as e:
                print(f"错误：处理第 {i} 部分时出错：{str(e)}", file=sys.stderr)
                raise
        
        # 合并所有分析结果
        print("正在合并分析结果...", file=sys.stderr)
        return self._merge_analysis_results(results)
    
    def format_analysis_result(self, result: Dict[str, Any]) -> str:
        """
        格式化分析结果为易读的文本格式
        
        Args:
            result: 分析结果字典
            
        Returns:
            str: 格式化后的文本
        """
        output = []
        
        # 1. 概述
        output.append("📝 内容概述")
        output.append(result["summary"])
        output.append("\n主要话题：")
        for topic in result["main_topics"]:
            output.append(f"• {topic}")
            
        # 2. 发言者分析
        if result["speakers_analysis"]:
            output.append("\n👥 发言者分析")
            for speaker in result["speakers_analysis"]:
                output.append(f"\n{speaker['speaker']}")
                if speaker.get("role"):
                    output.append(f"角色背景：{speaker['role']}")
                output.append("\n关键观点：")
                for point in speaker["key_points"]:
                    output.append(f"• {point}")
                output.append("\n逻辑分析：")
                output.append(speaker["logic_analysis"])
                if speaker.get("authority_source"):
                    output.append(f"\n专业权威来源：{speaker['authority_source']}")
            
        # 3. 背景信息
        if result["background_info"]:
            output.append("\n🔍 背景信息补充")
            for info in result["background_info"]:
                output.append(f"\n【{info['topic']}】")
                output.append(info["explanation"])
                if info.get("source"):
                    output.append(f"来源：{info['source']}")
            
        # 4. 问题讨论
        if result["questions_and_discussions"]:
            output.append("\n💭 问题与讨论")
            for qd in result["questions_and_discussions"]:
                output.append(f"\nQ: {qd['question']}")
                output.append(f"A: {qd['analysis']}")
                if qd.get("assumptions"):
                    output.append(f"潜在假设/动机：{qd['assumptions']}")
            
        # 5. 独特见解
        if result["unique_insights"]:
            output.append("\n💡 独特见解")
            for insight in result["unique_insights"]:
                output.append(f"\n见解：{insight['insight']}")
                output.append(f"价值评估：{insight['value']}")
                output.append(f"适用场景：{insight['application']}")
                if insight.get("innovation_point"):
                    output.append(f"创新价值点：{insight['innovation_point']}")
            
        return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description='分析文章内容并生成结构化总结')
    parser.add_argument('--input', type=str, help='输入文件路径')
    parser.add_argument('--provider', type=str, default='openai', help='LLM提供商')
    parser.add_argument('--model', type=str, help='模型名称')
    parser.add_argument('--output', type=str, help='输出文件路径')
    parser.add_argument('--max-tokens', type=int, default=4000, help='每个分段的最大token数')
    args = parser.parse_args()
    
    # 创建分析器实例
    analyzer = ArticleAnalyzer(
        provider=args.provider,
        model=args.model,
        max_tokens_per_chunk=args.max_tokens
    )
    
    # 读取输入
    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        print("请输入要分析的文本（输入完成后按Ctrl+D结束）：")
        text = sys.stdin.read()
    
    # 分析文本
    try:
        result = analyzer.analyze_text(text)
        formatted_result = analyzer.format_analysis_result(result)
        
        # 输出结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_result)
            print(f"分析结果已保存到：{args.output}")
        else:
            print(formatted_result)
            
    except Exception as e:
        print(f"错误：分析过程中出现异常：{e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 
"""LLM Reviewer:接 Claude API 当审稿人。

跟 reviewer_agent.py 的 rule-based 版本互补:
  - 规则版处理"明确的、可程序化的"问题(图重复 / bullets 溢出)
  - LLM 版处理"需要语义理解"的问题(配图对不对题、内容是否专业、表述是否清楚)

设计:
  - System prompt 用一批人工驳回反馈的原话作 few-shot,教 LLM 挑刺的口吻
    (下面 SYSTEM_PROMPT 里的示例已替换成占位内容,实际使用时建议换成
    你自己领域、自己专家的真实反馈原话,效果会好很多)
  - 每页一次 call,返回结构化 JSON
  - 没 API key 时优雅跳过(走纯规则版)

成本估算(粗略):按 Sonnet 价，约 ~1500 token/page，89 页的 deck 大概 $0.5 左右，按你的页数线性估算
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import anthropic
    _has_sdk = True
except ImportError:
    _has_sdk = False

from src.core.actions_schema import SlideActions
from src.core.outline_parser import Page
from src.reviewer_agent import Issue


# ===== System prompt =====
# 教 Claude 学「领域专家看一眼就能挑刺」的眼光——把下面的领域描述和
# few-shot 反馈原话换成你自己项目的真实内容，效果会明显更好。

# 示例值，换成你自己的技术领域，比如「半导体封装」「新能源电池」「生物医药」
DOMAIN_DESCRIPTION = "示例技术"

_SYSTEM_PROMPT_TEMPLATE = """\
你是一位__DOMAIN__领域的资深技术专家,在审一份给业内人士看的技术讲义。
你的工作是逐页审稿,挑出可能让目标读者觉得"不够专业 / 不到位"的问题。

每页给你:
- 标题、章节、layout 类型
- bullets(文字内容)
- image_hint(讲义大纲里写的"想要什么图")
- 当前挑的图(文件路径)

你要从三个角度挑问题:
1. content(内容问题):事实错误、术语不准、表述不专业、bullets 信息密度不够或太杂
2. design(设计问题):文字太多塞不下、版面会空、layout 跟内容不搭
3. paradigm(范式问题):配图应该用示意图却用了实物照、应该用对比表却只放了一张图、
   应该用多张照片展示几种东西却只放了一张

下面是几条示例反馈风格(占位内容,实际使用时请换成你自己领域专家驳回页面的真实原话——
真实的、带专业口吻的反馈样本，比泛泛而写的例子更能教会 LLM 挑刺的分寸):
- "换成示意图"(实物照不够,要原理性的图)
- "跟上面重复,换一个新的"(图片重复使用)
- "配图型号不对,换成示例中提到的那一款"(配图选错型号/版本)
- "展示三种材料要三张图,不能只放一张"(展示 N 种东西要 N 张图)
- "这个数据没有来源标注"(缺引用来源)

注意:不是每一页都有问题。判断标准是"目标读者(__DOMAIN__从业者)看了会不会挑刺"。
如果没问题,返回空列表。

输出格式严格按 JSON:
```json
{
  "issues": [
    {
      "kind": "paradigm",
      "severity": "high",
      "rule": "schematic_vs_photo",
      "message": "配图建议要示意图,但挑的是实物照(p17-i2.png 来自 ch1 实物图)",
      "suggestion": "换成原理图 / SVG 示意图"
    }
  ]
}
```

字段含义:
- kind: content / design / paradigm 三选一
- severity: high(影响理解) / medium(影响观感) / low(可改可不改)
- rule: 一个短英文 snake_case 标签,方便后面 contributor 分发动作
- message: 一句话说清楚问题是什么
- suggestion: 一句话给建议(可选)

返回的 JSON 必须能直接解析,不要在外面加多余文字。
"""

SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.replace("__DOMAIN__", DOMAIN_DESCRIPTION)


# ===== 单页 user prompt =====

def build_user_message(slide: SlideActions, page: Page | None) -> str:
    """组装单页的 user message。"""
    lines = []
    lines.append(f"# 第 {slide.page} 页")
    lines.append(f"章节: {slide.chapter}")
    lines.append(f"Layout: `{slide.layout}`")
    lines.append("")

    title_a = slide.find("title")
    if title_a:
        lines.append(f"标题: {title_a.get('text', '')}")

    if page and page.image_hint:
        lines.append(f"配图建议(outline 里写的): {page.image_hint}")

    bullets_a = slide.find("bullets")
    if bullets_a and bullets_a.get("items"):
        lines.append("")
        lines.append("Bullets:")
        for b in bullets_a["items"]:
            lines.append(f"- {b}")

    text_a = slide.find("text")
    if text_a and text_a.get("text"):
        lines.append("")
        lines.append(f"重点文字: {text_a['text']}")

    image_a = slide.find("image")
    placeholder_a = slide.find("image_placeholder")
    if image_a:
        path = image_a.get("path", "")
        lines.append("")
        lines.append(f"挑的图: `{path}`")
        if image_a.get("caption"):
            lines.append(f"图说: {image_a['caption']}")
    elif placeholder_a:
        lines.append("")
        lines.append(f"挑的图: [占位:{placeholder_a.get('note', '')}]")
    else:
        lines.append("")
        lines.append(f"挑的图: 无")

    table_a = slide.find("table")
    if table_a:
        n_cols = len(table_a.get("header", []))
        n_rows = len(table_a.get("rows", []))
        lines.append("")
        lines.append(f"有表格: {n_cols} 列 × {n_rows} 行")

    lines.append("")
    lines.append("请审一下这页,有问题列出来。没问题返回 `{\"issues\": []}`。")

    return "\n".join(lines)


# ===== 调 API =====

@dataclass
class LLMReviewerConfig:
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 1024
    temperature: float = 0.0
    skip_layouts: tuple[str, ...] = ("cover", "agenda", "section-divider")  # 结构性页面不审


def llm_review_slide(
    slide: SlideActions,
    page: Page | None,
    client: "anthropic.Anthropic",
    config: LLMReviewerConfig,
) -> list[Issue]:
    """让 Claude 审一页,返回 Issue list。"""
    if slide.layout in config.skip_layouts:
        return []

    user_msg = build_user_message(slide, page)

    try:
        resp = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        print(f"  ⚠ p{slide.page} API 出错: {e}")
        return []

    # 解析返回的 JSON
    text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            text += block.text
    text = text.strip()
    # 容忍 ```json ... ``` 包裹
    if "```" in text:
        import re
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ⚠ p{slide.page} JSON 解析失败: {e}; 原文: {text[:200]}")
        return []

    issues = []
    for entry in data.get("issues", []):
        try:
            issues.append(Issue(
                page=slide.page,
                kind=entry.get("kind", "content"),
                severity=entry.get("severity", "medium"),
                rule=f"llm_{entry.get('rule', 'unknown')}",
                message=entry.get("message", ""),
                suggestion=entry.get("suggestion", ""),
            ))
        except Exception:
            continue
    return issues


def llm_review_deck(
    deck,  # DeckActions
    pages_by_num: dict[int, Page],
    config: LLMReviewerConfig | None = None,
    api_key: str | None = None,
    verbose: bool = True,
) -> list[Issue]:
    """对整本 deck 跑 LLM reviewer。

    Returns:
        所有 issues 的合并列表;API key 缺失或 SDK 没装时返回 []。
    """
    config = config or LLMReviewerConfig()

    if not _has_sdk:
        if verbose:
            print("  ⚠ anthropic SDK 没装,跳过 LLM reviewer")
        return []

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        if verbose:
            print("  ⚠ ANTHROPIC_API_KEY 没设,跳过 LLM reviewer")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    all_issues: list[Issue] = []
    t0 = time.time()
    n_done = 0
    n_skipped = 0
    for slide in deck.slides:
        if slide.layout in config.skip_layouts:
            n_skipped += 1
            continue
        page = pages_by_num.get(slide.page)
        page_issues = llm_review_slide(slide, page, client, config)
        all_issues.extend(page_issues)
        n_done += 1
        if verbose and n_done % 10 == 0:
            elapsed = time.time() - t0
            rate = n_done / elapsed if elapsed > 0 else 0
            print(f"  [{n_done}/{len(deck.slides) - n_skipped}] {rate:.1f} page/s, 累计 {len(all_issues)} issues")

    if verbose:
        elapsed = time.time() - t0
        print(f"  ✓ LLM reviewer 跑完: {n_done} 页, {len(all_issues)} issues, {elapsed:.1f}s")
    return all_issues


# ===== 合并 rule-based 和 LLM 的结果 =====

def merge_issues(rule_issues: list[Issue], llm_issues: list[Issue]) -> list[Issue]:
    """合并两边的 issue list,去重(按 page+kind+rule)。

    策略:
      - 同一页 + 同 kind + 同 rule 视为重复,优先保留 rule 版本(可程序化)
      - 其他全部合并
    """
    # 先按 (page, kind, rule) 做 set
    seen = set()
    out: list[Issue] = []
    for issue in rule_issues + llm_issues:
        key = (issue.page, issue.kind, issue.rule)
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    # 按 page → severity 排
    severity_order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda i: (i.page, severity_order.get(i.severity, 9)))
    return out

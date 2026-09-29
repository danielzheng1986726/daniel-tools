"""Layout planner: 给每页打 layout 标签。

策略（按优先级）:
1. **Hard rules**: cover (p1), agenda (p2), section-divider (chapter starts),
   data-table (含 markdown 表格), formula-spotlight (化学结构 / 数学公式词),
   flow-strip (顺序步骤词), chart-hero (曲线 / 统计图词).
2. **Soft rules**: side-by-side (vs / 对比), multi-grid (≥3 并列), case-showcase (产品型号 / 应用实例).
3. **LLM**: 剩下用 Claude 跑 (可选，有 ANTHROPIC_API_KEY 时启用).
4. **Fallback**: content-body / hero-definition (兜底).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from src.core.layout_taxonomy import (
    LAYOUTS,
    DEFAULT_SECTION_DIVIDERS,
    layouts_summary_for_llm,
    all_layout_keys,
)
from src.core.outline_parser import Page, parse_outline
from src.core.style_vector import StyleVector, LayoutPreferences


# ===== Hard rule keywords =====

CHEMICAL_KEYWORDS = ["化学结构式", "分子结构", "结构式", "DGEBA", "BMI 结构", "聚酰亚胺结构", "PEEK 结构"]
CHART_KEYWORDS = ["曲线", "统计图", "趋势图", "对比图", "雷达图", "散点图", "柱状图", "S-N", "用量演进"]
FLOW_KEYWORDS = ["流程图", "工艺流程", "步骤", "Step", "→", "六步", "四步", "五步"]
COMPARE_KEYWORDS = [" vs ", "vs.", "对比", "比较", " v.s. "]
APPLICATION_KEYWORDS = ["型号", "应用实例", "案例"]  # 按你的领域补充具体产品型号

# hero-definition 信号词：标题里出现这些词，说明这页是单点深入
HERO_DEFINITION_TITLE_KEYWORDS = [
    "概述", "原理", "判别标准", "分类体系", "策略", "效应",
    "性能与应用", "性能与局限", "技术", "工艺概述", "概念",
    # 按你的领域补充，比如「设计方法」「选型」
]
# 出现这些专有名词的短标题倾向单点展开。按你的领域填：材料名、工艺缩写、方法名等。
HERO_TERMS = [
    "示例术语A", "示例术语B", "ABC", "XYZ",
]
# case-showcase 信号词
CASE_KEYWORDS = ["应用案例", "认证突破", "应用", "案例"]


@dataclass
class LayoutDecision:
    page: int
    layout: str
    reason: str
    confidence: str  # "hard", "soft", "llm", "fallback"


def _has_keyword(text: str, keywords: list[str]) -> bool:
    """Case-insensitive keyword match."""
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


def _count_parallel_items(bullets: list[str]) -> int:
    """估计 bullets 是不是在列举 3+ 并列物体。"""
    if len(bullets) < 3:
        return 0
    # 寻找"X / Y / Z"格式的 bullets，或者重复格式（同样的句式开头）
    enum_count = 0
    for b in bullets:
        if re.search(r"[/、，][^/、，]+[/、，]", b):
            enum_count += 1
    return enum_count


def _hint_is_dual(image_hint: str) -> bool:
    """配图建议里像两张图并排（'A + B 图'、'vs'、'对比图'）。"""
    if not image_hint:
        return False
    # ' + ' 连接两张图（"A示意图 + B照片"）
    if " + " in image_hint or "+示意" in image_hint or "图 +" in image_hint:
        return True
    # 显式对比词
    for kw in ["对比图", " vs ", "vs.", "v.s.", "两种", "二者"]:
        if kw in image_hint:
            return True
    return False


def classify_hard_rules(page: Page, section_dividers: set[int]) -> LayoutDecision | None:
    """硬规则分类，命中则返回，否则返回 None。"""
    pn = page.page

    # Cover / Agenda
    if pn == 1:
        return LayoutDecision(pn, "cover", "第 1 页", "hard")
    if pn == 2:
        return LayoutDecision(pn, "agenda", "第 2 页", "hard")

    # Section divider — 但如果 outline 里有 3+ 条 bullet，说明有实质内容，不该做纯标题页
    if pn in section_dividers:
        if len(page.bullets) < 3:
            return LayoutDecision(pn, "section-divider", "章节起点页", "hard")
        # else: 有内容的章节首页，继续走 soft/fallback 分类

    # 检查 image_hint + bullets 内容
    combined_text = page.image_hint + " " + " ".join(page.bullets) + " " + page.title

    # Formula / 化学结构（这个语义最强，优先于 data-table 之外的判断）
    if _has_keyword(combined_text, CHEMICAL_KEYWORDS):
        return LayoutDecision(pn, "formula-spotlight", "含化学结构 / 公式关键词", "hard")

    # ABD 矩阵之类的公式专题（v7 把 p44 标成 formula-spotlight）
    if "矩阵" in page.title or "ABD" in page.title.upper():
        return LayoutDecision(pn, "formula-spotlight", "标题含矩阵 / 公式", "hard")

    # Data table（标题含"总结/回顾/汇总"的最后一页例外，避免抢 content-body）
    if page.has_table and not any(w in page.title for w in ["总结", "回顾", "汇总"]):
        return LayoutDecision(pn, "data-table", "含 markdown 表格", "hard")

    # Case-showcase 提前（标题含案例 / 认证突破 / 应用，要在其他规则前抢）
    if _has_keyword(page.title, ["应用案例", "认证突破", "应用"]):
        # 但是"应用"太宽泛，要排除复合词避免误伤
        if any(w in page.title for w in ["案例", "认证突破"]) or \
           page.title.endswith("应用"):
            return LayoutDecision(pn, "case-showcase", "标题含案例 / 应用类", "hard")

    # Hero-definition 提前（短标题 + 概述 / 原理 / 判别标准）
    if _has_keyword(page.title, ["概述", "原理", "判别标准", "效应", "策略", "技术概述"]):
        return LayoutDecision(pn, "hero-definition", "标题含单点深入信号词", "hard")

    # Side-by-side（image_hint 双图模式）
    if _hint_is_dual(page.image_hint):
        return LayoutDecision(pn, "side-by-side", "配图建议是双图并排", "hard")

    # Side-by-side（标题或 bullets 含对比词）
    if _has_keyword(page.title + " " + " ".join(page.bullets), COMPARE_KEYWORDS):
        return LayoutDecision(pn, "side-by-side", "标题/正文含 vs / 对比", "hard")

    # Chart hero
    if _has_keyword(page.image_hint, CHART_KEYWORDS):
        return LayoutDecision(pn, "chart-hero", "配图建议含曲线 / 统计图词", "hard")

    # Flow strip
    if _has_keyword(combined_text, FLOW_KEYWORDS):
        return LayoutDecision(pn, "flow-strip", "含顺序步骤关键词", "hard")

    return None


def classify_soft_rules(page: Page) -> LayoutDecision | None:
    """软规则分类。"""
    pn = page.page
    combined = page.title + " " + " ".join(page.bullets) + " " + page.image_hint

    # Side-by-side (vs / 对比)
    if _has_keyword(combined, COMPARE_KEYWORDS):
        return LayoutDecision(pn, "side-by-side", "含 vs / 对比词", "soft")

    # Case showcase (应用案例 / 认证突破 — 优先级高于 multi-grid)
    if _has_keyword(page.title, ["应用案例", "认证突破"]):
        return LayoutDecision(pn, "case-showcase", "标题含应用案例 / 认证突破", "soft")

    # Hero-definition：标题里有"概述 / 原理 / 判别标准"类信号词
    if _has_keyword(page.title, HERO_DEFINITION_TITLE_KEYWORDS):
        return LayoutDecision(pn, "hero-definition", "标题含单点深入信号词", "soft")

    # Hero-definition：短标题 + 含专有术语（PEEK / RTM / Nomex 之类）
    if len(page.title) <= 18 and _has_keyword(page.title, HERO_TERMS):
        return LayoutDecision(pn, "hero-definition", "短标题含专有术语，单点展开", "soft")

    # Multi-grid (≥3 并列物体)
    if _count_parallel_items(page.bullets) >= 2:
        return LayoutDecision(pn, "multi-grid", "bullets 在并列描述多种物体", "soft")

    # Case showcase (产品型号 / 应用实例)
    if _has_keyword(page.image_hint, APPLICATION_KEYWORDS):
        return LayoutDecision(pn, "case-showcase", "配图建议含具体型号", "soft")

    return None


def classify_fallback(page: Page, style_prefs: LayoutPreferences | None = None) -> LayoutDecision:
    """Fallback: 没匹配上任何规则的页,根据风格偏好兜底。

    如果有 style_prefs (reference deck 的 layout 偏好):
      - reference 偏向 hero-definition (>= 25% 占比) → fallback 用 hero-definition
      - 否则用 content-body
    没有 style_prefs 时走原逻辑(定义类标题 → hero-definition, 其他 → content-body)。
    """
    pn = page.page
    definition_signals = ["什么是", "概述", "构成", "定义", "概念"]

    # 标题明确是定义类,直接 hero-definition
    if any(s in page.title for s in definition_signals):
        return LayoutDecision(pn, "hero-definition", "标题含定义类词（兜底）", "fallback")

    # 用 style_prefs 偏置
    if style_prefs and style_prefs.bias("hero-definition") >= 0.25:
        return LayoutDecision(pn, "hero-definition",
                              f"风格偏好（reference 中 hero-def 占 {style_prefs.bias('hero-definition')*100:.0f}%）",
                              "fallback")

    return LayoutDecision(pn, "content-body", "未匹配特定模式（兜底）", "fallback")


def plan_layouts(
    pages: list[Page],
    section_dividers: set[int] | None = None,
    use_llm: bool = False,
    style_vector: StyleVector | None = None,
) -> list[LayoutDecision]:
    """对每页打 layout 标签。

    Args:
        pages: parse_outline 返回的页面列表
        section_dividers: 章节起点页号集合（默认用 DEFAULT_SECTION_DIVIDERS）
        use_llm: 是否对硬+软规则都没命中的页调用 LLM（默认 False，用 fallback）
        style_vector: 可选的风格向量（来自 reference-deck），影响 fallback 偏好

    Returns:
        每页一个 LayoutDecision
    """
    if section_dividers is None:
        section_dividers = DEFAULT_SECTION_DIVIDERS

    style_prefs = style_vector.layout_prefs if style_vector else None

    decisions: list[LayoutDecision] = []
    for page in pages:
        # 1. Hard rules
        d = classify_hard_rules(page, section_dividers)
        if d is not None:
            decisions.append(d)
            continue
        # 2. Soft rules
        d = classify_soft_rules(page)
        if d is not None:
            decisions.append(d)
            continue
        # 3. LLM (optional, TODO Phase 2)
        if use_llm:
            # Placeholder: 将来用 Anthropic API 跑
            pass
        # 4. Fallback（接 style_prefs 偏置）
        decisions.append(classify_fallback(page, style_prefs))

    return decisions


def save_decisions(decisions: list[LayoutDecision], path: str | Path) -> None:
    """保存到 JSON。格式为 layout-classification.json。"""
    out = {}
    for d in decisions:
        out[str(d.page)] = {
            "layout": d.layout,
            "reason": d.reason,
            "confidence": d.confidence,
        }
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    from collections import Counter

    outline_path = sys.argv[1] if len(sys.argv) > 1 else "examples/demo-deck/outline.md"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "examples/demo-deck/layout-plan.json"

    pages = parse_outline(outline_path)
    decisions = plan_layouts(pages)

    # Stats
    layout_counter = Counter(d.layout for d in decisions)
    conf_counter = Counter(d.confidence for d in decisions)

    print(f"Total pages classified: {len(decisions)}")
    print("\nLayout distribution:")
    for layout, n in layout_counter.most_common():
        print(f"  {layout:20s}: {n:2d} ({n / len(decisions) * 100:.1f}%)")
    print("\nConfidence breakdown:")
    for conf, n in conf_counter.most_common():
        print(f"  {conf:10s}: {n:2d}")

    save_decisions(decisions, out_path)
    print(f"\nSaved to {out_path}")

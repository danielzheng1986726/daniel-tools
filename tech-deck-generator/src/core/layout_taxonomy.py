"""Layout taxonomy: 12 种 slide layout 类型的定义。

来自一次实测复盘的 layout 分类实验（规则版 AI 分类准确率约 87%）。
每种 layout 有：
- 代号 (key)
- 中文名 (zh)
- 何时使用 (when)
- 视觉特征 (visual)
- 内容能否让 AI 现场画 (ai_can_generate)
"""
from dataclasses import dataclass
from typing import Literal

AICanGenerate = Literal["yes", "partial", "no"]


@dataclass(frozen=True)
class LayoutSpec:
    key: str
    zh: str
    when: str
    visual: str
    ai_can_generate: AICanGenerate
    """
    yes:     纯几何排版，让 AI 画 SVG 不出问题
    partial: 用 AI 排版 + 真实素材填进去
    no:      必须用真实素材（论文 / Wikipedia / ChemDraw / 教科书）
    """


LAYOUTS: dict[str, LayoutSpec] = {
    "cover": LayoutSpec(
        key="cover",
        zh="封面",
        when="仅第 1 页",
        visual="大标题 + 主讲人 / 日期 / 单位 + 装饰元素",
        ai_can_generate="yes",
    ),
    "agenda": LayoutSpec(
        key="agenda",
        zh="目录",
        when="仅第 2 页",
        visual="章节卡片网格（3x2 或类似）",
        ai_can_generate="yes",
    ),
    "section-divider": LayoutSpec(
        key="section-divider",
        zh="章节扉页",
        when="每章起点页（章节分界页号，因项目而异，见 DEFAULT_SECTION_DIVIDERS）",
        visual="深色背景 + 超大章节号 + 章节内容预览",
        ai_can_generate="yes",
    ),
    "hero-definition": LayoutSpec(
        key="hero-definition",
        zh="概念聚焦",
        when="介绍单一概念，标题如『什么是 XX』『XX 概述』『XX 构成』",
        visual="大标题 + 关键词 / 关键数字 + 单一示意图 + 大量留白",
        ai_can_generate="partial",
    ),
    "side-by-side": LayoutSpec(
        key="side-by-side",
        zh="并排对比",
        when="bullets 在比较 2-3 种东西，或标题含『vs』『对比』",
        visual="2-3 列大色卡并列，每列代表一种类型，同样属性按行对齐",
        ai_can_generate="yes",
    ),
    "flow-strip": LayoutSpec(
        key="flow-strip",
        zh="横向流程链",
        when="bullets 是顺序步骤（Step 1/2/3 或 '→' 连接的多步）",
        visual="横向步骤框 + 箭头串联，每步带关键参数",
        ai_can_generate="yes",
    ),
    "chart-hero": LayoutSpec(
        key="chart-hero",
        zh="大图为主",
        when="配图建议含『曲线』『统计图』『趋势图』『对比图』",
        visual="图占主体面积（70%+），右侧或下方放 3-4 个『洞察 chip』",
        ai_can_generate="no",  # 数据图必须真实
    ),
    "multi-grid": LayoutSpec(
        key="multi-grid",
        zh="多图网格",
        when="bullets 在并列描述 3-4 种独立样品 / 对象",
        visual="2x2 或 3-row 网格，每格一种类型 + 中文 caption",
        ai_can_generate="no",  # 实物图必须真实
    ),
    "case-showcase": LayoutSpec(
        key="case-showcase",
        zh="案例展示",
        when="产品型号 / 应用实例的大图展示",
        visual="大图占主体 + 关键数字突出 + 简短描述",
        ai_can_generate="no",
    ),
    "formula-spotlight": LayoutSpec(
        key="formula-spotlight",
        zh="公式 / 结构聚光",
        when="化学结构式、数学公式为主体",
        visual="公式 / 结构居中放大占 60%，右侧 3-5 个属性 chip",
        ai_can_generate="no",  # 化学结构必须真实
    ),
    "data-table": LayoutSpec(
        key="data-table",
        zh="数据表格",
        when="内容含 markdown 表格语法",
        visual="navy 表头 + 浅色斑马纹 + 多行多列数据",
        ai_can_generate="yes",
    ),
    "content-body": LayoutSpec(
        key="content-body",
        zh="默认兜底",
        when="上面都不符合（左文右图）",
        visual="左半屏 bullets，右半屏单图",
        ai_can_generate="partial",
    ),
}


# 章节起点页码，默认空集——新客户接入时由 plan_layouts.py 自动识别，
# 或者在调用 plan_layouts 时手动传入自己项目的章节分界页号
DEFAULT_SECTION_DIVIDERS: set[int] = set()


def get_layout(key: str) -> LayoutSpec:
    """根据代号取 layout spec，找不到返回兜底 content-body。"""
    return LAYOUTS.get(key, LAYOUTS["content-body"])


def all_layout_keys() -> list[str]:
    """返回 12 种 layout 的代号列表，便于给 LLM 看选项。"""
    return list(LAYOUTS.keys())


def layouts_summary_for_llm() -> str:
    """生成给 LLM 看的简洁版本，用于 layout 分类 prompt。"""
    lines = []
    for spec in LAYOUTS.values():
        lines.append(f"- `{spec.key}` ({spec.zh}): {spec.when}")
    return "\n".join(lines)


if __name__ == "__main__":
    # quick sanity check
    print(f"Total layouts: {len(LAYOUTS)}")
    print(f"\nKeys: {all_layout_keys()}")
    print(f"\nFor LLM:\n{layouts_summary_for_llm()}")

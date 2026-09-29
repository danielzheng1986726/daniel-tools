"""Generate actions.json: 把 outline + layout + matches 转成 actions 序列。

PPTAgent 思路: 不直接出 PPTX,先出语义化 actions,
后面 reviewer / contributor / renderer 都基于 actions 工作。

actions 是"语义元素",不是"渲染指令":
  - title / eyebrow / bullets / image / table / flow_step / compare / text
  - reviewer 改 actions 不需要懂坐标

输入:
  pages: list[Page]                       outline 解析结果
  decisions: list[LayoutDecision]         每页 layout
  matches: dict[int, list[ImageCandidate]] 图片候选
  image_paths: dict[int, str|None]        每页 top-1 图绝对路径
  style_vector: StyleVector               风格向量

输出:
  DeckActions
"""
from __future__ import annotations

from pathlib import Path

from src.core.outline_parser import Page
from src.core.actions_schema import (
    DeckActions, SlideActions,
    TitleAction, EyebrowAction, BulletsAction, ImageAction,
    TableAction, TextBlockAction, FlowStepAction, CompareAction,
)
from src.core.style_vector import StyleVector
from src.plan_layouts import LayoutDecision
from src.source_images import ImageCandidate


def _chapter_num(chapter: str) -> str:
    """从 '第3章：示例主题' 抽 '03'。没有就空。"""
    import re
    m = re.search(r"第\s*(\d+)\s*章", chapter)
    if m:
        return f"{int(m.group(1)):02d}"
    return ""


def actions_for_cover(page: Page, image_path: str | None) -> list:
    """cover 页只有 title + subtitle,不要 bullets/image。"""
    return [
        TitleAction(text=page.title, subtitle=page.bullets[0] if page.bullets else ""),
    ]


def actions_for_agenda(page: Page) -> list:
    """agenda 页:bullets 作为大纲项,渲染时显示成 6 卡片。"""
    return [
        TitleAction(text=page.title),
        BulletsAction(items=page.bullets[:8]),
    ]


def actions_for_section_divider(page: Page) -> list:
    """章节起点页:大章号 + 章节名,不要 bullets。"""
    return [
        EyebrowAction(text=page.chapter, chapter_num=_chapter_num(page.chapter)),
        TitleAction(text=page.title),
    ]


def actions_for_data_table(page: Page) -> list:
    """表格页。"""
    out = [
        EyebrowAction(text=page.chapter, chapter_num=_chapter_num(page.chapter)),
        TitleAction(text=page.title),
        TableAction(header=page.table_header, rows=page.table_rows),
    ]
    # 表格下方留小段说明
    if page.bullets:
        out.append(BulletsAction(items=page.bullets[:3]))
    return out


def actions_for_flow_strip(page: Page, image_path: str | None) -> list:
    """流程步骤页。把 bullets 转成 flow_step。"""
    out = [
        EyebrowAction(text=page.chapter, chapter_num=_chapter_num(page.chapter)),
        TitleAction(text=page.title),
    ]
    # 试着从 bullets 拆步骤
    for i, b in enumerate(page.bullets[:5], 1):
        # "**步骤 1**：详细" 或 "01 详细" 都识别
        label = b
        detail = ""
        if "：" in b:
            parts = b.split("：", 1)
            label = parts[0].strip("*").strip()
            detail = parts[1].strip()
        out.append(FlowStepAction(index=i, label=label, detail=detail))
    if image_path:
        out.append(ImageAction(path=image_path, caption=page.image_hint, role="primary"))
    return out


def actions_for_chart_hero(page: Page, image_path: str | None) -> list:
    """图表中心页:大图 + 少量 bullets。"""
    out = [
        EyebrowAction(text=page.chapter, chapter_num=_chapter_num(page.chapter)),
        TitleAction(text=page.title),
    ]
    if image_path:
        out.append(ImageAction(path=image_path, caption=page.image_hint, role="primary"))
    if page.bullets:
        out.append(BulletsAction(items=page.bullets[:4]))
    return out


def actions_for_hero_definition(page: Page, image_path: str | None) -> list:
    """单点定义页:大字定义 + 配图。"""
    out = [
        EyebrowAction(text=page.chapter, chapter_num=_chapter_num(page.chapter)),
        TitleAction(text=page.title),
    ]
    # 第一条 bullet 作为定义大字
    if page.bullets:
        out.append(TextBlockAction(text=page.bullets[0], emphasis=True))
        if len(page.bullets) > 1:
            out.append(BulletsAction(items=page.bullets[1:6]))
    if image_path:
        out.append(ImageAction(path=image_path, caption=page.image_hint, role="primary"))
    return out


def actions_for_side_by_side(page: Page, image_path: str | None) -> list:
    """对比页。"""
    # 试着从 image_hint 或 title 里拆 "A vs B"
    left_label, right_label = "", ""
    txt = page.title + " " + page.image_hint
    for sep in [" vs ", " vs.", " v.s. ", "对比", "+"]:
        if sep in txt:
            parts = txt.split(sep, 1)
            left_label = parts[0].strip()[:20]
            right_label = parts[1].strip()[:20]
            break

    out = [
        EyebrowAction(text=page.chapter, chapter_num=_chapter_num(page.chapter)),
        TitleAction(text=page.title),
        CompareAction(
            left_label=left_label or "A",
            left_items=page.bullets[:len(page.bullets)//2] if len(page.bullets) >= 2 else page.bullets,
            right_label=right_label or "B",
            right_items=page.bullets[len(page.bullets)//2:] if len(page.bullets) >= 2 else [],
        ),
    ]
    if image_path:
        out.append(ImageAction(path=image_path, caption=page.image_hint, role="primary"))
    return out


def actions_for_default(page: Page, image_path: str | None) -> list:
    """通用 content-body / multi-grid / case-showcase / formula-spotlight 兜底。"""
    out = [
        EyebrowAction(text=page.chapter, chapter_num=_chapter_num(page.chapter)),
        TitleAction(text=page.title),
    ]
    if page.bullets:
        out.append(BulletsAction(items=page.bullets[:6], sub_items=page.sub_bullets))
    if image_path:
        out.append(ImageAction(path=image_path, caption=page.image_hint, role="primary"))
    return out


# layout → actions 函数
LAYOUT_ACTION_BUILDERS = {
    "cover": lambda p, img: actions_for_cover(p, img),
    "agenda": lambda p, img: actions_for_agenda(p),
    "section-divider": lambda p, img: actions_for_section_divider(p),
    "data-table": lambda p, img: actions_for_data_table(p),
    "flow-strip": actions_for_flow_strip,
    "chart-hero": actions_for_chart_hero,
    "hero-definition": actions_for_hero_definition,
    "side-by-side": actions_for_side_by_side,
}


def build_slide_actions(
    page: Page,
    layout: str,
    image_path: str | None,
) -> SlideActions:
    """对一页生成 SlideActions。"""
    builder = LAYOUT_ACTION_BUILDERS.get(layout, actions_for_default)
    raw_actions = builder(page, image_path)

    sa = SlideActions(page=page.page, layout=layout, chapter=page.chapter)
    for a in raw_actions:
        sa.add(a)
    return sa


def build_deck_actions(
    pages: list[Page],
    decisions: list[LayoutDecision],
    image_paths: dict[int, str | None],
    style_vector: StyleVector | None = None,
    source_outline: str = "",
    style_vector_path: str = "",
) -> DeckActions:
    """主入口:整本 PPT 的 actions 序列。"""
    layout_by_page = {d.page: d.layout for d in decisions}
    deck = DeckActions(
        source_outline=source_outline,
        style_vector_path=style_vector_path,
    )
    for page in pages:
        layout = layout_by_page.get(page.page, "content-body")
        img = image_paths.get(page.page)
        sa = build_slide_actions(page, layout, img)
        deck.slides.append(sa)
    return deck


def main():
    import argparse, json
    from src.core.outline_parser import parse_outline
    from src.plan_layouts import plan_layouts

    ap = argparse.ArgumentParser(description="生成 actions.json")
    ap.add_argument("--base", default="examples/demo-deck", help="项目目录")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    pages = parse_outline(base / "outline.md")

    style_vector = None
    sv_path = base / "style-vector.json"
    if sv_path.exists():
        style_vector = StyleVector.load(sv_path)

    decisions = plan_layouts(pages, style_vector=style_vector)

    # 读 matches.json 取 top-1
    matches_path = base / "matches.json"
    image_paths: dict[int, str | None] = {}
    if matches_path.exists():
        matches_data = json.loads(matches_path.read_text(encoding="utf-8"))
        for row in matches_data:
            pn = row["page"]
            cands = row.get("candidates", [])
            if cands:
                rel = cands[0]["file"]
                # 写绝对路径,renderer 用
                abs_path = base / rel
                image_paths[pn] = str(abs_path) if abs_path.exists() else None
            else:
                image_paths[pn] = None

    deck = build_deck_actions(
        pages, decisions, image_paths, style_vector,
        source_outline=str(base / "outline.md"),
        style_vector_path=str(sv_path) if sv_path.exists() else "",
    )

    out_path = base / "actions.json"
    deck.save(out_path)

    print(f"Generated {len(deck.slides)} slide actions")
    # 统计 action 类型
    from collections import Counter
    cnt = Counter()
    for s in deck.slides:
        for a in s.actions:
            cnt[a["type"]] += 1
    print("Action types:")
    for t, n in cnt.most_common():
        print(f"  {t:15s}: {n}")
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()

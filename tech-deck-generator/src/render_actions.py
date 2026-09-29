"""Render actions.json → PPTX。

PPTAgent 思路:actions.json 是中间产物,
reviewer/contributor agent 操作的是它,
renderer 把它还原成 PPTX/HTML。

Phase 2 简化版:把 actions 重建为 Page-like 结构,
然后复用现有的 export_pptx.build_pptx 渲染管道。
Phase 3+ 会让 renderer 直接吃 actions(不必走 Page)。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.actions_schema import DeckActions, SlideActions
from src.core.outline_parser import Page
from src.core.style_vector import StyleVector
from src.export_pptx import build_pptx


def actions_to_page(slide: SlideActions) -> Page:
    """从 SlideActions 重建 Page,供 export_pptx 用。"""
    title = ""
    bullets: list[str] = []
    sub_bullets: dict[int, list[str]] = {}
    image_hint = ""
    table_header: list[str] = []
    table_rows: list[list[str]] = []

    for a in slide.actions:
        t = a.get("type")
        if t == "title":
            title = a.get("text", "")
        elif t == "bullets":
            bullets.extend(a.get("items", []))
            for k, v in a.get("sub_items", {}).items():
                sub_bullets[int(k)] = list(v)
        elif t == "text":
            # hero 定义大字,放到 bullets 第一项
            text = a.get("text", "")
            if text:
                if a.get("emphasis"):
                    text = f"**{text}**" if not text.startswith("**") else text
                bullets.insert(0, text)
        elif t == "image":
            cap = a.get("caption", "")
            if cap:
                image_hint = cap
        elif t == "table":
            table_header = list(a.get("header", []))
            table_rows = [list(r) for r in a.get("rows", [])]
        elif t == "flow_step":
            label = a.get("label", "")
            detail = a.get("detail", "")
            if detail:
                bullets.append(f"**{label}**：{detail}")
            else:
                bullets.append(label)
        elif t == "compare":
            left_label = a.get("left_label", "")
            right_label = a.get("right_label", "")
            left_items = a.get("left_items", [])
            right_items = a.get("right_items", [])
            if left_label and left_items:
                bullets.append(f"**{left_label}**：" + " / ".join(left_items[:3]))
            if right_label and right_items:
                bullets.append(f"**{right_label}**：" + " / ".join(right_items[:3]))

    return Page(
        page=slide.page,
        title=title,
        bullets=bullets,
        sub_bullets=sub_bullets,
        image_hint=image_hint,
        table_header=table_header,
        table_rows=table_rows,
        chapter=slide.chapter,
    )


def actions_to_image_path(slide: SlideActions) -> str | None:
    """从 SlideActions 抽 image path。"""
    for a in slide.actions:
        if a.get("type") == "image":
            path = a.get("path", "")
            if path and Path(path).exists():
                return path
    return None


def render_deck(deck: DeckActions, out_pptx: str | Path) -> Path:
    """主入口:DeckActions → PPTX。"""
    pages: list[Page] = []
    layout_plan: dict[int, str] = {}
    image_paths: dict[int, str | None] = {}

    for slide in deck.slides:
        pages.append(actions_to_page(slide))
        layout_plan[slide.page] = slide.layout
        image_paths[slide.page] = actions_to_image_path(slide)

    return Path(build_pptx(pages, layout_plan, image_paths, out_pptx))


def main():
    ap = argparse.ArgumentParser(description="Render actions.json → PPTX")
    ap.add_argument("--actions", default="examples/demo-deck/actions.json", help="actions.json 路径")
    ap.add_argument("--out", default="examples/demo-deck/output-from-actions.pptx", help="输出 PPTX")
    args = ap.parse_args()

    deck = DeckActions.load(args.actions)
    print(f"Loaded {len(deck.slides)} slides from {args.actions}")
    out = render_deck(deck, args.out)
    size_mb = Path(out).stat().st_size / 1024 / 1024
    print(f"Rendered → {out} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

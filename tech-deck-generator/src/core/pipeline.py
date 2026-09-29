"""Pipeline orchestrator: 串起 outline_parser → plan_layouts → source_images → export_pptx.

Phase 1 版本：基础管道（不含 SlideTailor 风格学习、Reviewer-Contributor 闭环）。

用法：
    python -m src.core.pipeline --base examples/demo-deck
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.core.outline_parser import parse_outline
from src.core.style_vector import StyleVector
from src.plan_layouts import plan_layouts, save_decisions
from src.source_images import source_images_for_outline, save_matches
from src.export_pptx import build_pptx
from src.distill_preferences import distill
from src.generate_actions import build_deck_actions
from src.render_actions import render_deck


def run_pipeline(base: Path, verbose: bool = True):
    """End-to-end Phase 1 pipeline.

    输入约定（base 目录下）:
        outline.md            -- 内容大纲（必需）
        extracted/            -- 源图池（manifest + PNG，必需，Phase 1 简化版）
        reference-deck.pptx   -- 风格参考（可选，Phase 2 用）

    输出（base 目录下）:
        layout-plan.json      -- 每页 layout 标签
        matches.json          -- 每页图片候选 top-3
        output.pptx           -- 主交付
        build-log.md          -- 溯源记录
    """
    t_start = time.time()
    log_lines: list[str] = []

    def log(msg: str):
        if verbose:
            print(msg)
        log_lines.append(msg)

    log(f"# Build Log\n")
    log(f"Base: `{base}`\n")
    log(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 0. Style distillation（可选）
    log(f"\n## 0. Style distillation\n")
    style_path = base / "style-vector.json"
    ref_pptx = base / "reference-deck.pptx"
    layout_class = base / "layout-classification-v7.json"
    style_vector = None
    if style_path.exists():
        style_vector = StyleVector.load(style_path)
        log(f"- 从缓存读 `{style_path.name}`")
    elif ref_pptx.exists():
        layout_class_arg = layout_class if layout_class.exists() else None
        style_vector = distill(ref_pptx, layout_class_arg)
        style_vector.save(style_path)
        log(f"- 从 `{ref_pptx.name}` 提取风格,保存到 `{style_path.name}`")
    else:
        log(f"- 没有 reference-deck.pptx,跳过风格学习(用默认)")
    if style_vector:
        top_layout = max(style_vector.layout_prefs.counts.items(), key=lambda x: x[1]) if style_vector.layout_prefs.counts else None
        log(f"- 风格摘要: primary={style_vector.palette.primary}, accent={style_vector.palette.accent}, body={style_vector.fonts.body}pt")
        if top_layout:
            log(f"- Reference 偏好: `{top_layout[0]}` 占 {top_layout[1]/style_vector.layout_prefs.total_pages*100:.0f}%")

    # 1. Parse outline
    log(f"\n## 1. Parse outline\n")
    outline_path = base / "outline.md"
    pages = parse_outline(outline_path)
    log(f"- {len(pages)} pages loaded from `{outline_path.name}`")
    log(f"- First: p{pages[0].page} `{pages[0].title}`")
    log(f"- Last:  p{pages[-1].page} `{pages[-1].title}`")

    # 2. Layout planning
    log(f"\n## 2. Layout planning\n")
    decisions = plan_layouts(pages, style_vector=style_vector)
    save_decisions(decisions, base / "layout-plan.json")
    layout_plan = {d.page: d.layout for d in decisions}
    from collections import Counter
    layout_counter = Counter(d.layout for d in decisions)
    conf_counter = Counter(d.confidence for d in decisions)
    log(f"- 12 layout categories used:")
    for layout, n in layout_counter.most_common():
        log(f"  - `{layout}`: {n}")
    log(f"- Classification confidence: {dict(conf_counter)}")

    # 3. Source images
    log(f"\n## 3. Source images\n")
    extracted_dir = base / "extracted"
    matches = source_images_for_outline(pages, extracted_dir, base_dir=base)
    save_matches(matches, pages, base / "matches.json")
    n_with_match = sum(1 for cands in matches.values() if cands)
    log(f"- {n_with_match}/{len(pages)} pages have ≥1 candidate")
    avg_top1 = sum(cands[0].score if cands else 0 for cands in matches.values()) / len(pages)
    log(f"- Avg top-1 score: {avg_top1:.2f}")

    # Build image_paths {page: top-1 abs path}
    image_paths: dict[int, str | None] = {}
    for pn, cands in matches.items():
        if cands:
            rel = cands[0].file
            abs_path = base / rel
            image_paths[pn] = str(abs_path) if abs_path.exists() else None
        else:
            image_paths[pn] = None

    # 4. Generate actions.json（中间产物,reviewer/contributor 用）
    log(f"\n## 4. Generate actions\n")
    deck = build_deck_actions(
        pages, decisions, image_paths, style_vector,
        source_outline=str(base / "outline.md"),
        style_vector_path=str(base / "style-vector.json") if (base / "style-vector.json").exists() else "",
    )
    actions_path = base / "actions.json"
    deck.save(actions_path)
    from collections import Counter as _Counter
    type_cnt = _Counter()
    for s in deck.slides:
        for a in s.actions:
            type_cnt[a["type"]] += 1
    log(f"- {len(deck.slides)} 页 actions 写入 `{actions_path.name}`")
    log(f"- Action 类型: {dict(type_cnt)}")

    # 5. Render actions → PPTX
    log(f"\n## 5. Export PPTX\n")
    out_path = base / "output.pptx"
    render_deck(deck, out_path)
    size_mb = out_path.stat().st_size / 1024 / 1024
    log(f"- Output: `{out_path.name}` ({size_mb:.1f} MB)")

    elapsed = time.time() - t_start
    log(f"\n## Done\n\nTotal time: {elapsed:.1f}s")

    # Write build log
    (base / "build-log.md").write_text("\n".join(log_lines), encoding="utf-8")
    log(f"Build log: `build-log.md`")

    return out_path


def main():
    ap = argparse.ArgumentParser(description="AI TechDeck MVP — Phase 1 pipeline")
    ap.add_argument("--base", default="examples/demo-deck", help="Base dir with outline.md + extracted/")
    ap.add_argument("--quiet", action="store_true", help="Suppress stdout")
    args = ap.parse_args()
    base = Path(args.base).resolve()
    if not base.exists():
        raise SystemExit(f"Base dir not found: {base}")
    run_pipeline(base, verbose=not args.quiet)


if __name__ == "__main__":
    main()

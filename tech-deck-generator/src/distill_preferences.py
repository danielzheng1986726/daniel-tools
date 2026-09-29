"""从 reference-deck.pptx 提风格向量。

SlideTailor 思路:让新客户接入时给 1-2 个示范 PPT,
我们从里头读出他喜欢的色 / 字 / 排版 / 章节命名习惯,
后面 layout planning 和 PPTX 渲染都套这个 vector。

支持两种输入:
1. 一个 PPTX 路径  → 提一份 style vector
2. PPTX + outline → 顺便统计 layout 偏好(需要 layout-classification 标注)
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

from src.core.style_vector import (
    StyleVector, ColorPalette, FontRamp,
    LayoutDensity, ChromeStyle, LayoutPreferences,
)


# 已知的语义色 → 角色映射(出现次数最多的几种)
# 实际跑的时候按出现次数从高到低塞进 palette
SEMANTIC_ROLE_ORDER = [
    "text_primary", "primary", "text_secondary",
    "text_emphasis", "accent", "rule_color",
]


def _rgb_to_hex(rgb) -> str:
    """python-pptx RGBColor 的 hex 字符串(无 #)。"""
    return f"#{rgb}".upper()


def collect_colors(prs) -> Counter:
    """聚合所有文字颜色,返回 Counter。"""
    counter = Counter()
    for slide in prs.slides:
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            for para in sh.text_frame.paragraphs:
                for run in para.runs:
                    try:
                        if run.font.color and run.font.color.rgb:
                            counter[_rgb_to_hex(run.font.color.rgb)] += 1
                    except Exception:
                        pass
    return counter


def collect_font_stats(prs) -> tuple[Counter, Counter]:
    """聚合字号(pt) + 字体名。"""
    size_counter = Counter()
    name_counter = Counter()
    for slide in prs.slides:
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            for para in sh.text_frame.paragraphs:
                for run in para.runs:
                    if run.font.size:
                        size_counter[round(run.font.size.pt, 1)] += 1
                    if run.font.name:
                        name_counter[run.font.name] += 1
    return size_counter, name_counter


def derive_palette(color_counts: Counter) -> ColorPalette:
    """从 color counter 推 palette。

    策略:
      - 出现次数最多的深色(不是白)  → text_primary
      - 出现次数最多的有彩色(蓝/红/橙) → primary
      - 出现次数次多的中度彩色 → accent
      - 其他按角色补全
    """
    pal = ColorPalette()  # 兜底
    if not color_counts:
        return pal

    # 排除白色和近白
    def is_white(h: str) -> bool:
        h = h.lstrip("#")
        return all(int(h[i:i+2], 16) > 240 for i in range(0, 6, 2))

    # 排除彩度过低的（接近灰）
    def saturation(h: str) -> int:
        h = h.lstrip("#")
        r, g, b = [int(h[i:i+2], 16) for i in range(0, 6, 2)]
        return max(r, g, b) - min(r, g, b)

    sorted_colors = [(c, n) for c, n in color_counts.most_common() if not is_white(c)]

    # text_primary: 最多的低彩度深色
    for c, _ in sorted_colors:
        if saturation(c) < 30:
            pal.text_primary = c
            break

    # primary: 最多的高彩度色（偏冷色更可能是 navy/blue）
    for c, _ in sorted_colors:
        if saturation(c) >= 60:
            pal.primary = c
            pal.rule_color = c
            break

    # accent: 次多的高彩度色，且跟 primary 不同
    for c, _ in sorted_colors:
        if saturation(c) >= 60 and c != pal.primary:
            pal.accent = c
            break

    # text_secondary: 中等彩度灰
    for c, _ in sorted_colors:
        if 0 < saturation(c) < 30 and c != pal.text_primary:
            pal.text_secondary = c
            break

    return pal


def derive_fonts(size_counts: Counter, name_counts: Counter) -> FontRamp:
    """从字号 / 字体分布推 font ramp。

    body = 出现次数最多的字号
    eyebrow / caption = body - 2 或更小的最常见档
    title = 远高于 body 的最常见档(用作页标题,通常 ≥ body * 2)
    subtitle = body 和 title 之间最常见档
    """
    ramp = FontRamp()
    if not size_counts:
        return ramp

    sorted_sizes = sorted(size_counts.items(), key=lambda x: -x[1])

    # body: 出现次数最多的
    if sorted_sizes:
        ramp.body = sorted_sizes[0][0]

    # title: 比 body 大至少 1.5 倍的最常见
    big = [(s, n) for s, n in sorted_sizes if s >= ramp.body * 1.5]
    if big:
        ramp.title = big[0][0]

    # subtitle: body 和 title 之间
    mid = [(s, n) for s, n in sorted_sizes if ramp.body < s < ramp.title]
    if mid:
        ramp.subtitle = mid[0][0]

    # caption: 比 body 小
    small = [(s, n) for s, n in sorted_sizes if s < ramp.body]
    if small:
        ramp.caption = small[0][0]
        ramp.eyebrow = ramp.caption

    # 字体
    sorted_names = name_counts.most_common()
    cn_fonts = [n for n, _ in sorted_names if any(w in n for w in ["PingFang", "Hei", "Song", "Yuan", "Kai", "宋", "黑"])]
    en_fonts = [n for n, _ in sorted_names if n not in cn_fonts]
    if cn_fonts:
        ramp.font_cn = cn_fonts[0]
    if en_fonts:
        ramp.font_en = en_fonts[0]

    return ramp


def derive_density(prs) -> LayoutDensity:
    """估算文图密度。"""
    bullets_per_page = []
    image_count = 0
    text_box_count = 0

    for slide in prs.slides:
        n_bullets = 0
        for sh in slide.shapes:
            if sh.has_text_frame:
                text_box_count += 1
                # 数 paragraphs 里像 bullet 的(以 0/1/02 等开头 或 普通段落)
                for para in sh.text_frame.paragraphs:
                    if para.text.strip():
                        n_bullets += 1
            if sh.shape_type == 13:  # PICTURE
                image_count += 1
        bullets_per_page.append(n_bullets)

    avg = sum(bullets_per_page) / len(bullets_per_page) if bullets_per_page else 4.0
    mx = max(bullets_per_page) if bullets_per_page else 8

    n_slides = len(prs.slides)
    img_ratio = image_count / n_slides if n_slides else 0.45

    return LayoutDensity(
        bullets_per_page_avg=round(avg, 1),
        bullets_per_page_max=int(mx),
        image_ratio=round(min(img_ratio, 1.0), 2),
    )


def derive_chrome(prs) -> ChromeStyle:
    """从前几页找页眉页脚的格式。"""
    chrome = ChromeStyle()
    # 简单起见,扫前 5 页,看顶部是不是有 "PART NN" 之类
    has_part = False
    has_page_n = False
    has_brand_footer = False
    for slide in list(prs.slides)[:5]:
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            text = sh.text_frame.text
            if "PART" in text and "／" in text:
                has_part = True
            if "／" in text and any(c.isdigit() for c in text):
                has_page_n = True
            # 底部品牌行(y > 600 且文字较长)
            try:
                if sh.top and sh.top // 9525 > 600 and len(text) > 10:
                    has_brand_footer = True
            except Exception:
                pass

    chrome.show_part_top_right = has_part
    chrome.show_page_number = has_page_n
    chrome.show_brand_footer = has_brand_footer
    return chrome


def derive_layout_prefs(layout_class_path: str | Path | None) -> LayoutPreferences:
    """如果有 layout 标注（v7 的 layout-classification.json）,数 layout 偏好。"""
    if not layout_class_path or not Path(layout_class_path).exists():
        return LayoutPreferences()
    import json
    data = json.loads(Path(layout_class_path).read_text(encoding="utf-8"))
    counts = Counter(v.get("layout", "?") for v in data.values())
    return LayoutPreferences(counts=dict(counts), total_pages=len(data))


def distill(
    reference_pptx: str | Path,
    layout_classification: str | Path | None = None,
) -> StyleVector:
    """主入口:从 reference-deck.pptx 提风格向量。"""
    path = Path(reference_pptx)
    prs = Presentation(str(path))

    color_counts = collect_colors(prs)
    size_counts, name_counts = collect_font_stats(prs)

    canvas_w = int(prs.slide_width / 9525)
    canvas_h = int(prs.slide_height / 9525)

    sv = StyleVector(
        source=str(path),
        canvas_w_px=canvas_w,
        canvas_h_px=canvas_h,
        palette=derive_palette(color_counts),
        fonts=derive_fonts(size_counts, name_counts),
        density=derive_density(prs),
        chrome=derive_chrome(prs),
        layout_prefs=derive_layout_prefs(layout_classification),
    )
    return sv


def main():
    ap = argparse.ArgumentParser(description="从 reference-deck.pptx 提风格向量")
    ap.add_argument("pptx", help="reference deck PPTX 路径")
    ap.add_argument("--layout-class", help="可选: layout-classification.json 路径")
    ap.add_argument("--out", help="输出 style-vector.json 路径(默认与 pptx 同目录)")
    args = ap.parse_args()

    sv = distill(args.pptx, args.layout_class)

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path(args.pptx).with_name("style-vector.json")
    sv.save(out_path)

    print(f"Source: {sv.source}")
    print(f"Canvas: {sv.canvas_w_px}px x {sv.canvas_h_px}px")
    print(f"\nPalette:")
    print(f"  primary:        {sv.palette.primary}")
    print(f"  accent:         {sv.palette.accent}")
    print(f"  text_primary:   {sv.palette.text_primary}")
    print(f"  text_secondary: {sv.palette.text_secondary}")
    print(f"\nFont ramp:")
    print(f"  title:    {sv.fonts.title}pt")
    print(f"  subtitle: {sv.fonts.subtitle}pt")
    print(f"  body:     {sv.fonts.body}pt")
    print(f"  caption:  {sv.fonts.caption}pt")
    print(f"  CN:       {sv.fonts.font_cn}")
    print(f"  EN:       {sv.fonts.font_en}")
    print(f"\nDensity:")
    print(f"  bullets/page avg: {sv.density.bullets_per_page_avg}")
    print(f"  image ratio:      {sv.density.image_ratio}")
    print(f"\nChrome:")
    print(f"  PART top-right:   {sv.chrome.show_part_top_right}")
    print(f"  page number:      {sv.chrome.show_page_number}")
    print(f"  brand footer:     {sv.chrome.show_brand_footer}")
    if sv.layout_prefs.counts:
        print(f"\nLayout preferences ({sv.layout_prefs.total_pages} pages):")
        for layout, n in sorted(sv.layout_prefs.counts.items(), key=lambda x: -x[1]):
            print(f"  {layout:20s}: {n:2d} ({sv.layout_prefs.bias(layout)*100:.1f}%)")

    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()

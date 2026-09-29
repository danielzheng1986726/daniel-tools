"""Export outline + layout-plan + matches to editable PPTX.

Design 映射:
- 1920 x 1080 设计稿 → 13.333" x 7.5" PPTX 16:9
- 1 design px = 6350 EMU
- 字体: Helvetica Neue (英) + PingFang SC (中)
- 颜色: Navy #1E3A5F, Orange #C2410C

Implemented layouts (12 types):
  cover / agenda / section-divider / content-body / data-table
  hero-definition / side-by-side / flow-strip / multi-grid
  chart-hero / formula-spotlight / case-showcase
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from src.core.outline_parser import Page, parse_outline


# ===== Design tokens =====

SW = 1920  # design width
SH = 1080  # design height
PX = 6350  # EMU per design px

PAD_X = 100
PAD_TOP = 100
PAD_BOTTOM = 80

C_NAVY = RGBColor(0x1E, 0x3A, 0x5F)
C_ORANGE = RGBColor(0xC2, 0x41, 0x0C)
C_INK = RGBColor(0x13, 0x15, 0x17)
C_INK2 = RGBColor(0x2E, 0x33, 0x38)
C_MUTED = RGBColor(0x6B, 0x72, 0x80)
C_RULE = RGBColor(0xD8, 0xD4, 0xCC)
C_PAPER = RGBColor(0xFF, 0xFF, 0xFF)
C_BG = RGBColor(0xFA, 0xFA, 0xF7)
C_LIGHT = RGBColor(0xF3, 0xF0, 0xE8)

FONT_CN = "PingFang SC"
FONT_EN = "Helvetica Neue"

# 品牌行/封面文字，示例值——换成你自己项目的讲义名。
# 注：slide_cover() 和 slide_agenda() 目前是围绕一份具体大纲写的示例渲染，
# 标题、副标题、目录卡片都是这里的常量，不会读 outline.md 里的实际标题/章节。
# 要接自己的项目，最简单是直接改这几个常量；更彻底的做法是把这两个函数
# 改成从 Page/DeckActions 里取标题和章节结构（跟其余 10 种 layout 的做法一致）。
DECK_FOOTER_TEXT = "示例技术讲义"
COVER_EYEBROW_TEXT = "■  TECHNICAL DECK & LECTURE NOTES"
COVER_TITLE_LINE1 = "示例技术讲义"
COVER_TITLE_LINE2 = "标题第二行"
COVER_SUBTITLE = "—— 副标题占位 · 全 N 章 · 总时长 N H"
AGENDA_CARDS = [
    ("01", "第一章示例标题", "示例小节·示例小节·示例小节", "03 → 10"),
    ("02", "第二章示例标题", "示例小节·示例小节", "11 → 20"),
    ("03", "第三章示例标题", "示例小节·示例小节", "21 → 30"),
    ("04", "第四章示例标题", "示例小节·示例小节", "31 → 40"),
    ("05", "第五章示例标题", "示例小节·示例小节", "41 → 50"),
    ("06", "第六章示例标题", "示例小节·示例小节", "51 → 60"),
]

# 18pt 红线：经验值，正文字号建议 ≥ 18pt，避免观众看不清（即 size_px ≥ 36）
MIN_SIZE_PX = 36  # = 18pt after pt_from_px conversion


def emu(px: float) -> int:
    return int(px * PX)


def pt_from_px(px: float) -> float:
    """Design px (at 1920 design width) → slide pt (at 960pt slide width)."""
    return px * 0.5


# ===== Drawing primitives =====


def add_rect(slide, x_px, y_px, w_px, h_px, fill=None, line=None, line_w=0):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(x_px), emu(y_px), emu(w_px), emu(h_px))
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w if line_w else 1)
    try:
        shape.shadow.inherit = False
    except Exception:
        pass
    return shape


def add_text(
    slide, x_px, y_px, w_px, h_px, text,
    size_px=MIN_SIZE_PX, color=C_INK, bold=False, font=None,
    align="left", vertical="top", line_spacing=1.3,
):
    tb = slide.shapes.add_textbox(emu(x_px), emu(y_px), emu(w_px), emu(h_px))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {
        "top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM,
    }.get(vertical, MSO_ANCHOR.TOP)
    p = tf.paragraphs[0]
    p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}.get(align, PP_ALIGN.LEFT)
    p.line_spacing = line_spacing
    run = p.add_run()
    run.text = text
    run.font.size = Pt(pt_from_px(max(size_px, MIN_SIZE_PX)))
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = font or FONT_CN
    return tb


def add_text_rich(
    slide, x_px, y_px, w_px, h_px, text,
    size_px=MIN_SIZE_PX, color=C_INK, font=None,
    align="left", vertical="top", line_spacing=1.3,
):
    """Like add_text but handles **bold** and numeric highlights via parse_inline."""
    tb = slide.shapes.add_textbox(emu(x_px), emu(y_px), emu(w_px), emu(h_px))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {
        "top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM,
    }.get(vertical, MSO_ANCHOR.TOP)
    p = tf.paragraphs[0]
    p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}.get(align, PP_ALIGN.LEFT)
    p.line_spacing = line_spacing
    for chunk, style in parse_inline(text):
        run = p.add_run()
        run.text = chunk
        run.font.size = Pt(pt_from_px(max(style.get("size_px", size_px), MIN_SIZE_PX)))
        run.font.color.rgb = style.get("color", color)
        run.font.bold = style.get("bold", False)
        run.font.name = font or FONT_CN
    return tb


def _ensure_pptx_compatible(path: Path) -> Path:
    """python-pptx 只认 BMP/GIF/JPEG/PNG/TIFF/WMF，遇到 WEBP 等格式先转 PNG。"""
    suffix = path.suffix.lower()
    if suffix in {".bmp", ".gif", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".wmf"}:
        return path
    try:
        from PIL import Image
        with Image.open(path) as im:
            converted = path.with_suffix(".png")
            im.save(converted, "PNG")
            return converted
    except Exception:
        return path  # 转失败就原样返回，让后面报错


def add_image(slide, path: str | Path, x_px, y_px, w_px, h_px, with_border=True):
    p = Path(path)
    if not p.exists():
        return None
    p = _ensure_pptx_compatible(p)
    if with_border:
        add_rect(slide, x_px, y_px, w_px, h_px, fill=C_PAPER, line=C_RULE, line_w=1)
    # Aspect-fit
    try:
        from PIL import Image
        with Image.open(p) as im:
            iw, ih = im.size
    except Exception:
        return None
    pad = 12 if with_border else 0
    avail_w = w_px - pad * 2
    avail_h = h_px - pad * 2
    scale = min(avail_w / iw, avail_h / ih)
    fw, fh = iw * scale, ih * scale
    fx = x_px + (w_px - fw) / 2
    fy = y_px + (h_px - fh) / 2
    return slide.shapes.add_picture(str(p), emu(fx), emu(fy), emu(fw), emu(fh))


# ===== Inline formatting (numeric highlights, bold) =====

NUM_PATTERN = re.compile(r"\d+[\d.,]*\s*(?:GPa|MPa|℃|°C|g/cm³|%|mm|km|m/min|kN|kg|m³)")


def parse_inline(text: str) -> list[tuple[str, dict]]:
    """Parse **bold** + numeric highlights into list of (text, style)."""
    parts: list[tuple[str, dict]] = []
    last = 0
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        before = text[last:m.start()]
        if before:
            parts.extend(_highlight_numbers(before))
        parts.append((m.group(1), {"bold": True}))
        last = m.end()
    rest = text[last:]
    if rest:
        parts.extend(_highlight_numbers(rest))
    return parts


def _highlight_numbers(s: str) -> list[tuple[str, dict]]:
    nums = NUM_PATTERN.findall(s)
    if not nums:
        return [(s, {})]
    out, rest = [], s
    for n in nums:
        i = rest.find(n)
        if i < 0:
            continue
        if rest[:i]:
            out.append((rest[:i], {}))
        out.append((n, {"color": C_ORANGE, "bold": True}))
        rest = rest[i + len(n):]
    if rest:
        out.append((rest, {}))
    return out


# ===== Chrome (header / footer) =====


def chrome_top_bottom(slide, page_num: int, total: int, chapter_label: str):
    add_text(slide, PAD_X, 48, 800, 40, chapter_label, size_px=MIN_SIZE_PX, color=C_NAVY, bold=True, font=FONT_EN)
    add_text(slide, SW - PAD_X - 400, 48, 400, 40, f"PART {page_num:02d} ／ {total}",
             size_px=MIN_SIZE_PX, color=C_MUTED, font=FONT_EN, align="right")
    add_text(slide, PAD_X, SH - 60, 800, 40, DECK_FOOTER_TEXT,
             size_px=MIN_SIZE_PX, color=C_MUTED, font=FONT_CN)
    add_text(slide, SW - PAD_X - 200, SH - 60, 200, 40, f"{page_num:02d} ／ {total}",
             size_px=MIN_SIZE_PX, color=C_INK2, font=FONT_EN, bold=True, align="right")


# ===== Layout renderers =====


def slide_cover(slide, page: Page, total: int):
    # Orange stripe
    add_rect(slide, 0, 0, 14, SH, fill=C_ORANGE)
    # Eyebrow
    add_text(slide, PAD_X + 50, PAD_TOP + 50, SW - 300, 40,
             COVER_EYEBROW_TEXT,
             size_px=MIN_SIZE_PX, color=C_INK, bold=True, font=FONT_EN)
    add_text(slide, SW - PAD_X - 500, PAD_TOP + 50, 500, 40,
             "LECTURE  ·  内部技术讲座",
             size_px=MIN_SIZE_PX, color=C_MUTED, align="right")
    add_rect(slide, PAD_X + 50, PAD_TOP + 110, SW - 2*PAD_X - 100, 1.5, fill=C_INK)
    # Big "01" watermark
    add_text(slide, SW - 700, 280, 700, 600, "01",
             size_px=420, color=RGBColor(0xEE, 0xE8, 0xDC), bold=True, font=FONT_EN, align="left")
    # Title 2 lines
    add_text(slide, PAD_X + 50, 340, 1400, 200, COVER_TITLE_LINE1,
             size_px=168, color=C_INK, bold=True)
    add_text(slide, PAD_X + 50, 530, 1400, 200, COVER_TITLE_LINE2,
             size_px=168, color=C_NAVY, bold=True)
    # Subtitle
    add_text(slide, PAD_X + 50, 770, 1400, 60,
             COVER_SUBTITLE,
             size_px=38, color=C_INK2)


def slide_section_divider(slide, page: Page, total: int):
    # Whole-slide dark background
    add_rect(slide, 0, 0, SW, SH, fill=C_NAVY)
    add_rect(slide, 0, 0, 14, SH, fill=C_ORANGE)
    # Chrome (white text on dark)
    add_text(slide, PAD_X + 30, 48, 800, 40, page.chapter[:30] or "CHAPTER",
             size_px=MIN_SIZE_PX, color=C_PAPER, bold=True, font=FONT_EN)
    # Massive chapter number (extracted from chapter string if possible)
    ch_match = re.search(r"第(\d+)章", page.chapter)
    ch_num = ch_match.group(1) if ch_match else "?"
    add_text(slide, PAD_X + 50, 240, 400, 60, "CHAPTER",
             size_px=MIN_SIZE_PX, color=RGBColor(0x80, 0x80, 0xA0), bold=True, font=FONT_EN, line_spacing=1.0)
    add_text(slide, PAD_X + 50, 290, 800, 400, ch_num.zfill(2),
             size_px=280, color=C_PAPER, bold=True, font=FONT_EN, line_spacing=0.9)
    # Section title (use page title)
    add_text(slide, PAD_X + 50, 700, 1400, 100, page.title,
             size_px=72, color=C_PAPER, bold=True)
    # Page number bottom
    add_text(slide, SW - PAD_X - 200, SH - 60, 200, 40, f"{page.page:02d} ／ {total}",
             size_px=MIN_SIZE_PX, color=C_PAPER, font=FONT_EN, bold=True, align="right")


def slide_data_table(slide, page: Page, total: int):
    chrome_top_bottom(slide, page.page, total, page.chapter[:30])
    # Title (no duplicate chapter eyebrow — chrome already has it)
    add_rect(slide, PAD_X, 200, 10, 10, fill=C_ORANGE)
    add_text(slide, PAD_X + 24, 175, 1500, 100, page.title, size_px=52, color=C_INK, bold=True)
    add_rect(slide, PAD_X, 300, 88, 4, fill=C_NAVY)

    # Table
    headers, rows = page.table_header, page.table_rows
    if not headers or not rows:
        return
    n_cols = len(headers)
    table_x, table_y = PAD_X, 400
    table_w = SW - 2 * PAD_X
    col_w = table_w // n_cols
    row_h = 72  # increased for 18pt text
    for c, h in enumerate(headers):
        add_rect(slide, table_x + c * col_w, table_y, col_w, row_h, fill=C_NAVY)
        add_text(slide, table_x + c * col_w + 12, table_y + 12, col_w - 24, row_h - 24, h,
                 size_px=MIN_SIZE_PX, color=C_PAPER, bold=True, align="center")
    for r, row in enumerate(rows):
        y = table_y + (r + 1) * row_h
        bg = C_LIGHT if r % 2 == 0 else C_PAPER
        for c, cell in enumerate(row):
            add_rect(slide, table_x + c * col_w, y, col_w, row_h, fill=bg, line=C_RULE, line_w=0.5)
            color = C_NAVY if c == 0 else C_INK2
            add_text(slide, table_x + c * col_w + 12, y + 12, col_w - 24, row_h - 24, cell,
                     size_px=MIN_SIZE_PX, color=color, bold=(c == 0), align="center")


def slide_content_body(slide, page: Page, total: int, img_path: str | None = None):
    chrome_top_bottom(slide, page.page, total, page.chapter[:30])
    # Title (no duplicate chapter eyebrow — chrome already has it)
    add_rect(slide, PAD_X, 200, 10, 10, fill=C_ORANGE)
    add_text(slide, PAD_X + 24, 175, 1500, 100, page.title, size_px=48, color=C_INK, bold=True)
    add_rect(slide, PAD_X, 300, 88, 4, fill=C_NAVY)

    # Left bullets
    body_y = 340
    body_h = SH - body_y - 100
    col_w = (SW - 2 * PAD_X - 80) // 2
    n_bullets = len(page.bullets)
    body_size = 40 if n_bullets <= 3 else 38 if n_bullets <= 5 else MIN_SIZE_PX

    btb = slide.shapes.add_textbox(emu(PAD_X), emu(body_y), emu(col_w), emu(body_h - 20))
    btf = btb.text_frame
    btf.word_wrap = True
    btf.margin_left = btf.margin_right = 0
    btf.margin_top = btf.margin_bottom = 0
    first = True
    for i, b in enumerate(page.bullets):
        if not first:
            sep = btf.add_paragraph()
            sep.line_spacing = 0.2
            sep_run = sep.add_run()
            sep_run.text = ""
            sep_run.font.size = Pt(pt_from_px(MIN_SIZE_PX))
        p = btf.paragraphs[0] if first else btf.add_paragraph()
        p.line_spacing = 1.3
        # Bullet number
        num_run = p.add_run()
        num_run.text = f"{i+1:02d}  "
        num_run.font.size = Pt(pt_from_px(body_size))
        num_run.font.color.rgb = C_NAVY
        num_run.font.bold = True
        num_run.font.name = FONT_EN
        # Bullet text with inline formatting
        for text, style in parse_inline(b):
            run = p.add_run()
            run.text = text
            run.font.size = Pt(pt_from_px(max(style.get("size_px", body_size), MIN_SIZE_PX)))
            run.font.color.rgb = style.get("color", C_INK2)
            run.font.bold = style.get("bold", False)
            run.font.name = FONT_CN
        first = False

    # Right image (if any)
    right_x = PAD_X + col_w + 80
    if img_path and Path(img_path).exists():
        add_image(slide, img_path, right_x, body_y, col_w, body_h - 40)
        if page.image_hint:
            add_text(slide, right_x, body_y + body_h - 38, col_w, 36,
                     page.image_hint[:60], size_px=MIN_SIZE_PX, color=C_MUTED, align="center")
    else:
        # Placeholder
        add_rect(slide, right_x, body_y, col_w, body_h - 40, fill=C_LIGHT, line=C_RULE, line_w=1)
        add_text(slide, right_x, body_y + (body_h - 40) // 2 - 20, col_w, 40,
                 "待选择配图", size_px=MIN_SIZE_PX, color=C_MUTED, align="center")


def _render_bullets_box(slide, x, y, w, h, bullets, size_px=MIN_SIZE_PX, start_num=1):
    """Reusable: render numbered bullets in a textbox region. Returns the textbox."""
    size_px = max(size_px, MIN_SIZE_PX)  # enforce 18pt floor
    btb = slide.shapes.add_textbox(emu(x), emu(y), emu(w), emu(h))
    btf = btb.text_frame
    btf.word_wrap = True
    btf.margin_left = btf.margin_right = 0
    btf.margin_top = btf.margin_bottom = 0
    first = True
    for i, b in enumerate(bullets):
        if not first:
            sep = btf.add_paragraph()
            sep.line_spacing = 0.2
            sep_run = sep.add_run()
            sep_run.text = ""
            sep_run.font.size = Pt(pt_from_px(MIN_SIZE_PX))
        p = btf.paragraphs[0] if first else btf.add_paragraph()
        p.line_spacing = 1.3
        num_run = p.add_run()
        num_run.text = f"{start_num + i:02d}  "
        num_run.font.size = Pt(pt_from_px(size_px))
        num_run.font.color.rgb = C_NAVY
        num_run.font.bold = True
        num_run.font.name = FONT_EN
        for text, style in parse_inline(b):
            run = p.add_run()
            run.text = text
            run.font.size = Pt(pt_from_px(max(style.get("size_px", size_px), MIN_SIZE_PX)))
            run.font.color.rgb = style.get("color", C_INK2)
            run.font.bold = style.get("bold", False)
            run.font.name = FONT_CN
        first = False
    return btb


def _title_block(slide, page: Page, total: int):
    """Reusable: render chrome + title + navy rule. Returns y position after title."""
    chrome_top_bottom(slide, page.page, total, page.chapter[:30])
    add_rect(slide, PAD_X, 200, 10, 10, fill=C_ORANGE)
    add_text(slide, PAD_X + 24, 175, 1500, 100, page.title, size_px=48, color=C_INK, bold=True)
    add_rect(slide, PAD_X, 300, 88, 4, fill=C_NAVY)
    return 340


# ---------- hero-definition ----------
# 左侧大图（60%）+ 右侧精炼文字（40%），适合概念深讲页

def slide_hero_definition(slide, page: Page, total: int, img_path: str | None = None):
    body_y = _title_block(slide, page, total)
    body_h = SH - body_y - 100
    total_w = SW - 2 * PAD_X

    # Image takes 55% on left
    img_w = int(total_w * 0.55)
    text_x = PAD_X + img_w + 40
    text_w = total_w - img_w - 40

    if img_path and Path(img_path).exists():
        add_image(slide, img_path, PAD_X, body_y, img_w, body_h - 40)
        if page.image_hint:
            add_text(slide, PAD_X, body_y + body_h - 38, img_w, 36,
                     page.image_hint[:60], size_px=MIN_SIZE_PX, color=C_MUTED, align="center")
    else:
        add_rect(slide, PAD_X, body_y, img_w, body_h - 40, fill=C_LIGHT, line=C_RULE, line_w=1)
        add_text(slide, PAD_X, body_y + (body_h - 40) // 2 - 20, img_w, 40,
                 "待选择配图", size_px=MIN_SIZE_PX, color=C_MUTED, align="center")

    # Right side: bullets
    n = len(page.bullets)
    bsize = 40 if n <= 3 else 38 if n <= 5 else MIN_SIZE_PX
    _render_bullets_box(slide, text_x, body_y, text_w, body_h - 50, page.bullets, size_px=bsize)


# ---------- side-by-side ----------
# 左右对比双列，适合 "vs / 对比" 页面

def slide_side_by_side(slide, page: Page, total: int, img_path: str | None = None):
    body_y = _title_block(slide, page, total)
    body_h = SH - body_y - 100
    total_w = SW - 2 * PAD_X
    col_w = (total_w - 60) // 2  # 60px gap

    # Split bullets into left/right halves
    bullets = page.bullets
    mid = (len(bullets) + 1) // 2
    left_b = bullets[:mid]
    right_b = bullets[mid:]

    # Column backgrounds
    add_rect(slide, PAD_X, body_y, col_w, body_h - 50, fill=C_PAPER, line=C_RULE, line_w=1)
    add_rect(slide, PAD_X + col_w + 60, body_y, col_w, body_h - 50, fill=C_LIGHT, line=C_RULE, line_w=1)

    # Orange top accent on left column
    add_rect(slide, PAD_X, body_y, col_w, 6, fill=C_ORANGE)
    # Navy top accent on right column
    add_rect(slide, PAD_X + col_w + 60, body_y, col_w, 6, fill=C_NAVY)

    n = max(len(left_b), len(right_b), 1)
    bsize = 40 if n <= 3 else 38 if n <= 4 else MIN_SIZE_PX
    inset = 24

    _render_bullets_box(slide, PAD_X + inset, body_y + 20, col_w - 2 * inset,
                        body_h - 90, left_b, size_px=bsize)
    _render_bullets_box(slide, PAD_X + col_w + 60 + inset, body_y + 20, col_w - 2 * inset,
                        body_h - 90, right_b, size_px=bsize, start_num=mid + 1)

    # Image at bottom center if available (span both columns, thin strip)
    if img_path and Path(img_path).exists():
        img_h = min(160, body_h // 3)
        img_y = SH - 80 - img_h
        add_image(slide, img_path, PAD_X, img_y, total_w, img_h, with_border=False)


# ---------- flow-strip ----------
# 横向步骤卡片 + 箭头，适合流程类页面

def slide_flow_strip(slide, page: Page, total: int, img_path: str | None = None):
    body_y = _title_block(slide, page, total)
    total_w = SW - 2 * PAD_X
    steps = page.bullets

    if not steps:
        slide_content_body(slide, page, total, img_path)
        return

    # Compute card geometry
    n = len(steps)
    gap = 24
    arrow_w = 32
    usable = total_w - (n - 1) * (gap + arrow_w)
    card_w = max(usable // n, 120)
    card_h = 220
    cards_y = body_y + 30

    for i, step in enumerate(steps):
        cx = PAD_X + i * (card_w + gap + arrow_w)
        # Card
        add_rect(slide, cx, cards_y, card_w, card_h, fill=C_PAPER, line=C_RULE, line_w=1)
        # Step number circle (square with navy fill, acts as badge)
        badge_sz = 48
        add_rect(slide, cx + card_w // 2 - badge_sz // 2, cards_y - 8, badge_sz, badge_sz, fill=C_NAVY)
        add_text(slide, cx + card_w // 2 - badge_sz // 2, cards_y - 4, badge_sz, badge_sz,
                 str(i + 1), size_px=MIN_SIZE_PX, color=C_PAPER, bold=True, font=FONT_EN, align="center", vertical="middle")
        # Step text (rich: handles **bold** + numeric highlights)
        add_text_rich(slide, cx + 12, cards_y + 55, card_w - 24, card_h - 65,
                      step, size_px=MIN_SIZE_PX, color=C_INK2, line_spacing=1.3)
        # Arrow between cards
        if i < n - 1:
            ax = cx + card_w + gap // 2
            add_text(slide, ax, cards_y + card_h // 2 - 20, arrow_w + gap, 40,
                     "→", size_px=40, color=C_ORANGE, bold=True, font=FONT_EN, align="center", vertical="middle")

    # Image below the strip if available
    img_y = cards_y + card_h + 40
    img_h = SH - img_y - 80
    if img_path and Path(img_path).exists() and img_h > 100:
        add_image(slide, img_path, PAD_X, img_y, total_w, img_h)
    elif page.image_hint:
        add_text(slide, PAD_X, img_y, total_w, 36,
                 page.image_hint[:80], size_px=MIN_SIZE_PX, color=C_MUTED, align="center")


# ---------- multi-grid ----------
# 多卡片网格（3 列），适合并列展示 3+ 项目

def slide_multi_grid(slide, page: Page, total: int, img_path: str | None = None):
    body_y = _title_block(slide, page, total)
    total_w = SW - 2 * PAD_X
    items = page.bullets

    if len(items) < 2:
        slide_content_body(slide, page, total, img_path)
        return

    # Decide grid: 2 cols if <=4 items, 3 cols if more
    n_cols = 3 if len(items) >= 3 else 2
    n_rows = (len(items) + n_cols - 1) // n_cols
    gap = 24
    card_w = (total_w - (n_cols - 1) * gap) // n_cols
    card_h = min(260, (SH - body_y - 120) // n_rows - gap)

    for idx, item in enumerate(items):
        row, col = divmod(idx, n_cols)
        cx = PAD_X + col * (card_w + gap)
        cy = body_y + row * (card_h + gap)
        # Card
        bg = C_PAPER if col % 2 == 0 else C_LIGHT
        add_rect(slide, cx, cy, card_w, card_h, fill=bg, line=C_RULE, line_w=1)
        # Left accent stripe
        accent = C_ORANGE if idx == 0 else C_NAVY
        add_rect(slide, cx, cy, 6, card_h, fill=accent)
        # Number
        add_text(slide, cx + 20, cy + 14, 80, 50,
                 f"{idx + 1:02d}", size_px=40, color=C_RULE, bold=True, font=FONT_EN)
        # Text (rich: handles **bold** + numeric highlights)
        add_text_rich(slide, cx + 20, cy + 60, card_w - 40, card_h - 80,
                      item, size_px=MIN_SIZE_PX, color=C_INK2, line_spacing=1.3)


# ---------- chart-hero ----------
# 大图主导（70%），文字注释（30%右侧），适合数据可视化页面

def slide_chart_hero(slide, page: Page, total: int, img_path: str | None = None):
    body_y = _title_block(slide, page, total)
    body_h = SH - body_y - 100
    total_w = SW - 2 * PAD_X

    # Image area: 65% width
    img_w = int(total_w * 0.65)
    note_x = PAD_X + img_w + 40
    note_w = total_w - img_w - 40

    if img_path and Path(img_path).exists():
        add_image(slide, img_path, PAD_X, body_y, img_w, body_h - 40)
    else:
        add_rect(slide, PAD_X, body_y, img_w, body_h - 40, fill=C_LIGHT, line=C_RULE, line_w=1)
        add_text(slide, PAD_X, body_y + (body_h - 40) // 2 - 20, img_w, 40,
                 "图表区域", size_px=MIN_SIZE_PX, color=C_MUTED, align="center")

    # Right side annotation bullets
    n = len(page.bullets)
    bsize = 40 if n <= 3 else 38 if n <= 4 else MIN_SIZE_PX
    # Navy accent line
    add_rect(slide, note_x, body_y, 4, body_h - 50, fill=C_NAVY)
    _render_bullets_box(slide, note_x + 16, body_y + 10, note_w - 16,
                        body_h - 70, page.bullets, size_px=bsize)

    if page.image_hint:
        add_text(slide, PAD_X, body_y + body_h - 38, img_w, 36,
                 page.image_hint[:60], size_px=MIN_SIZE_PX, color=C_MUTED, align="center")


# ---------- formula-spotlight ----------
# 居中大图/公式 + 上方标题 + 下方参数列表，适合化学结构 / 公式页面

def slide_formula_spotlight(slide, page: Page, total: int, img_path: str | None = None):
    body_y = _title_block(slide, page, total)
    total_w = SW - 2 * PAD_X

    # Center area for formula/structure image
    img_w = int(total_w * 0.50)
    img_h = 320
    img_x = PAD_X + (total_w - img_w) // 2

    if img_path and Path(img_path).exists():
        add_image(slide, img_path, img_x, body_y, img_w, img_h)
    else:
        add_rect(slide, img_x, body_y, img_w, img_h, fill=C_LIGHT, line=C_RULE, line_w=1)
        add_text(slide, img_x, body_y + img_h // 2 - 20, img_w, 40,
                 "化学结构式 / 公式", size_px=MIN_SIZE_PX, color=C_MUTED, align="center")

    # Bullets below the formula — full width, two-column if many bullets
    bullet_y = body_y + img_h + 30
    bullet_h = SH - bullet_y - 100
    n = len(page.bullets)
    bsize = 40 if n <= 3 else 38 if n <= 4 else MIN_SIZE_PX

    if n <= 4:
        _render_bullets_box(slide, PAD_X, bullet_y, total_w, bullet_h, page.bullets, size_px=bsize)
    else:
        mid = (n + 1) // 2
        col_w = (total_w - 40) // 2
        _render_bullets_box(slide, PAD_X, bullet_y, col_w, bullet_h, page.bullets[:mid], size_px=bsize)
        _render_bullets_box(slide, PAD_X + col_w + 40, bullet_y, col_w, bullet_h,
                            page.bullets[mid:], size_px=bsize, start_num=mid + 1)

    # Table below if available
    if page.has_table:
        # Render a mini inline table
        headers, rows = page.table_header, page.table_rows
        n_cols = len(headers)
        tw = min(total_w, n_cols * 320)
        tx = PAD_X + (total_w - tw) // 2
        ty = bullet_y + bullet_h + 10
        col_w_t = tw // n_cols
        rh = 60  # increased for 18pt text
        if ty + rh * (1 + len(rows)) < SH - 50:
            for c, h in enumerate(headers):
                add_rect(slide, tx + c * col_w_t, ty, col_w_t, rh, fill=C_NAVY)
                add_text(slide, tx + c * col_w_t + 6, ty + 10, col_w_t - 12, rh - 20,
                         h, size_px=MIN_SIZE_PX, color=C_PAPER, bold=True, align="center")
            for r, row in enumerate(rows[:6]):  # max 6 rows to fit
                ry = ty + (r + 1) * rh
                for c, cell in enumerate(row):
                    bg = C_LIGHT if r % 2 == 0 else C_PAPER
                    add_rect(slide, tx + c * col_w_t, ry, col_w_t, rh, fill=bg, line=C_RULE, line_w=0.5)
                    add_text(slide, tx + c * col_w_t + 6, ry + 10, col_w_t - 12, rh - 20,
                             cell, size_px=MIN_SIZE_PX, color=C_INK2, align="center")


# ---------- case-showcase ----------
# 应用案例卡片（左文右图或上文下卡），适合"XX 应用案例"页面

def slide_case_showcase(slide, page: Page, total: int, img_path: str | None = None):
    body_y = _title_block(slide, page, total)
    body_h = SH - body_y - 100
    total_w = SW - 2 * PAD_X
    items = page.bullets

    if len(items) <= 2:
        # Few items: large card layout (image left, text right like hero but with card styling)
        card_y = body_y
        card_h = body_h - 50
        img_w = int(total_w * 0.45)
        text_x = PAD_X + img_w + 30
        text_w = total_w - img_w - 30

        # Card background
        add_rect(slide, PAD_X, card_y, total_w, card_h, fill=C_PAPER, line=C_RULE, line_w=1)
        add_rect(slide, PAD_X, card_y, total_w, 6, fill=C_ORANGE)

        if img_path and Path(img_path).exists():
            add_image(slide, img_path, PAD_X + 16, card_y + 20, img_w - 32, card_h - 40, with_border=False)
        else:
            add_rect(slide, PAD_X + 16, card_y + 20, img_w - 32, card_h - 40, fill=C_LIGHT)

        bsize = 40 if len(items) <= 2 else MIN_SIZE_PX
        _render_bullets_box(slide, text_x, card_y + 20, text_w - 20, card_h - 40,
                            items, size_px=bsize)
    else:
        # Multiple items: horizontal card strip (each bullet = a case card)
        n = min(len(items), 4)
        gap = 20
        card_w = (total_w - (n - 1) * gap) // n
        card_h = body_h - 50

        for i in range(n):
            cx = PAD_X + i * (card_w + gap)
            add_rect(slide, cx, body_y, card_w, card_h, fill=C_PAPER, line=C_RULE, line_w=1)
            # Top accent
            accent = C_ORANGE if i == 0 else C_NAVY
            add_rect(slide, cx, body_y, card_w, 5, fill=accent)
            # Case number
            add_text(slide, cx + 14, body_y + 14, 60, 40,
                     f"0{i + 1}", size_px=MIN_SIZE_PX, color=C_RULE, bold=True, font=FONT_EN)
            # Case text (rich: handles **bold** + numeric highlights)
            add_text_rich(slide, cx + 14, body_y + 60, card_w - 28, card_h - 80,
                          items[i], size_px=MIN_SIZE_PX, color=C_INK2, line_spacing=1.3)

        # If there's an image, show it as a thin strip at the bottom
        if img_path and Path(img_path).exists():
            strip_h = 120
            strip_y = SH - 80 - strip_h
            add_image(slide, img_path, PAD_X, strip_y, total_w, strip_h, with_border=False)


def slide_agenda(slide, total: int):
    chrome_top_bottom(slide, 2, total, "INTRO")
    add_text(slide, PAD_X, 130, 1000, 40, "AGENDA · 课程安排", size_px=MIN_SIZE_PX, color=C_NAVY, bold=True, font=FONT_EN)
    add_text(slide, PAD_X, 180, 1500, 100, "课程安排与参考教材", size_px=64, color=C_INK, bold=True)
    add_rect(slide, PAD_X, 290, 88, 4, fill=C_NAVY)
    # 6 cards in 2 rows × 3 cols
    cards = AGENDA_CARDS
    card_w = (SW - 2 * PAD_X - 60) // 3
    card_h = 250
    gap = 30
    grid_x, grid_y = PAD_X, 360
    for i, (num, t, sub, pr) in enumerate(cards):
        row, col = divmod(i, 3)
        x = grid_x + col * (card_w + gap)
        y = grid_y + row * (card_h + gap)
        add_rect(slide, x, y, card_w, card_h, fill=C_PAPER, line=C_RULE, line_w=1)
        if i == 0:
            add_rect(slide, x, y, 6, card_h, fill=C_ORANGE)
        add_text(slide, x + 30, y + 18, 200, 60, num, size_px=52, color=C_RULE, bold=True, font=FONT_EN)
        add_text(slide, x + 30, y + 80, card_w - 60, 50, t, size_px=MIN_SIZE_PX, color=C_INK, bold=True)
        add_text(slide, x + 30, y + 130, card_w - 60, 80, sub, size_px=MIN_SIZE_PX, color=C_MUTED)
        add_rect(slide, x + 30, y + card_h - 56, card_w - 60, 1, fill=C_RULE)
        add_text(slide, x + 30, y + card_h - 44, card_w - 60, 36, f"PAGES {pr}",
                 size_px=MIN_SIZE_PX, color=C_MUTED, font=FONT_EN, bold=True)


# ===== Main builder =====


def render_slide(slide, page: Page, layout: str, total: int, img_path: str | None = None):
    """Dispatch by layout."""
    if layout == "cover" or page.page == 1:
        slide_cover(slide, page, total)
    elif layout == "agenda" or page.page == 2:
        slide_agenda(slide, total)
    elif layout == "section-divider":
        slide_section_divider(slide, page, total)
    elif layout == "data-table" and page.has_table:
        slide_data_table(slide, page, total)
    elif layout == "hero-definition":
        slide_hero_definition(slide, page, total, img_path)
    elif layout == "side-by-side":
        slide_side_by_side(slide, page, total, img_path)
    elif layout == "flow-strip":
        slide_flow_strip(slide, page, total, img_path)
    elif layout == "multi-grid":
        slide_multi_grid(slide, page, total, img_path)
    elif layout == "chart-hero":
        slide_chart_hero(slide, page, total, img_path)
    elif layout == "formula-spotlight":
        slide_formula_spotlight(slide, page, total, img_path)
    elif layout == "case-showcase":
        slide_case_showcase(slide, page, total, img_path)
    else:
        slide_content_body(slide, page, total, img_path)


def build_pptx(
    pages: list[Page],
    layout_plan: dict[int, str],
    image_paths: dict[int, str | None],
    out_path: str | Path,
):
    """Build PPTX from outline + layout-plan + per-page image paths.

    Args:
        pages: parse_outline output
        layout_plan: {page_num: layout_key}
        image_paths: {page_num: absolute path to top-1 image or None}
        out_path: output PPTX path
    """
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    total = len(pages)
    for page in pages:
        slide = prs.slides.add_slide(blank)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = C_BG

        layout = layout_plan.get(page.page, "content-body")
        img = image_paths.get(page.page)
        render_slide(slide, page, layout, total, img)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path


if __name__ == "__main__":
    import sys
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "examples/demo-deck")

    pages = parse_outline(base / "outline.md")

    # Load layout plan
    layout_plan = {}
    layout_path = base / "layout-plan.json"
    if layout_path.exists():
        d = json.loads(layout_path.read_text(encoding="utf-8"))
        layout_plan = {int(k): v["layout"] for k, v in d.items() if k.isdigit()}

    # Load matches → image paths
    image_paths: dict[int, str | None] = {}
    matches_path = base / "matches.json"
    if matches_path.exists():
        matches_data = json.loads(matches_path.read_text(encoding="utf-8"))
        for entry in matches_data:
            pn = entry["page"]
            cands = entry.get("candidates", [])
            if cands:
                # Top-1 candidate. file 字段已是 "extracted/ch1/xxx.png"，直接 base / rel 即可
                rel = cands[0]["file"]
                abs_path = base / rel
                image_paths[pn] = str(abs_path) if abs_path.exists() else None
            else:
                image_paths[pn] = None

    out_path = base / "output.pptx"
    build_pptx(pages, layout_plan, image_paths, out_path)
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"✓ Built {out_path} ({size_mb:.1f} MB, {len(pages)} pages)")

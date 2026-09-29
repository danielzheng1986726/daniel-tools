"""Render actions.json → HTML deck 预览。

PPTAgent 思路:同一份 actions 既能 → PPTX,也能 → HTML。
HTML 用来在审改面板里 inline 预览,专家审起来比看文本直观得多。

每页一个 1280×720 设计稿(跟 reference deck 一致),
容器缩放到 viewport。
"""
from __future__ import annotations

import argparse
import base64
import json
from html import escape
from pathlib import Path

from src.core.actions_schema import DeckActions, SlideActions
from src.core.style_vector import StyleVector


# 页眉/页脚品牌行文字，示例值——换成你自己项目的讲义名
DECK_FOOTER_TEXT = "示例技术讲义"
COVER_EYEBROW_TEXT = "■ TECHNICAL DECK &nbsp; · &nbsp; LECTURE"


# ===== CSS =====
# 把 style_vector 的颜色 / 字号映射成 CSS 变量,所有 layout 都用这套 token

def make_css(sv: StyleVector) -> str:
    return f"""
:root {{
  --primary: {sv.palette.primary};
  --accent: {sv.palette.accent};
  --text: {sv.palette.text_primary};
  --text2: {sv.palette.text_secondary};
  --text3: {sv.palette.text_emphasis};
  --bg: #FAFAF7;
  --bg-card: {sv.palette.bg_card};
  --paper: #FFFFFF;
  --rule: #D8D4CC;

  --font-cn: "{sv.fonts.font_cn}", "PingFang SC", sans-serif;
  --font-en: "{sv.fonts.font_en}", "Helvetica Neue", sans-serif;
  --font-default: var(--font-cn);

  --title-pt: {sv.fonts.title}pt;
  --subtitle-pt: {sv.fonts.subtitle}pt;
  --body-pt: {sv.fonts.body}pt;
  --caption-pt: {sv.fonts.caption}pt;

  --canvas-w: {sv.canvas_w_px}px;
  --canvas-h: {sv.canvas_h_px}px;
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: var(--font-default);
  background: var(--bg);
  color: var(--text);
}}

.deck {{
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
}}

.slide {{
  position: relative;
  width: var(--canvas-w);
  height: var(--canvas-h);
  background: var(--paper);
  margin: 0 auto;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
  overflow: hidden;
  font-size: var(--body-pt);
}}

/* Chrome: 顶部 chapter eyebrow + part nav,底部品牌 + 页码 */
.chrome-eyebrow {{
  position: absolute;
  top: 32px; left: 66px;
  font-size: var(--caption-pt);
  color: var(--text2);
  letter-spacing: 1px;
}}
.chrome-part {{
  position: absolute;
  top: 32px; right: 66px;
  font-size: var(--caption-pt);
  color: var(--text2);
  letter-spacing: 1px;
}}
.chrome-footer {{
  position: absolute;
  bottom: 22px; left: 66px;
  font-size: var(--caption-pt);
  color: var(--text2);
}}
.chrome-pn {{
  position: absolute;
  bottom: 22px; right: 66px;
  font-size: var(--caption-pt);
  color: var(--text2);
}}

/* 标题区(大部分 layout 共用) */
.s-title {{
  position: absolute;
  top: 86px; left: 66px;
  width: 1080px;
  font-size: var(--title-pt);
  font-weight: 600;
  color: var(--text3);
  letter-spacing: -.5px;
  line-height: 1.2;
}}
.s-orange-dot {{
  position: absolute;
  top: 153px; left: 66px;
  width: 6px; height: 6px;
  background: var(--accent);
  border-radius: 50%;
}}
.s-rule {{
  position: absolute;
  top: 226px; left: 66px;
  width: 58px; height: 2px;
  background: var(--accent);
}}

/* content-body / hero-definition: 左文右图 */
.body-left {{ position: absolute; top: 253px; left: 66px; width: 546px; }}
.body-right-img {{
  position: absolute; top: 253px; left: 666px;
  width: 546px; height: 333px;
  border: 1px solid var(--rule);
  display: flex; align-items: center; justify-content: center;
  background: var(--paper);
}}
.body-right-img img {{ max-width: 100%; max-height: 100%; }}
.body-right-img.placeholder {{
  background: #FFF4E5; border: 1px dashed var(--accent); color: var(--accent);
  font-size: var(--caption-pt); padding: 12px; text-align: center;
}}
.body-caption {{
  position: absolute; top: 592px; left: 666px;
  width: 546px;
  font-size: var(--caption-pt);
  color: var(--text2);
}}

.bullets {{ margin: 0; padding: 0; list-style: none; }}
.bullets li {{
  margin-bottom: 12px;
  padding-left: 28px;
  position: relative;
  font-size: var(--body-pt);
  line-height: 1.5;
  color: var(--text);
}}
.bullets li::before {{
  content: counter(b, decimal-leading-zero);
  counter-increment: b;
  position: absolute; left: 0; top: 0;
  font-size: var(--caption-pt);
  color: var(--primary);
  font-weight: 600;
}}
.bullets {{ counter-reset: b; }}

.hero-emphasis {{
  font-size: 18pt;
  font-weight: 600;
  color: var(--text3);
  margin-bottom: 18px;
  line-height: 1.3;
}}
.hero-emphasis em {{
  color: var(--accent);
  font-style: normal;
  font-weight: 700;
}}

/* Cover 页 */
.cover {{
  background: linear-gradient(180deg, var(--paper) 0%, #F8F5EE 100%);
}}
.cover-eyebrow {{
  position: absolute; top: 100px; left: 100px;
  width: 1080px;
  font-size: var(--caption-pt); color: var(--text2);
  letter-spacing: 2px;
}}
.cover-rule {{
  position: absolute; top: 140px; left: 100px;
  width: 1080px; height: 1px; background: var(--rule);
}}
.cover-bignum {{
  position: absolute; top: 186px; right: 100px;
  font-size: 80pt; color: var(--rule);
  font-weight: 700;
  font-family: var(--font-en);
}}
.cover-title {{
  position: absolute; top: 226px; left: 100px;
  width: 933px;
  font-size: 56pt; font-weight: 700; color: var(--text3);
  line-height: 1.15;
}}
.cover-subtitle {{
  position: absolute; top: 513px; left: 100px;
  width: 933px;
  font-size: var(--subtitle-pt);
  color: var(--text2);
}}

/* Section divider */
.section-divider {{ background: var(--paper); }}
.divider-bignum {{
  position: absolute; top: 200px; left: 100px;
  font-size: 200pt; line-height: 1;
  font-weight: 700; color: var(--rule);
  font-family: var(--font-en);
}}
.divider-eyebrow {{
  position: absolute; top: 200px; right: 100px;
  width: 600px;
  font-size: var(--caption-pt); color: var(--primary);
  letter-spacing: 3px; text-transform: uppercase;
}}
.divider-title {{
  position: absolute; top: 240px; right: 100px;
  width: 600px;
  font-size: 36pt; font-weight: 600; color: var(--text3);
  line-height: 1.2;
}}

/* Agenda */
.agenda-grid {{
  position: absolute; top: 233px; left: 66px;
  width: 1146px;
  display: grid; grid-template-columns: 1fr 1fr 1fr;
  gap: 21px;
}}
.agenda-card {{
  background: var(--bg-card);
  border-left: 4px solid var(--primary);
  padding: 18px 20px;
  height: 186px;
  display: flex; flex-direction: column;
}}
.agenda-card .num {{
  font-size: 26pt; color: var(--primary); font-weight: 700;
  font-family: var(--font-en);
}}
.agenda-card .title {{ font-size: 16pt; color: var(--text3); margin-top: 8px; }}
.agenda-card .desc {{ font-size: var(--caption-pt); color: var(--text2); margin-top: 4px; flex: 1; }}
.agenda-card .pages {{ font-size: var(--caption-pt); color: var(--text2); }}

/* Data table */
.data-table {{
  position: absolute; top: 253px; left: 66px;
  width: 1146px; border-collapse: collapse; font-size: var(--body-pt);
}}
.data-table th, .data-table td {{
  border: 1px solid var(--rule);
  padding: 8px 14px;
  text-align: left;
  font-weight: 400;
}}
.data-table th {{ background: var(--bg-card); color: var(--primary); font-weight: 600; }}

/* Side-by-side */
.sbs {{
  position: absolute; top: 253px; left: 66px;
  width: 1146px;
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 24px;
}}
.sbs-col {{ background: var(--bg-card); padding: 18px; }}
.sbs-col .label {{ font-size: 14pt; color: var(--primary); font-weight: 600; margin-bottom: 12px; }}

/* Multi-grid */
.mg {{
  position: absolute; top: 253px; left: 66px;
  width: 1146px;
  display: grid; grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}}
.mg-item {{
  border: 1px solid var(--rule);
  padding: 16px;
  font-size: var(--caption-pt);
}}
.mg-item .num {{ font-size: 18pt; color: var(--primary); }}

/* Flow strip */
.flow {{
  position: absolute; top: 253px; left: 66px;
  width: 1146px;
}}
.flow-row {{
  display: grid; grid-template-columns: 60px 1fr;
  align-items: start;
  margin-bottom: 14px;
}}
.flow-row .step-num {{
  font-size: 24pt; font-weight: 700; color: var(--accent);
  font-family: var(--font-en);
}}
.flow-row .step-body .label {{ font-weight: 600; color: var(--text3); }}
.flow-row .step-body .detail {{ color: var(--text2); font-size: var(--caption-pt); margin-top: 2px; }}

/* Compare action 用在 side-by-side */
.compare {{
  position: absolute; top: 253px; left: 66px;
  width: 1146px;
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 24px;
}}
.compare .col {{ background: var(--bg-card); padding: 18px; }}
.compare .col .label {{
  font-size: 14pt; color: var(--primary);
  font-weight: 600; margin-bottom: 12px;
}}
.compare .col .item {{ margin-bottom: 8px; font-size: var(--body-pt); }}

/* Review note (contributor 留的标记) */
.review-note {{
  position: absolute; bottom: 60px; left: 66px;
  width: 1146px;
  background: #FFF4E5;
  border-left: 3px solid var(--accent);
  padding: 8px 12px;
  font-size: var(--caption-pt);
  color: var(--accent);
}}

/* 缩略图模式(给 list view 用) */
.thumb-mode .slide {{
  transform: scale(0.25);
  transform-origin: top left;
  margin-bottom: -540px; /* 720 - 720*0.25 */
}}
"""


# ===== Render helpers =====

def _esc(s: str | None) -> str:
    if s is None:
        return ""
    return escape(str(s))


def _img_as_data_uri(path: str) -> str | None:
    """把图片读成 data URI,这样 HTML 可以独立工作不依赖文件系统。"""
    try:
        p = Path(path)
        if not p.exists():
            return None
        data = p.read_bytes()
        ext = p.suffix.lstrip(".").lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "svg": "image/svg+xml"}.get(ext, "image/png")
        b64 = base64.b64encode(data).decode()
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def _find(slide: SlideActions, type_: str) -> dict | None:
    return slide.find(type_)


def _find_all(slide: SlideActions, type_: str) -> list[dict]:
    return [a for a in slide.actions if a.get("type") == type_]


def _chapter_num(slide: SlideActions) -> str:
    import re
    m = re.search(r"第\s*(\d+)\s*章", slide.chapter or "")
    return f"{int(m.group(1)):02d}" if m else ""


def render_inline(text: str) -> str:
    """Markdown 内联渲染:**bold** + 数字单位高亮。"""
    import re
    t = _esc(text)
    # **bold** → <strong>
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    # 数字+单位高亮(GPa/MPa/℃/°C/g/cm³/%/mm)
    t = re.sub(
        r"(\d+[\d.,]*\s*(?:GPa|MPa|℃|°C|g/cm³|%|mm|km|m/min|kN|kg|m³))",
        r'<em style="color:var(--accent);font-style:normal;font-weight:600">\1</em>',
        t,
    )
    return t


# ===== Per-layout render =====

def render_cover(slide: SlideActions, total: int) -> str:
    title = _find(slide, "title")
    title_txt = _esc(title["text"] if title else "")
    subtitle = _esc(title.get("subtitle", "") if title else "")
    return f"""
    <div class="slide cover" data-page="{slide.page}">
      <div class="cover-eyebrow">{COVER_EYEBROW_TEXT}</div>
      <div class="cover-rule"></div>
      <div class="cover-bignum">01</div>
      <div class="cover-title">{title_txt}</div>
      <div class="cover-subtitle">{subtitle}</div>
    </div>
    """


def render_section_divider(slide: SlideActions, total: int) -> str:
    title = _find(slide, "title")
    title_txt = _esc(title["text"] if title else "")
    eyebrow = _find(slide, "eyebrow")
    ch_num = (eyebrow.get("chapter_num") if eyebrow else "") or _chapter_num(slide)
    ch_name = _esc(eyebrow.get("text", "") if eyebrow else slide.chapter)
    return f"""
    <div class="slide section-divider" data-page="{slide.page}">
      <div class="chrome-part">PART {slide.page:02d} ／ {total}</div>
      <div class="chrome-footer">{DECK_FOOTER_TEXT}</div>
      <div class="chrome-pn">{slide.page:02d} ／ {total}</div>
      <div class="divider-bignum">{ch_num or '00'}</div>
      <div class="divider-eyebrow">{ch_name}</div>
      <div class="divider-title">{title_txt}</div>
    </div>
    """


def render_agenda(slide: SlideActions, total: int) -> str:
    title = _find(slide, "title")
    bullets = _find(slide, "bullets")
    items = bullets.get("items", [])[:6] if bullets else []
    cards_html = ""
    for i, item in enumerate(items, 1):
        cards_html += f"""
        <div class="agenda-card">
          <div class="num">{i:02d}</div>
          <div class="title">{_esc(item)[:20]}</div>
        </div>
        """
    return f"""
    <div class="slide" data-page="{slide.page}">
      {_chrome(slide, total)}
      <div class="s-title">AGENDA · {_esc(title['text'] if title else '')}</div>
      <div class="s-orange-dot" style="top:160px"></div>
      <div class="s-rule"></div>
      <div class="agenda-grid">{cards_html}</div>
    </div>
    """


def _chrome(slide: SlideActions, total: int) -> str:
    """通用 chrome:eyebrow / part / footer / pn。"""
    eyebrow = _find(slide, "eyebrow")
    ch_name = _esc(eyebrow.get("text", "") if eyebrow else slide.chapter)
    return f"""
      <div class="chrome-eyebrow">{ch_name[:40]}</div>
      <div class="chrome-part">PART {slide.page:02d} ／ {total}</div>
      <div class="chrome-footer">{DECK_FOOTER_TEXT}</div>
      <div class="chrome-pn">{slide.page:02d} ／ {total}</div>
    """


def render_data_table(slide: SlideActions, total: int) -> str:
    title = _find(slide, "title")
    table = _find(slide, "table")
    table_html = ""
    if table:
        headers = table.get("header", [])
        rows = table.get("rows", [])
        thead = "".join(f"<th>{_esc(h)}</th>" for h in headers)
        tbody = ""
        for r in rows:
            tbody += "<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in r) + "</tr>"
        table_html = f"""
          <table class="data-table">
            <thead><tr>{thead}</tr></thead>
            <tbody>{tbody}</tbody>
          </table>
        """
    return f"""
    <div class="slide" data-page="{slide.page}">
      {_chrome(slide, total)}
      <div class="s-title">{_esc(title['text'] if title else '')}</div>
      <div class="s-orange-dot"></div>
      <div class="s-rule"></div>
      {table_html}
    </div>
    """


def render_content_body(slide: SlideActions, total: int) -> str:
    """content-body / case-showcase / formula-spotlight / multi-grid 通用兜底:左文右图。"""
    title = _find(slide, "title")
    bullets = _find(slide, "bullets")
    text = _find(slide, "text")
    image = _find(slide, "image")
    placeholder = _find(slide, "image_placeholder")

    left_html = ""
    if text and text.get("text"):
        left_html += f'<div class="hero-emphasis">{render_inline(text["text"])}</div>'
    if bullets and bullets.get("items"):
        lis = "".join(f"<li>{render_inline(b)}</li>" for b in bullets["items"][:5])
        left_html += f'<ol class="bullets">{lis}</ol>'

    if image and image.get("path"):
        uri = _img_as_data_uri(image["path"])
        caption = _esc(image.get("caption", ""))
        if uri:
            right_html = f'<div class="body-right-img"><img src="{uri}"></div>'
        else:
            right_html = f'<div class="body-right-img placeholder">图加载失败<br>{_esc(image["path"][-40:])}</div>'
        cap_html = f'<div class="body-caption">{caption}</div>' if caption else ""
    elif placeholder:
        note = _esc(placeholder.get("note", "需要新图"))
        cap = _esc(placeholder.get("caption", ""))
        right_html = f'<div class="body-right-img placeholder">⚠️ {note}<br><small>{cap}</small></div>'
        cap_html = ""
    else:
        right_html = ""
        cap_html = ""

    review_note = _find(slide, "review_note")
    note_html = f'<div class="review-note">📝 {_esc(review_note["text"])}</div>' if review_note else ""

    return f"""
    <div class="slide" data-page="{slide.page}">
      {_chrome(slide, total)}
      <div class="s-title">{_esc(title['text'] if title else '')}</div>
      <div class="s-orange-dot"></div>
      <div class="s-rule"></div>
      <div class="body-left">{left_html}</div>
      {right_html}
      {cap_html}
      {note_html}
    </div>
    """


def render_flow_strip(slide: SlideActions, total: int) -> str:
    title = _find(slide, "title")
    steps = _find_all(slide, "flow_step")
    rows = ""
    for s in steps[:5]:
        rows += f"""
        <div class="flow-row">
          <div class="step-num">{s.get('index', 0):02d}</div>
          <div class="step-body">
            <div class="label">{_esc(s.get('label', ''))}</div>
            <div class="detail">{render_inline(s.get('detail', ''))}</div>
          </div>
        </div>
        """
    image = _find(slide, "image")
    img_html = ""
    if image and image.get("path"):
        uri = _img_as_data_uri(image["path"])
        if uri:
            img_html = f'<div style="position:absolute;bottom:60px;right:66px;width:400px;height:200px;border:1px solid var(--rule);display:flex;align-items:center;justify-content:center"><img src="{uri}" style="max-width:100%;max-height:100%"></div>'
    return f"""
    <div class="slide" data-page="{slide.page}">
      {_chrome(slide, total)}
      <div class="s-title">{_esc(title['text'] if title else '')}</div>
      <div class="s-orange-dot"></div>
      <div class="s-rule"></div>
      <div class="flow">{rows}</div>
      {img_html}
    </div>
    """


def render_side_by_side(slide: SlideActions, total: int) -> str:
    title = _find(slide, "title")
    compare = _find(slide, "compare")
    if compare:
        left_items = compare.get("left_items", [])
        right_items = compare.get("right_items", [])
        left_li = "".join(f'<div class="item">{render_inline(x)}</div>' for x in left_items[:5])
        right_li = "".join(f'<div class="item">{render_inline(x)}</div>' for x in right_items[:5])
        body = f"""
        <div class="compare">
          <div class="col">
            <div class="label">{_esc(compare.get('left_label', 'A'))}</div>
            {left_li}
          </div>
          <div class="col">
            <div class="label">{_esc(compare.get('right_label', 'B'))}</div>
            {right_li}
          </div>
        </div>
        """
    else:
        # 兜底:bullets 平分两栏
        bullets = _find(slide, "bullets")
        items = bullets.get("items", []) if bullets else []
        half = len(items) // 2 or len(items)
        left_li = "".join(f'<div class="item">{render_inline(x)}</div>' for x in items[:half])
        right_li = "".join(f'<div class="item">{render_inline(x)}</div>' for x in items[half:])
        body = f"""
        <div class="compare">
          <div class="col"><div class="label">A</div>{left_li}</div>
          <div class="col"><div class="label">B</div>{right_li}</div>
        </div>
        """
    return f"""
    <div class="slide" data-page="{slide.page}">
      {_chrome(slide, total)}
      <div class="s-title">{_esc(title['text'] if title else '')}</div>
      <div class="s-orange-dot"></div>
      <div class="s-rule"></div>
      {body}
    </div>
    """


LAYOUT_RENDERERS = {
    "cover": render_cover,
    "section-divider": render_section_divider,
    "agenda": render_agenda,
    "data-table": render_data_table,
    "flow-strip": render_flow_strip,
    "side-by-side": render_side_by_side,
}


def render_slide_html(slide: SlideActions, total: int) -> str:
    renderer = LAYOUT_RENDERERS.get(slide.layout, render_content_body)
    return renderer(slide, total)


# ===== Deck-level =====

def render_deck_html(
    deck: DeckActions,
    style_vector: StyleVector,
    title: str = "AI TechDeck",
    only_pages: list[int] | None = None,
) -> str:
    css = make_css(style_vector)
    total = len(deck.slides)
    slides_html = []
    for s in deck.slides:
        if only_pages and s.page not in only_pages:
            continue
        slides_html.append(render_slide_html(s, total))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{_esc(title)}</title>
<style>{css}</style>
</head>
<body>
<div class="deck">
{''.join(slides_html)}
</div>
</body>
</html>
"""


def render_single_slide_html(
    slide: SlideActions,
    style_vector: StyleVector,
    total: int,
    fit_width: bool = True,
) -> str:
    """单页 HTML(给审改面板 inline 嵌入用)。

    fit_width=True:让 1280px 设计稿缩放到 iframe 宽度,适合 inline 预览。
    """
    css = make_css(style_vector)
    body = render_slide_html(slide, total)
    extra = ""
    if fit_width:
        extra = """
        body { margin: 0; overflow: hidden; }
        .deck { padding: 0; display: block; }
        .deck .slide {
          transform-origin: top left;
          transform: scale(var(--scale, 1));
          margin: 0 auto;
        }
        """
        body = body + """
<script>
function updateScale() {
  const slide = document.querySelector('.slide');
  if (!slide) return;
  const w = window.innerWidth;
  const designW = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--canvas-w'));
  const designH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--canvas-h'));
  const scale = w / designW;
  document.documentElement.style.setProperty('--scale', scale);
  document.body.style.height = (designH * scale) + 'px';
}
updateScale();
window.addEventListener('resize', updateScale);
</script>
"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><style>{css}{extra}</style></head>
<body><div class="deck">{body}</div></body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="Render actions → HTML deck")
    ap.add_argument("--base", default="examples/demo-deck")
    ap.add_argument("--actions", help="actions.json 路径(默认 base/actions.json)")
    ap.add_argument("--style", help="style-vector.json 路径(默认 base/style-vector.json)")
    ap.add_argument("--out", help="输出 HTML(默认 base/output-preview.html)")
    ap.add_argument("--pages", help="只渲染这几页(逗号分隔),省略全部")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    actions_path = Path(args.actions) if args.actions else base / "actions.json"
    style_path = Path(args.style) if args.style else base / "style-vector.json"
    out_path = Path(args.out) if args.out else base / "output-preview.html"

    deck = DeckActions.load(actions_path)
    style_vector = StyleVector.load(style_path) if style_path.exists() else StyleVector.default()

    only = None
    if args.pages:
        only = [int(x) for x in args.pages.split(",") if x.strip().isdigit()]

    html = render_deck_html(deck, style_vector, only_pages=only)
    out_path.write_text(html, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"Wrote {len(deck.slides) if not only else len(only)} slides → {out_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()

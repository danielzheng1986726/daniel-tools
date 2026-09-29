#!/usr/bin/env python3
"""小红书知识卡片渲染器 — 自用版

Markdown → 1080x1440 PNG 卡片（封面 + 内容页），用 Playwright 截图。
按 --- 分页，YAML 头定义封面。

用法:
    python render_xhs_cards.py notes.md -o /tmp/xhs-cards/
    python render_xhs_cards.py notes.md -o /tmp/xhs-cards/ --accent "#4F46E5"

依赖:
    pip install pyyaml playwright && playwright install chromium
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    import yaml
    from playwright.async_api import async_playwright, Browser
except ImportError as e:
    print(f"缺少依赖: {e}\npip install pyyaml playwright && playwright install chromium")
    sys.exit(1)

W, H = 1080, 1440

PALETTE = {
    "accent":    "#4338CA",
    "accent2":   "#6366F1",
    "highlight": "#FEF08A",
    "bg":        "#F8F7F4",
    "text":      "#1E1B18",
    "muted":     "#78716C",
    "card":      "#FFFFFF",
    "tag_bg":    "#EEF2FF",
    "tag_text":  "#4338CA",
}


def parse_md(path: str) -> dict:
    raw = Path(path).read_text("utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
    meta, body = {}, raw
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        body = raw[m.end():]
    return {"meta": meta, "body": body.strip()}


def split_pages(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n---+\n", body) if p.strip()]


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    out = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
            continue
        hm = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if hm:
            if in_list:
                out.append("</ul>")
                in_list = False
            lvl = len(hm.group(1))
            out.append(f"<h{lvl}>{inline(hm.group(2))}</h{lvl}>")
            continue
        if stripped.startswith("> "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<blockquote>{inline(stripped[2:])}</blockquote>')
            continue
        lm = re.match(r"^[-*]\s+(.+)$", stripped)
        if lm:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(lm.group(1))}</li>")
            continue
        olm = re.match(r"^\d+\.\s+(.+)$", stripped)
        if olm:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(olm.group(1))}</li>")
            continue
        if re.match(r"^(#[\w一-龥]+\s*)+$", stripped):
            if in_list:
                out.append("</ul>")
                in_list = False
            tags = re.findall(r"#([\w一-龥]+)", stripped)
            tag_html = "".join(f'<span class="tag">#{t}</span>' for t in tags)
            out.append(f'<div class="tags">{tag_html}</div>')
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _title_font_size(title: str) -> int:
    n = len(title)
    if n <= 7:
        return 96
    if n <= 10:
        return 80
    if n <= 14:
        return 68
    return 58


def cover_html(meta: dict, pal: dict) -> str:
    title = meta.get("title", "标题")
    subtitle = meta.get("subtitle", "")
    emoji = meta.get("emoji", "")
    fs = _title_font_size(title)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700;900&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{W}px; height:{H}px; overflow:hidden;
       font-family:'Noto Sans SC','PingFang SC','Hiragino Sans GB',sans-serif; }}
.cover {{
    width:{W}px; height:{H}px;
    background: linear-gradient(145deg, {pal['accent']} 0%, {pal['accent2']} 100%);
    display:flex; flex-direction:column; justify-content:center; align-items:center;
    padding: 80px 90px;
    position: relative;
}}
.cover::before {{
    content:''; position:absolute;
    top:60px; left:60px; right:60px; bottom:60px;
    border: 2px solid rgba(255,255,255,0.15);
    border-radius: 32px;
}}
.emoji {{ font-size:100px; margin-bottom:40px; }}
.title {{
    font-weight:900; font-size:{fs}px; line-height:1.3;
    color:#fff; text-align:center;
    letter-spacing: -1px;
    max-width: 900px;
}}
.subtitle {{
    font-weight:400; font-size:42px; color:rgba(255,255,255,0.75);
    margin-top:40px; text-align:center;
    letter-spacing: 2px;
}}
</style></head><body>
<div class="cover">
    {"<div class='emoji'>" + emoji + "</div>" if emoji else ""}
    <div class="title">{title}</div>
    {"<div class='subtitle'>" + subtitle + "</div>" if subtitle else ""}
</div>
</body></html>"""


def card_html(content: str, page: int, total: int, pal: dict) -> str:
    body = md_to_html(content)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:{W}px; height:{H}px; overflow:hidden;
       font-family:'Noto Sans SC','PingFang SC','Hiragino Sans GB',sans-serif;
       background:{pal['bg']}; }}
.page {{
    position:absolute;
    top:40px; left:40px; right:40px; bottom:40px;
    background:{pal['card']};
    border-radius:28px;
    padding: 80px 76px 100px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.04);
    display:flex; flex-direction:column;
}}
.content {{ flex:1; overflow:hidden; }}
h2 {{
    font-weight:800; font-size:52px; line-height:1.3;
    color:{pal['accent']};
    margin-bottom:36px;
    padding-bottom:20px;
    border-bottom: 3px solid {pal['accent']};
}}
h3 {{
    font-weight:700; font-size:40px; line-height:1.4;
    color:{pal['text']}; margin-bottom:24px;
}}
p {{
    font-size:38px; line-height:1.85; color:{pal['text']};
    margin-bottom:28px;
}}
strong {{
    font-weight:700;
    background: linear-gradient(to top, {pal['highlight']} 40%, transparent 40%);
    padding: 0 4px;
}}
em {{ font-style:italic; color:{pal['muted']}; }}
code {{
    background:#F1F0EE; padding:4px 12px; border-radius:6px;
    font-size:34px; font-family:monospace;
}}
blockquote {{
    border-left:5px solid {pal['accent']};
    padding:16px 28px; margin-bottom:28px;
    background: {pal['tag_bg']};
    border-radius: 0 12px 12px 0;
    font-size:36px; line-height:1.7; color:{pal['muted']};
}}
ul {{ list-style:none; margin-bottom:28px; padding-left:0; }}
li {{
    font-size:38px; line-height:1.8; color:{pal['text']};
    padding-left:40px; position:relative; margin-bottom:8px;
}}
li::before {{
    content:''; position:absolute; left:8px; top:26px;
    width:12px; height:12px; border-radius:50%;
    background:{pal['accent2']};
}}
.tags {{ display:flex; flex-wrap:wrap; gap:16px; margin-top:32px; }}
.tag {{
    background:{pal['tag_bg']}; color:{pal['tag_text']};
    padding:10px 24px; border-radius:20px;
    font-size:30px; font-weight:500;
}}
.pagenum {{
    position:absolute; bottom:50px; right:70px;
    font-size:30px; color:{pal['muted']}; font-weight:500;
    opacity:0.5;
}}
.accent-bar {{
    position:absolute; left:40px; top:120px; bottom:120px;
    width:6px; border-radius:3px;
    background: linear-gradient(to bottom, {pal['accent']}, {pal['accent2']});
    opacity:0.5;
}}
</style></head><body>
<div class="accent-bar"></div>
<div class="page">
    <div class="content">{body}</div>
    <div class="pagenum">{page}/{total}</div>
</div>
</body></html>"""


async def render_all(cards_html: list[tuple[str, str]], dpr: int = 2) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": W, "height": H}, device_scale_factor=dpr
        )
        for html, out_path in cards_html:
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                f.write(html)
                tmp = f.name
            try:
                await page.goto(f"file://{tmp}")
                await page.wait_for_load_state("networkidle")
                try:
                    await page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
                except Exception:
                    pass
                await page.wait_for_timeout(200)
                await page.screenshot(
                    path=out_path,
                    clip={"x": 0, "y": 0, "width": W, "height": H},
                    type="png",
                )
            finally:
                os.unlink(tmp)
        await browser.close()


async def main_async(args: argparse.Namespace) -> list[str]:
    pal = dict(PALETTE)
    if args.accent:
        pal["accent"] = args.accent
        pal["tag_text"] = args.accent
    if args.accent2:
        pal["accent2"] = args.accent2

    data = parse_md(args.md)
    pages = split_pages(data["body"])
    total = len(pages)
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, str]] = []
    output_files: list[str] = []

    if data["meta"].get("title"):
        p = str(outdir / "cover.png")
        jobs.append((cover_html(data["meta"], pal), p))
        output_files.append(p)

    for i, content in enumerate(pages, 1):
        p = str(outdir / f"card_{i}.png")
        jobs.append((card_html(content, i, total, pal), p))
        output_files.append(p)

    print(f"渲染 {len(jobs)} 张图（封面 + {total} 张内容卡）")
    await render_all(jobs, args.dpr)
    for f in output_files:
        print(f"  → {f}")
    print("完成")
    return output_files


def render_cards(md_path: str, output_dir: str, accent: str | None = None,
                 accent2: str | None = None, dpr: int = 2) -> list[str]:
    """供其他脚本调用的同步接口，返回生成的文件路径列表。"""
    ns = argparse.Namespace(md=md_path, output_dir=output_dir,
                            accent=accent, accent2=accent2, dpr=dpr)
    return asyncio.run(main_async(ns))


def main():
    ap = argparse.ArgumentParser(description="Markdown → 小红书知识卡片")
    ap.add_argument("md", help="Markdown 文件")
    ap.add_argument("-o", "--output-dir", default=".", help="输出目录")
    ap.add_argument("--accent", help="主色 hex，如 #4338CA")
    ap.add_argument("--accent2", help="副色 hex，如 #6366F1")
    ap.add_argument("--dpr", type=int, default=2, help="设备像素比")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

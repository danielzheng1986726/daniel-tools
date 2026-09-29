#!/usr/bin/env python3
"""Markdown 转内联样式 HTML — 给微信公众号用。

公众号编辑器会丢掉 <style> 块和 class 选择器，只认元素上的 style="" 属性，
所以这里把主题样式逐个内联到标签上。直接把 markdown 渲染成的裸 HTML 传给公众号
编辑器或第三方发布工具，会得到零样式的裸文章，这个工具就是补那一段。

链接模式（公众号正文的超链接对订阅号是失效的，默认转脚注）：
    footnote    正文留 文字[1]，文末生成参考链接清单
    inline      正文写成 文字（https://...）
    keep        原样保留 <a>，知道自己在干什么时再用

Usage:
    python md_to_wechat_html.py article.md
    python md_to_wechat_html.py article.md -o out.html --theme plain
    python md_to_wechat_html.py article.md --link-mode inline --strip-h1
    cat article.md | python md_to_wechat_html.py -
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString
from markdown_it import MarkdownIt

# 公众号会过滤掉大部分 CSS，这里只用实测能留下的属性：
# font-size / line-height / color / margin / padding / background / border / text-align / font-weight
THEMES: dict[str, dict[str, str]] = {
    "plain": {
        "root": "font-size:16px;line-height:1.75;color:#3f3f3f;letter-spacing:0.4px;",
        "h1": "font-size:22px;font-weight:bold;color:#1a1a1a;margin:32px 0 20px;line-height:1.4;",
        "h2": "font-size:19px;font-weight:bold;color:#1a1a1a;margin:34px 0 16px;line-height:1.4;",
        "h3": "font-size:17px;font-weight:bold;color:#1a1a1a;margin:26px 0 14px;line-height:1.5;",
        "p": "margin:0 0 20px;line-height:1.75;color:#3f3f3f;",
        "blockquote": "margin:22px 0;padding:12px 16px;border-left:3px solid #d0d0d0;"
                      "background:#fafafa;color:#666;",
        "ul": "margin:0 0 20px;padding-left:24px;",
        "ol": "margin:0 0 20px;padding-left:24px;",
        "li": "margin:0 0 8px;line-height:1.75;color:#3f3f3f;",
        "code": "background:#f4f4f4;padding:2px 5px;border-radius:3px;"
                "font-size:14px;color:#c0341d;",
        "pre": "margin:22px 0;padding:14px 16px;background:#f7f7f7;border-radius:4px;"
               "overflow-x:auto;font-size:13px;line-height:1.6;color:#333;",
        "pre_code": "background:none;padding:0;color:#333;font-size:13px;",
        "strong": "font-weight:bold;color:#1a1a1a;",
        "em": "font-style:italic;color:#3f3f3f;",
        "a": "color:#576b95;text-decoration:none;word-break:break-all;",
        "hr": "border:none;border-top:1px solid #e5e5e5;margin:30px 0;",
        "table": "width:100%;border-collapse:collapse;margin:22px 0;font-size:14px;",
        "th": "border:1px solid #ddd;padding:8px 10px;background:#f5f5f5;"
              "font-weight:bold;text-align:left;",
        "td": "border:1px solid #ddd;padding:8px 10px;",
        "img": "max-width:100%;height:auto;display:block;margin:22px auto;border-radius:4px;",
        "footnote_h": "font-size:15px;font-weight:bold;color:#1a1a1a;margin:34px 0 12px;",
        "footnote_li": "margin:0 0 6px;font-size:13px;line-height:1.7;color:#888;"
                       "word-break:break-all;",
        "sup": "color:#576b95;font-size:12px;",
    },
}


def render_markdown(md_text: str) -> str:
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "breaks": False})
    md.enable("table")
    md.enable("strikethrough")
    return md.render(md_text)


def _collect_links(soup: BeautifulSoup) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if href and not href.startswith("#"):
            links.append((a.get_text(strip=True), href))
    return links


def apply_link_mode(soup: BeautifulSoup, mode: str, theme: dict[str, str]) -> list[str]:
    """按模式改写 <a>。返回文末要列出的链接清单。"""
    if mode == "keep":
        return []

    footnotes: list[str] = []
    seen: dict[str, int] = {}

    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        text = a.get_text(strip=True)
        if not href or href.startswith("#"):
            a.unwrap()
            continue

        if mode == "inline":
            a.replace_with(NavigableString(f"{text}（{href}）" if text else href))
            continue

        # footnote
        if href not in seen:
            seen[href] = len(footnotes) + 1
            footnotes.append(f"[{len(footnotes) + 1}] {text or href}：{href}" if text else f"[{len(footnotes) + 1}] {href}")
        idx = seen[href]
        sup = soup.new_tag("sup")
        sup["style"] = theme["sup"]
        sup.string = f"[{idx}]"
        a.insert_after(sup)
        a.unwrap()

    return footnotes


def append_footnotes(soup: BeautifulSoup, footnotes: list[str], theme: dict[str, str],
                     heading: str) -> None:
    if not footnotes:
        return
    h = soup.new_tag("p")
    h["style"] = theme["footnote_h"]
    h.string = heading
    soup.append(h)
    for line in footnotes:
        p = soup.new_tag("p")
        p["style"] = theme["footnote_li"]
        p.string = line
        soup.append(p)


def inline_styles(soup: BeautifulSoup, theme: dict[str, str]) -> None:
    simple = ("h1", "h2", "h3", "p", "blockquote", "ul", "ol", "li",
              "strong", "em", "a", "hr", "table", "th", "td", "img")
    for tag_name in simple:
        for el in soup.find_all(tag_name):
            if el.has_attr("style"):      # 已经设过的（比如 sup / 脚注）不覆盖
                continue
            el["style"] = theme[tag_name]

    for pre in soup.find_all("pre"):
        pre["style"] = theme["pre"]
        for code in pre.find_all("code"):
            code["style"] = theme["pre_code"]

    for code in soup.find_all("code"):
        if not code.has_attr("style"):
            code["style"] = theme["code"]

    # class 在公众号会被丢掉，留着只是噪音
    for el in soup.find_all(True):
        el.attrs.pop("class", None)
        el.attrs.pop("id", None)


def strip_first_h1(soup: BeautifulSoup) -> str | None:
    """摘掉正文首个 H1 并返回它的文字。标题应该走 title 字段，不该在正文里重复。"""
    h1 = soup.find("h1")
    if h1 is None:
        return None
    title = h1.get_text(strip=True)
    h1.decompose()
    return title


def convert(md_text: str, theme_name: str = "plain", link_mode: str = "footnote",
            strip_h1: bool = False, footnote_heading: str = "参考链接") -> dict[str, Any]:
    theme = THEMES[theme_name]
    soup = BeautifulSoup(render_markdown(md_text), "html.parser")

    title = strip_first_h1(soup) if strip_h1 else None
    links = _collect_links(soup)
    footnotes = apply_link_mode(soup, link_mode, theme)
    inline_styles(soup, theme)
    append_footnotes(soup, footnotes, theme, footnote_heading)

    inner = soup.decode()
    html = f'<section style="{theme["root"]}">{inner}</section>'
    return {"html": html, "title": title, "links": links, "footnotes": footnotes}


def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown 转公众号内联样式 HTML")
    ap.add_argument("input", help="Markdown 文件路径，用 - 表示从 stdin 读")
    ap.add_argument("-o", "--output", help="输出 HTML 路径，默认打到 stdout")
    ap.add_argument("--theme", default="plain", choices=sorted(THEMES), help="样式主题")
    ap.add_argument("--link-mode", default="footnote", choices=("footnote", "inline", "keep"),
                    help="链接处理方式，默认 footnote")
    ap.add_argument("--strip-h1", action="store_true",
                    help="摘掉正文首个 H1（标题应走 title 字段）")
    ap.add_argument("--footnote-heading", default="参考链接", help="脚注区标题")
    ap.add_argument("--stats", action="store_true", help="把统计打到 stderr")
    args = ap.parse_args()

    md_text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")

    result = convert(md_text, args.theme, args.link_mode, args.strip_h1, args.footnote_heading)

    if args.output:
        Path(args.output).write_text(result["html"], encoding="utf-8")
    else:
        sys.stdout.write(result["html"])

    if args.stats:
        print(f"标题: {result['title'] or '(未摘取)'}", file=sys.stderr)
        print(f"HTML: {len(result['html'])} 字符", file=sys.stderr)
        print(f"链接: {len(result['links'])} 个，脚注 {len(result['footnotes'])} 条", file=sys.stderr)
        for line in result["footnotes"]:
            print(f"  {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

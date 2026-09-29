#!/usr/bin/env python3
"""把一段长 Prompt 排成图片：3:4 评论区卡片（1080x1440）或 9:16 视频结尾定格帧（1080x1920）。

用法：
  python3 make_prompt_cards.py --text PROMPT.md --title "系统性因果分析框架 · 原版" --mode card  --out OUTDIR
  python3 make_prompt_cards.py --text PROMPT.md --title "..." --mode frame --out OUTDIR
自动分页；emoji 用系统 emoji 字体渲染（找不到就退化成普通文字）；以【开头的行加粗。
9:16 模式把文字放在平台 UI 安全区内（上 200、下 380、右 170 留白）。

字体：需要一个中文字体文件，优先级 --font 参数 > CARD_FONT_PATH 环境变量 >
自动探测几个常见 macOS 路径。不同字体文件里「常规/粗体」对应的 font index 不一样，
探测到的候选自带一份 index 映射；自己指定 --font 时可以用
--font-regular-index / --font-bold-index 覆盖默认的 0/1。
"""
import argparse
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# (路径, 常规字重 index, 粗字重 index)。前两个是 PingFang 在新旧 macOS 上的常见位置，
# 第三个是几乎所有 macOS 都有的 Hiragino 合集字体，作为兜底。
FONT_CANDIDATES: tuple[tuple[str, int, int], ...] = (
    ("/System/Library/AssetsV2/com_apple_MobileAsset_Font8/"
     "86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc", 3, 11),
    ("/System/Library/Fonts/PingFang.ttc", 3, 11),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0, 2),
)
EMOJI_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Fonts/Apple Color Emoji.ttc",
)
BG, FG, ACCENT, MUTED = (250, 247, 242), (34, 34, 34), (196, 72, 52), (140, 134, 126)
NO_LINE_START = set('，。、；：！？）」』”’》…,.;:!?)')


def resolve_font(cli_font, cli_reg_idx, cli_bold_idx):
    if cli_font:
        if not Path(cli_font).exists():
            raise SystemExit(f"--font 指定的字体文件不存在：{cli_font}")
        return cli_font, (cli_reg_idx if cli_reg_idx is not None else 0), \
               (cli_bold_idx if cli_bold_idx is not None else 1)
    env_font = os.environ.get("CARD_FONT_PATH")
    if env_font:
        if not Path(env_font).exists():
            raise SystemExit(f"环境变量 CARD_FONT_PATH 指定的字体文件不存在：{env_font}")
        return env_font, int(os.environ.get("CARD_FONT_REGULAR_INDEX", 0)), \
               int(os.environ.get("CARD_FONT_BOLD_INDEX", 1))
    for path, reg_idx, bold_idx in FONT_CANDIDATES:
        if Path(path).exists():
            return path, reg_idx, bold_idx
    raise SystemExit(
        "没找到可用的中文字体。用 --font /path/to/font.ttc 指定一个"
        "（可配 --font-regular-index / --font-bold-index），或设环境变量 CARD_FONT_PATH。"
    )


def resolve_emoji_font():
    for path in EMOJI_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def is_emoji(ch):
    o = ord(ch)
    return 0x1F300 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF or o in (0x2753, 0x2696, 0x26A1)


class Fonts:
    def __init__(self, size, font_path, reg_idx, bold_idx, emoji_path):
        self.size = size
        self.reg = ImageFont.truetype(font_path, size, index=reg_idx)
        self.bold = ImageFont.truetype(font_path, size, index=bold_idx)
        self.emoji = ImageFont.truetype(emoji_path, 160) if emoji_path else None  # 位图字体只有固定尺寸，画完再缩放

    def width(self, ch, bold=False):
        if is_emoji(ch) and self.emoji:
            return int(self.size * 1.15)
        return (self.bold if bold else self.reg).getlength(ch)


def wrap(text, fonts, maxw):
    """返回 [(line_text, bold, is_blank)]"""
    out = []
    for raw in text.split('\n'):
        raw = raw.replace('️', '')
        if not raw.strip():
            out.append(('', False, True)); continue
        bold = raw.lstrip().startswith('【')
        line, w = '', 0
        for ch in raw:
            cw = fonts.width(ch, bold)
            if w + cw > maxw and line and ch not in NO_LINE_START:
                out.append((line, bold, False)); line, w = '', 0
                if ch == ' ': continue
            line += ch; w += cw
        out.append((line, bold, False))
    # 去掉连续空行
    res = []
    for item in out:
        if item[2] and res and res[-1][2]: continue
        res.append(item)
    return res


def draw_line(d, img, x, y, text, bold, fonts):
    f = fonts.bold if bold else fonts.reg
    for ch in text:
        if is_emoji(ch) and fonts.emoji:
            tmp = Image.new('RGBA', (180, 180), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).text((0, 0), ch, font=fonts.emoji, embedded_color=True)
            s = int(fonts.size * 1.05)
            tmp = tmp.crop(tmp.getbbox() or (0, 0, 160, 160)).resize((s, s))
            img.paste(tmp, (int(x), int(y + fonts.size * 0.12)), tmp)
            x += fonts.width(ch)
        else:
            d.text((x, y), ch, font=f, fill=FG)
            x += f.getlength(ch)


def render(text, title, mode, out, size, footer, font_path, reg_idx, bold_idx, emoji_path):
    if mode == 'card':
        W, H = 1080, 1440; L, R, T, B = 90, 90, 190, 130
    else:
        W, H = 1080, 1920; L, R, T, B = 80, 150, 300, 400
    fonts = Fonts(size, font_path, reg_idx, bold_idx, emoji_path)
    lh = int(size * 1.62); blank_h = int(size * 0.7)
    lines = wrap(text, fonts, W - L - R)
    pages, cur, h = [], [], 0
    avail = H - T - B
    for ln in lines:
        add = blank_h if ln[2] else lh
        if h + add > avail and cur:
            pages.append(cur); cur, h = [], 0
            if ln[2]: continue
        cur.append(ln); h += add
    if cur: pages.append(cur)
    os.makedirs(out, exist_ok=True)
    tfont = ImageFont.truetype(font_path, int(size * 1.15), index=bold_idx)
    sfont = ImageFont.truetype(font_path, int(size * 0.72), index=reg_idx)
    paths = []
    for i, pg in enumerate(pages, 1):
        img = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(img)
        ty = T - int(size * 2.6)
        d.rectangle((L, ty, L + 10, ty + int(size * 1.3)), fill=ACCENT)
        d.text((L + 28, ty - int(size * 0.08)), title, font=tfont, fill=FG)
        d.text((W - R - sfont.getlength(f'{i}/{len(pages)}'), ty + int(size * 0.3)), f'{i}/{len(pages)}', font=sfont, fill=MUTED)
        y = T
        for text_, bold, blank in pg:
            if blank: y += blank_h; continue
            draw_line(d, img, L, y, text_, bold, fonts); y += lh
        d.text((L, H - B + int(size * 0.9)), footer, font=sfont, fill=MUTED)
        p = os.path.join(out, f'{mode}_{i:02d}.png'); img.save(p); paths.append(p)
    return paths


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--text', required=True); ap.add_argument('--title', required=True)
    ap.add_argument('--mode', choices=['card', 'frame'], default='card')
    ap.add_argument('--out', required=True); ap.add_argument('--size', type=int, default=0)
    ap.add_argument('--footer', default='示例落款 · 我的 Prompt 库')
    ap.add_argument('--font', default=None, help='中文字体文件路径（.ttc/.ttf），不给则自动探测')
    ap.add_argument('--font-regular-index', type=int, default=None)
    ap.add_argument('--font-bold-index', type=int, default=None)
    a = ap.parse_args()
    size = a.size or (34 if a.mode == 'card' else 36)
    font_path, reg_idx, bold_idx = resolve_font(a.font, a.font_regular_index, a.font_bold_index)
    emoji_path = resolve_emoji_font()
    for p in render(open(a.text, encoding='utf-8').read().strip(), a.title, a.mode, a.out, size,
                     a.footer, font_path, reg_idx, bold_idx, emoji_path):
        print(p)

#!/usr/bin/env python3
"""生成微信公众号封面图 — 字体排版风格，全自动无需人工审。

为什么不用 AI 生图：
    1. AI 生图工具偶尔会有 CLI/接口层面的故障（参数正常但生成失败），
       跟账号、额度无关，属于外部工具不稳定
    2. 就算稳定，AI 生图每次结果不一样，本质上要人眼过一遍，这跟"全自动"冲突

字体排版封面是确定性的：同样的标题永远得到同样的图，不用审。

尺寸：
    首图    2700x1149  2.35:1   订阅号列表里显示
    小图    1149x1149  1:1      主页 / 转发朋友圈显示

比例沿用公众号规格 900x383 / 383x383，只是等比放大 3 倍。
放大的理由：真正显示的是 16:9 裁完的那份，900 宽的源图裁完只剩 680，
手机 3 倍屏上要铺到 1000px 以上，等于硬放大 1.5 倍——糊不是图片内容的问题，
是源图一开始就比显示尺寸小。2700 宽裁完是 2040，够铺。

安全区是这个工具的核心约束。用 MultiPost（一个开源的多平台发布工具）
上传封面后，它会自己裁三个比例（源码 src/sync/article/weixin.ts:
`const ratios = [16 / 9, 1, 3 / 4]`），而且是**居中裁**：

    const targetWidth = height * ratio;
    const cropPercent = (width - targetWidth) / 2 / width;   // 除以 2 = 居中

对 2700x1149 来说，横向只保留：
    16:9 → x∈[329, 2371]  宽 2042
    1:1  → x∈[776, 1924]  宽 1148   ← 转发卡片/主页缩略图，实测左对齐文字在这里被切掉
    3:4  → x∈[919, 1781]  宽 862

微信公众号后台的「编辑封面」面板实测只有两个展示位——2.35:1（消息列表）
和 1:1（转发卡片和公众号主页），没有 3:4。MultiPost 照发三份裁剪，
但 3:4 那份在微信这边没有对应的展示位。所以默认安全区从 862px（保 3:4）
放宽到 1148px（只保 1:1），文字大了三分之一。真正的瓶颈是 1:1，不是 3:4。

所以文字必须待在中间 1148px 内（占全幅 43%）。代价是首图变成
「居中卡片 + 两边留白」，这是换缩略图不截字必须付的。

字体：需要一个支持中文的字体文件（.ttf/.ttc），优先级：
    1. --font 命令行参数
    2. 环境变量 COVER_FONT_PATH
    3. 常见系统字体自动探测（macOS 的 Hiragino/STHeiti、
       Linux 的 Noto Sans CJK / 文泉驿）
探测不到会直接报错并提示怎么指定。

Usage:
    python make_cover.py --title "最会踩刹车的人，把 AI 推得最快" -o cover.png
    python make_cover.py --title "标题" --kicker "播客手记" --brand "示例公众号"
    python make_cover.py --title "标题" --safe-zone thumb --theme dark
    python make_cover.py --title "标题" --contact-sheet   # 出裁剪验证图
    python make_cover.py --title "标题" --font /path/to/your-font.ttc
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 常见系统字体候选，按存在与否依次尝试。ttc 的 index 假设是类似 Hiragino
# 这种"一个文件多个字重"的合集字体（index 0≈细体、index 2≈粗体附近）；
# 单一字重的 .ttf 只有 index 0，粗体会退回常规体渲染（不会报错）。
FONT_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Fonts/Hiragino Sans GB.ttc",       # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",           # macOS 备选
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto CJK
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",      # Linux 文泉驿
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)
FONT_REGULAR = 0   # 合集字体里常规字重的 index
FONT_BOLD = 2      # 合集字体里粗字重的 index（Hiragino Sans GB 上约等于 W6）

COVER_W, COVER_H = 2700, 1149
SQUARE = 1149

# MultiPost 裁的比例，跟 weixin.ts 里的 ratios 保持一致
CROP_RATIOS: tuple[tuple[str, float], ...] = (("16:9", 16 / 9), ("1:1", 1.0), ("3:4", 3 / 4))


def resolve_font_path(cli_font: str | None) -> str:
    if cli_font:
        if not Path(cli_font).exists():
            raise SystemExit(f"--font 指定的字体文件不存在：{cli_font}")
        return cli_font
    env_font = os.environ.get("COVER_FONT_PATH")
    if env_font:
        if not Path(env_font).exists():
            raise SystemExit(f"环境变量 COVER_FONT_PATH 指定的字体文件不存在：{env_font}")
        return env_font
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise SystemExit(
        "没找到可用的中文字体。用 --font /path/to/font.ttc（或 .ttf）指定一个，"
        "或设环境变量 COVER_FONT_PATH。Linux 上可以装 Noto Sans CJK："
        "apt install fonts-noto-cjk"
    )


def crop_window(ratio: float, width: int = COVER_W, height: int = COVER_H) -> tuple[int, int]:
    """复刻 weixin.ts 的 calculateCropConfig，算出横向保留的 [x1, x2]。"""
    if width / height <= ratio:
        return 0, width
    target_w = height * ratio
    pct = (width - target_w) / 2 / width
    return round(pct * width), round((1 - pct) * width)


def safe_width(zone: str) -> int:
    """安全区宽度。strict 取最窄的裁剪比例，保证每个比例都不截字。"""
    if zone == "none":
        return COVER_W - int(COVER_W * 0.075) * 2
    # thumb 只保 1:1——微信后台的封面面板只有 2.35:1 和 1:1 两个展示位，
    # 3:4 是 MultiPost 多发的一份，微信没地方显示它。
    ratios = [r for _, r in CROP_RATIOS] if zone == "strict" else [1.0]
    return min(x2 - x1 for x1, x2 in (crop_window(r) for r in ratios))

THEMES: dict[str, dict[str, tuple[int, int, int]]] = {
    "plain": {
        "bg": (247, 245, 242),
        "title": (26, 26, 26),
        "kicker": (150, 120, 90),
        "brand": (168, 162, 152),
        "rule": (214, 208, 199),
    },
    "dark": {
        "bg": (28, 30, 34),
        "title": (238, 236, 232),
        "kicker": (196, 158, 108),
        "brand": (128, 126, 122),
        "rule": (66, 68, 72),
    },
}


def font(font_path: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if bold:
        try:
            return ImageFont.truetype(font_path, size, index=FONT_BOLD)
        except OSError:
            pass  # 单字重字体没有 bold index，退回常规体
    return ImageFont.truetype(font_path, size, index=FONT_REGULAR)


BREAK_AFTER = "，。；：！？、）】》」"
# 避头尾：这些字符不能出现在行首。硬断时把它悬挂到上一行末尾，
# 宁可轻微超出安全区（安全区本来还留了 inset），也不让标点起行。
NO_LINE_START = "，。；：！？、）】》」”』：·—…%"

def _hard_wrap(text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for ch in text:
        if fnt.getlength(cur + ch) <= max_w:
            cur += ch
            continue
        if ch in NO_LINE_START and cur:
            lines.append(cur + ch)      # 标点悬挂在行尾，不另起一行
            cur = ""
            continue
        if cur:
            lines.append(cur)
        cur = ch
    if cur:
        lines.append(cur)
    return lines


def _breakable_at(text: str, j: int) -> bool:
    """能不能在第 j 个字前断行。拉丁字母/数字连成的词不能拆开——
    「大厂把 A / I 使用率写进考核了」这种断法比字号小难看得多。"""
    if j <= 0 or j >= len(text):
        return True
    a, b = text[j - 1], text[j]
    return not (a.isascii() and a.isalnum() and b.isascii() and b.isalnum())


def _balanced_wrap(text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """固定字号下的均衡分行（动态规划）。

    贪心折行会把最后一行剩成一两个字（「最会踩刹车的人 / ，把 AI 推得最快」这种），
    所以改成整体最优：每行宽度都尽量接近安全区宽度，代价是各行宽度差的平方和。
    另外两条硬规则——标点不能起行（避头尾），能在标点后断就别断在词中间。"""
    n = len(text)
    if n == 0:
        return [""]
    pre = [0.0] * (n + 1)
    for i, ch in enumerate(text):
        pre[i + 1] = pre[i] + fnt.getlength(ch)

    INF = float("inf")
    mid_penalty = max_w * max_w * 0.12      # 断在非标点处的罚分
    best = [INF] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for j in range(1, n + 1):
        if j < n and text[j] in NO_LINE_START:
            continue                        # 下一行会以标点开头，这个断点不合法
        if not _breakable_at(text, j):
            continue                        # 会把一个拉丁词劈成两半
        for i in range(j):
            if text[i] == " ":
                continue                    # 行首不留空格
            if not _breakable_at(text, i):
                continue
            width = pre[j] - pre[i]
            # 标点悬挂：行尾的标点可以探出安全区，不占宽度预算。
            # 少了这条，「最会踩刹车的人，」这类刚好超几个像素的理想断点会被判死，
            # 分行就退化成「最会踩刹 / 车的人，」那种四字一行。
            fit_w = width
            if text[j - 1] in NO_LINE_START:
                fit_w -= fnt.getlength(text[j - 1])
            if fit_w > max_w and j - i > 1:
                continue
            cost = best[i] + (max_w - fit_w) ** 2
            if j < n and text[j - 1] not in BREAK_AFTER:
                cost += mid_penalty
            if cost < best[j]:
                best[j] = cost
                back[j] = i
    if best[n] == INF:                      # 规则互相冲突，退回逐字硬断
        return _hard_wrap(text, fnt, max_w)

    lines, j = [], n
    while j > 0:
        i = back[j]
        lines.append(text[i:j].strip())
        j = i
    return lines[::-1]


# 字数直接定档：同字数永远同字号，不做「试大的、不行再降」那套。
# 档位按 COVER_H=1149 定，其他尺寸按高度等比缩放。
TITLE_TIERS: tuple[tuple[int, int], ...] = ((10, 168), (16, 132), (24, 108))
MAX_LINES = 3


def tier_size(title: str, height: int) -> int:
    """字号跟高度走：行高填的是竖向空间，跟画布宽度无关。"""
    k = height / COVER_H
    px = next((sz for cap, sz in TITLE_TIERS if len(title) <= cap), TITLE_TIERS[-1][1])
    return max(12, round(px * k))


def fit_title(font_path: str, title: str, max_w: int, size: int
              ) -> tuple[ImageFont.FreeTypeFont, list[str], bool]:
    """字号已经由字数定死，这里只负责把它排好。绝不截断文字：
    排不下就让它多占一行并返回 overflow=True，由调用方警告。"""
    f = font(font_path, size, bold=True)
    lines: list[str] = []
    for para in title.split("\n"):
        lines.extend(_balanced_wrap(para, f, max_w))
    return f, lines, len(lines) > MAX_LINES


def render(font_path: str, title: str, kicker: str, brand: str, theme_name: str,
           width: int, height: int, zone: str = "strict") -> Image.Image:
    """文字整体居中排版。居中是安全区的必然结果：MultiPost 居中裁，
    所以只有居中的内容才在每个比例里都活下来。"""
    c = THEMES[theme_name]
    img = Image.new("RGB", (width, height), c["bg"])
    d = ImageDraw.Draw(img)

    square = width == height
    # 安全区是裁剪的硬边界，文字再往里收一点，别贴着边
    inset = round(width * 0.015)
    max_w = (width - int(width * 0.1) * 2) if square else safe_width(zone) - inset * 2
    cx = width // 2

    title_font, lines, overflow = fit_title(font_path, title, max_w, tier_size(title, height))
    if overflow and not square:
        print(f"⚠️  标题 {len(title)} 字，在 {max_w}px 安全区里排到 {len(lines)} 行"
              f"（上限 {MAX_LINES} 行）。给 --title 一个短一点的封面标题"
              f"（不必和文章标题一样，{TITLE_TIERS[-1][0]} 字以内最稳）",
              file=sys.stderr)

    line_h = int(title_font.size * 1.45)
    title_h = line_h * len(lines)

    kicker_font = font(font_path, max(12, int(title_font.size * 0.44)), bold=False)
    brand_font = font(font_path, max(11, int(title_font.size * 0.38)), bold=False)

    kicker_h = int(kicker_font.size * 2.2) if kicker else 0
    brand_h = int(brand_font.size * 2.8) if brand else 0
    block_h = kicker_h + title_h + brand_h
    y = (height - block_h) // 2

    if kicker:
        d.text((cx, y), kicker, font=kicker_font, fill=c["kicker"], anchor="ma")
        y += kicker_h

    for line in lines:
        d.text((cx, y), line, font=title_font, fill=c["title"], anchor="ma")
        y += line_h

    if brand:
        rule_w = int(title_font.size * 0.9)
        rule_y = y + int(brand_font.size * 0.9)
        d.line([(cx - rule_w // 2, rule_y), (cx + rule_w // 2, rule_y)],
               fill=c["rule"], width=max(2, round(width / 900)))
        d.text((cx, rule_y + int(brand_font.size * 0.7)), brand,
               font=brand_font, fill=c["brand"], anchor="ma")

    return img


def contact_sheet(font_path: str, img: Image.Image, out: Path) -> Path:
    """把 MultiPost 会裁出的三个比例并排画出来，肉眼确认没截字。"""
    crops = []
    for name, ratio in CROP_RATIOS:
        x1, x2 = crop_window(ratio, img.width, img.height)
        crops.append((name, img.crop((x1, 0, x2, img.height))))

    gap, label_h = 14, 26
    scale = max(1, img.width // 900)
    gap, label_h = gap * scale, label_h * scale
    total_w = max(img.width, sum(c.width for _, c in crops) + gap * (len(crops) - 1))
    sheet = Image.new("RGB", (total_w, img.height * 2 + gap + label_h * 2), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    lf = font(font_path, 14 * scale)

    d.text((0, 0), f"原图 {img.width}x{img.height}", font=lf, fill=(60, 60, 60))
    sheet.paste(img, (0, label_h))

    y = img.height + label_h + gap
    x = 0
    for name, c in crops:
        d.text((x, y), f"{name} 裁剪 {c.width}x{c.height}", font=lf, fill=(60, 60, 60))
        sheet.paste(c, (x, y + label_h))
        x += c.width + gap

    sheet.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成公众号封面图（字体排版风格）")
    ap.add_argument("--title", required=True, help="标题，用 \\n 可强制换行")
    ap.add_argument("--kicker", default="", help="标题上方的小字，比如栏目名")
    ap.add_argument("--brand", default="", help="左下角落款，比如公众号名")
    ap.add_argument("--theme", default="plain", choices=sorted(THEMES))
    ap.add_argument("-o", "--output", default="cover.png", help="输出路径")
    ap.add_argument("--font", default=None,
                    help="中文字体文件路径（.ttf/.ttc）。不给就用 COVER_FONT_PATH "
                         "环境变量，再不给就自动探测常见系统字体")
    ap.add_argument("--safe-zone", default="thumb", choices=("strict", "thumb", "none"),
                    help="thumb=1148px 只保 1:1（默认，微信只用 2.35:1 和 1:1）; "
                         "strict=862px 连 3:4 一起保（保守，字会小三分之一）; none=满版")
    ap.add_argument("--square-too", action="store_true",
                    help="额外出一张 383x383 小图（文件名加 _square）")
    ap.add_argument("--contact-sheet", action="store_true",
                    help="额外出一张裁剪验证图，把三个比例并排画出来")
    args = ap.parse_args()

    font_path = resolve_font_path(args.font)
    title = args.title.replace("\\n", "\n")
    out = Path(args.output)

    img = render(font_path, title, args.kicker, args.brand, args.theme, COVER_W, COVER_H, args.safe_zone)
    img.save(out, quality=95)
    print(f"{out}  {COVER_W}x{COVER_H}  安全区 {safe_width(args.safe_zone)}px  "
          f"({out.stat().st_size / 1024:.1f} KB)")

    if args.square_too:
        sq = out.with_name(f"{out.stem}_square{out.suffix}")
        render(font_path, title, args.kicker, args.brand, args.theme, SQUARE, SQUARE).save(sq, quality=95)
        print(f"{sq}  {SQUARE}x{SQUARE}  ({sq.stat().st_size / 1024:.1f} KB)")

    if args.contact_sheet:
        cs = contact_sheet(font_path, img, out.with_name(f"{out.stem}_crops{out.suffix}"))
        print(f"{cs}  裁剪验证图")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

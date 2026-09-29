#!/usr/bin/env python3
"""
transcript_suspects.py — 转写疑点清单（2026-09-17 起交付前硬卡点）

背景：字幕只改「有依据」的词，弱模型就只改有报道依据的三个名字，按上下文该纠的
（「老板基于 AI 转型」这种）一个不碰；强模型也可能漏。所以把「列疑点」和「定处置」拆开：
脚本先把机械能找到的候选列出来，模型必须逐条填「疑似应为 / 依据 / 处置」，
QA 前用 --verify 卡：有一行没填完就不许交付。

用法一（播种，跑在两遍转写之后）：
    python3 transcript_suspects.py --primary <Qwen 词级 .tsv> --secondary <whisper .tsv|.txt|.srt> \
        --out work/transcript/SUSPECTS.md [--baseline <基准文档.md>]

    产出三块：
      A. 两个引擎听得不一样的地方（按源片秒定位，附前后文）—— 最可靠的机械信号
      B. 主引擎稿里的英文 / 数字 / 混排词（HARO、CHO、754 人）—— 必核项
      C. 空表：模型按上下文自己补的疑点（脚本找不到，但必须有这一栏，哪怕填「无」）

用法二（交付前门禁）：
    python3 transcript_suspects.py --verify work/transcript/SUSPECTS.md
    每一行的「依据」「处置」都要填；「处置=改字幕」但「依据=未定」算没过。C 块至少一行（可写「无」）。
    有任何一条没过 → 退出码 1。

依据只认五种：定点ASR / 副引擎 / 上下文 / 基准文档 / 未定。
处置只认三种：改字幕 / 保留 / 待人工确认。
"""

import argparse
import csv
import difflib
import re
import sys
from pathlib import Path

FILLER = set("呃啊嗯哦唉嘛呢吧哈欸诶呀的了就是那个这个然后")
PUNCT_RE = re.compile(r"[\s,.，。、；;：:！!？?「」『』“”\"'()（）\[\]【】…—\-–]+")
LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.\-]*|\d+(?:[.,]\d+)*%?")
BASIS = {"定点ASR", "副引擎", "上下文", "基准文档", "未定"}
ACTION = {"改字幕", "保留", "待人工确认"}


def load(path: Path):
    """返回 [(start_s, end_s, text)]。.tsv 是 whisper/qwen 的 start end text（毫秒）；.srt；.txt 无时间。"""
    suf = path.suffix.lower()
    rows = []
    if suf == ".tsv":
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                try:
                    rows.append((int(r["start"]) / 1000.0, int(r["end"]) / 1000.0, r["text"]))
                except (KeyError, ValueError):
                    continue
    elif suf == ".srt":
        blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
        for b in blocks:
            lines = b.strip().splitlines()
            if len(lines) >= 3 and "-->" in lines[1]:
                a, _, c = lines[1].partition("-->")
                rows.append((srt_t(a), srt_t(c), " ".join(lines[2:])))
    else:
        rows.append((0.0, 0.0, path.read_text(encoding="utf-8")))
    rows.sort(key=lambda x: x[0])
    return rows


def srt_t(s: str) -> float:
    s = s.strip().replace(",", ".")
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def flatten(rows):
    """把转写压成无标点无空白的字符串，并记每个字符对应的源片秒。"""
    chars, times = [], []
    for st, _, text in rows:
        clean = PUNCT_RE.sub("", text)
        for ch in clean:
            chars.append(ch)
            times.append(st)
    return "".join(chars), times


def is_filler_only(s: str) -> bool:
    return all(ch in FILLER for ch in s)


def disagreements(a: str, ta, b: str, merge_gap=3):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    merged = []
    for tag, i1, i2, j1, j2 in ops:
        if merged and i1 - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], i2, merged[-1][2], j2)
        else:
            merged.append((i1, i2, j1, j2))
    out = []
    for i1, i2, j1, j2 in merged:
        x, y = a[i1:i2], b[j1:j2]
        if is_filler_only(x) and is_filler_only(y):
            continue
        if x in PRONOUN and y in PRONOUN:  # 它/他/她 同音，字幕上无所谓
            continue
        ctx_l, ctx_r = a[max(0, i1 - 10):i1], a[i2:i2 + 10]
        t = ta[i1] if i1 < len(ta) else (ta[-1] if ta else 0.0)
        out.append((t, x or "（无）", y or "（无）", ctx_l, ctx_r))
    return out


PRONOUN = {"它", "他", "她"}


def latin_terms(rows):
    """在压平后的全文上找英文/数字，前后文从全文取（Qwen 的 tsv 是逐字一行，单行没有上下文）。"""
    flat, times = flatten(rows)
    seen, out = set(), []
    for m in LATIN_RE.finditer(flat):
        k = m.group(0)
        if k.lower() in seen:
            continue
        seen.add(k.lower())
        i1, i2 = m.start(), m.end()
        ctx = f"…{flat[max(0, i1 - 10):i1]}**[{k}]**{flat[i2:i2 + 10]}…"
        out.append((times[i1], k, ctx))
    return out


def seed(a: argparse.Namespace) -> int:
    prim = load(Path(a.primary))
    pa, ta = flatten(prim)
    lines = [
        "# 转写疑点清单",
        "",
        f"- 主引擎：`{a.primary}`",
        f"- 副引擎：`{a.secondary or '（未跑）'}`",
        f"- 基准文档：`{a.baseline or '（无）'}`",
        "",
        "填法：每行「疑似应为」「依据」「处置」三栏必填。依据只认 定点ASR / 副引擎 / 上下文 / 基准文档 / 未定；处置只认 改字幕 / 保留 / 待人工确认。",
        "「处置=改字幕」不能配「依据=未定」。只改显示字幕，不动音频。交付前跑 `--verify`。",
        "",
        "## A. 两个引擎听得不一样的地方",
        "",
    ]
    if a.secondary:
        sec = load(Path(a.secondary))
        pb, _ = flatten(sec)
        rows = disagreements(pa, ta, pb)
        lines.append("| # | 源片秒 | 主引擎 | 副引擎 | 前后文 | 疑似应为 | 依据 | 处置 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for n, (t, x, y, l, r) in enumerate(rows, 1):
            lines.append(f"| A{n} | {t:.2f} | {x} | {y} | …{l}**[{x}]**{r}… |  |  |  |")
        if not rows:
            lines.append("| A0 | - | （两引擎一致） | | | 无 | 副引擎 | 保留 |")
    else:
        lines.append("| # | 源片秒 | 主引擎 | 副引擎 | 前后文 | 疑似应为 | 依据 | 处置 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        lines.append("| A0 | - | （副引擎未跑，先跑 whisper 再播种） | | |  |  |  |")
    lines += ["", "## B. 英文 / 数字 / 混排词（必核）", "", "| # | 源片秒 | 词 | 前后文 | 疑似应为 | 依据 | 处置 |", "|---|---|---|---|---|---|---|"]
    terms = latin_terms(prim)
    for n, (t, k, ctx) in enumerate(terms, 1):
        lines.append(f"| B{n} | {t:.2f} | {k} | {ctx} |  |  |  |")
    if not terms:
        lines.append("| B0 | - | （无） | | 无 | 上下文 | 保留 |")
    lines += [
        "",
        "## C. 按上下文自己补的疑点",
        "",
        "脚本找不到这一类。通读主引擎全稿，凡是「读起来不通、同音字更合理、和他前后文或基准文档矛盾」的词都列进来；确实没有就写一行「无」。",
        "",
        "| # | 源片秒 | 听成 | 疑似应为 | 依据 | 处置 |",
        "|---|---|---|---|---|---|",
        "| C1 |  |  |  |  |  |",
        "",
    ]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(lines), encoding="utf-8")
    na = len(rows) if a.secondary else 0
    print(f"播种完成 -> {a.out}：A 引擎分歧 {na} 处，B 英文/数字 {len(terms)} 个，C 待模型自填")
    return 0


def parse_tables(text: str):
    """返回 [(块名, 行号, cells)]。"""
    block, out = None, []
    for ln, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^## ([ABC])\.", line)
        if m:
            block = m.group(1)
            continue
        if block and line.startswith("|") and not re.match(r"^\|\s*#\s*\|", line) and not re.match(r"^\|[-\s|]+\|$", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append((block, ln, cells))
    return out


def verify(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8")
    rows = parse_tables(text)
    problems, counts = [], {"A": 0, "B": 0, "C": 0}
    for block, ln, cells in rows:
        counts[block] += 1
        # 最后三栏固定是 疑似应为 / 依据 / 处置
        if len(cells) < 4:
            problems.append(f"L{ln} {block} 行格式不对")
            continue
        guess, basis, action = cells[-3], cells[-2], cells[-1]
        rid = cells[0]
        if block == "C" and rid == "C1" and not any(cells[1:]):
            problems.append(f"L{ln} C 块空模板未填（没有疑点也要写一行「无」）")
            continue
        if not basis or not action or (not guess and block != "C"):
            problems.append(f"L{ln} {rid} 疑似应为/依据/处置 没填全")
            continue
        if basis not in BASIS:
            problems.append(f"L{ln} {rid} 依据「{basis}」不在允许值里")
        if action not in ACTION:
            problems.append(f"L{ln} {rid} 处置「{action}」不在允许值里")
        if action == "改字幕" and basis == "未定":
            problems.append(f"L{ln} {rid} 处置=改字幕 但 依据=未定")
    if counts["C"] == 0:
        problems.append("C 块一行都没有")
    print(f"疑点清单 {path}：A {counts['A']} 行，B {counts['B']} 行，C {counts['C']} 行")
    for p in problems:
        print("  - " + p)
    print("门禁：" + ("未过" if problems else "通过"))
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--primary", help="主引擎（Qwen）词级 .tsv")
    ap.add_argument("--secondary", help="副引擎（whisper）.tsv/.txt/.srt")
    ap.add_argument("--baseline", help="基准文档路径，只写进清单头部")
    ap.add_argument("--out", help="播种输出 SUSPECTS.md")
    ap.add_argument("--verify", help="门禁：检查已填完的 SUSPECTS.md")
    a = ap.parse_args()
    if a.verify:
        return verify(a.verify)
    if not (a.primary and a.out):
        ap.error("播种需要 --primary 和 --out；门禁用 --verify")
    return seed(a)


if __name__ == "__main__":
    sys.exit(main())

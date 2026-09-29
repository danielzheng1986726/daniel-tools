#!/usr/bin/env python3
"""保真闸：核对 AI 改稿前后是否偷偷改了链接、数字或打乱了小标题结构。

不调用任何 API，纯本地文本比对，不依赖任何 prompt 文件。核对四样：
  1. URL 集合是否一致（丢了/多了链接）
  2. 阿拉伯数字集合是否一致（丢了/多了数字）
  3. 中文数字＋量词是否一致（「九分钟」「三年」「五种」）；
     输出比输入多出来的算硬伤（疑似编造），输入有输出没有只告警
     （可能是被换成了阿拉伯数字，那会在第 2 项里被抓到）
  4. H2 结构：标题数量要一致，且每个标题下面的正文要跟输入里同一序号的
     标题下的正文是同一段（按字二元组相似度找最像的一节，序号对不上就是错位）

用法：
    python3 fidelity_check.py --before a.md --after b.md

退出码：0 通过（可能有告警），1 不通过（有硬伤）。硬伤和告警都打印到 stderr。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s)\]>」』】\"'，。；：]+")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*%?")
# 中文数字＋量词。只抓带量词的，避免把「一起」「一半」「十分」这类固定词算成数字。
CN_NUM_RE = re.compile(
    r"[零〇一二两三四五六七八九十百千万亿]+(?:点[零〇一二三四五六七八九]+)?"
    r"(?:分钟|小时|秒|天|周|个月|月|年|次|种|个|条|篇|家|人|位|成|倍|块|元|美元|万|亿|百分点|%)"
)
H2_RE = re.compile(r"^##\s+(.*?)\s*$", re.M)


def sections(text: str) -> list[tuple[str, str]]:
    """按 H2 切成 [(标题, 正文)]。第一个 H2 之前的内容不算一节。"""
    heads = list(H2_RE.finditer(text))
    out = []
    for i, m in enumerate(heads):
        body_end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append((m.group(1), text[m.end():body_end]))
    return out


def bigrams(s: str) -> set[str]:
    s = re.sub(r"[\s#*_`>\-\d\W]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def similarity(a: str, b: str) -> float:
    x, y = bigrams(a), bigrams(b)
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


def structure(src: str, out: str) -> tuple[list[str], list[str]]:
    """H2 结构闸。返回 (硬伤, 告警)。

    比如 rewrite 保留了开头段又插入标题，导致几个 H2 整体下移一格，每个标题
    配的却是上一节的正文——这种情况 URL 和数字可能一个不差，光看集合会漏放行。
    这里按正文找「最像输入哪一节」，序号对不上就是错位。
    """
    problems, warnings = [], []
    ss, os_ = sections(src), sections(out)
    if not ss:
        return problems, warnings  # 输入没有 H2，不做结构闸
    if len(ss) != len(os_):
        problems.append(f"H2 数量变了: 输入 {len(ss)} 个，输出 {len(os_)} 个")
        return problems, warnings
    for i, (oh, ob) in enumerate(os_):
        # 整节正文：抓「标题整体挪到自己那节的末尾」这种全错位
        scores = [similarity(ob, sb) for _, sb in ss]
        best = max(range(len(ss)), key=lambda k: scores[k])
        if best != i and scores[best] > scores[i] + 0.05:
            problems.append(
                f"H2 错位: 输出第 {i + 1} 节「{oh}」的正文最像输入第 {best + 1} 节「{ss[best][0]}」"
                f"（相似 {scores[best]:.2f} vs 同序号 {scores[i]:.2f}）"
            )
            continue
        # 标题下第一段：抓「标题下移一段」这种半错位（标题和它下面第一句连起来读）
        first = next((x for x in ob.split("\n\n") if x.strip()), "").strip()
        if len(first) >= 20:
            fs = [similarity(first, sb) for _, sb in ss]
            fbest = max(range(len(ss)), key=lambda k: fs[k])
            if fbest != i and fs[fbest] > fs[i] + 0.05:
                problems.append(
                    f"H2 标题下第一段不咬合: 输出第 {i + 1} 节「{oh}」的第一段最像输入第 {fbest + 1} 节「{ss[fbest][0]}」"
                    f"（相似 {fs[fbest]:.2f} vs 同序号 {fs[i]:.2f}）"
                )
                continue
        # 节末一段：标题下移一段时，上一节的末尾会多出本该属于下一节的开头段
        paras = [x.strip() for x in ob.split("\n\n") if x.strip()]
        last = paras[-1] if paras else ""
        if len(last) >= 20:
            ls = [similarity(last, sb) for _, sb in ss]
            lbest = max(range(len(ss)), key=lambda k: ls[k])
            if lbest != i and ls[lbest] > ls[i] + 0.05:
                problems.append(
                    f"H2 节末一段跑错节: 输出第 {i + 1} 节「{oh}」的最后一段最像输入第 {lbest + 1} 节「{ss[lbest][0]}」"
                    f"（相似 {ls[lbest]:.2f} vs 同序号 {ls[i]:.2f}）"
                )
                continue
        if scores[i] < 0.15:
            warnings.append(f"H2 第 {i + 1} 节「{oh}」正文与输入同序号那节几乎不像（相似 {scores[i]:.2f}），人工看一眼")
    return problems, warnings


def fidelity(src: str, out: str) -> tuple[list[str], list[str]]:
    """返回 (硬伤, 告警)。硬伤任一条即判定不通过。"""
    problems, warnings = [], []
    su, ou = set(URL_RE.findall(src)), set(URL_RE.findall(out))
    if su - ou:
        problems.append("丢了链接: " + ", ".join(sorted(su - ou)))
    if ou - su:
        problems.append("多了链接: " + ", ".join(sorted(ou - su)))
    sn, on = set(NUM_RE.findall(src)), set(NUM_RE.findall(out))
    if sn - on:
        problems.append("丢了数字: " + ", ".join(sorted(sn - on)))
    if on - sn:
        problems.append("多了数字: " + ", ".join(sorted(on - sn)))
    sc, oc = set(CN_NUM_RE.findall(src)), set(CN_NUM_RE.findall(out))
    if oc - sc:
        problems.append("多了中文数字（疑似编造）: " + ", ".join(sorted(oc - sc)))
    if sc - oc:
        warnings.append("丢了中文数字（若换成了阿拉伯数字会在上面被抓）: " + ", ".join(sorted(sc - oc)))
    p2, w2 = structure(src, out)
    return problems + p2, warnings + w2


def report(problems: list[str], warnings: list[str]) -> None:
    for p in problems:
        print("  - 硬伤 " + p, file=sys.stderr)
    for w in warnings:
        print("  - 告警 " + w, file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", required=True, help="改稿前的 Markdown 文件")
    ap.add_argument("--after", required=True, help="改稿后的 Markdown 文件")
    a = ap.parse_args()

    before, after = Path(a.before), Path(a.after)
    src = before.read_text(encoding="utf-8")
    out = after.read_text(encoding="utf-8")

    problems, warnings = fidelity(src, out)
    print(f"保真闸 {before.name} -> {after.name}: {'未过' if problems else '通过'}", file=sys.stderr)
    report(problems, warnings)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

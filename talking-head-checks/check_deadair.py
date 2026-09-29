#!/usr/bin/env python3
"""
check_deadair.py — 成片「无人说话空隙」检查

背景：口播素材是即兴录的，人会在句与句之间停下来想事情，这些停顿长达 2–5 秒。
它们既不是"静音"（背景有风噪车流，silencedetect 用 -32dB 会漏掉），也不在黑帧、
响度、解码这些常规 QA 的覆盖范围内 —— 但观众会直接感到"卡住了"。
2026-09-17 那条成片里残留了 18.34 s 这样的空隙（最长 5.29 s），常规 QA 全绿。

判定口径：相邻两个词之间的间隔。这是最可靠的"没人说话"信号，
因为它来自词级时间戳，不受环境噪声影响。

用法一（渲染前预检，最便宜 —— 不需要重新转写）：
    python3 check_deadair.py --source-tsv <源片词级.tsv> --segments <segments.json>

用法二（成片终检，最准 —— 需要成片自己的词级 tsv）：
    python3 check_deadair.py --tsv <成片词级.tsv>

阈值约定（可调）：
    >0.8 s  提示（正常呼吸停顿，通常可留）
    >1.2 s  告警（会被听出来，应切掉或显式说明为什么留）
    >2.0 s  失败（必须处理）
退出码：有任何 >1.2 s 的残留即返回 1，可直接用于流程卡点。
"""

import argparse
import csv
import json
import sys


def load_tsv(path):
    words = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                words.append((int(row["start"]) / 1000.0, int(row["end"]) / 1000.0, row["text"]))
            except (KeyError, ValueError):
                continue
    words.sort()
    return words


def find_gaps(words, floor):
    out = []
    for i in range(len(words) - 1):
        gap = words[i + 1][0] - words[i][1]
        if gap > floor:
            out.append((words[i][1], words[i + 1][0], gap, words[i][2], words[i + 1][2]))
    return out


def build_timeline(segments_path):
    """返回 [(id, src_start, src_end, final_start)]，已归整到 30 fps 帧边界。"""
    data = json.load(open(segments_path, encoding="utf-8"))
    segs = data["segments"] if isinstance(data, dict) else data
    norm = lambda s: round(s * 30) / 30
    ordered = sorted(((g["id"], norm(g["start"]), norm(g["end"])) for g in segs), key=lambda x: x[1])
    timeline, offset = [], 0.0
    for sid, a, b in ordered:
        timeline.append((sid, a, b, offset))
        offset += b - a
    return timeline, offset


def overlap(a, b, lo, hi):
    return max(0.0, min(b, hi) - max(a, lo))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv", help="成片自己的词级 tsv（终检）")
    ap.add_argument("--source-tsv", help="源片词级 tsv（预检）")
    ap.add_argument("--segments", help="segments.json（预检时必填）")
    ap.add_argument("--floor", type=float, default=0.8, help="起始报告阈值，默认 0.8s")
    ap.add_argument("--fail-over", type=float, default=1.2, help="超过此值即判定失败，默认 1.2s")
    args = ap.parse_args()

    if not args.tsv and not (args.source_tsv and args.segments):
        ap.error("要么给 --tsv（成片终检），要么给 --source-tsv + --segments（渲染前预检）")

    if args.tsv:
        mode = "成片终检"
        words = load_tsv(args.tsv)
        rows = []
        for a, b, gap, t1, t2 in find_gaps(words, args.floor):
            rows.append((a, b, gap, t1, t2, gap))  # 成片里 100% 残留
    else:
        mode = "渲染前预检"
        words = load_tsv(args.source_tsv)
        timeline, total = build_timeline(args.segments)
        rows = []
        for a, b, gap, t1, t2 in find_gaps(words, args.floor):
            best = None
            for sid, sa, sb, so in timeline:
                d = overlap(a, b, sa, sb)
                if d > 0.05 and (best is None or d > best[3]):
                    lo, hi = max(a, sa), min(b, sb)
                    best = (sid, so + (lo - sa), so + (hi - sa), d)
            if best:
                sid, fs, fe, d = best
                rows.append((fs, fe, d, t1, t2, d, sid))

    print(f"模式：{mode}")
    print(f"词数：{len(words)}   报告阈值：>{args.floor}s   失败阈值：>{args.fail_over}s")
    if not args.tsv:
        print(f"成片总长：{total:.3f} s")
    print()

    if not rows:
        print("✓ 没有任何超过阈值的空隙。")
        return 0

    print(f"{'位置':>18}  {'残留':>6}  前后词")
    print("-" * 78)
    worst, failures = 0.0, 0
    for r in sorted(rows, key=lambda x: x[0]):
        if len(r) == 7:
            fs, fe, d, t1, t2, _, sid = r
            where = f"{sid} {fs:7.2f}–{fe:7.2f}"
        else:
            fs, fe, d, t1, t2, _ = r
            where = f"{fs:7.2f}–{fe:7.2f}"
        verdict = ""
        if d > 2.0:
            verdict = "  ← 必须切"
            failures += 1
        elif d > args.fail_over:
            verdict = "  ← 应切"
            failures += 1
        worst = max(worst, d)
        print(f"{where:>18}  {d:5.2f}s  「{t1}」→「{t2}」{verdict}")

    print("-" * 78)
    print(f"合计残留 {sum(r[2] for r in rows):.2f} s，最长 {worst:.2f} s，需处理 {failures} 处")
    if failures:
        print()
        print("处理办法：把对应段的边界收到「该段最后一个词的结束 + 0.15~0.25s」，")
        print("或在段中间再补一刀。段边界不要用「下一个删点在哪」来定。")
        return 1
    print()
    print("✓ 都在可接受范围（长空隙都是自然呼吸停顿）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

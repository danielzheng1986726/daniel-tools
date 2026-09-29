"""完整审改闭环:reviewer → contributor → re-review → 直到收敛或达到轮次上限。

DesignLab 思路完整复刻:
  1. 当前 actions → reviewer 找问题
  2. (可选)专家审 reviewer 标注
  3. contributor 改 actions → actions-vN+1
  4. re-review,看新版还剩多少问题
  5. 收敛(改动页数 < 5%) 或达到 max_iter → 停

输出:
  - actions-v{N}.json     每轮的 actions
  - reviewer-report-v{N}.json   每轮的 issue 报告
  - contributor-report-v{N}.json  每轮的修改记录
  - convergence-report.md       全闭环总结
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.core.actions_schema import DeckActions
from src.core.outline_parser import parse_outline
from src.reviewer_agent import review_deck, evaluate_recall_against_feedback, ReviewerReport, Issue
from src.contributor_agent import contribute, has_converged


def run_loop(
    base: Path,
    max_iter: int = 3,
    use_expert_feedback: bool = True,
    use_llm: bool = False,
    verbose: bool = True,
) -> dict:
    """跑完整闭环。

    Args:
        base: 项目目录
        max_iter: 最多跑几轮(默认 3)
        use_expert_feedback: 是否读 expert-feedback.json
        verbose: 打印进度

    Returns:
        {iterations: [...], converged: bool, final_recall_vs_feedback: float}
    """
    pages = parse_outline(base / "outline.md")
    pages_by_num = {p.page: p for p in pages}

    deck_path = base / "actions.json"
    deck = DeckActions.load(deck_path)

    # 先跑一遍 reviewer baseline
    if verbose:
        print(f"\n=== Iteration 1: Reviewer baseline ===")
    report = review_deck(deck, pages_by_num, use_llm=use_llm, llm_verbose=False)
    report.save(base / "reviewer-report.json")
    if verbose:
        s = report.summary()
        print(f"  共 {s['total']} 个问题,涉及 {s['pages_with_issues']} 页")

    # 评 baseline 召回率(如果 base 目录下有 feedback.json)
    initial_recall = None
    feedback_path = base / "feedback.json"
    if feedback_path.exists():
        ev = evaluate_recall_against_feedback(report, feedback_path)
        initial_recall = ev["recall"]
        if verbose:
            print(f"  vs 人工反馈: 召回 {ev['recall']*100:.1f}% ({ev['n_reviewer_caught']}/{ev['n_rejected']})")

    iterations = [{
        "iter": 1,
        "n_issues": report.summary()["total"],
        "n_pages": report.summary()["pages_with_issues"],
        "recall_vs_feedback": initial_recall,
        "n_changes": 0,
        "converged": False,
    }]

    feedback = None
    if use_expert_feedback:
        fb_path = base / "expert-feedback.json"
        if fb_path.exists():
            feedback = json.loads(fb_path.read_text(encoding="utf-8"))
            if verbose:
                print(f"  读到专家反馈 {len(feedback)} 条")

    # 多轮迭代
    converged = False
    for it in range(2, max_iter + 1):
        if verbose:
            print(f"\n=== Iteration {it}: Contributor + re-review ===")

        new_deck, contrib_report = contribute(
            deck, report.to_dict()["issues"],
            iteration=it,
            expert_feedback=feedback,
        )

        actions_out = base / f"actions-v{it}.json"
        new_deck.save(actions_out)
        contrib_report.deck_in = str(deck_path if it == 2 else base / f"actions-v{it-1}.json")
        contrib_report.deck_out = str(actions_out)
        contrib_report.save(base / f"contributor-report-v{it}.json")

        cs = contrib_report.summary()
        if verbose:
            print(f"  Contributor 改了 {cs['n_changes']} 处,涉及 {cs['n_pages_changed']} 页")
            print(f"  动作分布: {cs['by_action']}")

        # 重新审
        new_report = review_deck(new_deck, pages_by_num, use_llm=use_llm, llm_verbose=False)
        new_report.save(base / f"reviewer-report-v{it}.json")

        new_recall = None
        if feedback_path.exists():
            ev = evaluate_recall_against_feedback(new_report, feedback_path)
            new_recall = ev["recall"]

        iter_converged = has_converged(contrib_report, len(new_deck.slides))
        s = new_report.summary()
        if verbose:
            print(f"  重新审后:{s['total']} 个问题(原 {iterations[-1]['n_issues']})")
            if new_recall is not None:
                print(f"  vs 人工反馈: 召回 {new_recall*100:.1f}%")
            print(f"  收敛: {iter_converged}")

        iterations.append({
            "iter": it,
            "n_issues": s["total"],
            "n_pages": s["pages_with_issues"],
            "recall_vs_feedback": new_recall,
            "n_changes": cs["n_changes"],
            "converged": iter_converged,
        })

        deck = new_deck
        report = new_report

        if iter_converged:
            converged = True
            break

    return {
        "iterations": iterations,
        "converged": converged,
        "final_recall_vs_feedback": iterations[-1].get("recall_vs_feedback"),
    }


def write_convergence_report(base: Path, result: dict) -> Path:
    """写 convergence-report.md。"""
    L = ["# Convergence Report — 审改闭环", ""]
    L.append(f"项目: `{base.name}`")
    L.append(f"总轮数: {len(result['iterations'])}")
    L.append(f"是否收敛: **{'是' if result['converged'] else '否'}**")
    L.append("")
    L.append("## 每轮指标")
    L.append("")
    L.append("| 轮 | issues | 涉及页 | 改动数 | 召回率 |")
    L.append("|---|---|---|---|---|")
    for it in result["iterations"]:
        recall = f"{it['recall_vs_feedback']*100:.1f}%" if it.get("recall_vs_feedback") is not None else "—"
        L.append(f"| {it['iter']} | {it['n_issues']} | {it['n_pages']} | {it['n_changes']} | {recall} |")

    L.append("")
    L.append("## 结论")
    L.append("")
    first = result["iterations"][0]
    last = result["iterations"][-1]
    delta_issues = first["n_issues"] - last["n_issues"]
    pct = (delta_issues / first["n_issues"] * 100) if first["n_issues"] else 0
    L.append(f"- 问题数: {first['n_issues']} → {last['n_issues']} (-{delta_issues}, -{pct:.0f}%)")
    if last.get("recall_vs_feedback") is not None:
        L.append(f"- 人工反馈 召回率: {last['recall_vs_feedback']*100:.1f}%")
    L.append(f"- 收敛状态: {'到达' if result['converged'] else '未到达(可能需要 LLM Reviewer 升级或专家介入)'}")

    out_path = base / "convergence-report.md"
    out_path.write_text("\n".join(L), encoding="utf-8")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="完整审改闭环")
    ap.add_argument("--base", default="examples/demo-deck", help="项目目录")
    ap.add_argument("--max-iter", type=int, default=3, help="最多跑几轮")
    ap.add_argument("--no-feedback", action="store_true", help="忽略 expert-feedback.json")
    ap.add_argument("--llm", action="store_true", help="额外接 Claude reviewer(需 ANTHROPIC_API_KEY 或现成 reviewer-report-llm.json)")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    t0 = time.time()
    result = run_loop(base, max_iter=args.max_iter, use_expert_feedback=not args.no_feedback, use_llm=args.llm)
    elapsed = time.time() - t0

    out = write_convergence_report(base, result)
    print(f"\n=== 闭环跑完 ({elapsed:.1f}s) ===")
    print(f"收敛: {result['converged']}")
    print(f"报告 → {out}")


if __name__ == "__main__":
    main()

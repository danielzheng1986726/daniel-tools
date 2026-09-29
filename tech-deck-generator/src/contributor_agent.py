"""Contributor Agent: 根据 reviewer 标注 + 专家反馈,自动改 actions.json。

DesignLab 思路:Reviewer 找问题,Contributor 修。
每个 issue 对应一种修改动作。

Phase 4 实现策略:
  - rule-based 改动作(跟 reviewer 的 rule 一一对应)
  - 留 Claude API hook 处理高级修改(内容改写、术语调整等)
  - 不直接覆盖 actions.json,出 actions-v{N}.json,方便对照

迭代收敛指标:
  - 每轮记录"被改的页数"
  - 当一轮改动页数 < 5% 就停
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

from src.core.actions_schema import DeckActions, SlideActions


@dataclass
class Change:
    page: int
    rule: str
    action: str           # "remove_image" / "split_bullets" / "change_layout" / "mark_for_review"
    detail: str = ""


@dataclass
class ContributorReport:
    deck_in: str = ""
    deck_out: str = ""
    iteration: int = 1
    changes: list[Change] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "deck_in": self.deck_in,
            "deck_out": self.deck_out,
            "summary": self.summary(),
            "changes": [asdict(c) for c in self.changes],
        }

    def summary(self) -> dict:
        return {
            "n_changes": len(self.changes),
            "by_action": dict(Counter(c.action for c in self.changes)),
            "n_pages_changed": len(set(c.page for c in self.changes)),
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ===== 单条修改动作 =====

def remove_image(slide: SlideActions, reason: str) -> bool:
    """把 image action 移除(并加标记说明)。"""
    new_actions = []
    found = False
    for a in slide.actions:
        if a.get("type") == "image":
            found = True
            # 不彻底删,改成 placeholder type,renderer 渲染为空(后面专家可以挂别的图)
            new_actions.append({
                "type": "image_placeholder",
                "caption": a.get("caption", ""),
                "note": reason,
                "previous_path": a.get("path", ""),
            })
        else:
            new_actions.append(a)
    slide.actions = new_actions
    return found


def split_bullets(slide: SlideActions, max_items: int = 5) -> bool:
    """bullets 太多时,只留前 max_items 条,其余加 'note' action 标记溢出。"""
    bullets_idx = None
    for i, a in enumerate(slide.actions):
        if a.get("type") == "bullets":
            bullets_idx = i
            break
    if bullets_idx is None:
        return False
    items = slide.actions[bullets_idx].get("items", [])
    if len(items) <= max_items:
        return False
    overflow = items[max_items:]
    slide.actions[bullets_idx]["items"] = items[:max_items]
    slide.actions.insert(bullets_idx + 1, {
        "type": "note",
        "text": f"[溢出 {len(overflow)} 条:已截断,考虑拆分到下一页]",
    })
    return True


def change_layout(slide: SlideActions, new_layout: str) -> bool:
    """改 layout(只改字段,渲染时 export_pptx 自然走对应分支)。"""
    if slide.layout == new_layout:
        return False
    slide.layout = new_layout
    return True


def mark_for_review(slide: SlideActions, note: str) -> None:
    """加一条 note action,提醒专家。"""
    slide.actions.append({"type": "review_note", "text": note})


# ===== 主入口:跑一轮 Contributor =====

# 规则 → 动作 映射
RULE_TO_ACTION = {
    "schematic_vs_photo": ("mark_for_review", "需要换示意图(当前是实物照)"),
    "missing_image": ("mark_for_review", "需要扩 image pool 找图"),
    "image_duplicate": ("remove_image", "去重:其他页已用此图"),
    "bullets_overflow": ("split_bullets", ""),
    "content_thin": ("mark_for_review", "版面会空,补内容或换 layout"),
    "layout_mismatch_compare": ("change_layout", "side-by-side"),
    "multi_photo_wanted": ("change_layout", "multi-grid"),
}


def contribute(
    deck: DeckActions,
    issues: list[dict],
    iteration: int = 1,
    expert_feedback: dict | None = None,
) -> tuple[DeckActions, ContributorReport]:
    """根据 issues 修一遍 deck。

    Args:
        deck: 当前的 actions
        issues: reviewer-report 的 issues list
        iteration: 第几轮(用于命名)
        expert_feedback: 可选, 专家对每个 issue 的判断
                         {page_rule: "accept" / "reject" / "edit:..."}

    Returns:
        修改后的 deck, contributor report
    """
    new_deck = copy.deepcopy(deck)
    slides_by_page = {s.page: s for s in new_deck.slides}
    report = ContributorReport(iteration=iteration)

    for issue in issues:
        pn = issue["page"]
        rule = issue["rule"]

        # 专家反馈如果是 reject,跳过这条
        if expert_feedback:
            key = f"{pn}_{rule}"
            decision = expert_feedback.get(key, "accept")
            if decision == "reject":
                continue
            # TODO:支持 edit:... 让专家自定义动作

        slide = slides_by_page.get(pn)
        if not slide:
            continue

        action_spec = RULE_TO_ACTION.get(rule)
        if not action_spec:
            continue
        action_name, param = action_spec

        applied = False
        if action_name == "remove_image":
            applied = remove_image(slide, reason=param or "reviewer 标记重复")
        elif action_name == "split_bullets":
            applied = split_bullets(slide, max_items=5)
        elif action_name == "change_layout":
            applied = change_layout(slide, new_layout=param)
        elif action_name == "mark_for_review":
            mark_for_review(slide, param)
            applied = True

        if applied:
            report.changes.append(Change(
                page=pn, rule=rule, action=action_name, detail=param,
            ))

    return new_deck, report


def has_converged(report: ContributorReport, total_pages: int, threshold: float = 0.05) -> bool:
    """判断是否收敛。

    "实质改动"=真改了 actions(remove_image/split_bullets/change_layout)
    mark_for_review 是"打标签等专家",不算实质改动。
    当一轮里"实质改动"页数 < 总页数 * threshold 就收敛。
    """
    substantial = {"remove_image", "split_bullets", "change_layout"}
    real_changes = [c for c in report.changes if c.action in substantial]
    pages = {c.page for c in real_changes}
    return len(pages) / total_pages < threshold


def main():
    ap = argparse.ArgumentParser(description="Contributor agent: 修 actions.json")
    ap.add_argument("--base", default="examples/demo-deck", help="项目目录")
    ap.add_argument("--actions", help="输入 actions.json(默认 base/actions.json)")
    ap.add_argument("--report", help="reviewer report 路径")
    ap.add_argument("--out", help="输出新 actions(默认 base/actions-v2.json)")
    ap.add_argument("--iter", type=int, default=2, help="迭代轮数(命名用)")
    ap.add_argument("--feedback", help="可选: 专家反馈 JSON 路径")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    actions_path = Path(args.actions) if args.actions else base / "actions.json"
    report_path = Path(args.report) if args.report else base / "reviewer-report.json"
    out_path = Path(args.out) if args.out else base / f"actions-v{args.iter}.json"

    deck = DeckActions.load(actions_path)
    review_data = json.loads(report_path.read_text(encoding="utf-8"))
    issues = review_data.get("issues", [])

    feedback = None
    if args.feedback and Path(args.feedback).exists():
        feedback = json.loads(Path(args.feedback).read_text(encoding="utf-8"))

    new_deck, contrib_report = contribute(deck, issues, iteration=args.iter, expert_feedback=feedback)

    # 保存
    new_deck.save(out_path)
    contrib_report.deck_in = str(actions_path)
    contrib_report.deck_out = str(out_path)

    contrib_report_path = base / f"contributor-report-v{args.iter}.json"
    contrib_report.save(contrib_report_path)

    summary = contrib_report.summary()
    print(f"Iteration {args.iter} 修改完:")
    print(f"  改动数: {summary['n_changes']}")
    print(f"  涉及页: {summary['n_pages_changed']} / {len(new_deck.slides)}")
    print(f"  按动作: {summary['by_action']}")
    print(f"\nActions  → {out_path}")
    print(f"Report → {contrib_report_path}")

    converged = has_converged(contrib_report, len(new_deck.slides))
    print(f"\n收敛: {converged} (改动页数 < 5% = {len(new_deck.slides) * 0.05:.0f} 页)")


if __name__ == "__main__":
    main()

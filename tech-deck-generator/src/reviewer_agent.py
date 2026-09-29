"""Reviewer Agent: 自动审一遍 actions.json,标出 3 类问题。

DesignLab 思路:扮演"挑剔的审稿人",分类挑问题:
  - design: 布局错乱 / 配色冲突 / 文字遮挡 / 图文比例失衡
  - content: 事实错误 / 术语不准 / 表述不清 / bullets 过多过少
  - paradigm: layout 类型用错(应该用示意图却用了实物照,应该对比却没对比)

实现策略:
  - rule-based 规则集做 baseline(可用一份人工反馈 JSON 做 ground truth 评估召回率)
  - 留 Claude API hook,后面用 few-shot prompt 升级

目标:对人工反馈里标记「有问题」的页,Reviewer 能召回大部分。
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

from src.core.actions_schema import DeckActions, SlideActions
from src.core.outline_parser import parse_outline, Page


IssueKind = Literal["design", "content", "paradigm"]
Severity = Literal["high", "medium", "low"]


@dataclass
class Issue:
    page: int
    kind: IssueKind
    severity: Severity
    rule: str               # 触发的规则名
    message: str            # 给专家看的描述
    suggestion: str = ""    # 改进建议(可选)


@dataclass
class ReviewerReport:
    deck_source: str = ""
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "deck_source": self.deck_source,
            "issues": [asdict(i) for i in self.issues],
            "summary": self.summary(),
        }

    def summary(self) -> dict:
        cnt_kind = Counter(i.kind for i in self.issues)
        cnt_severity = Counter(i.severity for i in self.issues)
        pages_with_issues = len(set(i.page for i in self.issues))
        return {
            "total": len(self.issues),
            "by_kind": dict(cnt_kind),
            "by_severity": dict(cnt_severity),
            "pages_with_issues": pages_with_issues,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ===== 规则集 =====

# 提示词:配图建议里出现这些词,说明专家要"示意图"
SCHEMATIC_HINT_WORDS = ["示意图", "原理图", "结构图", "示意", "原理", "示例图"]
# 配图建议里出现这些,说明要"实物照片"
PHOTO_HINT_WORDS = ["照片", "实物", "产品图", "现场图"]  # 按你的领域补充具体型号
# 配图建议里出现这些,说明要"图表"
CHART_HINT_WORDS = ["曲线", "统计图", "柱状图", "对比表", "趋势图", "雷达图", "散点图"]


def _hint_wants_schematic(hint: str) -> bool:
    return any(w in hint for w in SCHEMATIC_HINT_WORDS)


def _hint_wants_photo(hint: str) -> bool:
    return any(w in hint for w in PHOTO_HINT_WORDS)


def _image_looks_photo(image_path: str | None) -> bool:
    """启发式:从 extracted/ch*/ 来的 PNG 多半是实物照,
    从 web-sourced/schematic/ 来的多半是示意图。"""
    if not image_path:
        return False
    p = str(image_path).lower()
    # 我们 Phase 2 都从 extracted/ 来,大部分是实物图
    if "extracted/" in p and "schematic" not in p:
        return True
    if "/photo" in p or "实物" in p:
        return True
    return False


def rule_paradigm_schematic_vs_photo(slide: SlideActions, hint: str, image_path: str | None) -> list[Issue]:
    """配图建议要"示意图",但 MVP 挑了实物照。"""
    if not _hint_wants_schematic(hint):
        return []
    if not image_path:
        return []
    if _image_looks_photo(image_path):
        return [Issue(
            page=slide.page,
            kind="paradigm",
            severity="high",
            rule="schematic_vs_photo",
            message=f"配图建议要示意图（hint: '{hint[:30]}'）,但挑的是实物照",
            suggestion="换成 web-sourced/schematic/ 下的图或自绘 SVG",
        )]
    return []


def rule_paradigm_missing_image(slide: SlideActions, hint: str, image_path: str | None) -> list[Issue]:
    """有 hint 说要图但 MVP 没挑到。"""
    if not hint:
        return []
    if image_path:
        return []
    if slide.layout in {"cover", "agenda", "section-divider"}:
        # 这些 layout 本身就不要图
        return []
    return [Issue(
        page=slide.page,
        kind="content",
        severity="medium",
        rule="missing_image",
        message=f"配图建议有 '{hint[:30]}',但没挑到图",
        suggestion="扩 image pool 或调 keyword 匹配",
    )]


def rule_design_bullets_overflow(slide: SlideActions, page: Page) -> list[Issue]:
    """bullets 太多,可能溢出。"""
    bullets_action = slide.find("bullets")
    if not bullets_action:
        return []
    n = len(bullets_action.get("items", []))
    if n > 6:
        return [Issue(
            page=slide.page,
            kind="design",
            severity="medium",
            rule="bullets_overflow",
            message=f"{n} 条 bullets,可能超出版面",
            suggestion="拆分到下一页或合并条目",
        )]
    return []


def rule_design_bullets_too_few(slide: SlideActions, page: Page) -> list[Issue]:
    """bullets 太少且没图,版面空。"""
    if slide.layout in {"cover", "section-divider"}:
        return []
    bullets_action = slide.find("bullets")
    text_action = slide.find("text")
    n = len(bullets_action.get("items", [])) if bullets_action else 0
    has_text = bool(text_action and text_action.get("text"))
    has_image = bool(slide.find("image"))
    if n < 2 and not has_text and not has_image:
        return [Issue(
            page=slide.page,
            kind="design",
            severity="low",
            rule="content_thin",
            message=f"只有 {n} 个 bullet 且没图,版面会很空",
            suggestion="补内容或换 layout",
        )]
    return []


def rule_paradigm_layout_mismatch_compare(slide: SlideActions, hint: str) -> list[Issue]:
    """image_hint 含 'vs / 对比' 但 layout 不是 side-by-side / data-table。"""
    has_compare = any(w in hint for w in [" vs ", "vs.", "对比", "v.s.", "+"])
    if not has_compare:
        return []
    if slide.layout in {"side-by-side", "data-table", "chart-hero"}:
        return []
    return [Issue(
        page=slide.page,
        kind="paradigm",
        severity="medium",
        rule="layout_mismatch_compare",
        message=f"配图建议含对比信号,但 layout 是 `{slide.layout}` 而不是 side-by-side",
        suggestion="换 side-by-side 或 chart-hero",
    )]


def rule_paradigm_multiple_photos_wanted(slide: SlideActions, hint: str) -> list[Issue]:
    """hint 含"多张照片"但 layout 是单图。"""
    if not any(w in hint for w in ["多张", "多个", "几种"]):
        return []
    if slide.layout in {"multi-grid", "case-showcase"}:
        return []
    return [Issue(
        page=slide.page,
        kind="paradigm",
        severity="medium",
        rule="multi_photo_wanted",
        message=f"配图建议含'多张照片'类信号,但 layout 是 `{slide.layout}` 单图模式",
        suggestion="换 multi-grid",
    )]


def rule_image_duplicate(deck: DeckActions) -> list[Issue]:
    """同一张图在多页用到。"""
    paths: dict[str, list[int]] = {}
    for slide in deck.slides:
        for a in slide.actions:
            if a.get("type") == "image":
                p = a.get("path", "")
                if p:
                    paths.setdefault(p, []).append(slide.page)
    issues = []
    for path, pages in paths.items():
        if len(pages) >= 2:
            # 同一张图用了 ≥ 2 次,在第 2 次及之后的页提示
            for p in pages[1:]:
                issues.append(Issue(
                    page=p,
                    kind="content",
                    severity="medium",
                    rule="image_duplicate",
                    message=f"图片 `{Path(path).name}` 在 p{pages[0]} 已经用过",
                    suggestion="换一张,避免重复",
                ))
    return issues


# ===== Reviewer 主入口 =====

def review_deck(
    deck: DeckActions,
    pages_by_num: dict[int, Page] | None = None,
    use_llm: bool = False,
    llm_api_key: str | None = None,
    llm_verbose: bool = True,
) -> ReviewerReport:
    """跑一遍所有规则。

    Args:
        deck: actions
        pages_by_num: outline 解析后的 Page dict
        use_llm: 是否额外接 Claude LLM 找问题(需要 ANTHROPIC_API_KEY)
        llm_api_key: 可选,覆盖环境变量
        llm_verbose: LLM 跑时打进度

    Returns:
        ReviewerReport,issues 是 rule + LLM 的合并去重结果。
    """
    if pages_by_num is None:
        pages_by_num = {}

    report = ReviewerReport(deck_source=deck.source_outline)

    # 全 deck 级规则
    report.issues.extend(rule_image_duplicate(deck))

    # 单页规则
    rule_issues = []
    for slide in deck.slides:
        page = pages_by_num.get(slide.page)
        hint = page.image_hint if page else ""

        image_action = slide.find("image")
        image_path = image_action.get("path", "") if image_action else None

        rule_issues.extend(rule_paradigm_schematic_vs_photo(slide, hint, image_path))
        rule_issues.extend(rule_paradigm_missing_image(slide, hint, image_path))
        if page:
            rule_issues.extend(rule_design_bullets_overflow(slide, page))
            rule_issues.extend(rule_design_bullets_too_few(slide, page))
        rule_issues.extend(rule_paradigm_layout_mismatch_compare(slide, hint))
        rule_issues.extend(rule_paradigm_multiple_photos_wanted(slide, hint))

    report.issues.extend(rule_issues)

    # LLM 加持(可选)
    if use_llm:
        from src.reviewer_llm import llm_review_deck, merge_issues
        llm_issues = llm_review_deck(
            deck, pages_by_num,
            api_key=llm_api_key,
            verbose=llm_verbose,
        )
        # 如果 LLM 没跑成(没 SDK / 没 key),尝试读已有的 reviewer-report-llm.json
        # (允许用 sub-agent 离线跑出来的结果)
        if not llm_issues:
            # heuristic:从 deck.source_outline 推 base 目录,找 reviewer-report-llm.json
            try:
                base_guess = Path(deck.source_outline).parent
                llm_path = base_guess / "reviewer-report-llm.json"
                if llm_path.exists():
                    if llm_verbose:
                        print(f"  ↳ 从 {llm_path.name} 读已有 LLM review 结果")
                    llm_data = json.loads(llm_path.read_text(encoding="utf-8"))
                    for entry in llm_data.get("issues", []):
                        llm_issues.append(Issue(
                            page=entry["page"],
                            kind=entry.get("kind", "content"),
                            severity=entry.get("severity", "medium"),
                            rule=entry.get("rule", "llm_unknown"),
                            message=entry.get("message", ""),
                            suggestion=entry.get("suggestion", ""),
                        ))
            except Exception as e:
                if llm_verbose:
                    print(f"  ⚠ 读 LLM review fallback 失败: {e}")
        # 合并去重
        report.issues = merge_issues(report.issues, llm_issues)

    # 按 page → severity 排序
    severity_order = {"high": 0, "medium": 1, "low": 2}
    report.issues.sort(key=lambda i: (i.page, severity_order.get(i.severity, 9)))

    return report


def evaluate_recall_against_feedback(report: ReviewerReport, feedback_path: str | Path) -> dict:
    """跟一份人工反馈 JSON 对照,看 Reviewer 能召回多少「专家标了有问题」的页。

    反馈文件格式：{"<页码>": {"rejected": true/false, ...}, ...}
    Reviewer 召回 = rejected=true 的页里,有多少被 Reviewer 也标了 issue。
    """
    feedback = json.loads(Path(feedback_path).read_text(encoding="utf-8"))
    rejected_pages = {int(k) for k, v in feedback.items() if k.isdigit() and v.get("rejected")}
    pages_with_issues = {i.page for i in report.issues}

    hit = rejected_pages & pages_with_issues
    miss = rejected_pages - pages_with_issues
    return {
        "n_rejected": len(rejected_pages),
        "n_reviewer_caught": len(hit),
        "recall": len(hit) / len(rejected_pages) if rejected_pages else 0,
        "rejected_pages": sorted(rejected_pages),
        "hit_pages": sorted(hit),
        "miss_pages": sorted(miss),
    }


def main():
    ap = argparse.ArgumentParser(description="Reviewer agent: 审 actions.json")
    ap.add_argument("--base", default="examples/demo-deck", help="项目目录")
    ap.add_argument("--actions", help="actions.json 路径(默认 base/actions.json)")
    ap.add_argument("--outline", help="outline.md 路径(默认 base/outline.md)")
    ap.add_argument("--out", help="输出报告路径(默认 base/reviewer-report.json)")
    ap.add_argument("--eval-feedback", action="store_true", help="跟 base/feedback.json 对照召回率(需自备该文件)")
    ap.add_argument("--llm", action="store_true", help="额外接 Claude 找问题(需要 ANTHROPIC_API_KEY)")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    actions_path = Path(args.actions) if args.actions else base / "actions.json"
    outline_path = Path(args.outline) if args.outline else base / "outline.md"

    deck = DeckActions.load(actions_path)
    pages = parse_outline(outline_path)
    pages_by_num = {p.page: p for p in pages}

    report = review_deck(deck, pages_by_num, use_llm=args.llm)

    out_path = Path(args.out) if args.out else base / "reviewer-report.json"
    report.save(out_path)

    summary = report.summary()
    print(f"Reviewer 跑完:")
    print(f"  共标 {summary['total']} 个问题")
    print(f"  涉及 {summary['pages_with_issues']} 页")
    print(f"  按类型: {summary['by_kind']}")
    print(f"  按严重度: {summary['by_severity']}")
    print(f"\nReport → {out_path}")

    if args.eval_feedback:
        feedback_path = base / "feedback.json"
        if feedback_path.exists():
            ev = evaluate_recall_against_feedback(report, feedback_path)
            print(f"\n=== 对比人工反馈 ===")
            print(f"人工标记的驳回页数: {ev['n_rejected']}")
            print(f"Reviewer 标到的: {ev['n_reviewer_caught']}")
            print(f"召回率: {ev['recall']*100:.1f}%")
            print(f"漏掉的页: {ev['miss_pages']}")
        else:
            print(f"\n未找到 {feedback_path}，跳过召回率对照")


if __name__ == "__main__":
    main()

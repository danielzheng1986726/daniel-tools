"""Source images for each page.

Phase 1 简化版：基于 extracted/{ch1..ch6,intro,repair}/manifest.json
做关键词匹配。每页找 top-N 候选。

Phase 2 会加：sub-agent 网络采集 + style-vector 引导筛选 + AI 交叉验证。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.core.outline_parser import Page


@dataclass
class ImageCandidate:
    file: str  # 相对路径
    source: str  # 哪个子目录（ch1 / intro / repair 等）
    source_page: int  # 在源 PPT 里第几页
    width: int
    height: int
    text: str  # 原 slide 上下文
    score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)


def _normalize_text(s: str) -> str:
    """归一化文本，便于关键词匹配。"""
    return s.lower().replace(" ", "").replace("（", "(").replace("）", ")")


def extract_keywords(page: Page) -> list[str]:
    """从 outline 一页里抽关键词。"""
    sources = [page.title, page.image_hint] + page.bullets
    text = " ".join(sources)

    # 提取 2-6 字的中文词组、英文术语
    cn_words = re.findall(r"[一-鿿]{2,6}", text)
    en_words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,15}", text)

    # 去重、去停用词
    stopwords = {"的", "了", "在", "是", "和", "或", "等", "及", "与", "可", "为"}
    cn_words = [w for w in cn_words if w not in stopwords and not all(c in stopwords for c in w)]
    en_words = [w for w in en_words if w.lower() not in {"the", "of", "and", "or", "vs"}]

    # 关键词加权：image_hint 里的词权重最高
    hint_words = re.findall(r"[一-鿿]{2,6}", page.image_hint)
    keywords = []
    seen = set()
    for w in hint_words + cn_words + en_words:
        if w not in seen:
            keywords.append(w)
            seen.add(w)
    return keywords[:30]  # 限制数量


def load_manifests(extracted_dir: str | Path) -> list[ImageCandidate]:
    """从 extracted/{*}/manifest.json 加载所有图片元数据。"""
    extracted = Path(extracted_dir)
    candidates: list[ImageCandidate] = []

    for manifest_path in sorted(extracted.glob("*/manifest.json")):
        sub_dir = manifest_path.parent.name
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ Skip {manifest_path}: {e}")
            continue
        # manifest 格式：list of {page, idx, w, h, file, text}
        items = data if isinstance(data, list) else data.get("items", [])
        for it in items:
            try:
                candidates.append(
                    ImageCandidate(
                        # manifest 的 file 已经是从项目根的相对路径（如 "extracted/ch1/p01-i4.png"）
                        file=str(it.get("file", "")),
                        source=sub_dir,
                        source_page=int(it.get("page", 0)),
                        width=int(it.get("w", 0)),
                        height=int(it.get("h", 0)),
                        text=str(it.get("text", "")),
                    )
                )
            except Exception:
                continue

    return candidates


def load_web_sourced(base_dir: str | Path) -> list[ImageCandidate]:
    """从 base/web-sourced/manifest.json 加载 web 采到的图。

    格式跟原 manifest 不同(WebSourcedImage),字段映射:
      file → file
      kind → source(类型当 source dir)
      caption_or_context → text(供关键词匹配)
      width/height → width/height
    """
    base = Path(base_dir)
    manifest_path = base / "web-sourced" / "manifest.json"
    if not manifest_path.exists():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ Skip {manifest_path}: {e}")
        return []

    out: list[ImageCandidate] = []
    for entry in data:
        try:
            # caption + page_title + image_alt + matched_keywords 拼起来作为 text(关键词匹配源)
            # matched_keywords 是 sub-agent 标注的命中词,通常含中英双语,匹配命中率最高
            text_parts = [
                entry.get("caption_or_context", ""),
                entry.get("page_title", ""),
                entry.get("image_alt", ""),
                " ".join(entry.get("matched_keywords", [])),
                entry.get("notes", ""),
            ]
            text = " ".join(p for p in text_parts if p)
            out.append(ImageCandidate(
                file=str(entry.get("file", "")),
                source=f"web/{entry.get('kind', '')}",  # 标记为 web 来源
                source_page=int(entry.get("page", 0)),
                width=int(entry.get("width", 0)),
                height=int(entry.get("height", 0)),
                text=text,
            ))
        except Exception:
            continue
    return out


def score_candidate(cand: ImageCandidate, keywords: list[str]) -> tuple[float, list[str]]:
    """对单张候选图打分。返回 (score, matched_keywords)。"""
    cand_text = _normalize_text(cand.text)
    if not cand_text:
        return 0.0, []

    matched = []
    score = 0.0
    for kw in keywords:
        kw_norm = _normalize_text(kw)
        if kw_norm and kw_norm in cand_text:
            matched.append(kw)
            score += 1.0

    # Width 太小降权
    if cand.width < 200:
        score *= 0.5
    elif cand.width < 400:
        score *= 0.8

    return score, matched


def match_page(
    page: Page,
    all_candidates: list[ImageCandidate],
    top_k: int = 3,
) -> list[ImageCandidate]:
    """给一页找 top-K 候选图。"""
    keywords = extract_keywords(page)
    if not keywords:
        return []

    scored: list[ImageCandidate] = []
    for cand in all_candidates:
        s, matched = score_candidate(cand, keywords)
        if s > 0:
            new = ImageCandidate(
                file=cand.file,
                source=cand.source,
                source_page=cand.source_page,
                width=cand.width,
                height=cand.height,
                text=cand.text[:80],  # 截断
                score=s,
                matched_keywords=matched,
            )
            scored.append(new)

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]


def _load_cv_results(base_dir: str | Path) -> dict[int, bool]:
    """从 cross-validation.json 读取每页的验证结果。

    Returns: {page: passed} 映射
    """
    cv_path = Path(base_dir) / "web-sourced" / "cross-validation.json"
    if not cv_path.exists():
        return {}
    try:
        data = json.loads(cv_path.read_text(encoding="utf-8"))
        return {r["page"]: r["match"] for r in data.get("results", [])}
    except Exception:
        return {}


def source_images_for_outline(
    pages: list[Page],
    extracted_dir: str | Path,
    base_dir: str | Path | None = None,
    web_boost: float = 1.5,
    cv_pass_boost: float = 2.0,
    cv_fail_penalty: float = 0.1,
    dedup_penalty: float = 0.3,
) -> dict[int, list[ImageCandidate]]:
    """主入口：给整本 outline 每页找候选图。

    Args:
        pages: outline 解析后的页面列表
        extracted_dir: extracted/ 目录(原始 PPT 提取的图池)
        base_dir: 项目根目录,如果有则尝试读 web-sourced/manifest.json
        web_boost: web-sourced 的基础加权(默认 ×1.5)
        cv_pass_boost: 交叉验证通过的 web 图额外加权(默认 ×2.0)
        cv_fail_penalty: 交叉验证失败的 web 图惩罚(默认 ×0.3,大幅降权)
        dedup_penalty: 图片已被前面的页选为 top-1 时的降权系数(默认 ×0.3)
                       每多被选一次,再乘一次(第2次用 ×0.3, 第3次 ×0.09, ...)
    """
    extracted_cands = load_manifests(extracted_dir)
    print(f"Loaded {len(extracted_cands)} candidates from {extracted_dir}")

    web_cands = []
    cv_results: dict[int, bool] = {}
    if base_dir:
        web_cands = load_web_sourced(base_dir)
        if web_cands:
            print(f"Loaded {len(web_cands)} web-sourced candidates from {Path(base_dir) / 'web-sourced'}")
        cv_results = _load_cv_results(base_dir)
        if cv_results:
            n_pass = sum(1 for v in cv_results.values() if v)
            print(f"Loaded {len(cv_results)} CV results ({n_pass} passed, {len(cv_results)-n_pass} failed)")

    # 去重计数：记录每张图已经被多少页选为 top-1
    used_count: dict[str, int] = {}

    result: dict[int, list[ImageCandidate]] = {}
    for page in pages:
        # 分别打分
        extracted_scored = match_page(page, extracted_cands, top_k=10)
        web_scored = match_page(page, web_cands, top_k=10) if web_cands else []
        # web 图分数加权,结合交叉验证结果
        for c in web_scored:
            page_num = c.source_page or page.page
            if page_num in cv_results:
                if cv_results[page_num]:
                    c.score *= web_boost * cv_pass_boost
                else:
                    c.score *= cv_fail_penalty
            else:
                c.score *= web_boost

        # 合并
        merged = web_scored + extracted_scored

        # 去重降权：已被选过的图降分,鼓励每页用不同的图
        for c in merged:
            n_used = used_count.get(c.file, 0)
            if n_used > 0:
                c.score *= dedup_penalty ** n_used

        # 排序 + top-3
        merged.sort(key=lambda c: c.score, reverse=True)
        top3 = merged[:3]
        result[page.page] = top3

        # 记录 top-1 已使用
        if top3:
            f = top3[0].file
            used_count[f] = used_count.get(f, 0) + 1

    n_unique = len(set(
        cands[0].file for cands in result.values() if cands
    ))
    print(f"Dedup: {n_unique} unique top-1 images across {len(pages)} pages")
    return result


def save_matches(
    matches: dict[int, list[ImageCandidate]],
    pages: list[Page],
    path: str | Path,
) -> None:
    """保存到 matches.json。"""
    output = []
    pages_by_num = {p.page: p for p in pages}
    for pn in sorted(matches.keys()):
        cands = matches[pn]
        page = pages_by_num.get(pn)
        output.append({
            "page": pn,
            "title": page.title if page else "",
            "image_hint": page.image_hint if page else "",
            "candidates": [
                {
                    "file": c.file,
                    "source": c.source,
                    "source_page": c.source_page,
                    "score": c.score,
                    "keywords": c.matched_keywords,
                    "w": c.width,
                    "h": c.height,
                }
                for c in cands
            ],
        })
    Path(path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    from src.core.outline_parser import parse_outline

    outline_path = sys.argv[1] if len(sys.argv) > 1 else "examples/demo-deck/outline.md"
    extracted_dir = sys.argv[2] if len(sys.argv) > 2 else "examples/demo-deck/extracted"
    out_path = sys.argv[3] if len(sys.argv) > 3 else "examples/demo-deck/matches.json"

    pages = parse_outline(outline_path)
    matches = source_images_for_outline(pages, extracted_dir)

    # Stats
    n_with_match = sum(1 for cands in matches.values() if cands)
    avg_top1 = sum(cands[0].score if cands else 0 for cands in matches.values()) / len(pages)
    print(f"\nPages with matches: {n_with_match}/{len(pages)}")
    print(f"Avg top-1 score: {avg_top1:.2f}")

    save_matches(matches, pages, out_path)
    print(f"Saved to {out_path}")

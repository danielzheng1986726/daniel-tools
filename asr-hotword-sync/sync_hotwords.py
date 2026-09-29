#!/usr/bin/env python3
"""热词表 → 转写引擎同步。

把「正确写法 vs 常见误转」对照表（markdown 表格，见 example_glossaries/）里
「正确」列提炼成热词，喂给转写引擎，在源头减少同音字/术语误转（比如
「张三→张山」「Claude→cloud」这类问题）。

两个出口：
  1. DashScope paraformer-v2 —— 本脚本自动创建/更新 vocabulary，
     vocabulary_id 存 data/hotwords_state.json。
  2. 飞书妙记「个人热词」—— 无 API，本脚本产出 data/feishu_hotwords.txt，
     打开 minutes.feishu.cn → 设置 → 个人热词，整页粘贴一次即可。

用法（更新词表后重跑一次即可，幂等）：
    python3 sync_hotwords.py                         # 用默认的示例词表
    python3 sync_hotwords.py --dry-run                # 只看会喂哪些词，不调 API
    python3 sync_hotwords.py --glossary my_people.md --glossary my_terms.md
                                                        # 换成自己的词表文件（可传多个）

词表文件格式：markdown 表格，表头第一列写「正确」的表会被提炼；表头第一列
不是「正确」的表（比如还没确认对错的疑似误转词表）整表跳过，避免把错误写法
也喂进热词表。具体格式见 example_glossaries/ 下两个示例文件。

密钥：只从环境变量 DASHSCOPE_API_KEY 读，不读任何本机文件，不打印。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_GLOSSARIES = [
    SCRIPT_DIR / "example_glossaries" / "people_glossary.md",
    SCRIPT_DIR / "example_glossaries" / "terms_glossary.md",
]
DATA_DIR = SCRIPT_DIR / "data"
STATE_FILE = DATA_DIR / "hotwords_state.json"
FEISHU_OUT = DATA_DIR / "feishu_hotwords.txt"

# DashScope 热词约束：中文热词建议 ≤10 字，英文可稍长；超长词直接跳过
MAX_ZH_LEN = 10
MAX_EN_LEN = 25
WEIGHT = 4


def load_api_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if key and not key.startswith("replace-with"):
        return key
    sys.exit("DASHSCOPE_API_KEY 未设置。export DASHSCOPE_API_KEY='replace-with-your-key'")


def _clean_cell(cell: str) -> str:
    return cell.replace("**", "").strip()


def extract_terms(md_path: Path) -> list[str]:
    """只解析表头第一列为「正确」的表（另有「疑似误转」一类的表，
    其第一列是待核实的误转词，喂进热词等于强化错误识别，必须整表跳过）。
    取「正确」列，拆多名、拆括号，滤掉待核与占位。"""
    terms: list[str] = []
    in_correct_table = False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            in_correct_table = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        if set(cells[0]) <= {":", "-", " "}:
            continue  # 分隔线，沿用当前表状态
        if _clean_cell(cells[0]) == "正确":
            in_correct_table = True
            continue  # 表头行本身不是词
        if len(cells) >= 2 and not in_correct_table:
            continue  # 非「正确」表（如疑似误转表）整表跳过
        raw = _clean_cell(cells[0])
        if "待核" in raw or raw == "—" or len(raw) > 30:
            continue  # 超长第一列是描述句不是词
        # 拆「A / B（C）」：主名按 / 分，括号内容再按 ，、, 分
        for part in re.split(r"[/／]", raw):
            part = part.strip()
            inner = re.findall(r"[（(]([^（）()]*)[）)]", part)
            main = re.sub(r"[（(][^（）()]*[）)]", "", part).strip()
            for cand in [main] + [p.strip() for s in inner for p in re.split(r"[，、,]", s)]:
                if not cand or cand == "—" or "待核" in cand:
                    continue
                is_ascii = all(ord(ch) < 128 for ch in cand)
                if is_ascii and len(cand) > MAX_EN_LEN:
                    continue
                if not is_ascii and len(cand) > MAX_ZH_LEN:
                    continue
                terms.append(cand)
    return terms


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印词表，不调 API")
    ap.add_argument("--glossary", action="append", type=Path, default=None,
                     help="词表文件路径，可传多个；不传则用 example_glossaries/ 下的示例词表")
    args = ap.parse_args()

    glossaries = args.glossary if args.glossary else DEFAULT_GLOSSARIES

    seen: dict[str, None] = {}
    for g in glossaries:
        if g.exists():
            for t in extract_terms(g):
                seen.setdefault(t, None)
    terms = list(seen)
    if not terms:
        sys.exit("词表为空，检查词表文件路径和格式")

    vocab = [
        {"text": t, "weight": WEIGHT,
         "lang": "en" if all(ord(ch) < 128 for ch in t) else "zh"}
        for t in terms
    ]

    print(f"提炼热词 {len(vocab)} 条：")
    print("  " + "、".join(terms))

    # 飞书粘贴清单永远重新生成（dry-run 也生成，无副作用）
    DATA_DIR.mkdir(exist_ok=True)
    FEISHU_OUT.write_text("\n".join(terms) + "\n", encoding="utf-8")
    print(f"\n飞书粘贴清单已写入 {FEISHU_OUT}")
    print("  → 打开 minutes.feishu.cn 右上角设置 → 个人热词，整页粘贴")

    if args.dry_run:
        print("\n--dry-run：未调 DashScope API")
        return

    import dashscope
    dashscope.api_key = load_api_key()
    from dashscope.audio.asr import VocabularyService

    svc = VocabularyService()
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    vid = state.get("vocabulary_id")

    if vid:
        svc.update_vocabulary(vid, vocab)
        print(f"\nDashScope 词表已更新（vocabulary_id={vid}，{len(vocab)} 条）")
    else:
        vid = svc.create_vocabulary(target_model="paraformer-v2",
                                    prefix="hotwords", vocabulary=vocab)
        print(f"\nDashScope 词表已创建（vocabulary_id={vid}，{len(vocab)} 条）")

    state.update({"vocabulary_id": vid, "term_count": len(vocab)})
    from datetime import date
    state["last_synced"] = date.today().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"状态已存 {STATE_FILE}；下次转写调用可复用此 vocabulary_id")


if __name__ == "__main__":
    main()

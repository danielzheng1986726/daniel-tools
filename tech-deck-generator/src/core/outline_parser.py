"""Parse a markdown outline.md into structured page list.

Format expected:
```
## 章节标题（可选）

### 第N页：标题
**要点**：
- bullet 1
- bullet 2
- **加粗强调**：详细内容

> 配图建议：xxx

| col1 | col2 |
|------|------|
| a    | b    |
```
"""
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Page:
    page: int
    title: str
    bullets: list[str] = field(default_factory=list)
    sub_bullets: dict[int, list[str]] = field(default_factory=dict)  # idx → sub-items
    image_hint: str = ""
    table_header: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    chapter: str = ""

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "title": self.title,
            "bullets": self.bullets,
            "sub_bullets": self.sub_bullets,
            "image_hint": self.image_hint,
            "table_header": self.table_header,
            "table_rows": self.table_rows,
            "chapter": self.chapter,
        }

    @property
    def has_table(self) -> bool:
        return bool(self.table_header and self.table_rows)


def parse_outline(path: str | Path) -> list[Page]:
    """Parse markdown outline file → list of Page objects, ordered by page number."""
    text = Path(path).read_text(encoding="utf-8")
    pages: list[Page] = []
    current: Page | None = None
    current_chapter = ""

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()

        # Detect chapter heading (e.g. "## 第1章：示例主题概述")
        chap_m = re.match(r"^##\s+(.+)", line)
        if chap_m and not line.startswith("###"):
            current_chapter = chap_m.group(1).strip()
            continue

        # Detect page heading (e.g. "### 第3页：什么是示例主题？")
        page_m = re.match(r"^###\s*第(\d+)页[：:]\s*(.+)", line)
        if page_m:
            if current is not None:
                pages.append(current)
            current = Page(
                page=int(page_m.group(1)),
                title=page_m.group(2).strip(),
                chapter=current_chapter,
            )
            continue

        if current is None or not stripped:
            continue

        # Skip "**要点**" header line
        if stripped.startswith("**要点**"):
            continue

        # Image hint
        if stripped.startswith("> 配图建议"):
            current.image_hint = re.sub(r"^>\s*配图建议[：:]\s*", "", stripped).strip()
            continue

        # Markdown table
        if re.match(r"^\|.+\|.+\|", stripped) and "---" not in stripped:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not current.table_header:
                current.table_header = cells
            else:
                current.table_rows.append(cells)
            continue

        # Bullet
        if stripped.startswith("- "):
            bullet = stripped[2:].strip()
            current.bullets.append(bullet)
            continue

        # Sub-bullet (indented dash or — or · or  - at start)
        if (line.startswith("  ") and stripped.startswith("-")) or stripped.startswith("—") or stripped.startswith("·"):
            sub = re.sub(r"^[—·\s\-]+", "", stripped).strip()
            if current.bullets:
                idx = len(current.bullets) - 1
                current.sub_bullets.setdefault(idx, []).append(sub)
            continue

    if current is not None:
        pages.append(current)

    pages.sort(key=lambda p: p.page)
    return pages


if __name__ == "__main__":
    import sys
    from collections import Counter

    path = sys.argv[1] if len(sys.argv) > 1 else "examples/demo-deck/outline.md"
    pages = parse_outline(path)

    print(f"Total pages: {len(pages)}")
    print(f"First page: {pages[0].page} - {pages[0].title}")
    print(f"Last page: {pages[-1].page} - {pages[-1].title}")

    # Stats
    n_with_bullets = sum(1 for p in pages if p.bullets)
    n_with_image_hint = sum(1 for p in pages if p.image_hint)
    n_with_table = sum(1 for p in pages if p.has_table)
    n_with_sub = sum(1 for p in pages if p.sub_bullets)
    print(f"\nWith bullets: {n_with_bullets}")
    print(f"With image hint: {n_with_image_hint}")
    print(f"With table: {n_with_table}")
    print(f"With sub-bullets: {n_with_sub}")

    chapters = Counter(p.chapter for p in pages if p.chapter)
    print(f"\nChapters ({len(chapters)}):")
    for ch, n in chapters.most_common():
        print(f"  {ch}: {n} pages")

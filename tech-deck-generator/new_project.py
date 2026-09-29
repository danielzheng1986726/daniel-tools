#!/usr/bin/env python3
"""Initialize a new AI TechDeck project directory.

Usage:
    python3 new_project.py --name "示例技术讲义"
    python3 new_project.py --name "my-topic" --dir custom_output/
"""
from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path


OUTLINE_TEMPLATE = textwrap.dedent("""\
    # {title}


    ## 第1章：章节标题（页数）

    ### 第1页：封面
    **标题**：{title}
    **副标题**：副标题文字
    **信息**：主讲人｜日期｜单位

    > 配图建议：封面配图描述


    ### 第2页：幻灯片标题
    **要点**：
    - **关键概念**：对概念的解释说明
    - 普通要点内容
    - 另一条要点

    > 配图建议：建议使用的配图描述


    ### 第3页：另一张幻灯片
    **要点**：
    - 要点一
    - 要点二
    - 要点三

    > 配图建议：配图描述


    ## 第2章：下一章标题（页数）

    ### 第4页：幻灯片标题
    **要点**：
    - 内容要点
    - 更多内容

    > 配图建议：配图描述
""")


def slugify(name: str) -> str:
    """Turn a human-readable name into a filesystem-safe directory name."""
    # Keep Chinese characters, alphanumerics, hyphens, underscores
    slug = re.sub(r"[^\w一-鿿-]", "-", name)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def create_project(name: str, parent_dir: Path) -> Path:
    """Create the project directory structure and return its path."""
    dir_name = slugify(name)
    project_dir = parent_dir / dir_name

    if project_dir.exists():
        raise SystemExit(f"Error: directory already exists: {project_dir}")

    # Create directories
    project_dir.mkdir(parents=True)
    (project_dir / "extracted").mkdir()
    (project_dir / "source-materials").mkdir()

    # Write outline template
    outline = OUTLINE_TEMPLATE.format(title=name)
    (project_dir / "outline.md").write_text(outline, encoding="utf-8")

    return project_dir


def main():
    ap = argparse.ArgumentParser(
        description="Initialize a new AI TechDeck project directory.",
    )
    ap.add_argument(
        "--name",
        required=True,
        help="Project name (used as directory name and outline title)",
    )
    ap.add_argument(
        "--dir",
        default="projects",
        help="Parent directory for the new project (default: projects/)",
    )
    args = ap.parse_args()

    parent = Path(args.dir).resolve()
    project_dir = create_project(args.name, parent)

    # Print instructions
    rel = project_dir.relative_to(Path.cwd()) if project_dir.is_relative_to(Path.cwd()) else project_dir
    print(f"\n  Project created: {rel}/\n")
    print(f"  {rel}/")
    print(f"  ├── outline.md            <- 大纲模板（已生成）")
    print(f"  ├── extracted/            <- 图片提取目录（pipeline 自动填充）")
    print(f"  └── source-materials/     <- 源文件目录")
    print()
    print("  接下来：")
    print(f"  1. 把你的源 PPT/PDF 文件放到 source-materials/ 目录")
    print(f"  2. 编辑 outline.md，写你的大纲")
    print(f"  3. 然后运行 pipeline 生成 PPT：")
    print(f"     python -m src.core.pipeline --base {rel}")
    print()


if __name__ == "__main__":
    main()

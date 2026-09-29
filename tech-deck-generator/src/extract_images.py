"""从 PPTX 文件提取图片到 extracted/ 目录。

每个 PPTX 提取为一个子目录，包含 PNG 文件和 manifest.json。
manifest 格式与 source_images.py 兼容。

用法：
    python -m src.extract_images path/to/source.pptx --name ch1 --base examples/demo-deck
    python -m src.extract_images path/to/source.pptx --base projects/my-project
"""
from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Emu


MIN_SIZE = 50  # 宽高低于此值的图跳过


def _slugify(name: str) -> str:
    """把文件名转成 ASCII-safe 的目录名。"""
    stem = Path(name).stem
    # 如果全是中文，取前 10 个字符做拼音缩写太麻烦，直接用 hash
    safe = re.sub(r"[^\w一-鿿-]", "-", stem)
    safe = re.sub(r"-{2,}", "-", safe).strip("-")
    return safe[:40] or "source"


def _collect_slide_text(slide) -> str:
    """提取一页 slide 上所有文本，拼接为一行。"""
    texts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                line = para.text.strip()
                if line:
                    texts.append(line)
    return " ".join(texts)


def extract_from_pptx(
    pptx_path: str | Path,
    output_dir: str | Path,
    rel_prefix: str = "",
) -> list[dict]:
    """从单个 PPTX 提取所有图片。

    Args:
        pptx_path: PPTX 文件路径
        output_dir: 图片输出目录（绝对路径）
        rel_prefix: manifest 中 file 字段的相对路径前缀
                    例如 "extracted/ch1"，则 file = "extracted/ch1/p03-i1.png"

    Returns:
        manifest 条目列表
    """
    pptx_path = Path(pptx_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prs = Presentation(str(pptx_path))
    entries: list[dict] = []
    total_skipped = 0

    for slide_idx, slide in enumerate(prs.slides, start=1):
        slide_text = _collect_slide_text(slide)
        img_idx = 0

        for shape in slide.shapes:
            # shape_type == 13 是 Picture
            if shape.shape_type != 13:
                continue
            if not hasattr(shape, "image"):
                continue

            try:
                blob = shape.image.blob
                img = Image.open(io.BytesIO(blob))
                w, h = img.size

                # 跳过太小的图
                if w < MIN_SIZE or h < MIN_SIZE:
                    total_skipped += 1
                    continue

                img_idx += 1
                filename = f"p{slide_idx:02d}-i{img_idx}.png"
                out_path = output_dir / filename

                # 统一转 PNG
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.save(out_path, "PNG")

                rel_file = f"{rel_prefix}/{filename}" if rel_prefix else filename
                entries.append({
                    "page": slide_idx,
                    "idx": img_idx,
                    "w": w,
                    "h": h,
                    "file": rel_file,
                    "text": slide_text,
                })
            except Exception as e:
                print(f"  ⚠ slide {slide_idx}: 跳过一张图 ({e})")
                continue

    print(f"  提取 {len(entries)} 张图，跳过 {total_skipped} 张小图")
    return entries


def extract_all_sources(
    base_dir: str | Path,
    source_dir: str | Path | None = None,
) -> int:
    """批量提取 source-materials/ 下所有 PPTX 文件。

    Args:
        base_dir: 项目根目录（如 projects/my-project）
        source_dir: 源文件目录，默认 base_dir/source-materials/

    Returns:
        总提取图片数
    """
    base = Path(base_dir)
    src_dir = Path(source_dir) if source_dir else base / "source-materials"
    extracted = base / "extracted"
    extracted.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        print(f"⚠ 源文件目录不存在: {src_dir}")
        return 0

    pptx_files = sorted(src_dir.glob("*.pptx"))
    if not pptx_files:
        print(f"⚠ {src_dir} 下没有 PPTX 文件")
        return 0

    total = 0
    for pptx_path in pptx_files:
        sub_name = _slugify(pptx_path.name)
        out_dir = extracted / sub_name
        rel_prefix = f"extracted/{sub_name}"

        print(f"\n[{pptx_path.name}] → {out_dir.name}/")
        entries = extract_from_pptx(pptx_path, out_dir, rel_prefix)

        # 写 manifest
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  manifest: {len(entries)} 条 → {manifest_path.name}")
        total += len(entries)

    print(f"\n共提取 {total} 张图，来自 {len(pptx_files)} 个 PPTX")
    return total


def main():
    ap = argparse.ArgumentParser(description="从 PPTX 提取图片到 extracted/ 目录")
    ap.add_argument("pptx", nargs="?", help="单个 PPTX 文件路径（不指定则批量处理 source-materials/）")
    ap.add_argument("--name", help="子目录名（默认从文件名推导）")
    ap.add_argument("--base", default=".", help="项目根目录（默认当前目录）")
    args = ap.parse_args()

    base = Path(args.base).resolve()

    if args.pptx:
        # 单文件模式
        pptx_path = Path(args.pptx).resolve()
        sub_name = args.name or _slugify(pptx_path.name)
        out_dir = base / "extracted" / sub_name
        rel_prefix = f"extracted/{sub_name}"

        print(f"[{pptx_path.name}] → {out_dir}/")
        entries = extract_from_pptx(pptx_path, out_dir, rel_prefix)

        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"manifest: {len(entries)} 条 → {manifest_path}")
    else:
        # 批量模式
        extract_all_sources(base)


if __name__ == "__main__":
    main()

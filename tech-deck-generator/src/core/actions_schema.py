"""Actions schema: 每页 PPT 的语义化中间产物。

借鉴 PPTAgent (中科院 / DeepPresenter):不直接出 PPTX,先出 actions 序列,
然后 renderer 把 actions + layout + style_vector 还原成 PPTX/HTML。

好处:
  1. reviewer / contributor agent 改 actions 时,改的是"语义元素"
     (改标题 / 换图 / 调整 bullet 顺序),不必懂渲染坐标
  2. actions.json 可以版本化,审改记录追溯
  3. 同一份 actions 能 render 成 PPTX 和 HTML 预览,保证一致性
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Any


# ===== 单个 action 类型 =====

@dataclass
class TitleAction:
    type: Literal["title"] = "title"
    text: str = ""
    subtitle: str = ""  # 可选


@dataclass
class EyebrowAction:
    """章节标签(顶部小字)。"""
    type: Literal["eyebrow"] = "eyebrow"
    text: str = ""
    chapter_num: str = ""  # "01" "02" 等


@dataclass
class BulletsAction:
    type: Literal["bullets"] = "bullets"
    items: list[str] = field(default_factory=list)
    sub_items: dict[int, list[str]] = field(default_factory=dict)  # 父 bullet idx → 子 bullets


@dataclass
class ImageAction:
    type: Literal["image"] = "image"
    path: str = ""          # 相对 base 的路径
    caption: str = ""
    role: str = "primary"   # primary / secondary / decoration


@dataclass
class TableAction:
    type: Literal["table"] = "table"
    header: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class TextBlockAction:
    """通用文本块(用于 hero 定义、概述这种)。"""
    type: Literal["text"] = "text"
    text: str = ""
    emphasis: bool = False


@dataclass
class FlowStepAction:
    """流程步骤(配 flow-strip layout 用)。"""
    type: Literal["flow_step"] = "flow_step"
    index: int = 0
    label: str = ""
    detail: str = ""


@dataclass
class CompareAction:
    """对比项(配 side-by-side layout 用)。"""
    type: Literal["compare"] = "compare"
    left_label: str = ""
    left_items: list[str] = field(default_factory=list)
    right_label: str = ""
    right_items: list[str] = field(default_factory=list)


# ===== 一整页的 actions =====

@dataclass
class SlideActions:
    page: int                           # 页码
    layout: str                         # 12 种 layout 标签之一
    chapter: str = ""                   # 章节名(便于 chrome 渲染)
    actions: list[dict] = field(default_factory=list)

    def add(self, action: Any) -> None:
        """加一个 action(自动转 dict)。"""
        if hasattr(action, "__dataclass_fields__"):
            self.actions.append(asdict(action))
        elif isinstance(action, dict):
            self.actions.append(action)
        else:
            raise TypeError(f"unsupported action type: {type(action)}")

    def find(self, action_type: str) -> dict | None:
        """找某类型的第一个 action(改起来方便)。"""
        for a in self.actions:
            if a.get("type") == action_type:
                return a
        return None


# ===== 整本 deck =====

@dataclass
class DeckActions:
    """整本 PPT 的 actions 文件结构。"""
    version: str = "1.0"
    source_outline: str = ""           # outline.md 路径
    style_vector_path: str = ""        # style-vector.json 路径
    slides: list[SlideActions] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "source_outline": self.source_outline,
            "style_vector_path": self.style_vector_path,
            "slides": [asdict(s) for s in self.slides],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "DeckActions":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        deck = cls(
            version=data.get("version", "1.0"),
            source_outline=data.get("source_outline", ""),
            style_vector_path=data.get("style_vector_path", ""),
        )
        for s in data.get("slides", []):
            sa = SlideActions(
                page=s["page"],
                layout=s["layout"],
                chapter=s.get("chapter", ""),
                actions=s.get("actions", []),
            )
            deck.slides.append(sa)
        return deck

    def get_page(self, page: int) -> SlideActions | None:
        for s in self.slides:
            if s.page == page:
                return s
        return None

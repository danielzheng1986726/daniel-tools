"""Style vector: 从 reference-deck.pptx 提的风格指纹。

下游 sub-agent（layout planner / SVG generator / export_pptx）
都会读这个 vector,让产出的 PPT 跟示范稿对齐。

设计借鉴 SlideTailor (arXiv 2512.20292):
  - color palette (主色 + 强调色 + 文字色)
  - font ramp (eyebrow / body / sub / title 四档字号)
  - layout density (文/图比例)
  - chrome elements (页眉、页脚、页码格式)
  - aesthetic signals (横线、侧边章号、留白)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ColorPalette:
    # 命名都是语义化的（不绑定具体色值,方便换主题）
    primary: str = "#1E3A5F"      # 主色（页眉、章节号、强调）
    accent: str = "#C2410C"        # 强调色（关键数字、橙竖条）
    text_primary: str = "#2E3338"  # 正文文字
    text_secondary: str = "#6B7280"  # 辅助文字（caption / source）
    text_emphasis: str = "#131517"  # 重要文字（加粗、数字）
    bg_primary: str = "#FFFFFF"    # 主背景
    bg_card: str = "#F5F0E6"       # 卡片背景（米色）
    rule_color: str = "#1E3A5F"    # 横线/边线颜色


@dataclass
class FontRamp:
    """字号从大到小四档,按 PPTX 单位 pt。"""
    title: float = 26.0       # 页标题
    subtitle: float = 15.0    # 副标题/小节标题
    body: float = 12.0        # 正文
    caption: float = 10.0     # 图说/辅助
    eyebrow: float = 10.0     # 顶部章节标签
    font_cn: str = "PingFang SC"
    font_en: str = "Helvetica Neue"


@dataclass
class LayoutDensity:
    """文/图密度,影响每页内容量。"""
    bullets_per_page_avg: float = 4.0   # 一页几个 bullet
    bullets_per_page_max: int = 8       # 上限
    image_ratio: float = 0.45            # 图占内容区面积比
    has_caption_under_image: bool = True
    body_text_left_image_right: bool = True  # 主要排版模式


@dataclass
class ChromeStyle:
    """页眉页脚等装饰元素。"""
    show_page_number: bool = True
    page_number_format: str = "{n} / {total}"   # "03 / 89"
    show_eyebrow_top_left: bool = True          # 顶部章节
    eyebrow_format: str = "CH·{ch_num} {ch_name}"
    show_part_top_right: bool = True            # PART 03 / 89
    part_format: str = "PART {n:02d} / {total}"
    show_brand_footer: bool = True              # 底部品牌行
    has_horizontal_rules: bool = True           # 用细横线
    side_chapter_number: bool = True            # 大章号在侧边（cover/divider 用）


@dataclass
class LayoutPreferences:
    """各 layout 的使用偏好（从 reference 里数出来的）。

    用来在 plan_layouts 时给规则版做"风格偏置":
    比如 reference 用了 28 页 hero-definition,就给 hero-definition 加权。
    """
    counts: dict[str, int] = field(default_factory=dict)  # layout → 次数
    total_pages: int = 0

    def bias(self, layout: str) -> float:
        """这个 layout 在 reference 里的占比,作为加权信号。"""
        if not self.total_pages:
            return 0.0
        return self.counts.get(layout, 0) / self.total_pages


@dataclass
class StyleVector:
    """完整的风格向量。"""
    source: str                     # 来源 PPT 路径
    canvas_w_px: int = 1280         # 13.33" * 96dpi
    canvas_h_px: int = 720          # 7.5" * 96dpi
    palette: ColorPalette = field(default_factory=ColorPalette)
    fonts: FontRamp = field(default_factory=FontRamp)
    density: LayoutDensity = field(default_factory=LayoutDensity)
    chrome: ChromeStyle = field(default_factory=ChromeStyle)
    layout_prefs: LayoutPreferences = field(default_factory=LayoutPreferences)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "StyleVector":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            source=data["source"],
            canvas_w_px=data.get("canvas_w_px", 1280),
            canvas_h_px=data.get("canvas_h_px", 720),
            palette=ColorPalette(**data.get("palette", {})),
            fonts=FontRamp(**data.get("fonts", {})),
            density=LayoutDensity(**data.get("density", {})),
            chrome=ChromeStyle(**data.get("chrome", {})),
            layout_prefs=LayoutPreferences(**data.get("layout_prefs", {})),
        )

    @classmethod
    def default(cls) -> "StyleVector":
        """新客户没给 reference 时的兜底默认风格。"""
        return cls(source="<default>")

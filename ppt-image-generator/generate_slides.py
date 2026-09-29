#!/usr/bin/env python3
"""
本地 PPT 图片生成脚本
基于 Gemini API (Nano Banana Pro) 生成渐变毛玻璃风格 PPT 图片

使用: python generate_slides.py [slides.json]
  不传参数时默认读取同目录下的 example_slides.json

需要: GEMINI_API_KEY 环境变量

slides.json 格式（数组，每项一页）：
[
  {"number": 1, "type": "cover", "content": "标题\n副标题"},
  {"number": 2, "type": "content", "content": "小标题\n\n要点一\n要点二"},
  {"number": 3, "type": "data", "content": "数据小标题\n\n项目：数值"}
]

type 支持 cover / content / data，分别对应封面页、Bento 网格内容页、
左文右图数据页三种版式，脚本会据此拼出不同的构图指令。
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 风格基础提示词——只描述视觉美学，不含具体项目内容
STYLE = """你是一位专家级UI UX演示设计师，请生成高保真、未来科技感的16比9演示文稿幻灯片。请根据视觉平衡美学，自动在封面、网格布局或数据可视化中选择一种最完美的构图。

全局视觉语言方面，风格要无缝融合Apple Keynote的极简主义、现代SaaS产品设计和玻璃拟态风格。整体氛围需要高端、沉浸、洁净且有呼吸感。光照采用电影级体积光、柔和的光线追踪反射和环境光遮蔽。配色方案选择深邃的虚空黑或纯净的陶瓷白作为基底，并以流动的极光渐变色即霓虹紫、电光蓝、柔和珊瑚橙、青色作为背景和UI高光点缀。

关于画面内容模块，请智能整合以下元素：

1. 排版引擎采用Bento便当盒网格系统，将内容组织在模块化的圆角矩形容器中。容器材质必须是带有模糊效果的磨砂玻璃，具有精致的白色边缘和柔和的投影,并强制保留巨大的内部留白，避免拥挤。

2. 插入礼物质感的3D物体，渲染独特的高端抽象3D制品作为视觉锚点。它们的外观应像实体的昂贵礼物或收藏品，材质为抛光金属、幻彩亚克力、透明玻璃或软硅胶，形状可是悬浮胶囊、球体、盾牌、莫比乌斯环或流体波浪。

3. 字体与数据方面，使用干净的无衬线字体，建立高对比度。如果有图表，请使用发光的3D甜甜圈图、胶囊状进度条或悬浮数字，图表应看起来像发光的霓虹灯玩具。

渲染质量要求：虚幻引擎5渲染，8k分辨率，超细节纹理，UI设计感，UX界面，Dribbble热门趋势，设计奖获奖作品。"""


LAYOUT_HINT = {
    "cover": "请根据视觉平衡美学，生成封面页。在中心放置一个巨大的复杂3D玻璃物体，并覆盖粗体大字，背景有延伸的极光波浪。以下是要覆盖的文字：\n\n",
    "content": "请生成内容页。使用Bento网格布局，将以下内容组织在模块化的圆角矩形容器中，容器材质必须是带有模糊效果的磨砂玻璃：\n\n",
    "data": "请生成数据页或总结页。使用分屏设计，左侧排版以下文字，右侧悬浮巨大的发光3D数据可视化图表：\n\n",
}


def build_prompt(slide: dict) -> str:
    hint = LAYOUT_HINT.get(slide.get("type", "content"), LAYOUT_HINT["content"])
    return f"{STYLE}\n\n{hint}{slide['content']}"


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key.startswith("replace-with"):
        print("请先设置 GEMINI_API_KEY 环境变量")
        print("export GEMINI_API_KEY='replace-with-your-key'")
        sys.exit(1)

    slides_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "example_slides.json"
    if not slides_path.exists():
        print(f"找不到 slides 配置文件: {slides_path}")
        sys.exit(1)
    slides = json.loads(slides_path.read_text(encoding="utf-8"))

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("请先安装依赖: pip install google-genai pillow")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"output_{timestamp}")
    output_dir.mkdir(exist_ok=True)

    print(f"开始生成 {len(slides)} 页 PPT 图片...")
    print(f"输出目录: {output_dir}")
    print("=" * 50)

    for slide in slides:
        num = slide["number"]
        print(f"\n生成第 {num} 页 ({slide.get('type', 'content')})...")

        try:
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=build_prompt(slide),
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9",
                        image_size="2K",
                    ),
                ),
            )

            for part in response.parts:
                if part.inline_data is not None:
                    image = part.as_image()
                    path = output_dir / f"slide-{num:02d}.png"
                    image.save(str(path))
                    print(f"  已保存: {path}")
                    break
            else:
                print(f"  未收到图片数据")

        except Exception as e:
            print(f"  失败: {e}")

    # 生成简单的 HTML 查看器
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>PPT Viewer</title>
<style>
body {{ margin:0; background:#000; display:flex; align-items:center; justify-content:center; height:100vh; }}
img {{ max-width:100vw; max-height:100vh; object-fit:contain; }}
.nav {{ position:fixed; bottom:20px; left:50%; transform:translateX(-50%); color:#fff; font-family:sans-serif; font-size:14px; opacity:0.5; }}
</style></head><body>
<img id="slide" src="slide-01.png">
<div class="nav" id="nav">1 / {len(slides)} &nbsp; (← → 翻页)</div>
<script>
let c=0, t={len(slides)};
const img=document.getElementById('slide'), nav=document.getElementById('nav');
function go(n){{ c=Math.max(0,Math.min(t-1,n)); img.src=`slide-${{String(c+1).padStart(2,'0')}}.png`; nav.textContent=`${{c+1}} / ${{t}}  (← → 翻页)`; }}
document.addEventListener('keydown',e=>{{ if(e.key==='ArrowRight')go(c+1); if(e.key==='ArrowLeft')go(c-1); }});
</script></body></html>"""

    (output_dir / "index.html").write_text(html, encoding="utf-8")

    print(f"\n{'=' * 50}")
    print(f"完成！打开查看: open {output_dir}/index.html")


if __name__ == "__main__":
    main()

# 本地 PPT 出图

要做几页有设计感的 PPT 图片（封面+要点+数据页），手动在设计工具里调版式太慢，所以写了这个：用 Gemini 图片模型（Nano Banana Pro）按固定的「渐变毛玻璃」视觉风格批量出图，配一个纯前端翻页查看器直接预览。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-05-19

## 怎么用

```bash
export GEMINI_API_KEY='replace-with-your-key'
pip install google-genai pillow

# 用默认示例大纲出图
python3 generate_slides.py

# 用自己的大纲出图
python3 generate_slides.py my_slides.json

# 或直接跑封装好的 shell 脚本（会先装依赖）
./run.sh my_slides.json
```

大纲文件格式见 `example_slides.json`：每页一个对象，`number` 是页码，`type` 是 `cover`（封面）/ `content`（Bento 网格要点页）/ `data`（左文右图数据页）三选一，`content` 是这一页要出现的文字内容（用 `\n` 换行）。生成结果落在 `output_<时间戳>/`，里面有每页 PNG 和一个 `index.html`（方向键翻页查看）。

## 依赖

- `GEMINI_API_KEY`（Google Gemini API key，从环境变量读，见 `.env.example`）
- Python 包：`google-genai`、`pillow`

## 风险与边界

- 每次生成都是真实计费的 Gemini API 调用，页数多之前先想清楚要出几页。
- 视觉风格（渐变毛玻璃 + 3D 玻璃物体）是写死在 `STYLE` 提示词里的固定审美偏好，想要别的风格要自己改这段提示词。
- 没有断点续跑：单页失败只会打印错误继续下一页，整批跑完后要自己看输出目录里少了哪几页。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。迁移时做了：把脚本里原本写死的真实项目大纲（具体业务名称、真实执行步骤、真实成本数字）换成从外部 JSON 文件读取大纲的通用版本，`example_slides.json` 全部换成占位内容和假数字；新增 `.env.example`。生成机制（Gemini 调用、风格提示词、HTML 查看器）未改动。迁移时只做了 `python3 -m py_compile` / `bash -n` / JSON 解析检查，没有重新调用 API 生成过图片。

# Live Photo 转 PNG

苹果的 Live Photo 导出成 `.livp` 之后，很多地方（网页、非苹果设备、图片编辑工具）都打不开，所以写了这个批量转成 PNG 的小脚本。

- 形态：Python 命令行
- 状态：已停
- 最后改动：2026-03-07

## 怎么用

```bash
pip install -r requirements.txt
python3 converter.py
```

把 `.livp` 文件放进脚本所在目录（或改 `convert_livp_to_png(directory=...)` 传别的路径），运行后会在同目录生成同名 `.png`。

**输入输出说明**：`.livp` 本质是一个 zip 压缩包，里面装着一张 HEIC（或 JPG）静态图和一段视频构成「实况」效果；这个脚本只解出其中的静态图部分，转成 PNG，不处理动态视频部分。

## 依赖

- Python 3
- `pillow`、`pillow-heif`（给 Pillow 加 HEIC 解码支持）

## 风险与边界

- 只读取 `.livp`，只在同目录新建 `.png`，不修改或删除原文件。
- 如果目标 `.png` 已存在会跳过，不会覆盖。
- 只提取静态图，Live Photo 的动态部分（视频轨）不会被转换或保留。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：只带了脚本本身，仓库里原本用来测试的真实 Live Photo 原图和转换结果（`.livp` / `.png` 各一张）一个都没有带过来。迁移时只做了静态检查（`python3 -m py_compile converter.py`），没有重新运行。

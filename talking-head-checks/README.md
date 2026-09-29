# 口播交付前检查

口播成片常规 QA（黑帧、响度、解码）全绿，但字幕悄悄听错字、剪辑里留了几秒「卡住了」的空隙，这些常规工具都测不出来，靠肉眼一遍遍回看太累，所以写了这三个检查脚本。

- 形态：Python 命令行，三个独立脚本
- 状态：在用
- 最后改动：2026-09-25

## 怎么用

### `check_deadair.py` — 无人说话空隙检查

即兴口播录制里，人会在句与句之间停顿 2–5 秒去想事情。这种停顿不是「静音」（背景可能有风噪车流），常规 `silencedetect` 测不出来，但观众会直接感到卡住。这个脚本按词级时间戳算相邻两词的间隔来判定。

```bash
# 成片终检（需要成片自己的词级 tsv）
python3 check_deadair.py --tsv 成片词级.tsv

# 渲染前预检（不需要重新转写，源片 tsv + 剪辑点 json 就够）
python3 check_deadair.py --source-tsv 源片词级.tsv --segments segments.json
```

阈值：>0.8s 提示（正常呼吸停顿）、>1.2s 告警（应切掉）、>2.0s 失败（必须处理）。有任何 >1.2s 的残留退出码返回 1，可以直接接进流程当卡点。

### `transcript_suspects.py` — 转写疑点清单

字幕只改「有依据」的词，弱模型可能只改有报道依据的专名，语境该纠的一个不碰；强模型也可能漏。这个脚本把「列疑点」和「定处置」拆开：先机械列出候选疑点，人或模型必须逐条填「疑似应为 / 依据 / 处置」，交付前用 `--verify` 卡住不许过。

```bash
# 播种：跑在两遍转写之后（主引擎 + 副引擎交叉验证）
python3 transcript_suspects.py --primary 主引擎词级.tsv --secondary 副引擎.tsv \
  --out work/SUSPECTS.md --baseline 基准文档.md

# 门禁：交付前检查是否填完
python3 transcript_suspects.py --verify work/SUSPECTS.md
```

依据只认五种：定点ASR / 副引擎 / 上下文 / 基准文档 / 未定。处置只认三种：改字幕 / 保留 / 待人工确认（脚本里写的是 `待Daniel`，自己用可以直接改成自己的名字或团队角色）。「处置=改字幕」但「依据=未定」算没填对，会被门禁拦住。

### `make_prompt_cards.py` — Prompt 排版成图

把一段长 Prompt 排成图片，评论区卡片（3:4，1080x1440）或视频结尾定格帧（9:16，1080x1920）。

```bash
python3 make_prompt_cards.py --text PROMPT.md --title "标题" --mode card --out ./out/
python3 make_prompt_cards.py --text PROMPT.md --title "标题" --mode frame --out ./out/ --footer "你的落款"
```

自动分页；以【开头的行加粗；emoji 用系统 emoji 字体渲染（找不到就退化成普通文字，不会报错）。

## 依赖

```bash
pip install pillow
```

`make_prompt_cards.py` 需要一个中文字体文件，优先级：`--font` 参数 > `CARD_FONT_PATH` 环境变量 > 自动探测几个常见 macOS 系统字体路径（找不到会报错并提示怎么指定）。不同字体文件里「常规/粗体」对应的内部 index 不一样，自己指定字体时可以用 `--font-regular-index` / `--font-bold-index` 覆盖默认值。

三个脚本互相独立，不共享代码，可以只用其中一个。

## 风险与边界

不删改任何已有文件，只读输入、写检查报告或图片输出。这三个工具是给「即兴口播剪辑」这个具体工作流写的检查器，判定口径（词级间隔阈值、疑点分类的五种依据/三种处置）是按这个工作流的实际坑调出来的，换到别的视频类型可能需要调整阈值或分类。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。迁移时做了：`make_prompt_cards.py` 里硬编码的 macOS 系统字体绝对路径（一个带资源哈希的 AssetsV2 路径，换个 macOS 版本可能就失效）改成 `--font` 参数 / `CARD_FONT_PATH` 环境变量 / 几个常见路径自动探测三级兜底；emoji 字体找不到时改成优雅降级（退化成普通文字）而不是直接报错；默认落款从真实的个人品牌名改成占位文字 `示例落款`。`check_deadair.py` 和 `transcript_suspects.py` 没有本机路径或个人信息需要清理，原样搬运。迁移时只做了静态检查（`py_compile`），没有拿真实素材重新跑一遍。

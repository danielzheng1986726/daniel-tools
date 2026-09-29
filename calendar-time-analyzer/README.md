# 日历时间分析

时间到底花在哪了，光凭感觉说不清楚，日历里其实全记着；把 macOS 日历导出的 `.ics` 丢进来跑一遍，能看到每天/每周/每月的活动时长趋势、哪天时间分配明显异常，所以写了这个分析脚本。

- 形态：Python 命令行
- 状态：已停
- 最后改动：2026-03-07

## 怎么用

```bash
pip install -r requirements.txt
python3 analyze_calendar.py --ics /path/to/your_calendar_export.ics
```

不传 `--ics` 就用仓库自带的 `sample.ics`（几条泛泛的假日程，如「写周报」「开会」），可以先跑一遍看效果：

```bash
python3 analyze_calendar.py
```

输出在 `analysis_output/`（可用 `--output` 改路径）：`calendar_analysis_report.md`（文字报告：数据概览、月度/周度趋势、异常活动）和 `time_series_analysis.png`（每日时长趋势图 + 活动频率热力图）。

日历导出方法：macOS「日历」App 里选中日历 → 右键「导出」，会生成 `.ics` 文件。

## 依赖

- Python 3
- `pandas`、`matplotlib`、`seaborn`、`icalendar`、`pytz`、`numpy`

## 风险与边界

- 只读取 `.ics`，不写回、不修改原日历文件。
- 「异常活动」的判断很简单（时长超过均值 ± 2 个标准差），只是提示，不代表真的有问题。
- 日历里的日程标题、时间本身可能包含私密信息（会议对象、行程细节等），生成的报告和图表也会包含这些原文标题，注意别把分析结果转发出去或提交进公开仓库。
- 中文字体设置（`Arial Unicode MS`）是 macOS 默认可用的字体，其他系统上图表中文可能显示为方框，需要自己换一个本机有的中文字体名。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：脚本原来写死读取一份真实的个人日历导出（文件名本身也带着姓名信息），源目录下存放这份真实 `.ics` 的文件夹和已生成的分析结果（`analysis_output/`）一个都没有带过来；改成了 `--ics`/`--output` 命令行参数，并新写了一份 `sample.ics`（8 条虚构日程，标题用「写周报」「开会」这类泛泛的词）作为默认示例数据；给 `CREATED` 字段缺失的情况加了个兜底（用 `DTSTART` 代替），原脚本假设这个字段一定存在。仓库根目录 `.gitignore` 全局排除了 `*.ics`，这个文件夹下额外加了 `.gitignore` 把 `sample.ics` 加回白名单。`requirements.txt` 原来是 devin.cursorrules 模板的通用依赖列表，换成了脚本实际用到的库。迁移时只做了静态检查（`python3 -m py_compile analyze_calendar.py`），没有重新运行。

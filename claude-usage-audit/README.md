# Claude Code 用量审计

Claude Code 用久了不知道额度花在哪个项目、哪个模型、哪个档位上，靠印象猜不准，所以写了这个脚本读本机会话记录自己算。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-09-15

## 怎么用

```bash
python3 claude_usage_audit.py                       # 最近 7 天
python3 claude_usage_audit.py --days 30
python3 claude_usage_audit.py --since 2026-09-08 --until 2026-09-15
python3 claude_usage_audit.py --out usage-audit/2026-09-22.md
```

跑完会在 stdout 打一份 Markdown 报告：按模型的花费占比、钱花在输入/输出/缓存上的分布、按项目（工作线）的花费和档位分布、最贵的几场会话。`--out` 可以顺手存一份文件。

想让报告里「期望默认」那一列匹配自己的实际分工，用 `--routing` 传一份 JSON（参考 `routing.example.json`）：

```bash
python3 claude_usage_audit.py --routing routing.example.json
```

格式是 `{"项目名": ["模型族", "档位"]}`，项目名要跟报告里「按工作线」那列打印出来的一致（脚本会自动从 `~/.claude/projects` 的文件夹名里还原出项目名）。不传就都按脚本里 `GLOBAL_DEFAULT`（默认 `opus high`）算偏离。

## 依赖

无第三方依赖，只用 Python 标准库。只读本机 `~/.claude/projects/**/*.jsonl` 里的会话记录，不联网、不调用任何模型 API。

## 风险与边界

- 金额是按 Anthropic API 公开单价折算出来的估算值，不是真实账单（Max/Pro 订阅计划的额度换算方式不同），只用来看占比和相对花费，别当账单核对。
- 只统计本机写过的会话文件，换机器/清过 `~/.claude/projects` 就统计不到。
- `ROUTING` 表（项目 → 期望模型/档位）默认是空的占位示例，报告里「期望默认」和「偏离」两列在没配置前只会用统一的 `GLOBAL_DEFAULT`，参考意义有限——建议按自己的实际工作线配一份 `routing.json`。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：`project_name()` 里原来硬编码的本机用户名前缀（`-Users-xxx-Projects-active-`）改成在运行时用 `os.path.expanduser("~")` 动态算，不再写死任何用户名；`ROUTING` 里原来 Daniel 自己的一批项目文件夹名（工作线分工表）全部删掉，改成空表 + 注释示例，并新增 `--routing` 参数支持外部 JSON 文件配置，附带 `routing.example.json` 占位样例。计费和统计逻辑本身没有改动。迁移时只做了静态检查（`py_compile`），没有拿真实 `~/.claude/projects` 数据重新跑一遍（那些数据本来就在这台机器本地，工具设计上也不会离开本机）。

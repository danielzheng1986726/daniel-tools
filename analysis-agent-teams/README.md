# 四个分析用 Agent Team

单个 AI 做分析容易被自己写下的第一个结论框住——列完第一条原因/论据后，后面的内容会不自觉往同一个认知框架里靠，看着全面，其实同质。所以做成几个 Agent 各自独立思考、互相对抗或互相审查，再由一个 Lead Agent 合并出报告。

- 形态：Claude Code / Codex 项目配置（`AGENTS.md` + `agents/` 角色定义 + 模板），不是可执行程序
- 状态：已停
- 最后改动：2026-02-07

## 怎么用

每个子文件夹是一个独立项目，进入对应目录后用 Claude Code（或其他读 `AGENTS.md` 的 agentic 工具）打开，直接说出你的分析任务即可，例如：

```bash
cd causal-analysis
```
```
请分析以下现象的原因：[你的现象/事件]
```

四个子文件夹各自的角色设定、工作流和使用方式见其内部 README。

## 四个子项目

- `causal-analysis/`：因果分析——主流解释者 + 边缘探索者，两个认知入口互补，避免原因清单同质化。
- `critical-debate/`：争议议题分析——两个对立立场的辩护者 + 一个哲学审计员，对抗产生张力。
- `research-audit/`：研究报告审计——魔鬼代言人 + 善意诠释者，从对立预设并行审查同一份材料。
- `vrio-porter/`：战略竞争力诊断（VRIO × 波特五力）——内部资源审计师 + 行业竞争分析师独立分析，错位本身就是洞察。

## 依赖

- 一个能读 `AGENTS.md`/`CLAUDE.md` 并调度多个子 Agent 的工具（如 Claude Code）
- 不需要额外的 API key；分析内容本身通过对话输入

## 风险与边界

- 这是 prompt/角色设计，不是自动化脚本，产出质量取决于所用模型的能力。
- 每个子项目原本的 `output/` 目录只保留了空文件夹，之前跑出来的真实分析报告没有一起搬过来。

## 迁移说明

2026-09-29 从 Daniel 的四个本机项目（`causal-analysis-team`、`critical-debate-team`、`research-audit-team`、`vrio-porter-team`）复制过来，合并进这一个文件夹（不带原 git 历史）。迁移时做了：只复制 Agent 定义（`agents/`）、上下文规则（`context/`）、任务模板（`templates/`）、工作流说明（`workflow/`）和三份说明文件（`AGENTS.md`/`CLAUDE.md`/`README.md`），不搬任何 `output/` 里跑出来的真实分析报告；`vrio-porter-team` 里的 `.claude/settings.local.json`（本机权限设置）也没有搬。内容本身检查过，没有发现真实姓名、邮箱、本机路径。迁移时只做了人工通读检查，没有重新跑过分析。

#!/usr/bin/env python3
"""Claude Code 本机用量审计：按工作线 × 模型 × 档位统计额度去向。

只读 ~/.claude/projects 下的会话记录，不调用模型、不消耗额度。
金额按 API 单价折算，只用来看占比和单件活花费，不是账单。

用法：
  python3 claude_usage_audit.py                       # 最近 7 天
  python3 claude_usage_audit.py --days 30
  python3 claude_usage_audit.py --since 2026-09-08 --until 2026-09-15
  python3 claude_usage_audit.py --out usage-audit/2026-09-22.md
  python3 claude_usage_audit.py --routing routing.example.json
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os

# 每百万 token：输入、输出、缓存读、5 分钟缓存写、1 小时缓存写
PRICE = {
    "fable": (10, 50, 0.25, 12.5, 20),
    "opus": (5, 25, 0.5, 6.25, 10),
    "sonnet": (2, 10, 0.2, 2.5, 4),
    "haiku": (1, 5, 0.1, 1.25, 2),
}

# 项目文件夹 -> 期望默认（模型族, 档位）。未列出的项目走 GLOBAL_DEFAULT。
# 按自己的工作线改这张表，或者用 --routing routing.json 传一份 JSON 覆盖/补充
# （格式：{"项目名": ["sonnet", "medium"]}），不用改代码。
GLOBAL_DEFAULT = ("opus", "high")
ROUTING = {
    # "my-cli-tool": ("sonnet", "medium"),
    # "my-writing-project": ("opus", "high"),
}

LONG_CONTEXT = 200_000


def family(model):
    for k in PRICE:
        if k in (model or ""):
            return k
    return None


def project_name(path):
    """把 ~/.claude/projects/<编码后的路径>/... 还原成项目名。

    Claude Code 把项目的绝对路径按 / -> - 编码成文件夹名，比如
    ~/Projects/active/foo 会变成 -Users-xxx-Projects-active-foo。
    这里按当前用户的家目录动态算前缀，不写死任何用户名。
    """
    raw = path.split("/projects/")[1].split("/")[0]
    home_prefix = os.path.expanduser("~").replace("/", "-")
    for prefix in (f"{home_prefix}-Projects-active-", f"{home_prefix}-Projects-"):
        if raw.startswith(prefix):
            return raw[len(prefix):]
    return raw.replace(home_prefix, "~")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out")
    ap.add_argument("--routing", help="JSON 文件，覆盖/补充项目→(模型族,档位) 期望默认表，"
                                       '格式 {"项目名": ["sonnet", "medium"]}')
    return ap.parse_args()


def main():
    a = parse_args()
    routing = dict(ROUTING)
    if a.routing:
        with open(a.routing, encoding="utf-8") as f:
            routing.update({k: tuple(v) for k, v in json.load(f).items()})

    now = dt.datetime.now().astimezone()
    until = dt.datetime.fromisoformat(a.until).astimezone() if a.until else now
    since = dt.datetime.fromisoformat(a.since).astimezone() if a.since else until - dt.timedelta(days=a.days)
    t0, t1 = since.timestamp(), until.timestamp()

    seen = set()
    total = 0.0
    by_model = collections.defaultdict(collections.Counter)
    by_proj = collections.defaultdict(float)
    by_proj_model = collections.defaultdict(float)
    by_proj_effort = collections.defaultdict(collections.Counter)
    by_bucket = collections.Counter()
    sub_cost = collections.Counter()
    sessions = {}

    pattern = os.path.expanduser("~/.claude/projects/*/**/*.jsonl")
    for f in glob.glob(pattern, recursive=True):
        if os.path.getmtime(f) < t0:
            continue
        proj = project_name(f)
        is_sub = "/subagents/" in f
        sid = f.split("/")[-3] if is_sub else os.path.basename(f)[:-6]
        for line in open(f, errors="ignore"):
            if '"usage"' not in line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            msg = e.get("message") or {}
            u = msg.get("usage")
            fam = family(msg.get("model"))
            ts = e.get("timestamp")
            if not u or not fam or not ts:
                continue
            t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            if not (t0 <= t <= t1):
                continue
            key = (msg.get("id"), e.get("requestId"))
            if key in seen:
                continue
            seen.add(key)

            cc = u.get("cache_creation") or {}
            w1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
            w5 = cc.get("ephemeral_5m_input_tokens", 0) or 0
            if w1h + w5 == 0:
                w5 = u.get("cache_creation_input_tokens", 0) or 0
            i = u.get("input_tokens", 0) or 0
            o = u.get("output_tokens", 0) or 0
            cr = u.get("cache_read_input_tokens", 0) or 0
            p = PRICE[fam]
            c_out = o * p[1] / 1e6
            c_read = cr * p[2] / 1e6
            c_write = (w5 * p[3] + w1h * p[4]) / 1e6
            cost = i * p[0] / 1e6 + c_out + c_read + c_write

            total += cost
            m = by_model[fam]
            m["req"] += 1
            m["cost"] += cost
            by_bucket["输出"] += c_out
            by_bucket["缓存重读"] += c_read
            by_bucket["缓存写入"] += c_write
            by_bucket["普通输入"] += i * p[0] / 1e6
            by_proj[proj] += cost
            by_proj_model[(proj, fam)] += cost
            effort = e.get("effort") or msg.get("effort") or "未记录"
            by_proj_effort[proj][effort] += cost
            sub_cost["子代理" if is_sub else "主会话"] += cost

            s = sessions.setdefault(sid, {"proj": proj, "cost": 0.0, "req": 0, "ctx": [],
                                          "models": [], "start": t, "end": t})
            s["cost"] += cost
            s["start"] = min(s["start"], t)
            s["end"] = max(s["end"], t)
            if not is_sub:
                s["req"] += 1
                s["ctx"].append(i + cr + (u.get("cache_creation_input_tokens", 0) or 0))
                s["models"].append((t, fam))

    if total == 0:
        print("所选时间段没有用量记录。")
        return

    pct = lambda x: f"{x / total:.1%}"
    L = []
    L.append(f"# Claude Code 用量审计 {since:%Y-%m-%d} 至 {until:%Y-%m-%d}")
    L.append("")
    L.append("金额按 API 单价折算，只看占比和单件花费。只含本机记录。")
    L.append("")

    L.append("## 按模型")
    L.append("| 模型 | 请求数 | 占比 | 单次均价（相对 Opus） |")
    L.append("|---|---|---|---|")
    opus_avg = by_model["opus"]["cost"] / by_model["opus"]["req"] if by_model["opus"]["req"] else None
    for fam, m in sorted(by_model.items(), key=lambda x: -x[1]["cost"]):
        avg = m["cost"] / m["req"]
        rel = f"{avg / opus_avg:.1f} 倍" if opus_avg else "-"
        L.append(f"| {fam} | {m['req']} | {pct(m['cost'])} | {rel} |")
    L.append("")
    L.append(f"Fable 占本机总花费 {pct(by_model['fable']['cost'])}。Max 计划上 Fable 最多用周额度的一半。")
    L.append("")

    L.append("## 钱花在哪")
    L.append(" / ".join(f"{k} {pct(v)}" for k, v in by_bucket.most_common()))
    L.append("")
    L.append(" / ".join(f"{k} {pct(v)}" for k, v in sub_cost.most_common()))
    L.append("")

    L.append("## 按工作线")
    L.append("| 项目 | 占比 | 会话数 | 单场均花费占比 | 模型分布 | 档位分布 | 期望默认 | 偏离 |")
    L.append("|---|---|---|---|---|---|---|---|")
    sess_count = collections.Counter(s["proj"] for s in sessions.values())
    for proj, v in sorted(by_proj.items(), key=lambda x: -x[1]):
        if v < 0.005 * total:
            continue
        models = ", ".join(f"{fam} {by_proj_model[(proj, fam)] / v:.0%}"
                           for fam in PRICE if by_proj_model[(proj, fam)] > 0.02 * v)
        efforts = ", ".join(f"{k} {c / v:.0%}" for k, c in by_proj_effort[proj].most_common(3))
        want = routing.get(proj, GLOBAL_DEFAULT)
        off_model = 1 - by_proj_model[(proj, want[0])] / v
        n = sess_count[proj] or 1
        L.append(f"| {proj} | {pct(v)} | {n} | {v / n / total:.1%} | {models} | {efforts} | "
                 f"{want[0]} {want[1]} | 非默认模型 {off_model:.0%} |")
    L.append("")

    L.append(f"## 最贵的 {a.top} 场会话")
    L.append("| 占比 | 项目 | 时长 | 主会话请求 | 上下文中位数 | 峰值 | 中途换模型次数 | 会话 id |")
    L.append("|---|---|---|---|---|---|---|---|")
    long_sessions = 0
    for sid, s in sorted(sessions.items(), key=lambda x: -x[1]["cost"])[:a.top]:
        ctx = sorted(s["ctx"]) or [0]
        seq = [fam for _, fam in sorted(s["models"])]
        switches = sum(1 for x, y in zip(seq, seq[1:]) if x != y)
        hours = (s["end"] - s["start"]) / 3600
        L.append(f"| {pct(s['cost'])} | {s['proj']} | {hours:.1f} 小时 | {s['req']} | "
                 f"{ctx[len(ctx) // 2] // 1000}K | {ctx[-1] // 1000}K | {switches} | {sid[:8]} |")
    for s in sessions.values():
        if s["ctx"] and sorted(s["ctx"])[len(s["ctx"]) // 2] > LONG_CONTEXT:
            long_sessions += 1
    L.append("")
    L.append(f"上下文中位数超过 {LONG_CONTEXT // 1000}K 的会话：{long_sessions} 场。")
    L.append("")

    L.append("## 复盘时可以自问")
    L.append("1. 这段时间有没有哪次降档或换 Sonnet 后结果不行、要返工？")
    L.append("2. 有没有哪次开了高档位模型，其实中档就够？")

    report = "\n".join(L) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "w").write(report)
        print(f"已写入 {a.out}")
    print(report)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""生成本目录的假稿子 + 假识别结果 fixture（配合 README 的用法示例）。
不含任何真实录音或真实识别内容，是纯手写的示例文本。跑一次即可，产物已提交，不需要重新生成。
"""
import json
import re

SCRIPT = (
    "这是一段用于测试重放工具的示例稿子。今天天气不错，适合出门散步。\n\n"
    "第二页只是随便写的占位内容，用来验证翻页逻辑是否正常工作。\n"
)

with open("fixtures/fixture_script.txt", "w", encoding="utf-8") as f:
    f.write(SCRIPT)


def normalize(s: str) -> str:
    return re.sub(r"[^\w一-鿿]", "", s).lower()


# 两页文本按说话顺序拼起来，构造逐字的「参考稿」时间戳（truth.tsv），每字 200ms，
# 模拟另一路 ASR 的字级时间戳。
spoken = normalize(SCRIPT)
rows = ["start\tend\ttext"]
t = 1000
for ch in spoken:
    start, end = t, t + 200
    rows.append(f"{start}\t{end}\t{ch}")
    t = end + 40  # 字间隔 40ms
with open("fixtures/fixture_truth.tsv", "w", encoding="utf-8") as f:
    f.write("\n".join(rows) + "\n")

# page_ends.txt：每页最后一句实际说出口的结尾几个字
with open("fixtures/fixture_page_ends.txt", "w", encoding="utf-8") as f:
    f.write("# fixture：假稿子，每页结尾几个字\n")
    f.write("出门散步\n")
    f.write("正常工作\n")

# events.jsonl：模拟识别器按真实语速吐出的中间结果（volatile），逐字累加，
# 每次比上一条多几个字；最后一条标 final。时间轴对齐 truth.tsv。
events = []
acc = ""
for i, ch in enumerate(spoken):
    acc += ch
    tt = 1.0 + i * 0.24
    is_final = (i == len(spoken) - 1)
    events.append({"t": round(tt, 3), "final": is_final, "text": acc})
with open("fixtures/fixture_events.jsonl", "w", encoding="utf-8") as f:
    for e in events:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

print("写好：fixture_script.txt / fixture_truth.tsv / fixture_page_ends.txt / fixture_events.jsonl")

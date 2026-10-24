#!/usr/bin/env python3
"""从个人网站的 tools.json 重新生成本仓库根 README 的索引表。

用法：python3 scripts/build_index.py [tools.json 路径]
默认读同级目录的 ../daniel-site/src/content/tools/tools.json。
排序和网站「顺手做的」一致：在用 → 用过一次 → 已停，同状态按最后改动倒序。
只替换 README 里从表头到表格最后一行这一段，其余文字不动。
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / 'daniel-site/src/content/tools/tools.json'
tools = json.loads(src.read_text())
rank = {'在用': 0, '用过一次': 1, '已停': 2}
tools.sort(key=lambda t: t['updated'], reverse=True)   # 稳定排序：先按日期，再按状态
tools.sort(key=lambda t: rank[t['status']])

missing = [t['id'] for t in tools if not (ROOT / t['id']).is_dir()]
if missing:
    sys.exit(f'tools.json 里有、仓库里没有的文件夹：{missing}')

head = '| 工具 | 形态 | 状态 | 最后改动 | 解决什么 |'
rows = [head, '|---|---|---|---|---|'] + [
    f"| [{t['name']}]({t['id']}/) | {t['form']} | {t['status']} | {t['updated']} | {t['pain']} |" for t in tools]

readme = ROOT / 'README.md'
lines = readme.read_text().split('\n')
i = lines.index(head)
j = i
while j < len(lines) and lines[j].startswith('|'):
    j += 1
new = '\n'.join(lines[:i] + rows + lines[j:])
if new == readme.read_text():
    print(f'索引没变（{len(tools)} 个工具）')
else:
    readme.write_text(new)
    print(f'索引已更新（{len(tools)} 个工具）')

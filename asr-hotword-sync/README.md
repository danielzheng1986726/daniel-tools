# 转写热词同步

语音转写老是把人名、产品名认成同音字（比如「张三→张山」「Claude→cloud」），每次转写完都要手动挑错太麻烦，所以写了这个：把一张「正确写法 vs 常见误转」的对照表，提炼成热词，同步给转写引擎，从源头减少误转。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-08-27

## 怎么用

```bash
export DASHSCOPE_API_KEY='replace-with-your-key'

# 用仓库自带的示例词表跑一遍，只看会提炼出哪些热词，不调 API
python3 sync_hotwords.py --dry-run

# 实际同步到 DashScope（会创建或更新一个 vocabulary）
python3 sync_hotwords.py

# 换成自己的词表文件（可以传多个）
python3 sync_hotwords.py --glossary my_people.md --glossary my_terms.md
```

词表文件是 markdown 表格，格式见 `example_glossaries/people_glossary.md` 和 `example_glossaries/terms_glossary.md`：表头第一列写「正确」的表会被提炼（取该列，`A / B（C）`这种写法会自动拆成多个词）；表头第一列不是「正确」的表（比如还没确认对错的疑似误转词）整表跳过，避免把错误写法也喂进热词表强化误识别。

脚本产出两份东西（都写到 `data/`，已被仓库整体 `.gitignore` 忽略）：
- `data/hotwords_state.json`：DashScope 那边的 `vocabulary_id`，幂等更新用
- `data/feishu_hotwords.txt`：飞书妙记没有 API，这份是给你手动整页粘贴到「设置 → 个人热词」的清单

## 依赖

- `DASHSCOPE_API_KEY`（阿里云 DashScope API key，只从环境变量读，见 `.env.example`）
- Python 包：`dashscope`（只有非 `--dry-run` 时才需要）

## 风险与边界

- 非 dry-run 时会真实调用 DashScope API 创建/更新词表（计入你的 API 用量）。
- 词表提炼逻辑对 markdown 表格格式比较敏感（表头必须精确是「正确」两个字，分隔线和普通数据行的判断都依赖竖线开头），改了自己词表的表格格式前，先用 `--dry-run` 确认提炼结果符合预期。
- 飞书妙记那部分没有 API，`feishu_hotwords.txt` 生成之后仍需手动打开网页粘贴一次，脚本做不到全自动。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。迁移时做了：没有读取也没有复制原项目里 `people/` 目录或任何真实人名/术语对照表，词表默认路径改成本文件夹下 `example_glossaries/` 两份全假词的示例文件（张三、Claude、示例项目等），并加了 `--glossary` 参数方便指向自己的真实词表；密钥读取方式从「环境变量优先、缺省读本机 launchd plist」改成只认环境变量，不再依赖任何本机文件；输出路径从原项目的 `PROJECT_ROOT/data/` 改成本工具目录下的 `data/`（已被仓库 `.gitignore` 忽略）。核心的表格解析和热词提炼逻辑未改动。迁移时做了 `python3 -m py_compile` 静态检查，并用示例词表实际跑过一次 `--dry-run`（确认「正确」表提炼、疑似误转表跳过的逻辑符合预期），没有真的调用过 DashScope API。

# 即梦可靠提交队列

即梦（Dreamina）官方 CLI 并发限制严格，还会出现「幽灵任务」——提交后返回了 submit_id，但服务端其实没收到，一直卡在 querying 状态查不出结果。手动盯着重提太麻烦，所以写了这个：串行提交、自动识别幽灵任务重提、进度写状态文件，脚本挂了能从断点继续跑。

- 形态：Python 命令行
- 状态：在用
- 最后改动：2026-05-21

## 怎么用

依赖即梦官方 `dreamina` CLI，需要提前装好并登录（认证由 CLI 自己管理，本工具不碰密钥）。

```bash
# 首次运行：从队列配置生成状态文件并执行
python3 dreamina_queue.py example_queue.json

# 脚本中断后，从状态文件继续（只重跑 pending/failed/ghost 的镜头）
python3 dreamina_queue.py --resume assets/example-project/

# 多个项目排队串行跑
python3 dreamina_queue.py assets/project-a/i2v_queue.json assets/project-b/i2v_queue.json

# 只看计划，不实际提交
python3 dreamina_queue.py --dry-run example_queue.json
```

`dreamina_submit.py` 是更早、更轻量的一次性批量提交版本（无断点续跑），config 格式相同，独立可用：

```bash
python3 dreamina_submit.py example_queue.json
```

配置文件格式见 `example_queue.json`：每条记录是一个镜头，`image` 是关键帧图片路径，`prompt` 是生成描述，`model_version`/`duration`/`video_resolution` 可选。

## 依赖

- 即梦官方 `dreamina` CLI（在 PATH 里能直接跑通 `dreamina image2video ...`）
- Python 3，标准库即可，无第三方包

## 风险与边界

- 会消耗即梦账号积分（每次提交都是真实生成请求），没有 DRY_RUN 之外的“先算成本”功能。
- 幽灵任务检测、并发重试的阈值（等待秒数、重试次数）是针对即梦当时的行为调的经验值，即梦服务端逻辑变化后可能需要重新调参。
- 下载路径写死在关键帧图片同目录，跑之前确认目录结构符合预期。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：直接复制两个脚本（内容本身不含真实路径、密钥或项目信息，未改动逻辑），新增 `example_queue.json` 示例配置（假路径假描述）和本 README。迁移时只做了 `python3 -m py_compile` 静态检查，没有重新运行。

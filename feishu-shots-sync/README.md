# 分镜同步飞书

AI 视频项目一条条镜头手动往飞书多维表格里录太慢，还容易漏传关键帧、漏关联项目，所以写了这个：读一份 JSON 分镜清单，批量建记录、传关键帧图、关联到项目记录。

- 形态：Shell 命令行（依赖飞书 CLI）
- 状态：在用
- 最后改动：2026-04-15

## 怎么用

```bash
cp .env.example .env   # 填入你自己的 Base token / Table ID 后 source 或手动 export
export FEISHU_BASE_TOKEN="replace-with-your-base-token"
export FEISHU_TABLE_ID="replace-with-your-table-id"

./sync_shots_to_feishu.sh example_shots.json
```

分镜清单格式见 `example_shots.json`：数组，每条记录包含
- `record`：要写入多维表格的字段（字段名要和你表里的列名一致，示例用的是「镜头标题」「镜头ID」「Prompt摘要」等）
- `keyframe`：可选，本地关键帧图片路径，会上传到 `FEISHU_KEYFRAME_FIELD` 指定的附件字段
- `project_record_id`：可选，要关联到的项目记录 ID，写入 `FEISHU_LINK_FIELD` 指定的关联字段

## 依赖

- 飞书官方 CLI：`@larksuite/cli`（脚本用 `npx @larksuite/cli` 调用，需要本机已用 `--as user` 登录过一次）
- `FEISHU_BASE_TOKEN` / `FEISHU_TABLE_ID`：你自己飞书多维表格的 Base token 和 Table ID，从环境变量读，见 `.env.example`
- 可选环境变量 `FEISHU_LINK_FIELD` / `FEISHU_KEYFRAME_FIELD`：不设置则分别用默认字段名「关联项目」「关键帧」

## 风险与边界

- 会真实往飞书多维表格里写入记录、上传附件，没有 DRY_RUN 模式；跑之前先确认 `example_shots.json`（或你自己的清单）内容和目标表对得上。
- 依赖飞书 CLI 本机登录态，登录过期会导致所有记录创建失败（脚本会打印 FAILED 但不会中断整批）。
- 字段名写死在清单和环境变量里，换了表结构要同步改字段名。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史）。迁移时做了：原脚本里写死的真实 Base token、Table ID、项目记录 ID，以及混在代码里的真实分镜内容（真实项目的镜头描述、prompt、经验备注）全部拿掉；Base token/Table ID 改成从环境变量读（`FEISHU_BASE_TOKEN`/`FEISHU_TABLE_ID`），关联字段名和关键帧字段名也可选从环境变量覆盖；原本硬编码在脚本里的一条条 `create_shot` 调用改成从外部 JSON 清单读取（`example_shots.json` 用的是占位内容和假记录 ID），字段名本身保留。迁移时只做了 `bash -n` 静态检查和 JSON 解析测试，没有真的连过飞书。

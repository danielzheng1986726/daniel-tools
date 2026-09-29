#!/bin/bash
# 批量同步分镜到飞书多维表格（分镜资产库）
#
# 依赖飞书 CLI：npx @larksuite/cli（需要本机已登录，见 README）
#
# 用法：
#   export FEISHU_BASE_TOKEN="你的 Base token"
#   export FEISHU_TABLE_ID="你的 Table ID"
#   ./sync_shots_to_feishu.sh shots.json
#
# shots.json 格式见 example_shots.json：数组，每条记录包含
#   record: 要写入多维表格的字段（字段名需和你表里的列名一致）
#   keyframe: 可选，本地关键帧图片路径，会上传到 KEYFRAME_FIELD 指定的附件字段
#   project_record_id: 可选，要关联到的项目记录 ID，写入 LINK_FIELD 指定的关联字段
set -euo pipefail

: "${FEISHU_BASE_TOKEN:?请先 export FEISHU_BASE_TOKEN=你的 Base token}"
: "${FEISHU_TABLE_ID:?请先 export FEISHU_TABLE_ID=你的 Table ID}"

BASE_TOKEN="$FEISHU_BASE_TOKEN"
TABLE_ID="$FEISHU_TABLE_ID"
LINK_FIELD="${FEISHU_LINK_FIELD:-关联项目}"
KEYFRAME_FIELD="${FEISHU_KEYFRAME_FIELD:-关键帧}"

SHOTS_FILE="${1:-example_shots.json}"

if [ ! -f "$SHOTS_FILE" ]; then
  echo "找不到分镜配置文件: $SHOTS_FILE"
  exit 1
fi

create_shot() {
  local json="$1"
  local keyframe="$2"
  local project_rec="$3"

  echo ">>> Creating: $(echo "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("镜头标题","?"))')"

  # Create record
  result=$(npx @larksuite/cli base +record-upsert \
    --base-token "$BASE_TOKEN" --table-id "$TABLE_ID" \
    --json "$json" --as user 2>/dev/null)

  rec_id=$(echo "$result" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["data"]["record"]["record_id_list"][0])' 2>/dev/null)

  if [ -z "$rec_id" ]; then
    echo "    FAILED to create record"
    echo "$result"
    return 1
  fi
  echo "    record_id: $rec_id"

  # Upload keyframe if exists
  if [ -n "$keyframe" ] && [ -f "$keyframe" ]; then
    echo "    Uploading keyframe: $(basename "$keyframe")"
    npx @larksuite/cli base +record-upload-attachment \
      --base-token "$BASE_TOKEN" --table-id "$TABLE_ID" \
      --record-id "$rec_id" --field-id "$KEYFRAME_FIELD" \
      --file "$keyframe" --as user 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print("    Upload:", "OK" if d.get("ok") else "FAIL")'
  fi

  # Link to project
  if [ -n "$project_rec" ]; then
    echo "    Linking to project: $project_rec"
    npx @larksuite/cli base +record-upsert \
      --base-token "$BASE_TOKEN" --table-id "$TABLE_ID" \
      --record-id "$rec_id" \
      --json "{\"$LINK_FIELD\":[{\"record_id\":\"$project_rec\"}]}" \
      --as user 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print("    Link:", "OK" if d.get("ok") else "FAIL")'
  fi

  echo ""
  sleep 0.5
}

echo "=== 同步 $SHOTS_FILE 里的分镜 ==="

python3 -c '
import json, sys
shots = json.load(open(sys.argv[1]))
for s in shots:
    print(json.dumps(s.get("record", {}), ensure_ascii=False))
    print(s.get("keyframe", ""))
    print(s.get("project_record_id", ""))
' "$SHOTS_FILE" | while IFS= read -r record_json && IFS= read -r keyframe && IFS= read -r project_rec; do
  create_shot "$record_json" "$keyframe" "$project_rec"
done

echo "=== DONE ==="

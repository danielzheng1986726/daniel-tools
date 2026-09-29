#!/bin/zsh
# 用法：./run_on_device.sh [TEAM_ID]
# 前提：Xcode 许可已同意、Apple ID 已加进 Xcode、iPhone 已连接并开了开发者模式。
set -e
cd "$(dirname "$0")"
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
TEAM=${1:-}
if [[ -z "$TEAM" ]]; then
  echo "查找 Personal Team…"
  TEAM=$(defaults read com.apple.dt.Xcode 2>/dev/null | grep -oE '[A-Z0-9]{10}' | head -1 || true)
fi
[[ -z "$TEAM" ]] && { echo "没找到 Team ID，请传参：./run_on_device.sh XXXXXXXXXX（Xcode → Settings → Accounts 里能看到）"; exit 1; }
DEV=$(xcrun devicectl list devices --json-output /tmp/devs.json >/dev/null && python3 -c "import json;d=json.load(open('/tmp/devs.json'));r=[x for x in d['result']['devices'] if x['connectionProperties']['tunnelState']!='unavailable'];print(r[0]['identifier'] if r else '')")
[[ -z "$DEV" ]] && { echo "没有连着的 iPhone"; exit 1; }
echo "Team=$TEAM Device=$DEV"
xcodebuild -project PrompterSpike.xcodeproj -scheme PrompterSpike -destination "id=$DEV" -allowProvisioningUpdates -allowProvisioningDeviceRegistration DEVELOPMENT_TEAM=$TEAM -derivedDataPath build build 2>&1 | grep -E "error|warning: no|BUILD" || true
APP=$(find build/Build/Products -name "PrompterSpike.app" | head -1)
xcrun devicectl device install app --device "$DEV" "$APP"
xcrun devicectl device process launch --device "$DEV" --console com.example.prompterspike

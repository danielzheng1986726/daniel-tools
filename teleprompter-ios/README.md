# 提词器

剪映的提词功能两种模式都不好用：智能语速识别跟不上嘴，字和声音对不上；固定滚动语速一变就得伸手划。共同的毛病是程序在不该动的时候动了屏幕。自己写了一个 iOS App，专门解决「动得太频繁、动的时机不对」这一件事。

- 形态：iOS App
- 状态：在用，只给自己用，没上架
- 最后改动：2026-09-28

## 怎么用

这不是一个装了就能跑的成品 App，需要自己用 Xcode 编译签名装到手机上：

1. 装 Xcode（App Store），打开一次同意许可；Xcode → Settings → Accounts 里登录自己的 Apple ID（免费账号即可，不用付费开发者账号）。
2. 把 `app/gen_project.py` 里的 `BUNDLE = "com.example.prompter"` 改成自己的 bundle id（随便起一个没被人占用的反域名字符串），跑一次 `python3 gen_project.py` 重新生成工程文件；或者直接改 `Prompter.xcodeproj/project.pbxproj` 里的 `PRODUCT_BUNDLE_IDENTIFIER`。加了新的 `.swift` 源文件也要重跑这一步。
3. 用 Xcode 打开 `app/Prompter.xcodeproj`，Signing & Capabilities 里把 Team 选成自己的 Personal Team，顶部设备选自己的 iPhone，Cmd+R 装机。或者命令行：

   ```bash
   cd app
   xcodebuild -project Prompter.xcodeproj -scheme Prompter \
     -destination "id=<你的设备 id，xcrun devicectl list devices 查>" \
     -allowProvisioningUpdates DEVELOPMENT_TEAM=<你的 Team ID> \
     -derivedDataPath build build
   xcrun devicectl device install app build/Build/Products/Debug-iphoneos/Prompter.app
   xcrun devicectl device process launch --device <设备 id> --console <你的 bundle id>
   ```

4. 免费 Apple ID 签名的 App 大约 7 天后会过期打不开，图标还在，重新 Cmd+R 或跑一遍上面的命令重装即可，数据不丢（同一个包名是覆盖安装）。
5. 用法：Mac 上复制一段稿子（支持「【段 1·逐字】」「【段 1·要点】」这类标记区分照念段和自由说段，没标记就按空行分页），手机上进 App 粘贴。逐字段会跟着语音自动翻页，也可以按音量键、相机控制键或点屏手动翻。录完的片段和拍摄日志都存在 App 沙盒里，「文件 → 我的 iPhone → 提词」能直接看到，AirDrop 或系统分享面板导出。

## 依赖

- Xcode（较新版本，用到 iOS 26 的 SpeechAnalyzer API）
- 自己的 Apple ID（免费签名即可）
- 一台 iPhone（前置摄像头、麦克风、音量键都要用到；系统版本要够新才有 SpeechAnalyzer 和相机控制键支持）

## 几个关键决定

- **字不许乱动压过其他所有要求。** 识别不确定就停住等人按键，不做连续滚动，自动推进只往前不往后。两个目标打架时这条赢——宁可偶尔要按一下，也不让屏幕在不该动的时候乱跳。
- **用 App 自带相机录，不在系统相机上叠悬浮窗。** 第三方 App 在 iOS 上做不出真悬浮窗；而且系统相机录像时，别的 App 会失去麦克风，语音跟读和音量键都会失效，等于又绕回固定滚动的老路。
- **按段翻页，不做逐字滚动。** 逐字跟读要求识别延迟低于 300 毫秒还不能错字，本机中文识别做不到；按句/按段翻页只需要识别「大致说完了」，句尾又正好是自然停顿，这时挪屏幕眼睛本来就不在读。
- **识别用 SpeechAnalyzer，必须显式设 `priority: .userInitiated` 并打开 `.fastResults`。** 不设的话默认优先级下识别结果 11.5 秒才出一批，早就来不及判断翻页时机；设对了之后大约每 1 秒吐一批。
- **句尾判定规则不要求逐字对上，而是「结尾几个字大致对上 + 整句大部分字按顺序说到」两条同时满足。** 因为说话人念稿习惯在句尾顺口加字改字，逐字精确匹配的规则实测翻页命中率很低，放宽到近似匹配之后命中率明显提升。
- **改翻页规则之前先跑 `tools/replay/` 的重放测试，不让人当第一个测试对象。** 拿录好的音频重新按真实语速识别一遍，对着和 App 相同的引擎代码模拟「说完等 2.5 秒再按键」的人，能在几分钟内看出新规则会不会提前翻页或漏判，比每次改完都要实拍验证快得多。

## 风险与边界

- 只在自己的手机和自己的说话习惯上验证过。句尾匹配的容错参数是照着一个人念稿的口癖调出来的经验值，换一个人说话风格可能不准。
- `tools/replay/` 的重放测试只验证过一个说话人的一份素材，Mac 上的识别结果和手机实时识别的结果会有出入，重放测试通过不代表真机实拍一定通过。
- 不做美颜、降噪、防抖后期；这些还是交给剪映之类的工具处理。
- 免费 Apple ID 签名大约 7 天过期，需要定期用 Xcode 重装。
- 只给自己用，没有适配别的机型或说话习惯，没有账号体系和云同步，不打算上架。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。迁移时做了：
- 复制 `app/` 下的 Xcode 工程、Swift 源码、`Info.plist`、工程生成脚本 `gen_project.py`；没有找到需要搬的图标资源（原项目没有自定义 App 图标）。
- 复制 `tools/replay/` 的三个重放测试工具源码，不带原来的真实录音识别结果和真实逐字稿；新写了 `tools/replay/fixtures/` 下的假稿子和配套假识别数据（内容是随手编的两句话），详情见该目录的 README。
- 复制 `spike/` 下的真机验证代码（纯 API 试验：枚举相机格式、测语音识别延迟，不含个人数据），但没有搬两份真机控制台日志，因为里面是当时验证时念的真实口播稿逐字记录。
- 清理：`PRODUCT_BUNDLE_IDENTIFIER` 从真实 bundle id 改成占位值 `com.example.prompter` / `com.example.prompterspike`；工程文件里本来就没有写死签名 Team ID（原项目是运行时通过命令行参数传入），无需清理。不带 `xcuserdata`、`DerivedData`、`.xcuserstate`、构建产物（`app/build`、`spike/build`）。
- 迁移时对 Swift 源码做了 `swiftc -parse` 语法检查（能通过），`tools/replay/` 的两个可独立运行的工具（`replay_main.swift`、`offscript_main.swift`）实际编译并跑通了一遍假 fixture，`record_transcript.swift` 需要连麦克风和联网下载语音模型，只做了 `swiftc -typecheck`，没有实跑；`app/gen_project.py` 实际跑了一遍确认改完 bundle id 占位符后仍能正常生成工程文件。App 本体（相机、录制、语音识别、UI）没有在这个仓库里重新编译装机验证——iOS App 需要真机或模拟器加签名才能跑起来，这个验证在原项目里已经做过。

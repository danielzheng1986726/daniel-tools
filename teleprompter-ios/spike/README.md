# spike · 真机技术验证

写正式 App 之前，先用一天时间在真机上确认两件拿不准的事，再决定要不要往下做：

1. iPhone 前置摄像头对第三方 App 开放到什么规格（4K？10-bit？HLG？防抖档位？），实录几秒读回文件参数验证。
2. iOS 26 SpeechAnalyzer 本机中文识别：一句说完后多久出结果，中间结果（volatile）跟到句尾要多久。

结论见 `../README.md` 的「几个关键决定」一节：前置摄像头能拿到 4K 10-bit HLG；SpeechAnalyzer 必须设 `priority: .userInitiated` 并开 `.fastResults`，否则默认优先级下结果 11.5 秒才出一批。

## 怎么跑

1. 同意 Xcode 许可：打开 Xcode 点 Agree，或终端 `sudo xcodebuild -license accept`。
2. Xcode → Settings → Accounts → + → 登录自己的 Apple ID（免费即可，见 `../README.md` 的签名说明）。
3. iPhone：数据线连 Mac，手机上点「信任」；设置 → 隐私与安全性 → 开发者模式打开（会重启）。
4. 打开 `PrompterSpike.xcodeproj`，左栏点项目 → TARGETS PrompterSpike → Signing & Capabilities → Team 选自己的 Personal Team；顶部设备选自己的 iPhone；Cmd+R。第一次装完手机会拦，设置 → 通用 → VPN 与设备管理 → 信任这个开发者。

App 里两个页面：
- 「相机」：进去就列出前置所有格式，右上「录 5 秒最高格式」录一段并读回编码参数；左上「复制」。
- 「语音」：右上「开始」（第一次会下载中文模型），念一句话，句尾停住 1 秒，再念下一句；三四句后「停止」，左上「复制」。

也可以用 `./run_on_device.sh [TEAM_ID]`：自动用 xcodebuild 签名、装到连着的 iPhone 并带控制台启动，App 里 print 的内容会回到终端。不传 TEAM_ID 会尝试从 Xcode 的偏好设置里猜一个 Personal Team，猜不到就照提示手动传。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。这个文件夹是纯 API 试验代码（枚举相机格式、测语音识别延迟），本身不含个人数据，原样复制了 `Sources/`、工程文件和 `run_on_device.sh`；`run_on_device.sh` 里原本写死的 bundle id 改成了占位值 `com.example.prompterspike`，Team ID 本来就是运行时从 Xcode 读或由调用者传参，没有写死在文件里。**没有搬**原目录里的两份真机控制台运行日志（`console_run4_normal_vs_fast.log`、`console_run5_priority_vs_legacy.log`）——它们里面是当时验证语音识别时念的一段真实口播稿逐字记录，不是纯 API 数据，按迁移规矩不带真实录音/识别内容。验证结论（真机能拿到什么规格、SpeechAnalyzer 要设哪些参数）保留在上面和 `../README.md` 里，是已经核实过的事实，不是原始日志。迁移时只对 `Sources/*.swift` 做了 `swiftc -parse` 语法检查，没有重新装机运行。

# 语音翻页重放测试

改 `app/Sources/PrompterEngine.swift` 的匹配逻辑前后都跑一遍，不用每次让人拿着手机实拍验证。

## 原理

1. `record_transcript.swift`：在 Mac 上用和 App 相同的 SpeechTranscriber 参数（zh-CN、volatile + fastResults、`priority: .userInitiated`），**按真实语速**把一段录音识别一遍，每条识别结果（含 volatile 改写）连同时刻记成 JSONL。只需录一次。
2. `replay_main.swift`：把 JSONL 按时间喂给 App 的 `PrompterEngine`（直接编译 App 源码），模拟一个「这页说完 2.5 秒还没翻就按音量键」的人。输出自动/手动翻页、提前翻页（违反「字不许乱动」的原则）、没认出的句子。开头先跑压力测试：每句逐字说，最后两个字出来前不许判完；一句原文不许被判成后面的句子。
3. `offscript_main.swift`：拿一段无关的文字当即兴说话，看稿子里的句子会不会被误判说完。

「这页真的说完了」的时刻来自另一路 ASR 的字级时间戳（`truth.tsv`），每页最后一句实际说出口的结尾写在 `page_ends.txt`。

## 跑法（用仓库自带的假 fixture）

`fixtures/` 下是一份纯手写的示例稿子和配套的假识别数据（不是真录音、不是真识别结果），只演示怎么跑：

```bash
R=<本仓库路径>/teleprompter-ios
S=$(mktemp -d)
cp "$R/tools/replay/replay_main.swift" "$S/main.swift"
swiftc -O "$R/app/Sources/ScriptModel.swift" "$R/app/Sources/PrompterEngine.swift" "$S/main.swift" -o "$S/replay"
cd "$R/tools/replay"
"$S/replay" fixtures/fixture_script.txt fixtures/fixture_events.jsonl fixtures/fixture_truth.tsv fixtures/fixture_page_ends.txt
```

换成自己的真实素材时，三个输入文件按同样的格式自己生成：

```bash
# 1. 把原片转成单声道 wav
ffmpeg -v error -i <原片.mov> -vn -ac 1 -ar 48000 -c:a pcm_s16le "$S/a.wav"
# 2. 用和手机同样的识别参数重新识别一遍（顶层代码要叫 main.swift）
swiftc -O -parse-as-library "$R/tools/replay/record_transcript.swift" -o "$S/record"
"$S/record" "$S/a.wav" events.jsonl
# 3. 准备一份字级时间戳的参考稿（另一路更准的 ASR 转写，tsv: start_ms end_ms text）
#    和一份 page_ends.txt（每页最后一句实际说出口的结尾几个字，跨素材分段写 `TAKE 秒数`）
# 4. 重放
cp "$R/tools/replay/replay_main.swift" "$S/main.swift"
swiftc -O "$R/app/Sources/ScriptModel.swift" "$R/app/Sources/PrompterEngine.swift" "$S/main.swift" -o "$S/replay"
"$S/replay" <script.txt> <events.jsonl> <truth.tsv> <page_ends.txt>
```

离稿测试（`offscript_main.swift`）编译方式相同，`main.swift` 换成它，用法是 `offscript <script.txt> <随便一段无关文字的文件> [...]`。

## 结果记录

这份重放工具是照真实使用反馈迭代出来的：第一版匹配规则（尾巴 6 字容 1 错）在真机实拍时 8 次翻页只有 3 次自动，因为说话人念稿到句尾习惯顺口加字。改成「结尾 4 字中 3 字 + 整句覆盖率 70%（跨页 80%）+ 偏移回退」后，重放同一段素材做到 8 次全自动、0 次提前翻页；离稿测试（多条旧素材的逐字稿当即兴发言喂进去）没有误判。具体数字和迭代过程属于真实拍摄素材，不在这个公开仓库里保留；这里只留代码和跑法。

局限：只验证过一个说话人、一份素材；Mac 上的识别器和手机上的实际识别结果会有出入（本地重放比真机实拍更容易全部命中），重放结果通过不等于真机一定通过，改完规则仍建议至少实拍验证一次。

## 迁移说明

2026-09-29 从 Daniel 的本机项目复制过来（不带原 git 历史）。迁移时做了：只复制三个 `.swift` 工具源码，不带原来 `tools/replay/` 目录下的真实录音识别结果和真实逐字稿（`take7_*` 系列文件，含真实口播内容）；新写了 `fixtures/` 下的假稿子和配套假识别数据（`gen_fixture.py` 生成，内容是随手编的两句话，不对应任何真实录制），并按假数据重写了本 README 的跑法说明和结果记录段落。迁移时把三个工具源码都过了 `swiftc -parse` 语法检查，并且实际编译运行了一遍 `replay_main.swift` 和 `offscript_main.swift`（对着假 fixture，能跑通、输出合理），`record_transcript.swift` 因为要连麦克风和下载语音模型没有实跑，只过了 `swiftc -typecheck`。

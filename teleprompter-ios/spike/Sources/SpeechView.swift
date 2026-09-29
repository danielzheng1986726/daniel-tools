import SwiftUI
import AVFoundation
import Speech
import UIKit

struct SpeechView: View {
    @StateObject private var test = SpeechTest()
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 8) {
                Text(test.status).font(.system(size: 11, design: .monospaced))
                Divider()
                Text(test.tail).font(.system(size: 11, design: .monospaced))
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
            .padding()
            .navigationTitle("本机中文识别延迟")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("复制") { UIPasteboard.general.string = test.status + "\n" + test.fullLog() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    HStack {
                        if test.running {
                            Button("停止") { Task { await test.stop() } }
                        } else {
                            Button("新API快") { Task { await test.start(fast: true) } }
                            Button("旧API") { Task { await test.startLegacy() } }
                        }
                    }
                }
            }
        }
    }
}

/// 结果回调不经过主线程：到达时间在后台任务里立刻记录，UI 每 0.5 秒只刷最后几行。
/// 同时记录喂给分析器的音频累计秒数，用来判断是喂入停了还是识别慢。
@MainActor
final class SpeechTest: ObservableObject {
    @Published var status = "未开始"
    @Published var tail = ""
    @Published var running = false

    private let engine = AVAudioEngine()
    private var analyzer: SpeechAnalyzer?
    private var transcriber: SpeechTranscriber?
    private var continuation: AsyncStream<AnalyzerInput>.Continuation?
    private var resultTask: Task<Void, Never>?
    private var uiTimer: Timer?
    private let store = LogStore()

    func fullLog() -> String { store.all().joined(separator: "\n") }

    func start(fast: Bool) async {
        status = ""; tail = ""; store.reset()
        do {
            let supported = await SpeechTranscriber.supportedLocales
            let zh = supported.filter { $0.language.languageCode?.identifier == "zh" }
            guard let locale = zh.first(where: { $0.region?.identifier == "CN" }) ?? zh.first(where: { $0.language.script?.identifier == "Hans" }) else {
                status += "没有简体中文，停\n"; return
            }
            var reporting: Set<SpeechTranscriber.ReportingOption> = [.volatileResults]
            if fast { reporting.insert(.fastResults) }
            let tr = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: reporting, attributeOptions: [.audioTimeRange])
            transcriber = tr
            if let req = try await AssetInventory.assetInstallationRequest(supporting: [tr]) {
                status += "下载模型中…"; try await req.downloadAndInstall(); status += "完成\n"
            }
            let an = SpeechAnalyzer(modules: [tr], options: SpeechAnalyzer.Options(priority: .userInitiated, modelRetention: .processLifetime))
            analyzer = an
            guard let fmt = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [tr]) else { status += "拿不到音频格式\n"; return }
            let tPrep = Date()
            try await an.prepareToAnalyze(in: fmt)
            let prepSec = Date().timeIntervalSince(tPrep)
            status += String(format: "%@ locale=%@ 分析格式 %dHz ch=%d prepare %.2fs\n", fast ? "快速模式" : "普通模式", locale.identifier(.bcp47), Int(fmt.sampleRate), fmt.channelCount, prepSec)

            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            let input = engine.inputNode
            let inFmt = input.outputFormat(forBus: 0)
            guard let conv = AVAudioConverter(from: inFmt, to: fmt) else { status += "转换器创建失败\n"; return }
            let (stream, cont) = AsyncStream<AnalyzerInput>.makeStream()
            continuation = cont
            let store = self.store
            input.installTap(onBus: 0, bufferSize: 2048, format: inFmt) { buf, _ in
                let ratio = fmt.sampleRate / inFmt.sampleRate
                let cap = AVAudioFrameCount(Double(buf.frameLength) * ratio) + 32
                guard let out = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: cap) else { return }
                var err: NSError?
                var consumed = false
                let st = conv.convert(to: out, error: &err) { _, st in
                    if consumed { st.pointee = .noDataNow; return nil }
                    consumed = true; st.pointee = .haveData; return buf
                }
                if st != .error, out.frameLength > 0 {
                    cont.yield(AnalyzerInput(buffer: out))
                    store.fed(seconds: Double(out.frameLength) / fmt.sampleRate)
                }
            }
            engine.prepare()
            try engine.start()
            store.markStart()
            print(String(format: "SPEECH_STARTED mode=%@ prep=%.2fs mic=%dHz", fast ? "fast" : "normal", prepSec, Int(inFmt.sampleRate)))
            resultTask = Task.detached(priority: .userInitiated) {
                do {
                    for try await r in tr.results { store.record(r) }
                } catch {
                    store.append("结果流结束: \(error)")
                }
            }
            try await an.start(inputSequence: stream)
            running = true
            status += "已开始，念稿子，句尾停一秒。\n"
            uiTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
                guard let self else { return }
                let lines = self.store.all()
                self.tail = String(format: "已喂入音频 %.1fs，结果 %d 条\n", self.store.fedSeconds(), lines.count) + lines.suffix(6).joined(separator: "\n")
            }
        } catch {
            status += "错误: \(error)\n"
        }
    }


    // MARK: - 旧 API：SFSpeechRecognizer 本机听写，逐字部分结果
    private var sfRecognizer: SFSpeechRecognizer?
    private var sfRequest: SFSpeechAudioBufferRecognitionRequest?
    private var sfTask: SFSpeechRecognitionTask?

    func startLegacy() async {
        status = ""; tail = ""; store.reset()
        let auth = await withCheckedContinuation { (c: CheckedContinuation<SFSpeechRecognizerAuthorizationStatus, Never>) in
            SFSpeechRecognizer.requestAuthorization { c.resume(returning: $0) }
        }
        guard auth == .authorized else { status += "没有语音识别权限 \(auth.rawValue)\n"; return }
        guard let rec = SFSpeechRecognizer(locale: Locale(identifier: "zh-CN")) else { status += "zh-CN 识别器不可用\n"; return }
        sfRecognizer = rec
        status += "旧API zh-CN available=\(rec.isAvailable) onDevice=\(rec.supportsOnDeviceRecognition)\n"
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        req.requiresOnDeviceRecognition = rec.supportsOnDeviceRecognition
        req.taskHint = .dictation
        if #available(iOS 16, *) { req.addsPunctuation = true }
        sfRequest = req
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            let input = engine.inputNode
            let inFmt = input.outputFormat(forBus: 0)
            let store = self.store
            input.installTap(onBus: 0, bufferSize: 2048, format: inFmt) { buf, _ in
                req.append(buf)
                store.fed(seconds: Double(buf.frameLength) / inFmt.sampleRate)
            }
            engine.prepare()
            try engine.start()
            store.markStart()
            print(String(format: "SPEECH_STARTED mode=legacy onDevice=%d mic=%dHz", rec.supportsOnDeviceRecognition ? 1 : 0, Int(inFmt.sampleRate)))
            sfTask = rec.recognitionTask(with: req) { result, error in
                if let r = result { store.recordLegacy(r) }
                if let e = error { store.append("旧API结束: \(e.localizedDescription)") }
            }
            running = true
            status += "已开始（旧API），念稿子。\n"
            uiTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
                guard let self else { return }
                let lines = self.store.all()
                self.tail = String(format: "已喂入音频 %.1fs，结果 %d 条\n", self.store.fedSeconds(), lines.count) + lines.suffix(6).joined(separator: "\n")
            }
        } catch { status += "错误: \(error)\n" }
    }

    func stop() async {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        sfRequest?.endAudio(); sfTask = nil; sfRequest = nil
        continuation?.finish()
        try? await analyzer?.finalizeAndFinishThroughEndOfInput()
        resultTask?.cancel()
        uiTimer?.invalidate()
        running = false
        status += "已停止\n"
        print("SPEECH_STOPPED fed=\(String(format: "%.2f", store.fedSeconds()))s")
    }
}

/// 线程安全的小日志仓库；记录每条结果的到达墙钟、窗口范围、末字音频时间。
final class LogStore: @unchecked Sendable {
    private let lock = NSLock()
    private var lines: [String] = []
    private var fed: Double = 0
    private var t0 = Date()
    private var lastVolatileCount = 0
    private var firstLogged = false
    private var lastFedPrint: Double = 0

    func reset() { lock.lock(); lines = []; fed = 0; lastVolatileCount = 0; firstLogged = false; lastFedPrint = 0; lock.unlock() }
    func markStart() { lock.lock(); t0 = Date(); lock.unlock() }
    func fedSeconds() -> Double { lock.lock(); defer { lock.unlock() }; return fed }
    func all() -> [String] { lock.lock(); defer { lock.unlock() }; return lines }
    func append(_ s: String) { lock.lock(); lines.append(s); lock.unlock(); print("SPEECH " + s) }
    func fed(seconds: Double) {
        lock.lock()
        fed += seconds
        let wall = Date().timeIntervalSince(t0)
        var line: String? = nil
        if fed - lastFedPrint >= 5 { lastFedPrint = fed; line = String(format: "SPEECH_FED wall=%.2fs audio=%.2fs", wall, fed) }
        lock.unlock()
        if let line { print(line) }
    }
    func recordLegacy(_ r: SFSpeechRecognitionResult) {
        let wall = Date().timeIntervalSince(t0)
        let best = r.bestTranscription
        let text = best.formattedString
        let lastChar = best.segments.map { $0.timestamp + $0.duration }.max() ?? -1
        let lat = lastChar >= 0 ? wall - lastChar : -1
        lock.lock()
        let delta = r.isFinal ? "" : " +\(max(0, text.count - lastVolatileCount))字"
        lastVolatileCount = r.isFinal ? 0 : text.count
        let first = !firstLogged; firstLogged = true
        let fedNow = fed
        let line = String(format: "%@ 到达%.2fs 已喂%.2fs 窗口[0.00–%.2f] 末字%@ 延迟%.2fs%@ 「%@」", r.isFinal ? "FINAL" : "  vol", wall, fedNow, fedNow, lastChar >= 0 ? String(format: "%.2f", lastChar) : "无", lat, delta, text)
        lines.append(line)
        lock.unlock()
        if first { print(String(format: "SPEECH_FIRST_RESULT %.2fs", wall)) }
        print("SPEECH " + line)
    }

    func record(_ r: SpeechTranscriber.Result) {
        let wall = Date().timeIntervalSince(t0)
        let text = String(r.text.characters)
        let start = r.range.start.seconds, end = r.range.end.seconds
        var lastChar = -1.0
        for run in r.text.runs { if let tr = run.audioTimeRange { lastChar = max(lastChar, tr.end.seconds) } }
        let anchor = lastChar >= 0 ? lastChar : end
        let lat = wall - anchor
        lock.lock()
        let delta = r.isFinal ? "" : " +\(max(0, text.count - lastVolatileCount))字"
        lastVolatileCount = r.isFinal ? 0 : text.count
        let first = !firstLogged; firstLogged = true
        let fedNow = fed
        let line = String(format: "%@ 到达%.2fs 已喂%.2fs 窗口[%.2f–%.2f] 末字%@ 延迟%.2fs%@ 「%@」", r.isFinal ? "FINAL" : "  vol", wall, fedNow, start, end, lastChar >= 0 ? String(format: "%.2f", lastChar) : "无", lat, delta, text)
        lines.append(line)
        lock.unlock()
        if first { print(String(format: "SPEECH_FIRST_RESULT %.2fs", wall)) }
        print("SPEECH " + line)
    }
}

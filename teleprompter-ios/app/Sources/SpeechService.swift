import Foundation
import AVFoundation
import Speech

/// 把相机会话里的音频样本喂给 SpeechAnalyzer。线程安全，在音频队列上调用 feed。
final class SpeechFeeder: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: AsyncStream<AnalyzerInput>.Continuation?
    private var outFormat: AVAudioFormat?
    private var converter: AVAudioConverter?
    private var converterKey = ""
    private var fedSeconds: Double = 0
    private var lastPrint: Double = -10
    private var sampleCount = 0
    var totalSamples: Int { lock.lock(); defer { lock.unlock() }; return sampleCount }

    func attach(format: AVAudioFormat, continuation: AsyncStream<AnalyzerInput>.Continuation) {
        lock.lock(); outFormat = format; self.continuation = continuation; converter = nil; converterKey = ""; lock.unlock()
    }
    func detach() { lock.lock(); continuation?.finish(); continuation = nil; lock.unlock() }

    func feed(sampleBuffer sb: CMSampleBuffer) {
        guard let fd = CMSampleBufferGetFormatDescription(sb) else { return }
        let inFmt = AVAudioFormat(cmAudioFormatDescription: fd)
        let frames = AVAudioFrameCount(CMSampleBufferGetNumSamples(sb))
        lock.lock(); sampleCount += 1; let n = sampleCount; lock.unlock()
        guard frames > 0, let pcm = AVAudioPCMBuffer(pcmFormat: inFmt, frameCapacity: frames) else {
            if n <= 3 { print("SPEECH feed: PCMBuffer 建不出来 fmt=\(inFmt) frames=\(frames)") }; return
        }
        pcm.frameLength = frames
        let st = CMSampleBufferCopyPCMDataIntoAudioBufferList(sb, at: 0, frameCount: Int32(frames), into: pcm.mutableAudioBufferList)
        guard st == noErr else { if n <= 3 { print("SPEECH feed: 拷贝 PCM 失败 status=\(st)") }; return }
        if n == 1 { print("SPEECH feed: 首个样本 fmt=\(inFmt) frames=\(frames)") }
        feed(pcm: pcm, inFmt: inFmt)
    }

    var fedSecondsTotal: Double { lock.lock(); defer { lock.unlock() }; return fedSeconds }

    func feed(pcm: AVAudioPCMBuffer, inFmt: AVAudioFormat) {
        lock.lock()
        guard let out = outFormat, let cont = continuation else {
            let n = sampleCount; lock.unlock()
            if n <= 3 || n % 500 == 0 { print("SPEECH feed: 识别器还没接上，丢弃 (\(n))") }
            return
        }
        let key = "\(inFmt.sampleRate)/\(inFmt.channelCount)/\(inFmt.commonFormat.rawValue)/\(inFmt.isInterleaved)"
        if converter == nil || converterKey != key { converter = AVAudioConverter(from: inFmt, to: out); converterKey = key }
        guard let conv = converter else { lock.unlock(); return }
        lock.unlock()
        let ratio = out.sampleRate / inFmt.sampleRate
        let cap = AVAudioFrameCount(Double(pcm.frameLength) * ratio) + 32
        guard let outBuf = AVAudioPCMBuffer(pcmFormat: out, frameCapacity: cap) else { return }
        var err: NSError?
        var consumed = false
        let st = conv.convert(to: outBuf, error: &err) { _, status in
            if consumed { status.pointee = .noDataNow; return nil }
            consumed = true; status.pointee = .haveData; return pcm
        }
        if st != .error, outBuf.frameLength > 0 {
            cont.yield(AnalyzerInput(buffer: outBuf))
            lock.lock()
            fedSeconds += Double(outBuf.frameLength) / out.sampleRate
            let f = fedSeconds; let shouldPrint = f - lastPrint >= 5; if shouldPrint { lastPrint = f }
            lock.unlock()
            if shouldPrint { print(String(format: "SPEECH fed %.1fs", f)) }
        } else {
            print("SPEECH feed: 转换失败 st=\(st.rawValue) err=\(err?.localizedDescription ?? "-") in=\(inFmt) out=\(out)")
        }
    }
}

/// iOS 26 SpeechAnalyzer，zh-CN 本机。关键：priority .userInitiated + fastResults，否则十几秒才吐一批（09-27 验证）。
@MainActor
final class SpeechService: ObservableObject {
    @Published var status = "" { didSet { print("SPEECH status: \(status)") } }
    @Published var ready = false
    let feeder = SpeechFeeder()
    /// 每次识别文本变化时回调：finals 累计 + 当前 volatile
    var onTranscript: ((String) -> Void)?

    private var analyzer: SpeechAnalyzer?
    private var transcriber: SpeechTranscriber?
    private var resultTask: Task<Void, Never>?
    private var finalText = ""
    private var volatileText = ""

    var transcript: String { finalText + volatileText }

    func start() async {
        do {
            let supported = await SpeechTranscriber.supportedLocales
            let zh = supported.filter { $0.language.languageCode?.identifier == "zh" }
            guard let locale = zh.first(where: { $0.region?.identifier == "CN" }) ?? zh.first(where: { $0.language.script?.identifier == "Hans" }) else {
                status = "没有简体中文识别"; return
            }
            let tr = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [.volatileResults, .fastResults], attributeOptions: [])
            transcriber = tr
            if let req = try await AssetInventory.assetInstallationRequest(supporting: [tr]) {
                status = "下载中文模型…"
                try await req.downloadAndInstall()
            }
            let an = SpeechAnalyzer(modules: [tr], options: SpeechAnalyzer.Options(priority: .userInitiated, modelRetention: .processLifetime))
            analyzer = an
            guard let fmt = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [tr]) else { status = "拿不到识别音频格式"; return }
            try await an.prepareToAnalyze(in: fmt)
            let (stream, cont) = AsyncStream<AnalyzerInput>.makeStream()
            feeder.attach(format: fmt, continuation: cont)
            resultTask = Task.detached(priority: .userInitiated) { [weak self] in
                do {
                    for try await r in tr.results {
                        let text = String(r.text.characters)
                        let isFinal = r.isFinal
                        await MainActor.run { self?.handle(text: text, isFinal: isFinal) }
                    }
                } catch {
                    await MainActor.run { self?.status = "识别停止: \(error.localizedDescription)" }
                }
            }
            try await an.start(inputSequence: stream)
            ready = true
            status = "识别就绪"
        } catch {
            status = "识别启动失败: \(error.localizedDescription)"
        }
    }

    private var resultCount = 0
    private func handle(text: String, isFinal: Bool) {
        if isFinal { finalText += text; volatileText = "" } else { volatileText = text }
        resultCount += 1
        if resultCount <= 5 || resultCount % 20 == 0 || isFinal { print("SPEECH result#\(resultCount) \(isFinal ? "FINAL" : "vol") 「\(text.suffix(30))」") }
        onTranscript?(transcript)
    }

    func stop() async {
        feeder.detach()
        try? await analyzer?.finalizeAndFinishThroughEndOfInput()
        resultTask?.cancel()
        ready = false
    }
}

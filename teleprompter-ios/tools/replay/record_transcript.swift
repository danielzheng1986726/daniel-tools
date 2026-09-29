// 在 Mac 上用 SpeechTranscriber（和 App 同样的参数）按真实语速识别一段音频，
// 把每一次识别结果（volatile / final）连同音频时刻记成 JSONL，供 replay 重放匹配逻辑。
// 用法：swiftc -parse-as-library record_transcript.swift -o record && ./record in.wav out.jsonl
import AVFoundation
import Foundation
import Speech

@main
struct Recorder {
    static func main() async throws {
        let args = CommandLine.arguments
        guard args.count == 3 else { print("用法: record in.wav out.jsonl"); exit(2) }
        let file = try AVAudioFile(forReading: URL(fileURLWithPath: args[1]))
        let out = FileHandle(forWritingAtPath: args[2]) ?? {
            FileManager.default.createFile(atPath: args[2], contents: nil)
            return FileHandle(forWritingAtPath: args[2])!
        }()
        try out.truncate(atOffset: 0)

        let zh = await SpeechTranscriber.supportedLocales.filter { $0.language.languageCode?.identifier == "zh" }
        guard let locale = zh.first(where: { $0.region?.identifier == "CN" }) ?? zh.first else { print("没有中文"); exit(1) }
        let tr = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [.volatileResults, .fastResults], attributeOptions: [])
        if let req = try await AssetInventory.assetInstallationRequest(supporting: [tr]) {
            print("下载中文模型…"); try await req.downloadAndInstall()
        }
        let an = SpeechAnalyzer(modules: [tr], options: SpeechAnalyzer.Options(priority: .userInitiated, modelRetention: .processLifetime))
        guard let fmt = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [tr]) else { print("无格式"); exit(1) }
        try await an.prepareToAnalyze(in: fmt)
        let (stream, cont) = AsyncStream<AnalyzerInput>.makeStream()

        let clock = ContinuousClock()
        let t0 = clock.now
        func elapsed() -> Double { let d = clock.now - t0; return Double(d.components.seconds) + Double(d.components.attoseconds) / 1e18 }

        let results = Task {
            var n = 0
            for try await r in tr.results {
                n += 1
                let rec: [String: Any] = ["t": elapsed(), "final": r.isFinal, "text": String(r.text.characters),
                                          "rs": r.range.start.seconds, "re": r.range.end.seconds]
                let data = try JSONSerialization.data(withJSONObject: rec)
                out.write(data); out.write("\n".data(using: .utf8)!)
                if n % 20 == 0 || r.isFinal { print(String(format: "%.1fs %@ 「%@」", elapsed(), r.isFinal ? "FINAL" : "vol", String(String(r.text.characters).suffix(20)))) }
            }
        }
        try await an.start(inputSequence: stream)

        // 按真实语速喂：每 0.1 秒一块，和手机上实时录音的节奏一致
        let inFmt = file.processingFormat
        let conv = AVAudioConverter(from: inFmt, to: fmt)!
        let chunk = AVAudioFrameCount(inFmt.sampleRate / 10)
        var fed = 0.0
        while file.framePosition < file.length {
            guard let buf = AVAudioPCMBuffer(pcmFormat: inFmt, frameCapacity: chunk) else { break }
            try file.read(into: buf, frameCount: chunk)
            if buf.frameLength == 0 { break }
            let cap = AVAudioFrameCount(Double(buf.frameLength) * fmt.sampleRate / inFmt.sampleRate) + 32
            let ob = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: cap)!
            var used = false
            _ = conv.convert(to: ob, error: nil) { _, st in
                if used { st.pointee = .noDataNow; return nil }
                used = true; st.pointee = .haveData; return buf
            }
            cont.yield(AnalyzerInput(buffer: ob))
            fed += Double(buf.frameLength) / inFmt.sampleRate
            let wait = fed - elapsed()
            if wait > 0 { try await Task.sleep(for: .milliseconds(Int(wait * 1000))) }
        }
        cont.finish()
        try await an.finalizeAndFinishThroughEndOfInput()
        _ = try? await results.value
        try out.close()
        print(String(format: "完成，喂了 %.1f 秒", fed))
    }
}

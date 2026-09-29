import SwiftUI
@preconcurrency import AVFoundation
import UIKit

func fourCC(_ t: FourCharCode) -> String {
    let bytes: [UInt8] = [24, 16, 8, 0].map { UInt8((t >> $0) & 0xff) }
    return String(bytes: bytes, encoding: .ascii) ?? "????"
}

struct CameraFormatsView: View {
    @State private var report = "读取中…"
    @State private var recording = false
    @StateObject private var recorder = RecordTest()

    var body: some View {
        NavigationStack {
            ScrollView {
                Text(report + "\n" + recorder.report)
                    .font(.system(size: 11, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }
            .navigationTitle("前置摄像头格式")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("复制") { UIPasteboard.general.string = report + "\n" + recorder.report }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button(recording ? "录制中…" : "录 5 秒最高格式") {
                        recording = true
                        Task { await recorder.run(); recording = false }
                    }.disabled(recording)
                }
            }
        }
        .task {
            let ok = await AVCaptureDevice.requestAccess(for: .video)
            _ = await AVCaptureDevice.requestAccess(for: .audio)
            report = ok ? enumerateFormats() : "没有相机权限"
            print("FORMATS_DONE")
        }
    }

    func enumerateFormats() -> String {
        var out = "设备 \(UIDevice.current.model) iOS \(UIDevice.current.systemVersion)\n"
        let types: [AVCaptureDevice.DeviceType] = [.builtInWideAngleCamera, .builtInUltraWideCamera, .builtInTrueDepthCamera, .builtInDualWideCamera, .builtInTelephotoCamera]
        let ds = AVCaptureDevice.DiscoverySession(deviceTypes: types, mediaType: .video, position: .unspecified)
        for d in ds.devices {
            out += "\n== \(d.localizedName) type=\(d.deviceType.rawValue) pos=\(d.position == .front ? "front" : "back") centerStageSupported(any)=\(d.formats.contains { $0.isCenterStageSupported })\n"
            out += "   activeFormat=\(fmtLine(d.activeFormat)) activeColorSpace=\(d.activeColorSpace.rawValue)\n"
            for (i, f) in d.formats.enumerated() where d.position == .front {
                out += String(format: "%3d ", i) + fmtLine(f) + "\n"
            }
            if d.position == .back { out += "   (后置格式 \(d.formats.count) 个，略)\n" }
        }
        out += "\n颜色空间编号: sRGB=0 P3=1 HLG=2 appleLog=3\n"
        return out
    }

    func fmtLine(_ f: AVCaptureDevice.Format) -> String {
        let dims = CMVideoFormatDescriptionGetDimensions(f.formatDescription)
        let sub = fourCC(CMFormatDescriptionGetMediaSubType(f.formatDescription))
        let maxFps = f.videoSupportedFrameRateRanges.map { $0.maxFrameRate }.max() ?? 0
        let cs = f.supportedColorSpaces.map { String($0.rawValue) }.joined(separator: "/")
        let stabs: [(AVCaptureVideoStabilizationMode, String)] = [(.standard, "std"), (.cinematic, "cin"), (.cinematicExtended, "cinX"), (.cinematicExtendedEnhanced, "cinXE"), (.previewOptimized, "prev")]
        let stab = stabs.filter { f.isVideoStabilizationModeSupported($0.0) }.map { $0.1 }.joined(separator: ",")
        return String(format: "%dx%d %@ %.0ffps hdr=%d cs=%@ bin=%d cs_stage=%d fov=%.0f stab=%@", dims.width, dims.height, sub, maxFps, f.isVideoHDRSupported ? 1 : 0, cs, f.isVideoBinned ? 1 : 0, f.isCenterStageSupported ? 1 : 0, Double(f.videoFieldOfView), stab)
    }
}

/// 用前置摄像头能拿到的最高格式（优先 10-bit x420 + HLG）录 5 秒，然后读回文件的实际编码参数。
@MainActor
final class RecordTest: NSObject, ObservableObject, AVCaptureFileOutputRecordingDelegate {
    @Published var report = ""
    private var session: AVCaptureSession?
    private var output: AVCaptureMovieFileOutput?
    private var finished: CheckedContinuation<URL?, Never>?

    func run() async {
        report = "\n--- 录制测试 ---\n"
        guard let dev = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) else { report += "没有前置广角\n"; return }
        // 选格式：只看 16:9 视频格式；优先 HLG 10-bit（x420），再按像素数，再按帧率（上限 60）
        func score(_ f: AVCaptureDevice.Format) -> (Int, Int, Int, Double) {
            let d = CMVideoFormatDescriptionGetDimensions(f.formatDescription)
            let sub = fourCC(CMFormatDescriptionGetMediaSubType(f.formatDescription))
            let is169 = abs(Double(d.width) / Double(d.height) - 16.0 / 9.0) < 0.02 ? 1 : 0
            let hlg = (f.supportedColorSpaces.contains(.HLG_BT2020) && sub == "x420") ? 1 : 0
            let fps = min(60, f.videoSupportedFrameRateRanges.map { $0.maxFrameRate }.max() ?? 0)
            return (is169, hlg, Int(d.width) * Int(d.height), fps)
        }
        let best = dev.formats
            .max { a, b in
                let sa = score(a), sb = score(b)
                if sa.0 != sb.0 { return sa.0 < sb.0 }
                if sa.1 != sb.1 { return sa.1 < sb.1 }
                if sa.2 != sb.2 { return sa.2 < sb.2 }
                return sa.3 < sb.3
            }
        guard let fmt = best else { report += "没有可用格式\n"; return }
        let s = AVCaptureSession()
        s.beginConfiguration()
        s.automaticallyConfiguresCaptureDeviceForWideColor = false
        do {
            let vin = try AVCaptureDeviceInput(device: dev)
            guard s.canAddInput(vin) else { report += "加不进视频输入\n"; return }
            s.addInput(vin)
            if let mic = AVCaptureDevice.default(for: .audio), let ain = try? AVCaptureDeviceInput(device: mic), s.canAddInput(ain) { s.addInput(ain) }
            let out = AVCaptureMovieFileOutput()
            guard s.canAddOutput(out) else { report += "加不进输出\n"; return }
            s.addOutput(out)
            try dev.lockForConfiguration()
            dev.activeFormat = fmt
            let targetFps: Double = min(30, fmt.videoSupportedFrameRateRanges.map { $0.maxFrameRate }.max() ?? 30)
            dev.activeVideoMinFrameDuration = CMTime(value: 1, timescale: Int32(targetFps))
            dev.activeVideoMaxFrameDuration = CMTime(value: 1, timescale: Int32(targetFps))
            if fmt.supportedColorSpaces.contains(.HLG_BT2020) { dev.activeColorSpace = .HLG_BT2020 }
            dev.unlockForConfiguration()
            if let conn = out.connection(with: .video) {
                if conn.isVideoStabilizationSupported { conn.preferredVideoStabilizationMode = .auto }
                if out.availableVideoCodecTypes.contains(.hevc) { out.setOutputSettings([AVVideoCodecKey: AVVideoCodecType.hevc], for: conn) }
                report += "输出可用编码: \(out.availableVideoCodecTypes.map { $0.rawValue })\n"
                report += "输出设置: \(out.outputSettings(for: conn))\n"
            }
            s.commitConfiguration()
            session = s; output = out
            report += "选定格式: \(CameraFormatsView().fmtLine(fmt)) 目标 \(Int(targetFps))fps activeColorSpace=\(dev.activeColorSpace.rawValue)\n"
        } catch { report += "配置失败 \(error)\n"; return }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("spike_\(Int(Date().timeIntervalSince1970)).mov")
        await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
            DispatchQueue.global().async { s.startRunning(); c.resume() }
        }
        output?.startRecording(to: url, recordingDelegate: self)
        let fileURL: URL? = await withCheckedContinuation { c in
            finished = c
            Task { try? await Task.sleep(for: .seconds(5)); self.output?.stopRecording() }
        }
        s.stopRunning()
        guard let f = fileURL else { report += "录制失败\n"; return }
        await inspect(f)
    }

    nonisolated func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL, from connections: [AVCaptureConnection], error: Error?) {
        Task { @MainActor in
            if let e = error { report += "录制回调错误: \(e)\n" }
            finished?.resume(returning: outputFileURL); finished = nil
        }
    }

    func inspect(_ url: URL) async {
        let asset = AVURLAsset(url: url)
        do {
            let size = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0
            let dur = try await asset.load(.duration).seconds
            report += String(format: "文件 %.1f MB, %.2f s\n", Double(size) / 1e6, dur)
            for t in try await asset.loadTracks(withMediaType: .video) {
                let descs = try await t.load(.formatDescriptions)
                let fps = try await t.load(.nominalFrameRate)
                let rate = try await t.load(.estimatedDataRate)
                for d in descs {
                    let dims = CMVideoFormatDescriptionGetDimensions(d)
                    let codec = fourCC(CMFormatDescriptionGetMediaSubType(d))
                    let ext = CMFormatDescriptionGetExtensions(d) as? [String: Any] ?? [:]
                    let keys = ["ColorPrimaries", "TransferFunction", "YCbCrMatrix", "BitsPerComponent", "FullRangeVideo"]
                    let kv = keys.map { "\($0)=\(ext[$0].map { "\($0)" } ?? "-")" }.joined(separator: " ")
                    report += String(format: "视频轨 %@ %dx%d %.1ffps %.1f Mbps %@\n", codec, dims.width, dims.height, fps, rate / 1e6, kv)
                }
            }
            for t in try await asset.loadTracks(withMediaType: .audio) {
                for d in try await t.load(.formatDescriptions) {
                    let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(d)?.pointee
                    report += "音频轨 \(fourCC(CMFormatDescriptionGetMediaSubType(d))) \(asbd?.mSampleRate ?? 0)Hz ch=\(asbd?.mChannelsPerFrame ?? 0)\n"
                }
            }
        } catch { report += "读文件失败 \(error)\n" }
        print(report)
        print("RECORD_DONE")
        try? FileManager.default.removeItem(at: url)
    }
}

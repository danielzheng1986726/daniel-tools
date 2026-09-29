@preconcurrency import AVFoundation
import Photos
import UIKit

/// 音频样本的中转：相机会话的音频输出在后台队列回调，这里转给识别器。
final class AudioRelay: NSObject, AVCaptureAudioDataOutputSampleBufferDelegate, @unchecked Sendable {
    var sink: ((CMSampleBuffer) -> Void)?
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        sink?(sampleBuffer)
    }
}

func fourCC(_ t: FourCharCode) -> String {
    let bytes: [UInt8] = [24, 16, 8, 0].map { UInt8((t >> $0) & 0xff) }
    return String(bytes: bytes, encoding: .ascii) ?? "????"
}

/// 前置摄像头：16:9 里选 10-bit HLG 像素最多的格式，30 fps，HEVC 录到临时文件再存相册。
@MainActor
final class CameraService: NSObject, ObservableObject, AVCaptureFileOutputRecordingDelegate {
    let session = AVCaptureSession()
    @Published var isRecording = false
    @Published var elapsed: TimeInterval = 0
    @Published var status = ""
    @Published var formatLine = ""
    @Published var audioViaCapture = false
    /// 录完一段的回调（文件已经在 Documents/takes 里）
    var onTakeFinished: ((URL) -> Void)?
    /// 正在录 / 刚录完的那段的文件路径，日志用同名 .md 放旁边
    @Published var currentTakeURL: URL? = nil

    let relay = AudioRelay()
    private let movieOutput = AVCaptureMovieFileOutput()
    private let audioOutput = AVCaptureAudioDataOutput()
    private let audioQueue = DispatchQueue(label: "prompter.audio")
    private var timer: Timer?
    private var recordStart = Date()
    private var configured = false
    private var device: AVCaptureDevice?

    /// 防抖档：最强 = cinematicExtended（走路手持，画面更稳但视野裁得多）；否则交给系统自动。
    /// 格式不支持最强档时退回自动。录制中不改。
    func setStabilization(strong: Bool) {
        guard !isRecording, let conn = movieOutput.connection(with: .video), conn.isVideoStabilizationSupported else { return }
        let canStrong = device?.activeFormat.isVideoStabilizationModeSupported(.cinematicExtended) ?? false
        conn.preferredVideoStabilizationMode = (strong && canStrong) ? .cinematicExtended : .auto
        print("CAMERA 防抖 preferred=\(conn.preferredVideoStabilizationMode.rawValue) canStrong=\(canStrong)")
    }

    /// 这段实际生效的防抖档，写进拍摄日志
    var activeStabilizationName: String {
        guard let conn = movieOutput.connection(with: .video) else { return "" }
        switch conn.activeVideoStabilizationMode {
        case .off: return "关"
        case .standard: return "标准（standard）"
        case .cinematic: return "强（cinematic）"
        case .cinematicExtended: return "最强（cinematicExtended）"
        case .cinematicExtendedEnhanced: return "最强增强（cinematicExtendedEnhanced）"
        case .previewOptimized: return "预览优化（previewOptimized）"
        case .lowLatency: return "低延迟（lowLatency）"
        case .auto: return "自动"
        @unknown default: return "未知（\(conn.activeVideoStabilizationMode.rawValue)）"
        }
    }

    func configure(strongStabilization: Bool) async -> Bool {
        if configured { return true }
        guard await AVCaptureDevice.requestAccess(for: .video) else { status = "没有相机权限"; return false }
        _ = await AVCaptureDevice.requestAccess(for: .audio)
        guard let dev = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) else { status = "没有前置摄像头"; return false }
        device = dev
        func score(_ f: AVCaptureDevice.Format) -> (Int, Int, Int, Double) {
            let d = CMVideoFormatDescriptionGetDimensions(f.formatDescription)
            let sub = fourCC(CMFormatDescriptionGetMediaSubType(f.formatDescription))
            let is169 = abs(Double(d.width) / Double(d.height) - 16.0 / 9.0) < 0.02 ? 1 : 0
            let hlg = (f.supportedColorSpaces.contains(.HLG_BT2020) && sub == "x420") ? 1 : 0
            let fps = min(60, f.videoSupportedFrameRateRanges.map { $0.maxFrameRate }.max() ?? 0)
            return (is169, hlg, Int(d.width) * Int(d.height), fps)
        }
        guard let fmt = dev.formats.max(by: { a, b in
            let sa = score(a), sb = score(b)
            if sa.0 != sb.0 { return sa.0 < sb.0 }
            if sa.1 != sb.1 { return sa.1 < sb.1 }
            if sa.2 != sb.2 { return sa.2 < sb.2 }
            return sa.3 < sb.3
        }) else { status = "没有可用格式"; return false }

        session.beginConfiguration()
        session.automaticallyConfiguresCaptureDeviceForWideColor = false
        do {
            let vin = try AVCaptureDeviceInput(device: dev)
            guard session.canAddInput(vin) else { status = "加不进视频输入"; session.commitConfiguration(); return false }
            session.addInput(vin)
            if let mic = AVCaptureDevice.default(for: .audio), let ain = try? AVCaptureDeviceInput(device: mic), session.canAddInput(ain) {
                session.addInput(ain)
            }
            guard session.canAddOutput(movieOutput) else { status = "加不进录制输出"; session.commitConfiguration(); return false }
            session.addOutput(movieOutput)
            audioOutput.setSampleBufferDelegate(relay, queue: audioQueue)
            if session.canAddOutput(audioOutput) {
                session.addOutput(audioOutput)
                audioViaCapture = true
            } else {
                audioViaCapture = false
                print("CAMERA audio data output 不能和录制输出共存，识别改走 AVAudioEngine")
            }
            try dev.lockForConfiguration()
            dev.activeFormat = fmt
            dev.activeVideoMinFrameDuration = CMTime(value: 1, timescale: 30)
            dev.activeVideoMaxFrameDuration = CMTime(value: 1, timescale: 30)
            if fmt.supportedColorSpaces.contains(.HLG_BT2020) { dev.activeColorSpace = .HLG_BT2020 }
            dev.unlockForConfiguration()
            if let conn = movieOutput.connection(with: .video) {
                if conn.isVideoStabilizationSupported {
                    conn.preferredVideoStabilizationMode = (strongStabilization && fmt.isVideoStabilizationModeSupported(.cinematicExtended)) ? .cinematicExtended : .auto
                }
                if conn.isVideoRotationAngleSupported(90) { conn.videoRotationAngle = 90 }
                if movieOutput.availableVideoCodecTypes.contains(.hevc) {
                    movieOutput.setOutputSettings([AVVideoCodecKey: AVVideoCodecType.hevc], for: conn)
                }
            }
            let d = CMVideoFormatDescriptionGetDimensions(fmt.formatDescription)
            formatLine = "\(d.width)×\(d.height) \(fourCC(CMFormatDescriptionGetMediaSubType(fmt.formatDescription))) 30fps cs=\(dev.activeColorSpace.rawValue)"
        } catch {
            status = "相机配置失败: \(error.localizedDescription)"; session.commitConfiguration(); return false
        }
        session.commitConfiguration()
        let s = session
        await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
            DispatchQueue.global(qos: .userInitiated).async { s.startRunning(); c.resume() }
        }
        configured = true
        print("CAMERA ready \(formatLine) audioViaCapture=\(audioViaCapture)")
        return true
    }

    func startRecording() {
        guard !isRecording else { return }
        let url = TakeStore.newTakeURL()
        currentTakeURL = url
        movieOutput.startRecording(to: url, recordingDelegate: self)
        isRecording = true
        recordStart = Date()
        elapsed = 0
        status = ""
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.elapsed = Date().timeIntervalSince(self.recordStart)
        }
    }

    func stopRecording() {
        guard isRecording else { return }
        movieOutput.stopRecording()
        timer?.invalidate(); timer = nil
        isRecording = false
        status = "正在收尾…"
    }

    nonisolated func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL, from connections: [AVCaptureConnection], error: Error?) {
        Task { @MainActor in
            if let e = error as NSError?, !(e.userInfo[AVErrorRecordingSuccessfullyFinishedKey] as? Bool ?? false) {
                status = "录制出错: \(e.localizedDescription)"; return
            }
            let size = (try? FileManager.default.attributesOfItem(atPath: outputFileURL.path)[.size] as? Int) ?? 0
            status = String(format: "录好一段 %.0f MB，在下面看", Double(size) / 1e6)
            onTakeFinished?(outputFileURL)
        }
    }
}

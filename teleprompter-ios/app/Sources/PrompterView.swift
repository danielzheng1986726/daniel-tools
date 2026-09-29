import SwiftUI
import AVFoundation
import AVKit
import UIKit

/// 相机预览 + 实体键（音量键、相机控制键）触发。
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    let onPrimary: () -> Void     // 音量下 / 相机控制键
    let onSecondary: () -> Void   // 音量上

    func makeUIView(context: Context) -> PreviewUIView {
        let v = PreviewUIView()
        v.videoPreviewLayer.session = session
        v.videoPreviewLayer.videoGravity = .resizeAspectFill
        let interaction = AVCaptureEventInteraction(primary: { e in if e.phase == .began { onPrimary() } },
                                                    secondary: { e in if e.phase == .began { onSecondary() } })
        v.addInteraction(interaction)
        return v
    }
    func updateUIView(_ uiView: PreviewUIView, context: Context) {}
}

final class PreviewUIView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var videoPreviewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
}

/// 备用：相机会话不肯同时给音频样本时，用 AVAudioEngine 直接从麦克风取。
final class MicTap {
    private let engine = AVAudioEngine()
    func start(feeder: SpeechFeeder) throws {
        let input = engine.inputNode
        let fmt = input.outputFormat(forBus: 0)
        input.installTap(onBus: 0, bufferSize: 2048, format: fmt) { buf, _ in feeder.feed(pcm: buf, inFmt: fmt) }
        engine.prepare()
        try engine.start()
    }
    func stop() { engine.inputNode.removeTap(onBus: 0); engine.stop() }
}

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

struct PrompterView: View {
    let onExit: () -> Void
    @StateObject private var engine: PrompterEngine
    @StateObject private var camera = CameraService()
    @StateObject private var speech = SpeechService()
    @StateObject private var takes = TakeStore()
    @State private var previewTake: Take? = nil
    @State private var confirmDelete: Take? = nil
    @State private var pendingTake: Take? = nil
    @State private var pendingStartPage = 0
    @State private var shareTake: Take? = nil
    @State private var merging = false
    @State private var mergedItems: [URL]? = nil
    @State private var mergedFrom: [Take] = []
    @State private var askDeleteMerged = false
    @AppStorage("fontSize") private var fontSize: Double = 32
    @AppStorage("strongStabilization") private var strongStabilization = true
    @State private var showFont = false
    @State private var showShare = false
    @State private var exportURL: URL? = nil
    @State private var micTap: MicTap? = nil
    @State private var lastLogMarkdown = ""

    init(script: Script, onExit: @escaping () -> Void) {
        self.onExit = onExit
        _engine = StateObject(wrappedValue: PrompterEngine(script: script))
    }

    var body: some View {
        ZStack {
            CameraPreview(session: camera.session,
                          onPrimary: { engine.next(manual: true) },
                          onSecondary: { engine.prev() })
                .ignoresSafeArea()
            Color.black.opacity(camera.isRecording ? 0.6 : 0).ignoresSafeArea().allowsHitTesting(false)

            VStack(spacing: 0) {
                if let page = engine.currentPage {
                    PrompterCard(engine: engine, page: page, fontSize: fontSize)
                        .padding(.top, 6)
                        .padding(.bottom, 22)
                }
                Spacer()
                if !camera.isRecording && !takes.takes.isEmpty { takeStrip }
                statusLine
                controls.padding(.bottom, 10)
            }
        }
        .preferredColorScheme(.dark)
        .statusBarHidden(true)
        .sheet(isPresented: $showFont) { fontSheet }
        .sheet(isPresented: $showShare) { if let u = exportURL { ShareSheet(items: [u]) } }
        .sheet(item: $previewTake) { t in TakePreview(take: t, store: takes, onShare: { shareTake = t }) { previewTake = nil } }
        .sheet(item: $shareTake) { t in ShareSheet(items: t.shareItems) }
        .sheet(isPresented: Binding(get: { mergedItems != nil }, set: { if !$0 { mergedItems = nil } }), onDismiss: { if !mergedFrom.isEmpty { askDeleteMerged = true } }) { ShareSheet(items: mergedItems ?? []) }
        .confirmationDialog("合并好的已导出。这几段原片删掉吗？", isPresented: $askDeleteMerged, titleVisibility: .visible) {
            Button("删掉 \(mergedFrom.count) 段原片", role: .destructive) { takes.deleteAll(mergedFrom); mergedFrom = [] }
            Button("留着", role: .cancel) { mergedFrom = [] }
        } message: { Text("合并文件本身留在 文件 → 提词 → exports 里，随时能再分享。") }
        .confirmationDialog("这段留不留？", isPresented: Binding(get: { pendingTake != nil }, set: { if !$0 { pendingTake = nil } }), titleVisibility: .visible) {
            Button("留下") { pendingTake = nil }
            Button("先看看") { if let t = pendingTake { previewTake = t }; pendingTake = nil }
            Button("丢掉", role: .destructive) { if let t = pendingTake { takes.delete(t); engine.returnTo(page: pendingStartPage) }; pendingTake = nil }
        } message: { Text(pendingTake.map { String(format: "%.0f 秒，%.0f MB。\n视频 ✓  日志 %@  已存在 App 里（文件 → 我的 iPhone → 提词 → takes）。留下的段在下面一排，随时能看、分享或删。", $0.duration, $0.sizeMB, $0.hasLog ? "✓" : "✗ 没写上") } ?? "") }
        .alert("删除这段？", isPresented: Binding(get: { confirmDelete != nil }, set: { if !$0 { confirmDelete = nil } })) {
            Button("删除", role: .destructive) { if let t = confirmDelete { takes.delete(t) }; confirmDelete = nil }
            Button("取消", role: .cancel) { confirmDelete = nil }
        } message: { Text(confirmDelete.map { String(format: "%.0f 秒，%.0f MB", $0.duration, $0.sizeMB) } ?? "") }
        .task { await setup() }
        .onDisappear { teardown() }
    }

    private var takeStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(takes.takes) { t in
                    ZStack(alignment: .topTrailing) {
                        Group {
                            if let img = t.thumbnail { Image(uiImage: img).resizable().scaledToFill() } else { Color.gray }
                        }
                        .frame(width: 64, height: 112).clipped().cornerRadius(8)
                        .overlay(alignment: .topLeading) {
                            Text(t.hasLog ? "日志✓" : "无日志")
                                .font(.system(size: 9, weight: .semibold)).foregroundColor(t.hasLog ? .white : .orange)
                                .padding(.horizontal, 3).padding(.vertical, 1).background(Color.black.opacity(0.6)).cornerRadius(3).padding(3)
                        }
                        .overlay(alignment: .bottom) {
                            Text(String(format: "%d:%02d", Int(t.duration) / 60, Int(t.duration) % 60))
                                .font(.system(size: 11, weight: .semibold)).foregroundColor(.white)
                                .padding(.horizontal, 4).padding(.vertical, 2).background(Color.black.opacity(0.6)).cornerRadius(4).padding(4)
                        }
                        .onTapGesture { previewTake = t }
                        Button { confirmDelete = t } label: {
                            Image(systemName: "xmark.circle.fill").font(.system(size: 18)).foregroundColor(.white).shadow(radius: 2)
                        }.offset(x: 6, y: -6)
                    }
                }
                Button {
                    merging = true
                    let list = takes.takes
                    Task {
                        do { let u = try await takes.merge(list); mergedFrom = list; mergedItems = u; takes.message = "已合并 \(list.count) 段，视频和日志一起分享" }
                        catch { takes.message = "合并失败: \(error.localizedDescription)" }
                        merging = false
                    }
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: merging ? "hourglass" : "checkmark.circle.fill").font(.system(size: 28))
                        Text(merging ? "合并中" : "完成\n合并 \(takes.takes.count) 段").font(.system(size: 11)).multilineTextAlignment(.center)
                    }
                    .foregroundColor(.white).frame(width: 72, height: 112).background(Color.green.opacity(0.35)).cornerRadius(8)
                }.disabled(merging)
            }
            .padding(.horizontal, 16).padding(.vertical, 6)
        }
    }

    private var statusLine: some View {
        HStack(spacing: 12) {
            if camera.isRecording {
                Text(String(format: "● %02d:%02d", Int(camera.elapsed) / 60, Int(camera.elapsed) % 60)).foregroundColor(.red).monospacedDigit()
            } else if !takes.message.isEmpty {
                Text(takes.message).foregroundColor(.white.opacity(0.8))
            } else if !camera.status.isEmpty {
                Text(camera.status).foregroundColor(.white.opacity(0.8))
            }
            if !speech.ready { Text(speech.status).foregroundColor(.orange) }
        }
        .font(.system(size: 13))
        .padding(.bottom, 6)
    }

    private var controls: some View {
        HStack(alignment: .center, spacing: 6) {
            ToolButton(icon: "doc.text", label: "换稿子") { onExit() }
            ToolButton(icon: "arrow.uturn.backward", label: "回第一页") { engine.goToStart() }
            Button {
                if camera.isRecording {
                    engine.log.stabilization = camera.activeStabilizationName
                    camera.stopRecording(); engine.endTake(); prepareExport()
                } else {
                    takes.message = ""
                    pendingStartPage = engine.pageIndex
                    engine.startTake(); camera.startRecording()
                }
            } label: {
                VStack(spacing: 4) {
                    ZStack {
                        Circle().stroke(Color.white, lineWidth: 4).frame(width: 78, height: 78)
                        if camera.isRecording {
                            RoundedRectangle(cornerRadius: 6).fill(Color.red).frame(width: 34, height: 34)
                        } else {
                            Circle().fill(Color.red).frame(width: 64, height: 64)
                        }
                    }
                    Text(camera.isRecording ? "停止" : "录制").font(.system(size: 12)).foregroundColor(.white)
                }
            }
            .padding(.horizontal, 4)
            ToolButton(icon: "textformat.size", label: "字号大小") { showFont = true }
            ToolButton(icon: "doc.text.magnifyingglass", label: "拍摄日志", disabled: exportURL == nil) { showShare = true }
        }
        .padding(.horizontal, 8)
    }

    private var fontSheet: some View {
        VStack(spacing: 16) {
            Text("字号 \(Int(fontSize))").font(.headline)
            Slider(value: $fontSize, in: 24...48, step: 1)
            Text("AI 跟你说查不到的时候，先别信。").font(.system(size: fontSize)).foregroundColor(.white)
            Text("翻页：音量下键 / 相机控制键 = 下一页，音量上键 = 上一页；点词卡下半 = 下一页，上半 = 上一页，长按 = 回到本页开头。")
                .font(.system(size: 13)).foregroundColor(.gray)
            Toggle(isOn: $strongStabilization) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("防抖最强档")
                    Text(strongStabilization ? "走路手持用：画面更稳，视野裁得多一点" : "系统自动：视野大，适合手机架").font(.system(size: 12)).foregroundColor(.gray)
                }
            }
            .disabled(camera.isRecording)
            .onChange(of: strongStabilization) { _, v in camera.setStabilization(strong: v) }
            Text("相机 \(camera.formatLine)").font(.system(size: 12)).foregroundColor(.gray)
            Button("好") { showFont = false }
        }
        .padding(24)
        .presentationDetents([.medium])
    }

    private func setup() async {
        UIApplication.shared.isIdleTimerDisabled = true
        speech.onTranscript = { [weak engine] t in engine?.onTranscript(t) }
        camera.onTakeFinished = { [weak takes] url in
            Task { @MainActor in
                await takes?.add(url)
                if let t = takes?.takes.first(where: { $0.url == url }) { pendingTake = t }
            }
        }
        await takes.load()
        let ok = await camera.configure(strongStabilization: strongStabilization)
        guard ok else { return }
        if camera.audioViaCapture {
            let feeder = speech.feeder
            camera.relay.sink = { sb in feeder.feed(sampleBuffer: sb) }
        }
        await speech.start()
        // 兜底：相机会话 3 秒内没送出音频样本，就改用麦克风直采
        try? await Task.sleep(for: .seconds(3))
        if !camera.audioViaCapture || speech.feeder.fedSecondsTotal < 0.5 {
            print("SPEECH 相机音频喂入=\(speech.feeder.fedSecondsTotal)s，改走 AVAudioEngine 直采")
            camera.relay.sink = nil
            let tap = MicTap()
            do { try tap.start(feeder: speech.feeder); micTap = tap } catch { camera.status = "麦克风启动失败: \(error.localizedDescription)"; print("SPEECH MicTap 失败 \(error)") }
        }
    }

    private func teardown() {
        UIApplication.shared.isIdleTimerDisabled = false
        micTap?.stop()
        camera.relay.sink = nil
        Task { await speech.stop() }
    }

    private func prepareExport() {
        let md = engine.log.markdown(pageCount: engine.pageCount)
        lastLogMarkdown = md
        guard let takeURL = camera.currentTakeURL else { return }
        let url = takeURL.deletingPathExtension().appendingPathExtension("md")
        do { try md.write(to: url, atomically: true, encoding: .utf8); exportURL = url } catch { camera.status = "日志写入失败" }
    }
}

/// 词卡：靠上、窄列、深底。逐字句按状态上色，要点行加「·」。
struct PrompterCard: View {
    @ObservedObject var engine: PrompterEngine
    let page: Page
    let fontSize: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text("\(engine.pageIndex + 1)/\(engine.pageCount) · \(page.title)").font(.system(size: 12)).foregroundColor(.gray)
                Spacer()
                if let h = engine.hint {
                    Text(h).font(.system(size: 12, weight: .semibold)).foregroundColor(.orange)
                } else {
                    Text("音量键 ↓下一页 ↑上一页").font(.system(size: 11)).foregroundColor(.gray)
                }
            }
            if engine.pageIndex > 0 {
                Button { engine.prev() } label: {
                    Label("上一页", systemImage: "chevron.up").font(.system(size: 12)).foregroundColor(.white.opacity(0.7))
                }.frame(maxWidth: .infinity)
            }
            ForEach(page.items) { item in
                if item.kind == .points {
                    ForEach(item.sentences) { s in
                        Text("· " + s.text).font(.system(size: fontSize + 2, weight: .semibold)).foregroundColor(.white)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                } else {
                    item.sentences.reduce(Text("")) { acc, s in acc + Text(s.text).foregroundColor(engine.color(for: s, in: page)) }
                        .font(.system(size: fontSize))
                        .lineSpacing(fontSize * 0.3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding(16)
        .frame(width: UIScreen.main.bounds.width * 0.8, alignment: .leading)
        .background(Color.black.opacity(0.6))
        .cornerRadius(16)
        .overlay {
            VStack(spacing: 0) {
                Color.clear.contentShape(Rectangle()).onTapGesture { engine.prev() }
                Color.clear.contentShape(Rectangle()).onTapGesture { engine.next(manual: true) }
            }
            .simultaneousGesture(LongPressGesture(minimumDuration: 0.8).onEnded { _ in engine.resetPage() })
        }
        .overlay(alignment: .bottom) {
            if engine.pageIndex + 1 < engine.pageCount {
                Button { engine.next(manual: true) } label: {
                    HStack(spacing: 6) { Text("下一页"); Image(systemName: "chevron.down") }
                        .font(.system(size: 15, weight: .semibold)).foregroundColor(.black)
                        .padding(.horizontal, 18).padding(.vertical, 8)
                        .background(Color(red: 1.0, green: 0.85, blue: 0.2)).cornerRadius(20)
                }
                .offset(y: 18)
            }
        }
    }
}

/// 看一段：播放、存相册、删除。
struct TakePreview: View {
    let take: Take
    @ObservedObject var store: TakeStore
    var onShare: () -> Void
    var onClose: () -> Void
    @State private var player: AVPlayer? = nil

    var body: some View {
        VStack(spacing: 12) {
            if let p = player {
                VideoPlayer(player: p).frame(maxWidth: .infinity, maxHeight: .infinity).cornerRadius(12)
            }
            Text(String(format: "%.0f 秒 · %.0f MB · 视频 ✓ 日志 %@ · 分享会把两个一起发", take.duration, take.sizeMB, take.hasLog ? "✓" : "✗")).font(.system(size: 13)).foregroundColor(.gray)
            HStack(spacing: 24) {
                Button(role: .destructive) { player?.pause(); store.delete(take); onClose() } label: { Label("删除", systemImage: "trash") }
                Button { player?.pause(); onClose(); onShare() } label: { Label("分享", systemImage: "square.and.arrow.up") }.fontWeight(.semibold)
                Button("关闭") { player?.pause(); onClose() }
            }
            .padding(.bottom, 8)
        }
        .padding(12)
        .background(Color.black)
        .onAppear { let p = AVPlayer(url: take.url); player = p; p.play() }
        .onDisappear { player?.pause() }
    }
}

/// 底部工具按钮：图标 + 说明，整块可点。
struct ToolButton: View {
    let icon: String
    let label: String
    var disabled: Bool = false
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            VStack(spacing: 5) {
                Image(systemName: icon).font(.system(size: 22, weight: .regular))
                Text(label).font(.system(size: 12))
            }
            .foregroundColor(.white)
            .frame(width: 68, height: 60)
            .background(Color.white.opacity(0.12))
            .cornerRadius(12)
            .contentShape(Rectangle())
        }
        .disabled(disabled)
        .opacity(disabled ? 0.35 : 1)
    }
}

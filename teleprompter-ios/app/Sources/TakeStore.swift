import Foundation
import AVFoundation
import Photos
import UIKit

/// 一条录好的片段：留在 App 的 Documents/takes 里，看过满意再存相册，不要的删。
struct Take: Identifiable, Equatable {
    let id: String          // 文件名
    let url: URL
    var duration: Double
    var thumbnail: UIImage?
    var sizeMB: Double
    var createdAt: Date
    static func == (a: Take, b: Take) -> Bool { a.id == b.id }
    /// 同名日志
    var logURL: URL { url.deletingPathExtension().appendingPathExtension("md") }
    var hasLog: Bool { FileManager.default.fileExists(atPath: logURL.path) }
    var shareItems: [Any] { FileManager.default.fileExists(atPath: logURL.path) ? [url, logURL] : [url] }
}

@MainActor
final class TakeStore: ObservableObject {
    @Published var takes: [Take] = []
    @Published var message = ""

    static var dir: URL {
        let d = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("takes", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }

    static func newTakeURL() -> URL {
        let f = DateFormatter(); f.dateFormat = "yyyyMMdd-HHmmss"
        return dir.appendingPathComponent("take-\(f.string(from: Date())).mov")
    }

    func load() async {
        let files = (try? FileManager.default.contentsOfDirectory(at: Self.dir, includingPropertiesForKeys: [.creationDateKey], options: [.skipsHiddenFiles])) ?? []
        var list: [Take] = []
        for u in files where u.pathExtension.lowercased() == "mov" {
            list.append(await makeTake(u))
        }
        takes = list.sorted { $0.createdAt < $1.createdAt }
    }

    func add(_ url: URL) async {
        let t = await makeTake(url)
        takes.append(t)
    }

    private func makeTake(_ url: URL) async -> Take {
        let attrs = (try? FileManager.default.attributesOfItem(atPath: url.path)) ?? [:]
        let size = (attrs[.size] as? Int) ?? 0
        let created = (attrs[.creationDate] as? Date) ?? Date()
        let asset = AVURLAsset(url: url)
        let dur = (try? await asset.load(.duration).seconds) ?? 0
        var thumb: UIImage? = nil
        let gen = AVAssetImageGenerator(asset: asset)
        gen.appliesPreferredTrackTransform = true
        gen.maximumSize = CGSize(width: 360, height: 360)
        if let cg = try? await gen.image(at: CMTime(seconds: min(0.5, dur / 2), preferredTimescale: 600)).image {
            thumb = UIImage(cgImage: cg)
        }
        return Take(id: url.lastPathComponent, url: url, duration: dur, thumbnail: thumb, sizeMB: Double(size) / 1e6, createdAt: created)
    }

    func delete(_ take: Take) {
        try? FileManager.default.removeItem(at: take.url)
        try? FileManager.default.removeItem(at: take.logURL)
        takes.removeAll { $0.id == take.id }
        message = "已删除"
    }

    /// 把留下的片段按顺序拼成一条，原样封装（不重编码）。
    /// 合并视频 + 合并日志（按顺序拼接各段日志）
    func merge(_ list: [Take]) async throws -> [URL] {
        let mov = try await mergeVideo(list)
        var md = "# 拍摄日志（合并 \(list.count) 段）\n\n"
        for (i, t) in list.enumerated() {
            md += "# 第 \(i + 1) 段 \(t.id)\n\n"
            md += (try? String(contentsOf: t.logURL, encoding: .utf8)) ?? "（这段没有日志）\n"
            md += "\n"
        }
        let mdURL = mov.deletingPathExtension().appendingPathExtension("md")
        try md.write(to: mdURL, atomically: true, encoding: .utf8)
        return [mov, mdURL]
    }

    func mergeVideo(_ list: [Take]) async throws -> URL {
        let comp = AVMutableComposition()
        guard let vTrack = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid) else { throw NSError(domain: "merge", code: 1) }
        let aTrack = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)
        var cursor = CMTime.zero
        var transformSet = false
        for t in list {
            let asset = AVURLAsset(url: t.url)
            let dur = try await asset.load(.duration)
            if let v = try await asset.loadTracks(withMediaType: .video).first {
                try vTrack.insertTimeRange(CMTimeRange(start: .zero, duration: dur), of: v, at: cursor)
                if !transformSet { vTrack.preferredTransform = try await v.load(.preferredTransform); transformSet = true }
            }
            if let a = try await asset.loadTracks(withMediaType: .audio).first, let aTrack {
                try aTrack.insertTimeRange(CMTimeRange(start: .zero, duration: dur), of: a, at: cursor)
            }
            cursor = CMTimeAdd(cursor, dur)
        }
        let outDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("exports", isDirectory: true)
        try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
        let f = DateFormatter(); f.dateFormat = "yyyyMMdd-HHmmss"
        let out = outDir.appendingPathComponent("merged-\(f.string(from: Date())).mov")
        guard let session = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetPassthrough) else { throw NSError(domain: "merge", code: 2) }
        try await session.export(to: out, as: .mov)
        return out
    }

    func deleteAll(_ list: [Take]) { for t in list { try? FileManager.default.removeItem(at: t.url); try? FileManager.default.removeItem(at: t.logURL) }; takes.removeAll { x in list.contains(where: { $0.id == x.id }) } }

    func saveToPhotos(_ take: Take) async {
        let auth = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        guard auth == .authorized || auth == .limited else { message = "没有相册写入权限"; return }
        do {
            try await PHPhotoLibrary.shared().performChanges {
                PHAssetChangeRequest.creationRequestForAssetFromVideo(atFileURL: take.url)
            }
            try? FileManager.default.removeItem(at: take.url)
            takes.removeAll { $0.id == take.id }
            message = String(format: "已存相册 %.0f MB", take.sizeMB)
        } catch {
            message = "存相册失败: \(error.localizedDescription)"
        }
    }
}

extension URL: @retroactive Identifiable { public var id: String { absoluteString } }

// 逐帧文字识别：用 macOS 自带的 Vision 识别一个文件夹里每张 .jpg 上的文字（中英）。
// 输出一行一帧：「帧文件名 文字@x,y,宽,高 | 文字@… 」，坐标是这张图的像素，左上角为原点。
// 编译：swiftc -O ocr_scan.swift -o ocr_scan
// 一般不用直接调它，用同目录的 scan.sh。
import Vision
import AppKit
guard CommandLine.arguments.count > 1 else {
  FileHandle.standardError.write("用法：ocr_scan <放帧图的文件夹>\n".data(using: .utf8)!); exit(2)
}
let dir = CommandLine.arguments[1]
guard let all = try? FileManager.default.contentsOfDirectory(atPath: dir) else {
  FileHandle.standardError.write("打不开文件夹：\(dir)\n".data(using: .utf8)!); exit(2)
}
for f in all.filter({ $0.hasSuffix(".jpg") }).sorted() {
  guard let img = NSImage(contentsOfFile: dir + "/" + f),
        let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
  let w = Double(cg.width), h = Double(cg.height)
  let req = VNRecognizeTextRequest(); req.recognitionLanguages = ["zh-Hans", "en-US"]; req.recognitionLevel = .accurate
  try? VNImageRequestHandler(cgImage: cg).perform([req])
  let t = (req.results ?? []).compactMap { o -> String? in
    guard let s = o.topCandidates(1).first?.string else { return nil }
    let b = o.boundingBox
    return "\(s)@\(Int(b.minX * w)),\(Int((1 - b.maxY) * h)),\(Int(b.width * w)),\(Int(b.height * h))"
  }
  if !t.isEmpty { print(f, t.joined(separator: " | ")) }
}

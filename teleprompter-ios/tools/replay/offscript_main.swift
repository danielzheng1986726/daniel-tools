// 离稿测试：拿别的视频的逐字稿当「即兴说的话」，看这份稿子的任何一句会不会被误判说完。
// 窗口 150 字（离稿 30 秒左右的量），每次滑 10 字。
import Foundation

@MainActor func offscript() {
    let args = CommandLine.arguments
    let script = Script.parse(try! String(contentsOfFile: args[1], encoding: .utf8))
    let sents = script.pages.flatMap { $0.verbatimSentences }
    var hits = 0, windows = 0
    for path in args.dropFirst(2) {
        let t = Array(Script.normalize(try! String(contentsOfFile: path, encoding: .utf8)))
        var i = 0
        while i < t.count {
            let w = String(t[i..<min(t.count, i + 150)])
            windows += 1
            for s in sents {
                let short = s.norm.count < 8
                if let _ = PrompterEngine.sentenceEnd(s.norm, in: w, minCoverage: PrompterEngine.inPageCoverage) {
                    hits += 1
                    print("  误判（本页规则\(short ? "，短句" : "")）：「\(s.text)」 ← \((path as NSString).pathComponents.suffix(5).first ?? "")")
                }
            }
            i += 10
        }
    }
    print("离稿测试：\(windows) 个窗口 × \(sents.count) 句，误判 \(hits) 次")
}
MainActor.assumeIsolated { offscript() }

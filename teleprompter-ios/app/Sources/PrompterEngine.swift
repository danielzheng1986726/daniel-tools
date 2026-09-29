import Foundation
import SwiftUI

struct SentenceRecord {
    let page: Int
    let idx: Int
    let text: String
    let completedAt: TimeInterval   // 距开录秒数
    let manual: Bool                // 是手动翻页带过去的（没识别到句尾）
}

struct TakeLog {
    var start = Date()
    var end: Date? = nil
    var startPage = 0
    var manualNext = 0
    var manualPrev = 0
    var prevOnFirstPage = 0
    var autoFlips = 0
    var stabilization = ""          // 这段实际用的防抖档（CameraService 给）
    var records: [SentenceRecord] = []

    func markdown(pageCount: Int) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm"
        let dur = (end ?? Date()).timeIntervalSince(start)
        var md = "## 提词记账 \(f.string(from: start))\n\n"
        md += String(format: "- 素材时长 %.0f 秒，从第 %d 页开始，共 %d 页\n", dur, startPage + 1, pageCount)
        md += "- 自动翻页 \(autoFlips) 次，手动下一页 \(manualNext) 次，手动上一页 \(manualPrev) 次（开场页回退 \(prevOnFirstPage) 次）\n"
        if !stabilization.isEmpty { md += "- 防抖：\(stabilization)\n" }
        // 重说不在这里数（09-28 删）：App 只数得出约三分之一，「做视频」从逐字稿找更准
        md += "\n| 页 | 句 | 说完时刻 s | 备注 |\n|---|---|---|---|\n"
        for r in records {
            let note = r.manual ? "手动带过" : ""
            md += String(format: "| %d | %@ | %.1f | %@ |\n", r.page + 1, r.text.replacingOccurrences(of: "|", with: "｜"), r.completedAt, note)
        }
        return md
    }
}

/// 翻页与匹配逻辑。原则：屏幕只在句尾或页尾动；识别不确定就停住等手动；自动永不后退。
@MainActor
final class PrompterEngine: ObservableObject {
    @Published var script: Script
    @Published var pageIndex = 0
    @Published var currentSentenceIdx = 0
    @Published var hint: String? = nil
    @Published var log = TakeLog()
    @Published var inTake = false

    /// 时钟可替换：重放测试（tools/replay）用虚拟时间
    var now: () -> Date = Date.init
    private(set) var lastNorm = ""
    private var pageStartOffset = 0        // 本页显示时识别文本的长度
    private(set) var sentenceSearchOffset = 0   // 当前句从这个位置往后找
    private var lastChangeAt = Date()
    private var watchdog: Timer?
    private let stallSeconds: TimeInterval = 8

    init(script: Script) {
        self.script = script
        watchdog = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.checkStall() }
        }
    }

    var currentPage: Page? { script.pages.indices.contains(pageIndex) ? script.pages[pageIndex] : nil }
    var pageCount: Int { script.pages.count }

    func color(for sentence: Sentence, in page: Page) -> Color {
        guard let pos = page.verbatimSentences.firstIndex(where: { $0.id == sentence.id }) else { return .white }
        if pos < currentSentenceIdx { return Color.white.opacity(0.45) }
        if pos == currentSentenceIdx { return Color(red: 1.0, green: 0.85, blue: 0.2) }
        return .white
    }

    // MARK: 手动

    func next(manual: Bool) {
        guard pageIndex + 1 < pageCount else { hint = "已是最后一页"; return }
        if manual {
            log.manualNext += 1
            // 没识别到句尾就翻走的句子，记成手动带过
            if let page = currentPage {
                for (i, s) in page.verbatimSentences.enumerated() where i >= currentSentenceIdx {
                    log.records.append(SentenceRecord(page: pageIndex, idx: i, text: s.text, completedAt: sinceStart(), manual: true))
                }
            }
        } else {
            log.autoFlips += 1
        }
        show(page: pageIndex + 1)
    }

    func prev() {
        log.manualPrev += 1
        if pageIndex == 0 { log.prevOnFirstPage += 1 }
        show(page: max(0, pageIndex - 1))
    }

    func resetPage() { show(page: pageIndex) }

    func goToStart() { show(page: 0) }

    func returnTo(page: Int) { show(page: min(max(0, page), max(0, pageCount - 1))) }

    private func show(page: Int) {
        print("ENGINE 显示页 \(page + 1)/\(pageCount) 识别文本长度 \(lastNorm.count)")
        pageIndex = page
        currentSentenceIdx = 0
        pageStartOffset = lastNorm.count
        sentenceSearchOffset = lastNorm.count
        lastChangeAt = now()
        hint = (currentPage?.hasVerbatim ?? true) ? nil : "要点页：说完按音量键翻页"
    }

    // MARK: 记账

    func startTake() {
        log = TakeLog(); log.start = now(); log.startPage = pageIndex
        inTake = true
        resetPage()
    }

    func endTake() {
        log.end = now()
        inTake = false
    }

    private func sinceStart() -> TimeInterval { now().timeIntervalSince(log.start) }

    // MARK: 语音

    func onTranscript(_ raw: String) {
        let n = Script.normalize(raw)
        guard n != lastNorm else { return }
        // 识别器会回头改写还没定稿的文字（长度会变）。偏移只在没被改动的前缀里才可信，否则退回去，免得把新说的字挡在窗口外
        let stable = zip(n, lastNorm).prefix { $0 == $1 }.count
        pageStartOffset = min(pageStartOffset, stable)
        sentenceSearchOffset = min(sentenceSearchOffset, stable)
        lastNorm = n
        lastChangeAt = now()
        if hint != nil, currentPage?.hasVerbatim ?? false { hint = nil }
        evaluate()
    }

    private func evaluate() {
        guard let page = currentPage else { return }
        let vs = page.verbatimSentences
        var guardCount = 0
        while currentSentenceIdx < vs.count, guardCount < 10 {
            guardCount += 1
            let offset = min(sentenceSearchOffset, lastNorm.count)
            let recent = String(lastNorm.dropFirst(offset))
            let cur = vs[currentSentenceIdx]
            if let end = Self.sentenceEnd(cur.norm, in: recent, minCoverage: Self.inPageCoverage) {
                complete(sentenceIdx: currentSentenceIdx, in: page, endOffset: offset + end, manual: false)
                continue
            }
            // 本页后面的某一句说完了：中间的记成带过，跳到那一句之后
            var jumped = false
            for k in (currentSentenceIdx + 1)..<vs.count {
                if let end = Self.sentenceEnd(vs[k].norm, in: recent, minCoverage: Self.inPageCoverage) {
                    for m in currentSentenceIdx..<k {
                        log.records.append(SentenceRecord(page: pageIndex, idx: m, text: vs[m].text, completedAt: sinceStart(), manual: true))
                    }
                    currentSentenceIdx = k
                    complete(sentenceIdx: k, in: page, endOffset: offset + end, manual: false)
                    jumped = true
                    break
                }
            }
            if jumped { continue }
            // 往后两页内的某一句说完了（尾巴要多对两个字才算）：翻过去
            if catchUpAcrossPages(recent: recent, offset: offset) { continue }
            break
        }
    }

    /// 高亮落后于人时的追赶：只往前；跨页比本页要求更严（整句覆盖率更高，短句不追）。
    private func catchUpAcrossPages(recent: String, offset: Int) -> Bool {
        guard pageIndex + 1 < pageCount else { return false }
        for p in (pageIndex + 1)...min(pageIndex + 2, pageCount - 1) {
            let vs = script.pages[p].verbatimSentences
            for (k, sent) in vs.enumerated() {
                guard sent.norm.count >= 8, let end = Self.sentenceEnd(sent.norm, in: recent, minCoverage: Self.crossPageCoverage) else { continue }
                print("ENGINE 追赶：页\(pageIndex + 1) → 页\(p + 1) 句\(k + 1)")
                if let page = currentPage {
                    for m in currentSentenceIdx..<page.verbatimSentences.count {
                        log.records.append(SentenceRecord(page: pageIndex, idx: m, text: page.verbatimSentences[m].text, completedAt: sinceStart(), manual: true))
                    }
                }
                log.autoFlips += 1
                show(page: p)
                currentSentenceIdx = k
                complete(sentenceIdx: k, in: script.pages[p], endOffset: offset + end, manual: false)
                return true
            }
        }
        return false
    }

    private func complete(sentenceIdx: Int, in page: Page, endOffset: Int, manual: Bool) {
        let vs = page.verbatimSentences
        let s = vs[sentenceIdx]
        print("ENGINE 句完成 页\(pageIndex + 1) 句\(sentenceIdx + 1)/\(vs.count) 「\(s.text.prefix(20))」")
        log.records.append(SentenceRecord(page: pageIndex, idx: sentenceIdx, text: s.text, completedAt: sinceStart(), manual: manual))
        sentenceSearchOffset = endOffset
        currentSentenceIdx = sentenceIdx + 1
        if currentSentenceIdx >= vs.count {
            // 页尾：最后一个逐字句说完就翻页；如果后面还跟着要点条目，也翻（要点在下一页看不到，但要点段本来就是自由说）
            if pageIndex + 1 < pageCount { next(manual: false) } else { hint = "稿子念完了" }
        }
    }

    private func checkStall() {
        guard inTake, let page = currentPage, page.hasVerbatim, currentSentenceIdx < page.verbatimSentences.count else { return }
        if now().timeIntervalSince(lastChangeAt) > stallSeconds, hint == nil {
            print("ENGINE 停滞 \(Int(stallSeconds))s 无新识别文本，当前页 \(pageIndex + 1) 句 \(currentSentenceIdx + 1)，文本尾「\(lastNorm.suffix(20))」")
            hint = "识别没跟上，按音量键翻页"
        }
    }

    // MARK: 匹配工具


    /// 在 text 里近似找 pattern（编辑距离 ≤ maxDist：认错、漏字、多字都算一次），返回匹配结束位置。
    static func approxFind(_ pattern: String, in text: String, maxDist: Int) -> Int? {
        let p = Array(pattern), t = Array(text)
        guard !p.isEmpty, !t.isEmpty else { return nil }
        var prev = Array(0...p.count)
        var cur = [Int](repeating: 0, count: p.count + 1)
        for j in 1...t.count {
            cur[0] = 0
            for i in 1...p.count {
                let sub = prev[i - 1] + (p[i - 1] == t[j - 1] ? 0 : 1)
                cur[i] = min(prev[i] + 1, cur[i - 1] + 1, sub)
            }
            if cur[p.count] <= maxDist { return j }
            swap(&prev, &cur)
        }
        return nil
    }

    static let inPageCoverage = 0.7
    static let crossPageCoverage = 0.8

    /// 这句说完了没有。Daniel 念稿会在句尾顺口加字改字（「没有读完」「读不下来」「作废掉了」「读到哪里了」），
    /// 所以不要求尾巴原样对上，而是两条同时满足：
    /// ① 结尾：句子最后 4 个字至少 3 个按顺序出现在一小段里（最多 7 个字宽），且这一小段以其中最后两个字之一收尾；
    /// ② 整句：句子至少 minCoverage 的字按顺序说到了（最长公共子序列）。
    /// 两条都满足才算，返回说完的位置；短句（少于 6 字）退回整句近似匹配。09-28 第七支重放定的规则，见 tools/replay。
    static func sentenceEnd(_ s: String, in text: String, minCoverage: Double) -> Int? {
        let p = Array(s), t = Array(text)
        guard !p.isEmpty, !t.isEmpty else { return nil }
        if p.count < 6 { return approxFind(s, in: text, maxDist: p.count >= 4 ? 1 : 0) }
        let tail = Array(p.suffix(4))
        let need = Int((Double(p.count) * minCoverage).rounded(.up))
        // 整句 LCS 按文本位置逐列推进：lcsAt[j] = s 与 t[0..<j+1] 的最长公共子序列长度
        var row = [Int](repeating: 0, count: p.count + 1)
        for j in 0..<t.count {
            var prevDiag = 0
            for i in 1...p.count {
                let old = row[i]
                row[i] = p[i - 1] == t[j] ? prevDiag + 1 : max(row[i], row[i - 1])
                prevDiag = old
            }
            guard row[p.count] >= need, t[j] == tail[3] || t[j] == tail[2] else { continue }
            let window = Array(t[max(0, j - 6)...j])
            if lcs(tail, window) >= 3 { return j + 1 }
        }
        return nil
    }

    static func lcs(_ a: [Character], _ b: [Character]) -> Int {
        var row = [Int](repeating: 0, count: a.count + 1)
        for c in b {
            var prevDiag = 0
            for i in 1...max(1, a.count) where !a.isEmpty {
                let old = row[i]
                row[i] = a[i - 1] == c ? prevDiag + 1 : max(row[i], row[i - 1])
                prevDiag = old
            }
        }
        return row[a.count]
    }

}

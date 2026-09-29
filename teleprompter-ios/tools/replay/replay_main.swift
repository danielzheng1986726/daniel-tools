// 重放测试：把 record_transcript 录下的识别结果按时间喂给 App 的 PrompterEngine（同一份源码），
// 模拟一个「翻页没动就在句尾后 2.5 秒按音量键」的人，数自动翻页、手动翻页、提前翻页。
// 编译：见 tools/replay/README.md
import Foundation

struct Event { let t: Double; let isFinal: Bool; let text: String }

func loadEvents(_ path: String) -> [Event] {
    let raw = try! String(contentsOfFile: path, encoding: .utf8)
    return raw.split(separator: "\n").compactMap { line in
        guard let d = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any] else { return nil }
        return Event(t: d["t"] as! Double, isFinal: d["final"] as! Bool, text: d["text"] as! String)
    }.sorted { $0.t < $1.t }
}

/// 参考逐字稿（另一个 ASR 的字级时间戳，tsv: start_ms end_ms text），用来定每页最后一句真实说完的时刻。
func loadTruth(_ path: String) -> (text: [Character], end: [Double]) {
    var chars: [Character] = [], ends: [Double] = []
    for line in try! String(contentsOfFile: path, encoding: .utf8).split(separator: "\n").dropFirst() {
        let f = line.split(separator: "\t", omittingEmptySubsequences: false)
        guard f.count >= 3, let e = Double(f[1]) else { continue }
        for c in Script.normalize(String(f[2])) { chars.append(c); ends.append(e / 1000) }
    }
    return (chars, ends)
}

func endTime(of phrase: String, in truth: (text: [Character], end: [Double]), after: Double) -> Double {
    let p = Array(phrase)
    for i in 0...(truth.text.count - p.count) where truth.end[i] > after && Array(truth.text[i..<(i + p.count)]) == p {
        return truth.end[i + p.count - 1]
    }
    fatalError("参考稿里找不到「\(phrase)」")
}

let args = CommandLine.arguments
guard args.count == 5 else { print("用法: replay script.txt events.jsonl truth.tsv page_ends.txt"); exit(2) }
let script = Script.parse(try! String(contentsOfFile: args[1], encoding: .utf8))
let events = loadEvents(args[2])
let truth = loadTruth(args[3])
// page_ends.txt：每行一页，写这一页最后一句「实际说出来」的结尾几个字；take 分界写成「TAKE 秒数」
var pageEnds: [Double] = []
var takeBreaks: [Double] = []
var lastT = 0.0
for line in try! String(contentsOfFile: args[4], encoding: .utf8).split(separator: "\n") where !line.hasPrefix("#") {
    if line.hasPrefix("TAKE ") { takeBreaks.append(Double(line.dropFirst(5))!); continue }
    lastT = endTime(of: Script.normalize(String(line)), in: truth, after: lastT)
    pageEnds.append(lastT)
}
precondition(pageEnds.count == script.pages.count, "页数对不上：稿子 \(script.pages.count) 页，page_ends \(pageEnds.count) 行")

@MainActor func run() {
    let base = Date(timeIntervalSince1970: 0)
    var clock = 0.0
    let engine = PrompterEngine(script: script)
    engine.now = { base.addingTimeInterval(clock) }
    engine.startTake()

    var finalText = "", volatileText = ""
    var flips: [(t: Double, from: Int, to: Int, auto: Bool)] = []
    var driftEvents = 0, hiddenChars = 0
    var takes: [TakeLog] = []
    let pressDelay = 2.5

    @MainActor func observe(_ before: Int, auto: Bool) {
        if engine.pageIndex != before { flips.append((clock, before, engine.pageIndex, auto)) }
    }
    @MainActor func pressIfDue(until t: Double) {
        // 人：当前页最后一句说完 2.5 秒还没翻，就按一下
        while engine.pageIndex + 1 < script.pages.count, pageEnds[engine.pageIndex] + pressDelay <= t {
            clock = pageEnds[engine.pageIndex] + pressDelay
            let b = engine.pageIndex
            engine.next(manual: true)
            observe(b, auto: false)
        }
    }
    var breaks = takeBreaks
    for e in events {
        while let tb = breaks.first, tb <= e.t {
            pressIfDue(until: tb); clock = tb
            engine.endTake(); takes.append(engine.log); engine.startTake(); breaks.removeFirst()
        }
        pressIfDue(until: e.t)
        clock = e.t
        let oldNorm = engine.lastNorm, off = engine.sentenceSearchOffset
        if e.isFinal { finalText += e.text; volatileText = "" } else { volatileText = e.text }
        let b = engine.pageIndex
        engine.onTranscript(finalText + volatileText)
        observe(b, auto: true)
        // 偏移漂移：识别器改写了偏移之前的文字，偏移还指着老位置
        let newNorm = Script.normalize(finalText + volatileText)
        if off > 0, off <= oldNorm.count, newNorm.prefix(off) != oldNorm.prefix(off) {
            driftEvents += 1
            let common = zip(newNorm, oldNorm.prefix(off)).prefix { $0 == $1 }.count
            hiddenChars += max(0, off - common)
        }
    }
    pressIfDue(until: events.last!.t + 10)
    engine.endTake(); takes.append(engine.log)

    let autoN = flips.filter { $0.auto }.count, manualN = flips.filter { !$0.auto }.count
    let premature = flips.filter { $0.auto && $0.t < pageEnds[$0.from] - 0.2 }
    print("翻页：自动 \(autoN)，手动 \(manualN)，提前翻页 \(premature.count)")
    for f in flips {
        let lag = f.t - pageEnds[f.from]
        print(String(format: "  %6.1fs 页%d→%d %@  （这页说完后 %+.1fs）", f.t, f.from + 1, f.to + 1, f.auto ? "自动" : "手动", lag))
    }
    let recs = takes.flatMap { $0.records }
    print("句子：识别到 \(recs.filter { !$0.manual }.count)/\(recs.count)")
    for r in recs where r.manual { print("  没认出：页\(r.page + 1) 「\(r.text)」") }
    print("识别器改写了已查过的文字：\(driftEvents) 次（共 \(hiddenChars) 字；引擎会把起点退回，不再挡字）")
}

/// 压力测试：① 每句一个字一个字说，最后两个字出来前不许判「说完」；② 一句的原文不许被判成本页后面或后两页的某句说完。
@MainActor func selfTest() {
    var early = 0, cross = 0
    let pages = script.pages.map { $0.verbatimSentences }
    for (pi, vs) in pages.enumerated() {
        for (si, s) in vs.enumerated() {
            let prev = si > 0 ? vs[si - 1].norm : (pi > 0 ? pages[pi - 1].last?.norm ?? "" : "")
            let p = Array(s.norm)
            for k in 0..<max(0, p.count - 2) where PrompterEngine.sentenceEnd(s.norm, in: prev + String(p.prefix(k)), minCoverage: PrompterEngine.inPageCoverage) != nil {
                early += 1; print("  提前判完：页\(pi + 1) 「\(s.text)」 只说到「\(String(p.prefix(k)))」"); break
            }
            var later: [(Int, Sentence, Double)] = vs[(si + 1)...].map { (pi, $0, PrompterEngine.inPageCoverage) }
            for q in (pi + 1)..<min(pi + 3, pages.count) { later += pages[q].filter { $0.norm.count >= 8 }.map { (q, $0, PrompterEngine.crossPageCoverage) } }
            for (q, o, cov) in later where PrompterEngine.sentenceEnd(o.norm, in: prev + s.norm, minCoverage: cov) != nil {
                cross += 1; print("  误跳：说「\(s.text)」被当成页\(q + 1)「\(o.text)」")
            }
        }
    }
    print("压力测试：提前判完 \(early) 句，误跳 \(cross) 处")
}

MainActor.assumeIsolated { selfTest(); run() }

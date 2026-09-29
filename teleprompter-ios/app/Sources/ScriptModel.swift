import Foundation

/// 稿子模型。页 = 一次翻页看到的内容（对应稿子模板里的「开场」「段 1」「论点句」「结尾」）。
/// 页里有若干条目，条目分两种：逐字（照念，语音匹配）和要点（自由说，不匹配）。

enum ItemKind { case verbatim, points }

struct Sentence: Identifiable, Hashable {
    let id: Int          // 页内逐字句序号（要点行也用它当行号）
    let text: String     // 显示用，带标点
    let norm: String     // 匹配用：去标点空格，小写
}

struct PageItem: Identifiable {
    let id: Int
    let kind: ItemKind
    let sentences: [Sentence]
}

struct Page: Identifiable {
    let id: Int
    let title: String
    let items: [PageItem]
    var verbatimSentences: [Sentence] { items.filter { $0.kind == .verbatim }.flatMap { $0.sentences } }
    var hasVerbatim: Bool { !verbatimSentences.isEmpty }
}

struct Script {
    var pages: [Page]
    var isEmpty: Bool { pages.isEmpty }

    /// 匹配用归一化：只留汉字、字母、数字；字母小写。
    static func normalize(_ s: String) -> String {
        var out = ""
        for u in s.lowercased().unicodeScalars where CharacterSet.alphanumerics.contains(u) { out.unicodeScalars.append(u) }
        return out
    }

    /// 按句号、问号、叹号、分号、换行切句，标点留在句尾。
    static func splitSentences(_ text: String) -> [String] {
        var out: [String] = []
        var cur = ""
        for ch in text {
            cur.append(ch)
            if "。！？!?；;\n".contains(ch) {
                let t = cur.trimmingCharacters(in: .whitespacesAndNewlines)
                if !t.isEmpty { out.append(t) }
                cur = ""
            }
        }
        let t = cur.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty { out.append(t) }
        return out
    }

    static func parse(_ raw: String) -> Script {
        // 去掉 Markdown 标题行
        let cleaned = raw.split(separator: "\n", omittingEmptySubsequences: false)
            .filter { !$0.trimmingCharacters(in: .whitespaces).hasPrefix("#") }
            .joined(separator: "\n")
        let tagRegex = try! NSRegularExpression(pattern: "【([^】]*)】")
        let ns = cleaned as NSString
        let matches = tagRegex.matches(in: cleaned, range: NSRange(location: 0, length: ns.length))
        if matches.isEmpty { return parsePlain(cleaned) }

        // 有标记：按「·」前面的名字分页，后面的「逐字/要点」定条目类型
        var pages: [Page] = []
        var curTitle = ""
        var curItems: [PageItem] = []
        var itemSeq = 0
        func flush() {
            if !curItems.isEmpty { pages.append(Page(id: pages.count, title: curTitle, items: curItems)) }
            curItems = []
        }
        for (i, m) in matches.enumerated() {
            let label = ns.substring(with: m.range(at: 1))
            let bodyStart = m.range.location + m.range.length
            let bodyEnd = i + 1 < matches.count ? matches[i + 1].range.location : ns.length
            let body = ns.substring(with: NSRange(location: bodyStart, length: bodyEnd - bodyStart)).trimmingCharacters(in: .whitespacesAndNewlines)
            let parts = label.components(separatedBy: CharacterSet(charactersIn: "·・.:："))
            let title = parts.first?.trimmingCharacters(in: .whitespaces) ?? label
            let kind: ItemKind = label.contains("要点") ? .points : .verbatim
            if title != curTitle { flush(); curTitle = title }
            if body.isEmpty { continue }
            let lines: [String]
            if kind == .points {
                lines = body.split(separator: "\n").map { String($0).trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
            } else {
                lines = splitSentences(body)
            }
            let base = curItems.reduce(0) { $0 + $1.sentences.count }
            let sents = lines.enumerated().map { Sentence(id: base + $0.offset, text: $0.element, norm: normalize($0.element)) }
            curItems.append(PageItem(id: itemSeq, kind: kind, sentences: sents)); itemSeq += 1
        }
        flush()
        return Script(pages: pages)
    }

    /// 没有标记的纯文本：空行分段，每段一页；超过约 110 字的段按句拆成多页。
    static func parsePlain(_ text: String) -> Script {
        let paras = text.components(separatedBy: "\n\n").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        var pages: [Page] = []
        for p in paras {
            let sents = splitSentences(p)
            var chunk: [String] = []
            var chunkLen = 0
            func emit() {
                guard !chunk.isEmpty else { return }
                let ss = chunk.enumerated().map { Sentence(id: $0.offset, text: $0.element, norm: normalize($0.element)) }
                pages.append(Page(id: pages.count, title: "第 \(pages.count + 1) 页", items: [PageItem(id: 0, kind: .verbatim, sentences: ss)]))
                chunk = []; chunkLen = 0
            }
            for s in sents {
                let n = normalize(s).count
                if chunkLen + n > 110 && !chunk.isEmpty { emit() }
                chunk.append(s); chunkLen += n
            }
            emit()
        }
        return Script(pages: pages)
    }
}

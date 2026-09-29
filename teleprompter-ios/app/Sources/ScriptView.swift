import SwiftUI
import UIKit

/// 稿子页：粘贴、改、看分页预览，然后进提词。
struct ScriptView: View {
    @Binding var scriptRaw: String
    var onStart: () -> Void
    @State private var pasteNote = ""

    private var script: Script { Script.parse(scriptRaw) }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                TextEditor(text: $scriptRaw)
                    .font(.system(size: 15))
                    .scrollContentBackground(.hidden)
                    .background(Color(white: 0.1))
                    .foregroundColor(.white)
                    .frame(maxHeight: 260)
                    .overlay(alignment: .topLeading) {
                        if scriptRaw.isEmpty {
                            Text("在 Mac 上复制稿子，这里点右上「粘贴」。\n认「【段 1·逐字】」「【段 1·要点】」这种标记；没有标记就按空行分页。")
                                .font(.system(size: 14)).foregroundColor(.gray).padding(8).allowsHitTesting(false)
                        }
                    }
                Divider()
                List {
                    Section("分页预览（\(script.pages.count) 页）") {
                        ForEach(script.pages) { page in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(page.title).font(.headline)
                                ForEach(page.items) { item in
                                    ForEach(item.sentences) { s in
                                        Text((item.kind == .points ? "· " : "") + s.text)
                                            .font(.system(size: 14, weight: item.kind == .points ? .semibold : .regular))
                                            .foregroundColor(item.kind == .points ? .primary : .secondary)
                                    }
                                }
                            }.padding(.vertical, 2)
                        }
                    }
                }
                .listStyle(.plain)
            }
            .background(Color.black)
            .navigationTitle("稿子")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("粘贴") {
                        if let s = UIPasteboard.general.string, !s.isEmpty { scriptRaw = s; pasteNote = "" } else { pasteNote = "剪贴板里没有文字" }
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("开始提词") { onStart() }.disabled(script.isEmpty).fontWeight(.semibold)
                }
            }
            .overlay(alignment: .bottom) {
                if !pasteNote.isEmpty { Text(pasteNote).font(.caption).foregroundColor(.orange).padding(8) }
            }
        }
        .preferredColorScheme(.dark)
    }
}

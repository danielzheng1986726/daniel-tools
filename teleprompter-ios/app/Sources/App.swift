import SwiftUI

@main
struct PrompterApp: App {
    var body: some Scene {
        WindowGroup { RootView() }
    }
}

struct RootView: View {
    @AppStorage("scriptRaw") private var scriptRaw = ""
    @State private var showPrompter = false

    var body: some View {
        if showPrompter {
            PrompterView(script: Script.parse(scriptRaw), onExit: { showPrompter = false })
        } else {
            ScriptView(scriptRaw: $scriptRaw, onStart: { showPrompter = true })
        }
    }
}

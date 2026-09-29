import SwiftUI

@main
struct PrompterSpikeApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

struct ContentView: View {
    var body: some View {
        TabView {
            CameraFormatsView()
                .tabItem { Label("相机", systemImage: "camera") }
            SpeechView()
                .tabItem { Label("语音", systemImage: "waveform") }
        }
    }
}

import SwiftUI

@main
struct LifeWatchApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    var body: some View {
        TabView {
            DashboardView()
            RoutinesView()
            HabitsView()
            GoalsView()
            SettingsView()
        }
        .tabViewStyle(.verticalPage)
    }
}

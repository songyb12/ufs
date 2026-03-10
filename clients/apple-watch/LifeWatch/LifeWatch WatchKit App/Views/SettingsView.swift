import SwiftUI

struct SettingsView: View {
    @AppStorage("serverURL") private var serverURL = "http://192.168.0.100:8004"
    @State private var isConnected: Bool?
    @State private var isTesting = false

    var body: some View {
        List {
            Section("서버") {
                TextField("서버 URL", text: $serverURL)
                    .font(.caption2)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)

                Button(action: testConnection) {
                    HStack {
                        if isTesting {
                            ProgressView()
                                .frame(width: 16, height: 16)
                        } else {
                            Image(systemName: connectionIcon)
                                .foregroundColor(connectionColor)
                        }
                        Text("연결 테스트")
                            .font(.caption)
                    }
                }
                .disabled(isTesting)
            }

            Section("정보") {
                HStack {
                    Text("버전")
                        .font(.caption)
                    Spacer()
                    Text("1.0.0")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                HStack {
                    Text("서비스")
                        .font(.caption)
                    Spacer()
                    Text("Life-Master")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .navigationTitle("설정")
    }

    private var connectionIcon: String {
        guard let connected = isConnected else { return "wifi.slash" }
        return connected ? "checkmark.circle.fill" : "xmark.circle.fill"
    }

    private var connectionColor: Color {
        guard let connected = isConnected else { return .gray }
        return connected ? .green : .red
    }

    private func testConnection() {
        isTesting = true
        isConnected = nil
        Task {
            do {
                _ = try await APIClient.shared.fetchDashboard()
                isConnected = true
            } catch {
                isConnected = false
            }
            isTesting = false
        }
    }
}

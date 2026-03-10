import SwiftUI

struct DashboardView: View {
    @State private var dashboard: DashboardData?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, minHeight: 100)
                } else if let error = errorMessage {
                    VStack(spacing: 8) {
                        Image(systemName: "wifi.slash")
                            .font(.title2)
                            .foregroundColor(.red)
                        Text(error)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Button("재시도") { Task { await loadDashboard() } }
                            .font(.caption)
                    }
                } else if let data = dashboard {
                    // 루틴 진행률
                    SummaryCard(
                        icon: "checkmark.circle.fill",
                        title: "루틴",
                        value: "\(data.routines.completed)/\(data.routines.total)",
                        progress: data.routines.total > 0
                            ? Double(data.routines.completed) / Double(data.routines.total)
                            : 0,
                        color: .blue
                    )

                    // 습관 기록
                    SummaryCard(
                        icon: "flame.fill",
                        title: "습관",
                        value: "\(data.habits.logged)/\(data.habits.total)",
                        progress: data.habits.total > 0
                            ? Double(data.habits.logged) / Double(data.habits.total)
                            : 0,
                        color: .orange
                    )

                    // 목표
                    HStack {
                        Image(systemName: "target")
                            .foregroundColor(.green)
                        Text("활성 목표")
                            .font(.caption)
                        Spacer()
                        Text("\(data.goals.active)개")
                            .font(.headline)
                            .foregroundColor(.green)
                    }
                    .padding(.horizontal, 4)

                    // 다음 일정
                    if let next = data.schedule?.nextBlock {
                        HStack {
                            Image(systemName: "clock.fill")
                                .foregroundColor(.purple)
                            VStack(alignment: .leading) {
                                Text("다음")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                                Text(next.title)
                                    .font(.caption)
                                    .lineLimit(1)
                            }
                            Spacer()
                            Text(next.startTime)
                                .font(.caption)
                                .monospacedDigit()
                        }
                        .padding(.horizontal, 4)
                    }
                }
            }
            .padding(.vertical, 4)
        }
        .navigationTitle("오늘")
        .task { await loadDashboard() }
    }

    private func loadDashboard() async {
        isLoading = true
        errorMessage = nil
        do {
            dashboard = try await APIClient.shared.fetchDashboard()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

// MARK: - Summary Card

struct SummaryCard: View {
    let icon: String
    let title: String
    let value: String
    let progress: Double
    let color: Color

    var body: some View {
        VStack(spacing: 6) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                Text(title)
                    .font(.caption)
                Spacer()
                Text(value)
                    .font(.headline)
                    .monospacedDigit()
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(color.opacity(0.2))
                        .frame(height: 6)
                    RoundedRectangle(cornerRadius: 3)
                        .fill(color)
                        .frame(width: geo.size.width * min(progress, 1.0), height: 6)
                }
            }
            .frame(height: 6)
        }
        .padding(.horizontal, 4)
    }
}

import SwiftUI

struct GoalsView: View {
    @State private var goals: [Goal] = []
    @State private var isLoading = true

    var body: some View {
        List {
            if isLoading {
                ProgressView()
            } else if goals.isEmpty {
                Text("활성 목표 없음")
                    .foregroundColor(.secondary)
                    .font(.caption)
            } else {
                ForEach(goals) { goal in
                    GoalRow(goal: goal)
                }
            }
        }
        .navigationTitle("목표")
        .task { await loadGoals() }
    }

    private func loadGoals() async {
        do {
            goals = try await APIClient.shared.fetchGoals()
        } catch {
            // 에러 시 빈 목록
        }
        isLoading = false
    }
}

struct GoalRow: View {
    let goal: Goal

    private var deadlineColor: Color {
        guard let days = goal.daysRemaining else { return .secondary }
        if days <= 0 { return .red }
        if days <= 7 { return .orange }
        return .secondary
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(goal.title)
                    .font(.caption)
                    .lineLimit(2)
                Spacer()
                Text("\(goal.progressPercent)%")
                    .font(.caption2)
                    .monospacedDigit()
                    .foregroundColor(goal.progress >= 1.0 ? .green : .primary)
            }

            // 진행 바
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.green.opacity(0.2))
                        .frame(height: 5)
                    RoundedRectangle(cornerRadius: 3)
                        .fill(goal.progress >= 1.0 ? Color.green : Color.blue)
                        .frame(width: geo.size.width * min(goal.progress, 1.0), height: 5)
                }
            }
            .frame(height: 5)

            // 마감일
            if let days = goal.daysRemaining {
                HStack {
                    Image(systemName: "calendar")
                        .font(.system(size: 9))
                    Text(days <= 0 ? "마감 지남" : "D-\(days)")
                        .font(.system(size: 10))
                }
                .foregroundColor(deadlineColor)
            }
        }
        .padding(.vertical, 2)
    }
}

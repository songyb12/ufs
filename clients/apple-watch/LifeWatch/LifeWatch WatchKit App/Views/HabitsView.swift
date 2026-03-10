import SwiftUI

struct HabitsView: View {
    @State private var habits: [HabitOverviewItem] = []
    @State private var isLoading = true

    var body: some View {
        List {
            if isLoading {
                ProgressView()
            } else if habits.isEmpty {
                Text("등록된 습관 없음")
                    .foregroundColor(.secondary)
                    .font(.caption)
            } else {
                ForEach(habits) { item in
                    HabitRow(item: item, onIncrement: { incrementHabit(item) })
                }
            }
        }
        .navigationTitle("습관")
        .task { await loadHabits() }
    }

    private func loadHabits() async {
        do {
            habits = try await APIClient.shared.fetchHabitsOverview()
        } catch {
            // 에러 시 빈 목록
        }
        isLoading = false
    }

    private func incrementHabit(_ item: HabitOverviewItem) {
        Task {
            do {
                try await APIClient.shared.incrementHabit(id: item.habit.id)
                await loadHabits()
            } catch {
                // 실패 시 유지
            }
        }
    }
}

struct HabitRow: View {
    let item: HabitOverviewItem
    let onIncrement: () -> Void

    private var todayProgress: Double {
        guard item.habit.targetValue > 0 else { return 0 }
        return (item.todayValue ?? 0) / item.habit.targetValue
    }

    private var streakText: String {
        let streak = item.streak.currentStreak
        return streak > 0 ? "\(streak)일 연속" : "시작하세요"
    }

    var body: some View {
        Button(action: onIncrement) {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(item.habit.name)
                        .font(.caption)
                        .lineLimit(1)
                    Spacer()
                    // 스트릭 배지
                    if item.streak.currentStreak > 0 {
                        HStack(spacing: 2) {
                            Image(systemName: "flame.fill")
                                .font(.caption2)
                                .foregroundColor(.orange)
                            Text("\(item.streak.currentStreak)")
                                .font(.caption2)
                                .monospacedDigit()
                        }
                    }
                }

                HStack(spacing: 4) {
                    // 진행 바
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(Color.orange.opacity(0.2))
                                .frame(height: 4)
                            RoundedRectangle(cornerRadius: 2)
                                .fill(todayProgress >= 1.0 ? Color.green : Color.orange)
                                .frame(width: geo.size.width * min(todayProgress, 1.0), height: 4)
                        }
                    }
                    .frame(height: 4)

                    Text("\(Int(item.todayValue ?? 0))/\(Int(item.habit.targetValue))\(item.habit.unit)")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                        .monospacedDigit()
                }
            }
        }
        .buttonStyle(.plain)
    }
}

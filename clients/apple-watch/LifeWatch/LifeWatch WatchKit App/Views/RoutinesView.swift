import SwiftUI

struct RoutinesView: View {
    @State private var routines: [Routine] = []
    @State private var checkedIds: Set<Int> = []
    @State private var isLoading = true

    var body: some View {
        List {
            if isLoading {
                ProgressView()
            } else if routines.isEmpty {
                Text("오늘 루틴 없음")
                    .foregroundColor(.secondary)
                    .font(.caption)
            } else {
                ForEach(groupedByTimeSlot, id: \.0) { slot, items in
                    Section(header: Text(slot).font(.caption2)) {
                        ForEach(items) { routine in
                            RoutineRow(
                                routine: routine,
                                isDone: checkedIds.contains(routine.id),
                                onToggle: { toggleRoutine(routine) }
                            )
                        }
                    }
                }
            }
        }
        .navigationTitle("루틴")
        .task { await loadRoutines() }
    }

    private var groupedByTimeSlot: [(String, [Routine])] {
        let order = ["MORNING": 0, "AFTERNOON": 1, "EVENING": 2, "FLEXIBLE": 3]
        let grouped = Dictionary(grouping: routines) { $0.timeSlot }
        return grouped.sorted { (order[$0.key] ?? 4) < (order[$1.key] ?? 4) }
            .map { ($0.key == "MORNING" ? "오전" :
                    $0.key == "AFTERNOON" ? "오후" :
                    $0.key == "EVENING" ? "저녁" : "자유", $0.value) }
    }

    private func loadRoutines() async {
        do {
            routines = try await APIClient.shared.fetchTodayRoutines()
        } catch {
            // 에러 시 빈 목록
        }
        isLoading = false
    }

    private func toggleRoutine(_ routine: Routine) {
        Task {
            do {
                if checkedIds.contains(routine.id) {
                    try await APIClient.shared.uncheckRoutine(id: routine.id)
                    checkedIds.remove(routine.id)
                } else {
                    try await APIClient.shared.checkRoutine(id: routine.id)
                    checkedIds.insert(routine.id)
                }
            } catch {
                // 실패 시 상태 유지
            }
        }
    }
}

struct RoutineRow: View {
    let routine: Routine
    let isDone: Bool
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            HStack(spacing: 8) {
                Image(systemName: isDone ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(isDone ? .green : .gray)
                    .font(.title3)

                VStack(alignment: .leading, spacing: 2) {
                    Text(routine.name)
                        .font(.caption)
                        .lineLimit(1)
                        .strikethrough(isDone)
                        .foregroundColor(isDone ? .secondary : .primary)
                    Text("\(routine.durationMin)분")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                Spacer()

                Text(routine.categoryEmoji)
                    .font(.caption)
            }
        }
        .buttonStyle(.plain)
    }
}

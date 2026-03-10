import SwiftUI
import WidgetKit

// MARK: - Watch Complication (위젯)
// 시계 화면에 루틴 완료율, 습관 스트릭 표시

struct RoutineComplicationEntry: TimelineEntry {
    let date: Date
    let completed: Int
    let total: Int
}

struct HabitComplicationEntry: TimelineEntry {
    let date: Date
    let topStreak: Int
    let habitsLogged: Int
    let habitsTotal: Int
}

// Circular: 루틴 완료 게이지
struct RoutineCircularView: View {
    let completed: Int
    let total: Int

    private var progress: Double {
        guard total > 0 else { return 0 }
        return Double(completed) / Double(total)
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.blue.opacity(0.2), lineWidth: 4)
            Circle()
                .trim(from: 0, to: progress)
                .stroke(Color.blue, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(completed)")
                    .font(.system(size: 16, weight: .bold))
                Text("/\(total)")
                    .font(.system(size: 9))
                    .foregroundColor(.secondary)
            }
        }
    }
}

// Corner: 습관 스트릭 불꽃
struct HabitCornerView: View {
    let streak: Int

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: "flame.fill")
                .foregroundColor(.orange)
            Text("\(streak)")
                .font(.system(size: 14, weight: .semibold))
                .monospacedDigit()
        }
    }
}

// Rectangular: 오늘 요약
struct DailySummaryRectView: View {
    let routinesDone: Int
    let routinesTotal: Int
    let habitsLogged: Int
    let habitsTotal: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("오늘")
                .font(.system(size: 10))
                .foregroundColor(.secondary)
            HStack(spacing: 8) {
                Label("\(routinesDone)/\(routinesTotal)", systemImage: "checkmark.circle")
                    .font(.system(size: 11))
                    .foregroundColor(.blue)
                Label("\(habitsLogged)/\(habitsTotal)", systemImage: "flame")
                    .font(.system(size: 11))
                    .foregroundColor(.orange)
            }
        }
    }
}

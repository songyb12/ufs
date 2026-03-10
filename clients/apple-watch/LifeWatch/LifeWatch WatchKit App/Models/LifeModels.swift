import Foundation

// MARK: - Routine Models

struct Routine: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let category: String        // HEALTH, WORK, STUDY, SELF_DEV, SOCIAL, CREATIVE, GENERAL
    let timeSlot: String        // MORNING, AFTERNOON, EVENING, FLEXIBLE
    let durationMin: Int
    let priority: Int           // 1-5
    let repeatDays: [String]    // ["mon","tue",...]
    let isActive: Int
    let color: String
    let icon: String?

    enum CodingKeys: String, CodingKey {
        case id, name, description, category, priority, color, icon
        case timeSlot = "time_slot"
        case durationMin = "duration_min"
        case repeatDays = "repeat_days"
        case isActive = "is_active"
    }
}

struct RoutineLog: Codable {
    let id: Int
    let routineId: Int
    let date: String
    let status: String          // DONE, SKIPPED, PARTIAL

    enum CodingKeys: String, CodingKey {
        case id, date, status
        case routineId = "routine_id"
    }
}

struct RoutineWithStatus: Identifiable {
    let routine: Routine
    let todayStatus: String?    // nil = unchecked

    var id: Int { routine.id }
    var isDone: Bool { todayStatus == "DONE" }
}

// MARK: - Habit Models

struct Habit: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let targetType: String      // DAILY, WEEKLY, COUNT
    let targetValue: Double
    let unit: String
    let color: String
    let icon: String?
    let isActive: Int

    enum CodingKeys: String, CodingKey {
        case id, name, description, unit, color, icon
        case targetType = "target_type"
        case targetValue = "target_value"
        case isActive = "is_active"
    }
}

struct HabitStreak: Codable {
    let habitId: Int
    let currentStreak: Int
    let longestStreak: Int
    let weeklyRate: Double
    let monthlyRate: Double
    let totalLogs: Int

    enum CodingKeys: String, CodingKey {
        case currentStreak = "current_streak"
        case longestStreak = "longest_streak"
        case weeklyRate = "weekly_rate"
        case monthlyRate = "monthly_rate"
        case totalLogs = "total_logs"
        case habitId = "habit_id"
    }
}

struct HabitOverviewItem: Codable, Identifiable {
    let habit: Habit
    let streak: HabitStreak
    let todayValue: Double?

    var id: Int { habit.id }

    enum CodingKeys: String, CodingKey {
        case habit, streak
        case todayValue = "today_value"
    }
}

// MARK: - Goal Models

struct Goal: Codable, Identifiable {
    let id: Int
    let title: String
    let description: String?
    let category: String        // CAREER, HEALTH, FINANCE, SKILL, RELATIONSHIP, GENERAL
    let deadline: String?
    let status: String          // ACTIVE, ACHIEVED, ABANDONED, PAUSED
    let progress: Double        // 0.0 - 1.0
    let priority: Int
    let color: String
    let daysRemaining: Int?

    enum CodingKeys: String, CodingKey {
        case id, title, description, category, deadline, status, progress, priority, color
        case daysRemaining = "days_remaining"
    }
}

// MARK: - Dashboard

struct DashboardData: Codable {
    let date: String
    let routines: DashboardRoutines
    let habits: DashboardHabits
    let goals: DashboardGoals
    let schedule: DashboardSchedule?
}

struct DashboardRoutines: Codable {
    let total: Int
    let completed: Int
    let skipped: Int
    let remaining: Int
}

struct DashboardHabits: Codable {
    let total: Int
    let logged: Int
    let remaining: Int
}

struct DashboardGoals: Codable {
    let active: Int
    let nearDeadline: Int?

    enum CodingKeys: String, CodingKey {
        case active
        case nearDeadline = "near_deadline"
    }
}

struct DashboardSchedule: Codable {
    let totalBlocks: Int?
    let nextBlock: ScheduleBlock?

    enum CodingKeys: String, CodingKey {
        case totalBlocks = "total_blocks"
        case nextBlock = "next_block"
    }
}

struct ScheduleBlock: Codable, Identifiable {
    let id: Int
    let date: String
    let startTime: String
    let endTime: String
    let title: String
    let priority: Int

    enum CodingKeys: String, CodingKey {
        case id, date, title, priority
        case startTime = "start_time"
        case endTime = "end_time"
    }
}

// MARK: - Category Helpers

extension Routine {
    var categoryEmoji: String {
        switch category {
        case "HEALTH": return "💪"
        case "WORK": return "💼"
        case "STUDY": return "📚"
        case "SELF_DEV": return "🌱"
        case "SOCIAL": return "👥"
        case "CREATIVE": return "🎨"
        default: return "📌"
        }
    }

    var timeSlotLabel: String {
        switch timeSlot {
        case "MORNING": return "오전"
        case "AFTERNOON": return "오후"
        case "EVENING": return "저녁"
        default: return "자유"
        }
    }
}

extension Goal {
    var progressPercent: Int {
        Int(progress * 100)
    }
}

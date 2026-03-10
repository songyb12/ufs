import Foundation

// MARK: - Life-Master API Client

actor APIClient {
    static let shared = APIClient()

    // 서버 주소 (Settings에서 변경 가능)
    private var baseURL: String {
        UserDefaults.standard.string(forKey: "serverURL") ?? "http://192.168.0.100:8004"
    }

    private let session: URLSession
    private let decoder: JSONDecoder

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        config.timeoutIntervalForResource = 15
        self.session = URLSession(configuration: config)

        self.decoder = JSONDecoder()
    }

    // MARK: - Dashboard

    func fetchDashboard(date: String? = nil) async throws -> DashboardData {
        var path = "/dashboard"
        if let date = date {
            path += "?date=\(date)"
        }
        return try await get(path)
    }

    // MARK: - Routines

    func fetchTodayRoutines() async throws -> [Routine] {
        try await get("/routines/today")
    }

    func checkRoutine(id: Int, status: String = "DONE") async throws {
        let body: [String: Any] = ["status": status]
        try await post("/routines/\(id)/check", body: body)
    }

    func uncheckRoutine(id: Int) async throws {
        try await delete("/routines/\(id)/check")
    }

    func fetchRoutineStats(days: Int = 7) async throws -> [String: Any] {
        let today = ISO8601DateFormatter.dateOnly.string(from: Date())
        let from = ISO8601DateFormatter.dateOnly.string(
            from: Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        )
        return try await getRaw("/routines/stats?from_date=\(from)&to_date=\(today)")
    }

    // MARK: - Habits

    func fetchHabitsOverview() async throws -> [HabitOverviewItem] {
        try await get("/habits/overview")
    }

    func logHabit(id: Int, value: Double = 1.0) async throws {
        let body: [String: Any] = ["value": value]
        try await post("/habits/\(id)/log", body: body)
    }

    func incrementHabit(id: Int, delta: Double = 1.0) async throws {
        let body: [String: Any] = ["delta": delta]
        try await patch("/habits/\(id)/increment", body: body)
    }

    // MARK: - Goals

    func fetchGoals(status: String = "ACTIVE") async throws -> [Goal] {
        try await get("/goals?status=\(status)")
    }

    // MARK: - Schedule

    func fetchTodaySchedule() async throws -> [ScheduleBlock] {
        try await get("/schedule/today")
    }

    // MARK: - HTTP Methods

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let url = URL(string: baseURL + path)!
        let (data, response) = try await session.data(from: url)
        try validateResponse(response)
        return try decoder.decode(T.self, from: data)
    }

    private func getRaw(_ path: String) async throws -> [String: Any] {
        let url = URL(string: baseURL + path)!
        let (data, response) = try await session.data(from: url)
        try validateResponse(response)
        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }

    private func post(_ path: String, body: [String: Any]) async throws {
        var request = URLRequest(url: URL(string: baseURL + path)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (_, response) = try await session.data(for: request)
        try validateResponse(response)
    }

    private func patch(_ path: String, body: [String: Any]) async throws {
        var request = URLRequest(url: URL(string: baseURL + path)!)
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (_, response) = try await session.data(for: request)
        try validateResponse(response)
    }

    private func delete(_ path: String) async throws {
        var request = URLRequest(url: URL(string: baseURL + path)!)
        request.httpMethod = "DELETE"
        let (_, response) = try await session.data(for: request)
        try validateResponse(response)
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            throw APIError.httpError(http.statusCode)
        }
    }
}

// MARK: - Errors

enum APIError: LocalizedError {
    case invalidResponse
    case httpError(Int)
    case decodingError

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "서버 응답 오류"
        case .httpError(let code): return "HTTP \(code)"
        case .decodingError: return "데이터 파싱 오류"
        }
    }
}

// MARK: - Date Formatter

extension ISO8601DateFormatter {
    static let dateOnly: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

/**
 * LocalStorage persistence layer for Bocchi-master.
 * Saves and restores user settings across sessions.
 */

const STORAGE_KEY = 'bocchi-master-settings'

export interface PersistedSettings {
  // Metronome
  bpm: number
  beatsPerMeasure: number

  // Instrument
  instrumentType: 'guitar' | 'bass'
  instrumentName: string  // matches InstrumentConfig.name for exact tuning lookup

  // Scale/Chord selector
  selectedRoot: string | null
  selectedDefinitionName: string | null
  mode: 'scale' | 'chord'

  // Progression
  progressionKey: string | null
  progressionPresetName: string | null

  // Voicing
  voicingMode: 'all' | 'voicing'
  voicingSource: 'caged' | 'auto'
  isOptimized: boolean

  // Backing track
  backingEnabled: boolean
  drumVolume: number
  bassVolume: number

  // Practice stats (cumulative)
  practiceHistory: PracticeSession[]
}

export interface PracticeSession {
  date: string  // ISO date string
  accuracy: number
  totalAttempts: number
  correctAttempts: number
  targetDescription: string  // e.g., "C Major Scale" or "Am7 Chord"
  durationSeconds: number
  rating?: number   // 1-5 star self-assessment
  notes?: string    // free-form practice notes
}

/** Daily practice goal tracking */
export interface DailyGoal {
  targetMinutes: number
  /** Accumulated seconds per day, keyed by YYYY-MM-DD */
  dailyLog: Record<string, number>
}

const DAILY_GOAL_KEY = 'bocchi-daily-goal'

export function loadDailyGoal(): DailyGoal {
  try {
    const raw = localStorage.getItem(DAILY_GOAL_KEY)
    if (!raw) return { targetMinutes: 30, dailyLog: {} }
    return JSON.parse(raw) as DailyGoal
  } catch {
    return { targetMinutes: 30, dailyLog: {} }
  }
}

export function saveDailyGoal(goal: DailyGoal): void {
  try {
    // Keep only last 60 days of logs to prevent unbounded growth
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - 60)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    const trimmed: Record<string, number> = {}
    for (const [date, secs] of Object.entries(goal.dailyLog)) {
      if (date >= cutoffStr) trimmed[date] = secs
    }
    localStorage.setItem(DAILY_GOAL_KEY, JSON.stringify({ ...goal, dailyLog: trimmed }))
  } catch { /* ignore */ }
}

export function addDailyPracticeTime(seconds: number): void {
  const goal = loadDailyGoal()
  const today = new Date().toISOString().slice(0, 10)
  goal.dailyLog[today] = (goal.dailyLog[today] ?? 0) + seconds
  saveDailyGoal(goal)
}

const DEFAULTS: PersistedSettings = {
  bpm: 120,
  beatsPerMeasure: 4,
  instrumentType: 'guitar',
  instrumentName: 'Standard Guitar',
  selectedRoot: null,
  selectedDefinitionName: 'Major (Ionian)',
  mode: 'scale',
  progressionKey: null,
  progressionPresetName: null,
  voicingMode: 'all',
  voicingSource: 'caged',
  isOptimized: true,
  backingEnabled: false,
  drumVolume: 70,
  bassVolume: 60,
  practiceHistory: [],
}

export function loadSettings(): PersistedSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw) as Partial<PersistedSettings>
    // Merge with defaults to handle missing keys from older versions
    return { ...DEFAULTS, ...parsed }
  } catch {
    return { ...DEFAULTS }
  }
}

export function saveSettings(settings: Partial<PersistedSettings>): void {
  try {
    const current = loadSettings()
    const merged = { ...current, ...settings }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
  } catch {
    // localStorage may be full or disabled — silently ignore
  }
}

export function addPracticeSession(session: PracticeSession): void {
  const settings = loadSettings()
  // Keep last 100 sessions
  settings.practiceHistory = [session, ...settings.practiceHistory].slice(0, 100)
  saveSettings({ practiceHistory: settings.practiceHistory })
}

export function clearPracticeHistory(): void {
  saveSettings({ practiceHistory: [] })
}

/**
 * Export all practice data as a JSON blob for download.
 * Includes settings, practice history, and metadata.
 */
export function exportPracticeData(): string {
  const settings = loadSettings()
  const exportData = {
    version: 1,
    exportedAt: new Date().toISOString(),
    app: 'bocchi-master',
    settings: {
      bpm: settings.bpm,
      beatsPerMeasure: settings.beatsPerMeasure,
      instrumentType: settings.instrumentType,
      instrumentName: settings.instrumentName,
      mode: settings.mode,
    },
    practiceHistory: settings.practiceHistory,
    totalSessions: settings.practiceHistory.length,
  }
  return JSON.stringify(exportData, null, 2)
}

/**
 * Import practice history from a JSON string.
 * Merges with existing data (avoids duplicates by date).
 */
export function importPracticeData(jsonString: string): { imported: number; errors: string[] } {
  const errors: string[] = []
  try {
    const data = JSON.parse(jsonString)
    if (!data || data.app !== 'bocchi-master') {
      return { imported: 0, errors: ['Invalid file: not a bocchi-master export'] }
    }

    const sessions: PracticeSession[] = data.practiceHistory ?? []
    if (!Array.isArray(sessions)) {
      return { imported: 0, errors: ['Invalid practice history format'] }
    }

    // Validate each session
    const validSessions = sessions.filter((s, i) => {
      if (!s.date || typeof s.accuracy !== 'number') {
        errors.push(`Session ${i}: missing required fields`)
        return false
      }
      return true
    })

    // Merge with existing (deduplicate by date + target)
    const existing = loadSettings().practiceHistory
    const existingKeys = new Set(existing.map((s) => `${s.date}-${s.targetDescription}`))
    const newSessions = validSessions.filter(
      (s) => !existingKeys.has(`${s.date}-${s.targetDescription}`),
    )

    if (newSessions.length > 0) {
      const merged = [...newSessions, ...existing].slice(0, 200)
      saveSettings({ practiceHistory: merged })
    }

    return { imported: newSessions.length, errors }
  } catch (e) {
    return { imported: 0, errors: [`Parse error: ${(e as Error).message}`] }
  }
}

/**
 * Trigger a file download in the browser.
 */
export function downloadAsFile(content: string, filename: string, mimeType = 'application/json'): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

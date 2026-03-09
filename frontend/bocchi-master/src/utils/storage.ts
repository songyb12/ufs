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

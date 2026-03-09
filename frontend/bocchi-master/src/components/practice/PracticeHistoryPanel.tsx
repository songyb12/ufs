import { memo, useState, useEffect, useRef, useCallback } from 'react'
import {
  loadSettings,
  saveSettings,
  clearPracticeHistory,
  exportPracticeData,
  importPracticeData,
  downloadAsFile,
  type PracticeSession,
} from '../../utils/storage'

/** Compact inline star rating (1-5) */
function StarRating({
  value,
  onChange,
}: {
  value: number | undefined
  onChange: (rating: number) => void
}) {
  return (
    <span className="inline-flex gap-px">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          onClick={(e) => { e.stopPropagation(); onChange(star) }}
          className={`text-xs leading-none ${
            (value ?? 0) >= star ? 'text-amber-400' : 'text-slate-600'
          } hover:text-amber-300`}
          title={`Rate ${star}/5`}
        >
          ★
        </button>
      ))}
    </span>
  )
}

/**
 * Practice History Panel
 *
 * Displays accumulated practice statistics from localStorage.
 * Shows recent sessions, total practice time, and accuracy trends.
 */
export const PracticeHistoryPanel = memo(function PracticeHistoryPanel() {
  const [sessions, setSessions] = useState<PracticeSession[]>([])
  const [expanded, setExpanded] = useState(false)
  const [editingNoteIdx, setEditingNoteIdx] = useState<number | null>(null)
  const [noteText, setNoteText] = useState('')

  useEffect(() => {
    const settings = loadSettings()
    setSessions(settings.practiceHistory)
  }, [])

  // Refresh sessions when component becomes visible (practice might have ended)
  useEffect(() => {
    const interval = setInterval(() => {
      const settings = loadSettings()
      setSessions(settings.practiceHistory)
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  if (sessions.length === 0) {
    return (
      <div className="bg-slate-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
          📊 Practice History
        </h2>
        <p className="text-xs text-slate-500">
          No practice sessions recorded yet. Start a practice session to begin tracking.
        </p>
      </div>
    )
  }

  // Aggregate stats
  const totalSessions = sessions.length
  const totalTime = sessions.reduce((sum, s) => sum + s.durationSeconds, 0)
  const totalAttempts = sessions.reduce((sum, s) => sum + s.totalAttempts, 0)
  const totalCorrect = sessions.reduce((sum, s) => sum + s.correctAttempts, 0)
  const overallAccuracy = totalAttempts > 0 ? Math.round((totalCorrect / totalAttempts) * 100) : 0

  // Recent 7-day trend
  const now = new Date()
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  const recentSessions = sessions.filter((s) => new Date(s.date) >= weekAgo)
  const recentAttempts = recentSessions.reduce((sum, s) => sum + s.totalAttempts, 0)
  const recentCorrect = recentSessions.reduce((sum, s) => sum + s.correctAttempts, 0)
  const recentAccuracy = recentAttempts > 0 ? Math.round((recentCorrect / recentAttempts) * 100) : 0

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    if (mins < 60) return `${mins}m ${secs}s`
    const hours = Math.floor(mins / 60)
    return `${hours}h ${mins % 60}m`
  }

  const updateSession = useCallback((idx: number, patch: Partial<PracticeSession>) => {
    setSessions((prev) => {
      const updated = prev.map((s, i) => (i === idx ? { ...s, ...patch } : s))
      saveSettings({ practiceHistory: updated })
      return updated
    })
  }, [])

  const handleClear = () => {
    clearPracticeHistory()
    setSessions([])
  }

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [importStatus, setImportStatus] = useState<string | null>(null)

  const handleExport = useCallback(() => {
    const json = exportPracticeData()
    const date = new Date().toISOString().slice(0, 10)
    downloadAsFile(json, `bocchi-practice-${date}.json`)
  }, [])

  const handleImport = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const result = importPracticeData(reader.result as string)
      if (result.errors.length > 0) {
        setImportStatus(`⚠ ${result.errors[0]}`)
      } else if (result.imported > 0) {
        setImportStatus(`✓ Imported ${result.imported} sessions`)
        const settings = loadSettings()
        setSessions(settings.practiceHistory)
      } else {
        setImportStatus('No new sessions to import')
      }
      setTimeout(() => setImportStatus(null), 4000)
    }
    reader.readAsText(file)
    // Reset input for re-import
    e.target.value = ''
  }, [])

  return (
    <div className="bg-slate-800 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          📊 Practice History
        </h2>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          {expanded ? 'Collapse' : 'Details'}
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-2 text-center">
        <div>
          <div className="text-lg font-bold text-slate-300">{totalSessions}</div>
          <div className="text-[10px] text-slate-500 uppercase">Sessions</div>
        </div>
        <div>
          <div className="text-lg font-bold text-slate-300">{formatDuration(totalTime)}</div>
          <div className="text-[10px] text-slate-500 uppercase">Total Time</div>
        </div>
        <div>
          <div className={`text-lg font-bold ${
            overallAccuracy >= 80 ? 'text-emerald-400' :
            overallAccuracy >= 50 ? 'text-amber-400' :
            'text-red-400'
          }`}>
            {overallAccuracy}%
          </div>
          <div className="text-[10px] text-slate-500 uppercase">Accuracy</div>
        </div>
        <div>
          <div className={`text-lg font-bold ${
            recentAccuracy >= 80 ? 'text-emerald-400' :
            recentAccuracy >= 50 ? 'text-amber-400' :
            recentSessions.length > 0 ? 'text-red-400' : 'text-slate-500'
          }`}>
            {recentSessions.length > 0 ? `${recentAccuracy}%` : '—'}
          </div>
          <div className="text-[10px] text-slate-500 uppercase">7-day</div>
        </div>
      </div>

      {/* Expanded session list */}
      {expanded && (
        <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
          {sessions.slice(0, 20).map((session, idx) => {
            const date = new Date(session.date)
            const dateStr = `${date.getMonth() + 1}/${date.getDate()}`
            const accuracy = session.totalAttempts > 0
              ? Math.round((session.correctAttempts / session.totalAttempts) * 100)
              : 0
            const isEditingNote = editingNoteIdx === idx
            return (
              <div key={idx} className="border-b border-slate-700/50">
                <div className="flex items-center gap-2 text-xs text-slate-400 py-0.5">
                  <span className="text-slate-500 w-10">{dateStr}</span>
                  <span className="flex-1 truncate text-slate-300">{session.targetDescription}</span>
                  <StarRating
                    value={session.rating}
                    onChange={(r) => updateSession(idx, { rating: r })}
                  />
                  <span className={`w-8 text-right font-mono ${
                    accuracy >= 80 ? 'text-emerald-400' :
                    accuracy >= 50 ? 'text-amber-400' : 'text-red-400'
                  }`}>
                    {accuracy}%
                  </span>
                  <span className="text-slate-600 w-10 text-right">
                    {formatDuration(session.durationSeconds)}
                  </span>
                  <button
                    onClick={() => {
                      if (isEditingNote) {
                        updateSession(idx, { notes: noteText || undefined })
                        setEditingNoteIdx(null)
                      } else {
                        setNoteText(session.notes ?? '')
                        setEditingNoteIdx(idx)
                      }
                    }}
                    className={`text-[10px] ${session.notes || isEditingNote ? 'text-sky-400' : 'text-slate-600 hover:text-slate-400'}`}
                    title={isEditingNote ? 'Save note' : (session.notes ? 'Edit note' : 'Add note')}
                  >
                    {isEditingNote ? '✓' : '📝'}
                  </button>
                </div>
                {isEditingNote && (
                  <input
                    type="text"
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        updateSession(idx, { notes: noteText || undefined })
                        setEditingNoteIdx(null)
                      }
                    }}
                    placeholder="Practice notes..."
                    autoFocus
                    className="w-full bg-slate-700/50 text-xs text-slate-300 rounded px-2 py-1 mb-1 outline-none placeholder-slate-600"
                  />
                )}
                {!isEditingNote && session.notes && (
                  <div className="text-[10px] text-slate-500 italic pl-10 pb-0.5">{session.notes}</div>
                )}
              </div>
            )
          })}
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-700/50">
            <button
              onClick={handleExport}
              className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
              title="Download practice data as JSON"
            >
              📥 Export
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
              title="Import practice data from JSON file"
            >
              📤 Import
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleImport}
            />
            {importStatus && (
              <span className="text-[10px] text-slate-500">{importStatus}</span>
            )}
            <button
              onClick={handleClear}
              className="text-xs text-red-500/60 hover:text-red-400 ml-auto"
            >
              Clear history
            </button>
          </div>
        </div>
      )}
    </div>
  )
})

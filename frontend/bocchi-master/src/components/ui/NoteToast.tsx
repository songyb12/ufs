import { useState, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react'
import type { Note, NoteName } from '../../types/music'
import { getNoteLabel } from '../../utils/noteLabelFormatter'

interface NoteInfo {
  note: Note
  stringIndex: number
  fret: number
}

/** Frequency of a note: A4 = 440 Hz */
function noteFreq(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12)
}

export interface NoteToastHandle {
  show: (note: Note, stringIndex: number, fret: number) => void
}

/**
 * Floating toast that appears briefly when a fretboard note is clicked.
 * Shows note name, octave, frequency, string/fret, and interval from root.
 */
export const NoteToast = forwardRef<NoteToastHandle, { rootNote?: NoteName }>(
  function NoteToast({ rootNote }, ref) {
    const [info, setInfo] = useState<NoteInfo | null>(null)
    const [visible, setVisible] = useState(false)
    const [key, setKey] = useState(0) // force re-trigger animation

    const show = useCallback((note: Note, stringIndex: number, fret: number) => {
      setInfo({ note, stringIndex, fret })
      setVisible(true)
      setKey((k) => k + 1)
    }, [])

    useImperativeHandle(ref, () => ({ show }), [show])

    // Auto-hide after 2 seconds
    useEffect(() => {
      if (!visible) return
      const t = setTimeout(() => setVisible(false), 2000)
      return () => clearTimeout(t)
    }, [visible, key])

    if (!visible || !info) return null

    const { note, stringIndex, fret } = info
    const freq = noteFreq(note.midiNumber)
    const interval = rootNote ? getNoteLabel(note.name, rootNote, 'interval') : undefined

    return (
      <div
        key={key}
        className="fixed top-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none
          bg-slate-900/95 border border-slate-600 rounded-lg px-4 py-2 shadow-xl
          animate-fade-in-out"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-white">
            {note.name}<sub className="text-slate-400 text-xs">{note.octave}</sub>
          </span>
          <span className="text-xs text-slate-500 tabular-nums">
            {freq.toFixed(1)} Hz
          </span>
          <span className="text-xs text-slate-500">
            S{stringIndex + 1} F{fret}
          </span>
          {interval && (
            <span className="text-xs text-amber-400 font-semibold">
              {interval}
            </span>
          )}
        </div>
      </div>
    )
  },
)

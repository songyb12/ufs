import { useState, useCallback } from 'react'
import type { InstrumentConfig, Note } from './types/music'
import { STANDARD_GUITAR } from './constants/tunings'
import { AppShell } from './components/layout/AppShell'
import { Fretboard } from './components/fretboard/Fretboard'
import { MetronomePanel } from './components/metronome/MetronomePanel'
import { MidiStatus } from './components/midi/MidiStatus'

export default function App() {
  const [instrument, setInstrument] =
    useState<InstrumentConfig>(STANDARD_GUITAR)
  const [highlightedNotes, setHighlightedNotes] = useState<Note[]>([])

  const handleNoteClick = useCallback(
    (note: Note) => {
      setHighlightedNotes((prev) => {
        const exists = prev.some(
          (n) => n.name === note.name && n.octave === note.octave,
        )
        if (exists) {
          return prev.filter(
            (n) => !(n.name === note.name && n.octave === note.octave),
          )
        }
        return [...prev, note]
      })
    },
    [],
  )

  return (
    <AppShell instrument={instrument} onInstrumentChange={setInstrument}>
      {/* Fretboard */}
      <section>
        <Fretboard
          instrument={instrument}
          highlightedNotes={highlightedNotes}
          onNoteClick={handleNoteClick}
        />
        {highlightedNotes.length > 0 && (
          <div className="flex items-center gap-2 mt-2 px-1">
            <span className="text-xs text-slate-500">Selected:</span>
            <div className="flex gap-1 flex-wrap">
              {highlightedNotes.map((n, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded bg-orange-500/20 text-orange-400 text-xs font-mono"
                >
                  {n.name}{n.octave}
                </span>
              ))}
            </div>
            <button
              onClick={() => setHighlightedNotes([])}
              className="text-xs text-slate-500 hover:text-slate-300 ml-auto"
            >
              Clear
            </button>
          </div>
        )}
      </section>

      {/* Bottom controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetronomePanel />
        <MidiStatus />
      </div>
    </AppShell>
  )
}

import { useState, useCallback, useMemo, useEffect } from 'react'
import type { InstrumentConfig, Note, NoteName } from './types/music'
import { STANDARD_GUITAR } from './constants/tunings'
import { AppShell } from './components/layout/AppShell'
import { Fretboard } from './components/fretboard/Fretboard'
import { MetronomePanel } from './components/metronome/MetronomePanel'
import { MidiStatus } from './components/midi/MidiStatus'
import { ScaleSelector } from './components/scale/ScaleSelector'
import { ChordProgressionPanel } from './components/progression/ChordProgressionPanel'
import { useMetronome } from './hooks/useMetronome'
import {
  SCALES,
  getScaleNoteNames,
  type ScaleDefinition,
  type ChordDefinition,
} from './utils/scaleCalculator'
import {
  resolveProgression,
  type ProgressionPreset,
} from './utils/chordProgression'

export default function App() {
  const [instrument, setInstrument] =
    useState<InstrumentConfig>(STANDARD_GUITAR)
  const [highlightedNotes, setHighlightedNotes] = useState<Note[]>([])

  // Scale/Chord overlay state
  const [selectedRoot, setSelectedRoot] = useState<NoteName | null>(null)
  const [selectedDefinition, setSelectedDefinition] = useState<
    ScaleDefinition | ChordDefinition | null
  >(SCALES[0]) // Default: Major
  const [mode, setMode] = useState<'scale' | 'chord'>('scale')

  // Metronome state (lifted from MetronomePanel)
  const metronome = useMetronome()

  // Chord progression state
  const [progressionKey, setProgressionKey] = useState<NoteName | null>(null)
  const [progressionPreset, setProgressionPreset] =
    useState<ProgressionPreset | null>(null)
  const [activeChordIndex, setActiveChordIndex] = useState(0)

  // Resolve progression chords
  const resolvedChords = useMemo(() => {
    if (!progressionKey || !progressionPreset) return []
    return resolveProgression(progressionKey, progressionPreset)
  }, [progressionKey, progressionPreset])

  // Sync activeChordIndex with metronome measure
  useEffect(() => {
    if (resolvedChords.length > 0 && metronome.isPlaying) {
      setActiveChordIndex(metronome.currentMeasure % resolvedChords.length)
    }
  }, [metronome.currentMeasure, metronome.isPlaying, resolvedChords.length])

  // Reset activeChordIndex when progression changes
  useEffect(() => {
    setActiveChordIndex(0)
  }, [progressionKey, progressionPreset])

  // Compute scale note names from ScaleSelector (memoized)
  const scaleSelectorNoteNames = useMemo(() => {
    if (!selectedRoot || !selectedDefinition) return []
    return getScaleNoteNames(selectedRoot, selectedDefinition)
  }, [selectedRoot, selectedDefinition])

  // Determine what to show on fretboard:
  // Priority: active progression chord > scale selector
  const { fretboardNoteNames, fretboardRootNote } = useMemo(() => {
    const hasProgression = resolvedChords.length > 0
    if (hasProgression) {
      const chord = resolvedChords[activeChordIndex]
      if (chord) {
        return {
          fretboardNoteNames: chord.notes,
          fretboardRootNote: chord.root,
        }
      }
    }
    // Fallback to scale selector
    return {
      fretboardNoteNames: scaleSelectorNoteNames,
      fretboardRootNote: selectedRoot ?? undefined,
    }
  }, [
    resolvedChords,
    activeChordIndex,
    scaleSelectorNoteNames,
    selectedRoot,
  ])

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

  const handleProgressionChordClick = useCallback(
    (index: number) => {
      setActiveChordIndex(index)
    },
    [],
  )

  return (
    <AppShell instrument={instrument} onInstrumentChange={setInstrument}>
      {/* Scale/Chord selector */}
      <ScaleSelector
        selectedRoot={selectedRoot}
        selectedDefinition={selectedDefinition}
        mode={mode}
        onRootChange={setSelectedRoot}
        onDefinitionChange={setSelectedDefinition}
        onModeChange={setMode}
      />

      {/* Fretboard */}
      <section>
        <Fretboard
          instrument={instrument}
          highlightedNotes={highlightedNotes}
          scaleNoteNames={fretboardNoteNames}
          rootNote={fretboardRootNote}
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

      {/* Chord Progression */}
      <ChordProgressionPanel
        progressionKey={progressionKey}
        progressionPreset={progressionPreset}
        activeChordIndex={activeChordIndex}
        isPlaying={metronome.isPlaying}
        onKeyChange={setProgressionKey}
        onPresetChange={setProgressionPreset}
        onChordClick={handleProgressionChordClick}
      />

      {/* Bottom controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetronomePanel
          bpm={metronome.bpm}
          setBpm={metronome.setBpm}
          isPlaying={metronome.isPlaying}
          toggle={metronome.toggle}
          currentBeat={metronome.currentBeat}
          beatsPerMeasure={metronome.beatsPerMeasure}
          setBeatsPerMeasure={metronome.setBeatsPerMeasure}
        />
        <MidiStatus />
      </div>
    </AppShell>
  )
}

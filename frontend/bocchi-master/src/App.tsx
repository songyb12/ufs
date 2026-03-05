import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import type { InstrumentConfig, Note, NoteName } from './types/music'
import { STANDARD_GUITAR } from './constants/tunings'
import { AppShell } from './components/layout/AppShell'
import { Fretboard } from './components/fretboard/Fretboard'
import { MetronomePanel } from './components/metronome/MetronomePanel'
import { MidiStatus } from './components/midi/MidiStatus'
import { ScaleSelector } from './components/scale/ScaleSelector'
import {
  ChordProgressionPanel,
  type VoicingMode,
  type VoicingSource,
} from './components/progression/ChordProgressionPanel'
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
import { getCAGEDVoicings, type ChordVoicing } from './utils/voicingLibrary'
import { generateVoicings } from './utils/voicingGenerator'
import { optimizeProgressionVoicings } from './utils/voicingOptimizer'

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

  // Voicing state
  const [voicingMode, setVoicingMode] = useState<VoicingMode>('all')
  const [voicingSource, setVoicingSource] = useState<VoicingSource>('caged')
  const [voicingIndex, setVoicingIndex] = useState(0)
  const [isOptimized, setIsOptimized] = useState(true)

  // Resolve progression chords
  const resolvedChords = useMemo(() => {
    if (!progressionKey || !progressionPreset) return []
    return resolveProgression(progressionKey, progressionPreset)
  }, [progressionKey, progressionPreset])

  // Active chord info
  const activeChord = resolvedChords[activeChordIndex] ?? null

  // Compute available voicings for ALL chords in the progression
  const allProgressionVoicings: ChordVoicing[][] = useMemo(() => {
    return resolvedChords.map((chord) => {
      if (voicingSource === 'caged') {
        return getCAGEDVoicings(chord.root, chord.quality, instrument)
      }
      return generateVoicings(chord.root, chord.quality, instrument)
    })
  }, [resolvedChords, voicingSource, instrument])

  // Available voicings for the currently active chord
  const availableVoicings = allProgressionVoicings[activeChordIndex] ?? []

  // DP-optimized voicing indices for the entire progression
  const optimizedIndices = useMemo(() => {
    if (allProgressionVoicings.length === 0) return []
    return optimizeProgressionVoicings(allProgressionVoicings)
  }, [allProgressionVoicings])

  // Use a ref to track whether the chord change was from metronome/click (auto)
  // vs manual ◀▶ navigation
  const isAutoChordChange = useRef(false)

  // When active chord changes, apply optimized index if optimization is ON
  useEffect(() => {
    if (isOptimized && optimizedIndices.length > 0) {
      const optIdx = optimizedIndices[activeChordIndex] ?? 0
      setVoicingIndex(optIdx)
    } else if (isAutoChordChange.current) {
      // Non-optimized: reset to 0 on auto chord change
      setVoicingIndex(0)
    }
    isAutoChordChange.current = false
  }, [activeChordIndex, isOptimized, optimizedIndices])

  // When voicing source changes, reset index
  useEffect(() => {
    if (isOptimized && optimizedIndices.length > 0) {
      const optIdx = optimizedIndices[activeChordIndex] ?? 0
      setVoicingIndex(optIdx)
    } else {
      setVoicingIndex(0)
    }
  }, [voicingSource]) // eslint-disable-line react-hooks/exhaustive-deps

  // Clamp voicingIndex when voicing list changes
  useEffect(() => {
    if (availableVoicings.length > 0 && voicingIndex >= availableVoicings.length) {
      setVoicingIndex(0)
    }
  }, [availableVoicings.length, voicingIndex])

  // Current voicing (if in voicing mode with available voicings)
  const currentVoicing =
    voicingMode === 'voicing' && availableVoicings.length > 0
      ? availableVoicings[voicingIndex] ?? null
      : null

  // Sync activeChordIndex with metronome measure
  useEffect(() => {
    if (resolvedChords.length > 0 && metronome.isPlaying) {
      isAutoChordChange.current = true
      setActiveChordIndex(metronome.currentMeasure % resolvedChords.length)
    }
  }, [metronome.currentMeasure, metronome.isPlaying, resolvedChords.length])

  // Reset activeChordIndex when progression changes
  useEffect(() => {
    isAutoChordChange.current = true
    setActiveChordIndex(0)
  }, [progressionKey, progressionPreset])

  // Compute scale note names from ScaleSelector (memoized)
  const scaleSelectorNoteNames = useMemo(() => {
    if (!selectedRoot || !selectedDefinition) return []
    return getScaleNoteNames(selectedRoot, selectedDefinition)
  }, [selectedRoot, selectedDefinition])

  // Determine what to show on fretboard:
  // Priority: voicing positions > active progression chord > scale selector
  const { fretboardNoteNames, fretboardRootNote, fretboardVoicingPositions } =
    useMemo(() => {
      const hasProgression = resolvedChords.length > 0

      // When voicing mode is active with a valid voicing
      if (hasProgression && currentVoicing) {
        return {
          fretboardNoteNames: [] as NoteName[], // voicing mode uses positions, not names
          fretboardRootNote: activeChord?.root,
          fretboardVoicingPositions: currentVoicing.frets,
        }
      }

      // When progression is active but in "all notes" mode
      if (hasProgression && activeChord) {
        return {
          fretboardNoteNames: activeChord.notes,
          fretboardRootNote: activeChord.root,
          fretboardVoicingPositions: undefined,
        }
      }

      // Fallback to scale selector
      return {
        fretboardNoteNames: scaleSelectorNoteNames,
        fretboardRootNote: selectedRoot ?? undefined,
        fretboardVoicingPositions: undefined,
      }
    }, [
      resolvedChords,
      activeChord,
      currentVoicing,
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
      isAutoChordChange.current = true
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
          voicingPositions={fretboardVoicingPositions}
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
        voicingMode={voicingMode}
        onVoicingModeChange={setVoicingMode}
        voicingSource={voicingSource}
        onVoicingSourceChange={setVoicingSource}
        voicingIndex={voicingIndex}
        onVoicingIndexChange={setVoicingIndex}
        voicingCount={availableVoicings.length}
        voicingName={currentVoicing?.name ?? ''}
        isOptimized={isOptimized}
        onOptimizedChange={setIsOptimized}
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

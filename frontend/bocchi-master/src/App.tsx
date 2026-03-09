import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import type { InstrumentConfig, Note, NoteName } from './types/music'
import { STANDARD_GUITAR, STANDARD_BASS, INSTRUMENTS } from './constants/tunings'
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
  CHORDS,
  getScaleNoteNames,
  type ScaleDefinition,
  type ChordDefinition,
} from './utils/scaleCalculator'
import {
  resolveProgression,
  PROGRESSION_PRESETS,
  type ProgressionPreset,
  type ProgressionStep,
} from './utils/chordProgression'
import { getCAGEDVoicings, type ChordVoicing } from './utils/voicingLibrary'
import { generateVoicings } from './utils/voicingGenerator'
import { optimizeProgressionVoicings } from './utils/voicingOptimizer'
import { useSoundEngine } from './hooks/useSoundEngine'
import { useMidi } from './hooks/useMidi'
import { CHROMATIC_SCALE } from './constants/notes'
import { getScaleSuggestions, type ScaleSuggestion } from './utils/scaleAdvisor'
import { ScaleSuggestionPanel } from './components/scale/ScaleSuggestionPanel'
import { useBackingTrack } from './hooks/useBackingTrack'
import { BackingTrackPanel } from './components/backing/BackingTrackPanel'
import { usePracticeMode } from './hooks/usePracticeMode'
import { PracticePanel } from './components/practice/PracticePanel'
import { loadSettings, saveSettings } from './utils/storage'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { useIntervalTrainer } from './hooks/useIntervalTrainer'
import { IntervalTrainerPanel } from './components/trainer/IntervalTrainerPanel'
import { PracticeHistoryPanel } from './components/practice/PracticeHistoryPanel'
import { ShortcutHelpOverlay } from './components/help/ShortcutHelpOverlay'
import { ScaleFinderPanel } from './components/scale/ScaleFinderPanel'
import { FretboardQuizPanel, type FretboardQuizHandle } from './components/trainer/FretboardQuizPanel'
import { ScalePatternPanel } from './components/scale/ScalePatternPanel'
import { PracticeTimerPanel } from './components/practice/PracticeTimerPanel'
import { suggestEnharmonicMode, getEnharmonicName, type EnharmonicMode } from './utils/enharmonic'
import { StrumPatternPanel } from './components/rhythm/StrumPatternPanel'
import { TempoTrainerPanel } from './components/metronome/TempoTrainerPanel'
import { TuningQuickSwitch } from './components/fretboard/TuningQuickSwitch'
import { ChordTransitionTimer } from './components/trainer/ChordTransitionTimer'
import { CircleOfFifths } from './components/theory/CircleOfFifths'

// Restore persisted settings on initial load
const initialSettings = loadSettings()

function resolveInstrument(name: string, type: string): InstrumentConfig {
  // Try exact name match first (for alternate tunings), fallback to type
  return INSTRUMENTS.find((i) => i.name === name)
    ?? INSTRUMENTS.find((i) => i.type === type)
    ?? STANDARD_GUITAR
}

function resolveDefinition(
  name: string | null,
  mode: 'scale' | 'chord',
): ScaleDefinition | ChordDefinition | null {
  if (!name) return null
  const pool = mode === 'scale' ? SCALES : CHORDS
  return pool.find((d) => d.name === name) ?? pool[0]
}

function resolvePreset(name: string | null): ProgressionPreset | null {
  if (!name) return null
  return PROGRESSION_PRESETS.find((p) => p.name === name) ?? null
}

export default function App() {
  const [instrument, setInstrument] = useState<InstrumentConfig>(
    resolveInstrument(initialSettings.instrumentName, initialSettings.instrumentType),
  )
  const [highlightedNotes, setHighlightedNotes] = useState<Note[]>([])
  const soundEngine = useSoundEngine()
  const midi = useMidi()
  const practice = usePracticeMode()
  const intervalTrainer = useIntervalTrainer()

  // Scale pattern positions (for box shapes on fretboard)
  const [patternPositions, setPatternPositions] = useState<{ stringIndex: number; fret: number }[] | null>(null)

  // Chord tone highlighting toggle
  const [showChordTones, setShowChordTones] = useState(false)

  // Ghost mode: hide note labels (dots only)
  const [hideNoteLabels, setHideNoteLabels] = useState(false)

  // Fretboard quiz state
  const [fretboardQuizActive, setFretboardQuizActive] = useState(false)
  const fretboardQuizRef = useRef<FretboardQuizHandle>(null)

  // Derive MIDI active note name for fretboard highlight
  const midiNoteName: NoteName | undefined = useMemo(() => {
    if (!midi.lastNote) return undefined
    return CHROMATIC_SCALE[midi.lastNote.note % 12]
  }, [midi.lastNote])

  // Play sound + evaluate practice when MIDI note arrives
  useEffect(() => {
    if (!midi.lastNote) return
    const midiNum = midi.lastNote.note
    const name = CHROMATIC_SCALE[midiNum % 12]
    const octave = Math.floor(midiNum / 12) - 1
    soundEngine.playFretboardNote({ name, octave, midiNumber: midiNum })
    practice.evaluateNote(midiNum)
  }, [midi.lastNote]) // eslint-disable-line react-hooks/exhaustive-deps

  // Scale/Chord overlay state
  const [selectedRoot, setSelectedRoot] = useState<NoteName | null>(
    (initialSettings.selectedRoot as NoteName) ?? null,
  )
  const [selectedDefinition, setSelectedDefinition] = useState<
    ScaleDefinition | ChordDefinition | null
  >(resolveDefinition(initialSettings.selectedDefinitionName, initialSettings.mode))
  const [mode, setMode] = useState<'scale' | 'chord'>(initialSettings.mode)

  // Note label mode (name / interval / degree)
  const [labelMode, setLabelMode] = useState<import('./utils/noteLabelFormatter').NoteLabelMode>('name')

  // Enharmonic display mode (sharp/flat)
  const [enharmonicMode, setEnharmonicMode] = useState<import('./utils/enharmonic').EnharmonicMode>('sharp')

  // Fretboard orientation
  const [leftHanded, setLeftHanded] = useState(false)

  // Auto-suggest enharmonic mode when root key changes
  useEffect(() => {
    const key = selectedRoot ?? progressionKey
    if (key) setEnharmonicMode(suggestEnharmonicMode(key))
  }, [selectedRoot, progressionKey])

  // Fretboard zoom (fret range) — reset when instrument changes
  const [fretRange, setFretRange] = useState<[number, number]>([0, instrument.fretCount])
  const [autoZoom, setAutoZoom] = useState(false)
  useEffect(() => {
    setFretRange([0, instrument.fretCount])
  }, [instrument.fretCount])

  // String focus (dim unselected strings)
  const [dimmedStrings, setDimmedStrings] = useState<Set<number>>(new Set())
  const toggleStringDim = useCallback((stringIndex: number) => {
    setDimmedStrings((prev) => {
      const next = new Set(prev)
      if (next.has(stringIndex)) next.delete(stringIndex)
      else next.add(stringIndex)
      return next
    })
  }, [])
  const clearDimmedStrings = useCallback(() => setDimmedStrings(new Set()), [])

  // Shortcut help overlay
  const [showShortcutHelp, setShowShortcutHelp] = useState(false)

  // Refs for backing track getters (avoids circular dependency with useMetronome)
  const chordRootRef = useRef<NoteName | null>(null)
  const bpmRef = useRef(120)
  const getChordRoot = useCallback(() => chordRootRef.current, [])
  const getBpm = useCallback(() => bpmRef.current, [])

  // Backing track (must be before useMetronome so we can pass onBeatSchedule)
  const backingTrack = useBackingTrack(getChordRoot, getBpm)

  // Metronome state (lifted from MetronomePanel)
  const metronome = useMetronome(backingTrack.onBeatSchedule)

  // Restore persisted BPM + beats on mount
  useEffect(() => {
    if (initialSettings.bpm !== 120) metronome.setBpm(initialSettings.bpm)
    if (initialSettings.beatsPerMeasure !== 4) metronome.setBeatsPerMeasure(initialSettings.beatsPerMeasure)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Chord progression state
  const [progressionKey, setProgressionKey] = useState<NoteName | null>(
    (initialSettings.progressionKey as NoteName) ?? null,
  )
  const [progressionPreset, setProgressionPreset] =
    useState<ProgressionPreset | null>(
      resolvePreset(initialSettings.progressionPresetName),
    )
  const [activeChordIndex, setActiveChordIndex] = useState(0)

  // Progression loop control (0 = infinite loop, N = stop after N loops)
  const [loopCount, setLoopCount] = useState(0)

  // Custom progression state
  const [isCustomProgression, setIsCustomProgression] = useState(false)
  const [customSteps, setCustomSteps] = useState<ProgressionStep[]>([
    { degreeIndex: 0 }, // I
    { degreeIndex: 3 }, // IV
    { degreeIndex: 4 }, // V
    { degreeIndex: 0 }, // I
  ])

  const handleCustomToggle = useCallback(() => {
    setIsCustomProgression((v) => {
      const next = !v
      if (next) {
        // Switch to custom: create a preset from customSteps
        onCustomPresetUpdate(customSteps)
      }
      return next
    })
  }, [customSteps]) // eslint-disable-line react-hooks/exhaustive-deps

  const onCustomPresetUpdate = useCallback((steps: ProgressionStep[]) => {
    setCustomSteps(steps)
    if (steps.length > 0) {
      setProgressionPreset({ name: 'Custom', steps })
    } else {
      setProgressionPreset(null)
    }
  }, [])

  const handleCustomStepsChange = useCallback((steps: ProgressionStep[]) => {
    onCustomPresetUpdate(steps)
  }, [onCustomPresetUpdate])

  // Voicing state
  const [voicingMode, setVoicingMode] = useState<VoicingMode>(initialSettings.voicingMode)
  const [voicingSource, setVoicingSource] = useState<VoicingSource>(initialSettings.voicingSource)
  const [voicingIndex, setVoicingIndex] = useState(0)
  const [isOptimized, setIsOptimized] = useState(initialSettings.isOptimized)

  // Persist settings on change (debounced)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      saveSettings({
        bpm: metronome.bpm,
        beatsPerMeasure: metronome.beatsPerMeasure,
        instrumentType: instrument.type as 'guitar' | 'bass',
        instrumentName: instrument.name,
        selectedRoot: selectedRoot,
        selectedDefinitionName: selectedDefinition?.name ?? null,
        mode,
        progressionKey,
        progressionPresetName: progressionPreset?.name ?? null,
        voicingMode,
        voicingSource,
        isOptimized,
      })
    }, 500)
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [
    metronome.bpm, metronome.beatsPerMeasure,
    instrument, selectedRoot, selectedDefinition, mode,
    progressionKey, progressionPreset, voicingMode, voicingSource, isOptimized,
  ])

  // Resolve progression chords
  const resolvedChords = useMemo(() => {
    if (!progressionKey || !progressionPreset) return []
    return resolveProgression(progressionKey, progressionPreset)
  }, [progressionKey, progressionPreset])

  // Active chord info
  const activeChord = resolvedChords[activeChordIndex] ?? null

  // Sync backing track refs
  chordRootRef.current = activeChord?.root ?? null
  bpmRef.current = metronome.bpm

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

  // Auto-zoom fretboard to fit current voicing (when enabled)
  useEffect(() => {
    if (!autoZoom) return
    if (currentVoicing) {
      const frettedFrets = currentVoicing.frets.filter((f) => f > 0)
      if (frettedFrets.length > 0) {
        const min = Math.min(...frettedFrets)
        const max = Math.max(...frettedFrets)
        const hasOpen = currentVoicing.frets.some((f) => f === 0)
        const start = hasOpen ? 0 : Math.max(0, min - 1)
        const end = Math.min(instrument.fretCount, max + 2)
        setFretRange([start, end])
      }
    } else {
      // No voicing — reset to full
      setFretRange([0, instrument.fretCount])
    }
  }, [autoZoom, currentVoicing, instrument.fretCount])

  // Sync activeChordIndex with metronome measure + auto-stop
  useEffect(() => {
    if (resolvedChords.length > 0 && metronome.isPlaying) {
      const loopNum = Math.floor(metronome.currentMeasure / resolvedChords.length)
      // Auto-stop after N loops (loopCount=0 means infinite)
      if (loopCount > 0 && loopNum >= loopCount) {
        metronome.stop()
        return
      }
      isAutoChordChange.current = true
      setActiveChordIndex(metronome.currentMeasure % resolvedChords.length)
    }
  }, [metronome.currentMeasure, metronome.isPlaying, resolvedChords.length, loopCount, metronome.stop])

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

  // Scale suggestions for the active chord
  const scaleSuggestions: ScaleSuggestion[] = useMemo(() => {
    if (!activeChord) return []
    return getScaleSuggestions(activeChord)
  }, [activeChord])

  // Which suggestion is selected for overlay
  const [activeScaleSuggestionIdx, setActiveScaleSuggestionIdx] = useState<number | null>(null)

  // Reset suggestion selection when chord changes
  useEffect(() => {
    setActiveScaleSuggestionIdx(null)
  }, [activeChord?.root, activeChord?.quality])

  // Scale overlay note names (for fretboard amber overlay)
  const scaleOverlayNoteNames: NoteName[] = useMemo(() => {
    if (activeScaleSuggestionIdx === null) return []
    return scaleSuggestions[activeScaleSuggestionIdx]?.noteNames ?? []
  }, [activeScaleSuggestionIdx, scaleSuggestions])

  // Chord tone note names (for highlighting chord tones on fretboard)
  const chordToneNoteNames: NoteName[] = useMemo(() => {
    if (!showChordTones || !activeChord) return []
    return activeChord.notes // root, 3rd, 5th (and 7th if applicable)
  }, [showChordTones, activeChord])

  // Practice target: combine fretboard notes + scale overlay
  const practiceTargetNotes = useMemo(() => {
    const notes = [...fretboardNoteNames, ...scaleOverlayNoteNames]
    return [...new Set(notes)]
  }, [fretboardNoteNames, scaleOverlayNoteNames])

  // Keep practice mode target in sync
  useEffect(() => {
    if (practice.active && practiceTargetNotes.length > 0) {
      practice.updateTarget(practiceTargetNotes)
    }
  }, [practiceTargetNotes]) // eslint-disable-line react-hooks/exhaustive-deps

  // Practice mode toggle handler
  const handlePracticeToggle = useCallback(() => {
    if (practice.active) {
      practice.deactivate()
    } else if (practiceTargetNotes.length > 0) {
      practice.activate(practiceTargetNotes)
    }
  }, [practice, practiceTargetNotes])

  // Keyboard shortcuts (Space=play, ↑↓=BPM, ←→=chord, B=backing, P=practice)
  // Use a ref for bpm to avoid stale closure in the shortcut callbacks
  const bpmForShortcuts = useRef(metronome.bpm)
  bpmForShortcuts.current = metronome.bpm
  const chordsLenRef = useRef(resolvedChords.length)
  chordsLenRef.current = resolvedChords.length

  useKeyboardShortcuts(
    useMemo(
      () => ({
        toggleMetronome: metronome.toggle,
        stopMetronome: metronome.stop,
        increaseBpm: (amt = 5) => metronome.setBpm(bpmForShortcuts.current + amt),
        decreaseBpm: (amt = 5) => metronome.setBpm(bpmForShortcuts.current - amt),
        toggleBackingTrack: backingTrack.toggle,
        nextChord: () => {
          if (chordsLenRef.current > 0) {
            isAutoChordChange.current = true
            setActiveChordIndex((i) => (i + 1) % chordsLenRef.current)
          }
        },
        prevChord: () => {
          if (chordsLenRef.current > 0) {
            isAutoChordChange.current = true
            setActiveChordIndex(
              (i) => (i - 1 + chordsLenRef.current) % chordsLenRef.current,
            )
          }
        },
        togglePracticeMode: handlePracticeToggle,
        toggleShortcutHelp: () => setShowShortcutHelp((v) => !v),
        cycleSubdivision: () => {
          const cycle = [1, 2, 3, 4] as const
          const idx = cycle.indexOf(metronome.subdivision)
          metronome.setSubdivision(cycle[(idx + 1) % 4])
        },
        toggleCountIn: () => metronome.setCountIn(!metronome.countIn),
      }),
      [metronome.toggle, metronome.stop, metronome.setBpm, metronome.subdivision, metronome.setSubdivision, metronome.countIn, metronome.setCountIn, backingTrack.toggle, handlePracticeToggle],
    ),
  )

  const handleNoteClick = useCallback(
    (note: Note) => {
      soundEngine.playFretboardNote(note)

      // When fretboard quiz is active, intercept clicks for quiz answer
      if (fretboardQuizActive && fretboardQuizRef.current) {
        fretboardQuizRef.current.checkAnswer(note.name)
        return // don't toggle highlight during quiz
      }

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
    [soundEngine, fretboardQuizActive],
  )

  const handleProgressionChordClick = useCallback(
    (index: number) => {
      isAutoChordChange.current = true
      setActiveChordIndex(index)
      // Play the voicing or chord tones when clicking a chord block
      const voicings = allProgressionVoicings[index] ?? []
      if (voicings.length > 0) {
        const idx = isOptimized && optimizedIndices.length > 0
          ? (optimizedIndices[index] ?? 0)
          : 0
        const v = voicings[idx]
        if (v) soundEngine.playVoicing(v, instrument)
      }
    },
    [allProgressionVoicings, isOptimized, optimizedIndices, soundEngine, instrument],
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
        {/* Tuning quick-switch */}
        <div className="mb-1.5">
          <TuningQuickSwitch instrument={instrument} onInstrumentChange={setInstrument} />
        </div>
        {/* Fretboard controls bar */}
        <div className="flex items-center gap-1.5 mb-1 flex-wrap">
          <span className="text-xs text-slate-500 mr-1">Labels:</span>
          {(['name', 'interval', 'degree'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setLabelMode(m)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                m === labelMode
                  ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
                  : 'bg-slate-700 text-slate-500 hover:text-slate-300'
              }`}
            >
              {m === 'name' ? 'Note' : m === 'interval' ? 'Interval' : 'Degree'}
            </button>
          ))}
          <button
            onClick={() => setEnharmonicMode((m) => m === 'sharp' ? 'flat' : 'sharp')}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              enharmonicMode === 'flat'
                ? 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
            title={`Show ${enharmonicMode === 'sharp' ? 'flats (♭)' : 'sharps (#)'}`}
          >
            {enharmonicMode === 'sharp' ? '#' : '♭'}
          </button>
          <button
            onClick={() => setHideNoteLabels((v) => !v)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              hideNoteLabels
                ? 'bg-rose-500/20 text-rose-400 ring-1 ring-rose-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
            title="Ghost mode: hide note labels (dots only) for fretboard memorization"
          >
            👻
          </button>
          {activeChord && (
            <button
              onClick={() => setShowChordTones((v) => !v)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                showChordTones
                  ? 'bg-pink-500/20 text-pink-400 ring-1 ring-pink-500/40'
                  : 'bg-slate-700 text-slate-500 hover:text-slate-300'
              }`}
              title="Highlight chord tones (R, 3, 5, 7) with ring indicator"
            >
              CT
            </button>
          )}
          <span className="text-slate-700 mx-1">|</span>
          <button
            onClick={() => setLeftHanded((v) => !v)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              leftHanded
                ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
          >
            {leftHanded ? '🫲 Left' : '🫱 Right'}
          </button>
          <span className="text-slate-700 mx-1">|</span>
          <span className="text-xs text-slate-500">Frets:</span>
          <select
            value={fretRange[0]}
            onChange={(e) => setFretRange(([, end]) => [Number(e.target.value), end])}
            className="bg-slate-700 text-slate-300 text-xs rounded px-1.5 py-0.5 outline-none w-12"
          >
            {Array.from({ length: instrument.fretCount }, (_, i) => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
          <span className="text-xs text-slate-600">-</span>
          <select
            value={fretRange[1]}
            onChange={(e) => setFretRange(([start]) => [start, Number(e.target.value)])}
            className="bg-slate-700 text-slate-300 text-xs rounded px-1.5 py-0.5 outline-none w-12"
          >
            {Array.from({ length: instrument.fretCount + 1 }, (_, i) => (
              <option key={i} value={i} disabled={i <= fretRange[0]}>{i}</option>
            ))}
          </select>
          {(fretRange[0] !== 0 || fretRange[1] !== instrument.fretCount) && (
            <button
              onClick={() => { setFretRange([0, instrument.fretCount]); setAutoZoom(false) }}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Reset
            </button>
          )}
          <button
            onClick={() => setAutoZoom((v) => !v)}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
              autoZoom
                ? 'bg-cyan-500/20 text-cyan-400 ring-1 ring-cyan-500/40'
                : 'bg-slate-700 text-slate-500 hover:text-slate-300'
            }`}
            title="Auto-zoom fretboard to fit current voicing position"
          >
            Auto
          </button>
          {/* String focus toggles */}
          <span className="text-slate-700 mx-1">|</span>
          <span className="text-xs text-slate-500">Strings:</span>
          {instrument.tuning.map((openNote, si) => (
            <button
              key={si}
              onClick={() => toggleStringDim(si)}
              className={`w-6 h-5 rounded text-[10px] font-medium transition-colors ${
                dimmedStrings.has(si)
                  ? 'bg-slate-800 text-slate-600 line-through'
                  : 'bg-slate-700 text-slate-400 hover:text-slate-200'
              }`}
              title={`${dimmedStrings.has(si) ? 'Show' : 'Dim'} string ${si + 1} (${openNote})`}
            >
              {openNote}
            </button>
          ))}
          {dimmedStrings.size > 0 && (
            <button
              onClick={clearDimmedStrings}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              All
            </button>
          )}
        </div>
        <Fretboard
          instrument={instrument}
          highlightedNotes={highlightedNotes}
          scaleNoteNames={fretboardNoteNames}
          rootNote={fretboardRootNote}
          voicingPositions={fretboardVoicingPositions}
          midiNoteName={midiNoteName}
          scaleOverlayNoteNames={scaleOverlayNoteNames}
          patternPositions={patternPositions ?? undefined}
          chordToneNoteNames={chordToneNoteNames}
          labelMode={labelMode}
          enharmonicMode={enharmonicMode}
          leftHanded={leftHanded}
          fretRange={fretRange}
          dimmedStrings={dimmedStrings.size > 0 ? dimmedStrings : undefined}
          hideLabels={hideNoteLabels}
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

      {/* Scale Suggestions (shown when progression is active) */}
      {scaleSuggestions.length > 0 && (
        <ScaleSuggestionPanel
          suggestions={scaleSuggestions}
          activeIndex={activeScaleSuggestionIdx}
          onSelect={setActiveScaleSuggestionIdx}
        />
      )}

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
        voicingFrets={currentVoicing?.frets}
        activeChordName={activeChord?.chordName}
        allVoicings={availableVoicings}
        onPlayVoicing={useCallback((idx: number) => {
          const v = availableVoicings[idx]
          if (v) soundEngine.playVoicing(v, instrument)
        }, [availableVoicings, soundEngine, instrument])}
        loopCount={loopCount}
        onLoopCountChange={setLoopCount}
        isCustom={isCustomProgression}
        onCustomToggle={handleCustomToggle}
        customSteps={customSteps}
        onCustomStepsChange={handleCustomStepsChange}
      />

      {/* Bottom controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetronomePanel
          bpm={metronome.bpm}
          setBpm={metronome.setBpm}
          isPlaying={metronome.isPlaying}
          toggle={metronome.toggle}
          currentBeat={metronome.currentBeat}
          currentMeasure={metronome.currentMeasure}
          beatsPerMeasure={metronome.beatsPerMeasure}
          setBeatsPerMeasure={metronome.setBeatsPerMeasure}
          countIn={metronome.countIn}
          onCountInChange={metronome.setCountIn}
          isCountingIn={metronome.isCountingIn}
          clickSound={metronome.clickSound}
          onClickSoundChange={metronome.setClickSound}
          subdivision={metronome.subdivision}
          onSubdivisionChange={metronome.setSubdivision}
          swing={metronome.swing}
          onSwingChange={metronome.setSwing}
          accentPattern={metronome.accentPattern}
          onAccentPatternChange={metronome.setAccentPattern}
        />
        <BackingTrackPanel
          enabled={backingTrack.enabled}
          drumVolume={backingTrack.drumVolume}
          bassVolume={backingTrack.bassVolume}
          styleIndex={backingTrack.styleIndex}
          styleName={backingTrack.style.name}
          onToggle={backingTrack.toggle}
          onDrumVolumeChange={backingTrack.setDrumVolume}
          onBassVolumeChange={backingTrack.setBassVolume}
          onStyleChange={backingTrack.setStyleIndex}
        />
        <PracticePanel
          active={practice.active}
          stats={practice.stats}
          lastResult={practice.lastResult}
          hasTarget={practiceTargetNotes.length > 0}
          onToggle={handlePracticeToggle}
          onReset={practice.reset}
        />
        <MidiStatus
          isSupported={midi.isSupported}
          isConnected={midi.isConnected}
          devices={midi.devices}
          lastNote={midi.lastNote}
          error={midi.error}
          requestAccess={midi.requestAccess}
        />
        <IntervalTrainerPanel
          active={intervalTrainer.active}
          question={intervalTrainer.question}
          stats={intervalTrainer.stats}
          setIndex={intervalTrainer.setIndex}
          direction={intervalTrainer.direction}
          lastAnswer={intervalTrainer.lastAnswer}
          revealed={intervalTrainer.revealed}
          onStart={intervalTrainer.start}
          onStop={intervalTrainer.stop}
          onSetChange={intervalTrainer.setSetIndex}
          onDirectionChange={intervalTrainer.setDirection}
          onAnswer={intervalTrainer.answer}
          onReplay={intervalTrainer.replay}
          onNext={intervalTrainer.next}
          onReset={intervalTrainer.reset}
        />
      </div>

      {/* Scale Finder */}
      <ScaleFinderPanel
        onScaleSelect={useCallback((root: NoteName, scaleName: string) => {
          setSelectedRoot(root)
          const foundDef = SCALES.find((s) => s.name === scaleName) ?? null
          if (foundDef) {
            setMode('scale')
            setSelectedDefinition(foundDef)
          }
        }, [])}
      />

      {/* Circle of Fifths */}
      <CircleOfFifths
        activeKey={progressionKey ?? selectedRoot}
        onKeySelect={useCallback((key: NoteName) => {
          if (progressionPreset) {
            setProgressionKey(key)
          } else {
            setSelectedRoot(key)
          }
        }, [progressionPreset])}
      />

      {/* Scale Patterns (box shapes) */}
      <ScalePatternPanel
        instrument={instrument}
        selectedRoot={selectedRoot}
        onPatternPositionsChange={setPatternPositions}
      />

      {/* Strum Patterns */}
      <StrumPatternPanel
        currentBeat={metronome.currentBeat}
        beatsPerMeasure={metronome.beatsPerMeasure}
        isPlaying={metronome.isPlaying}
      />

      {/* Tempo Trainer */}
      <TempoTrainerPanel
        currentBpm={metronome.bpm}
        isPlaying={metronome.isPlaying}
        currentMeasure={metronome.currentMeasure}
        onBpmChange={metronome.setBpm}
      />

      {/* Chord Transition Timer */}
      <ChordTransitionTimer
        activeChordName={activeChord?.chordName}
        isPlaying={metronome.isPlaying}
      />

      {/* Fretboard Quiz */}
      <FretboardQuizPanel
        ref={fretboardQuizRef}
        active={fretboardQuizActive}
        onToggle={useCallback(() => setFretboardQuizActive((v) => !v), [])}
      />

      {/* Practice Timer */}
      <PracticeTimerPanel isActive={metronome.isPlaying || practice.active} />

      {/* Practice History (persistent stats) */}
      <PracticeHistoryPanel />

      {/* Help button (fixed bottom-right) */}
      <div className="flex justify-end mt-2">
        <button
          onClick={() => setShowShortcutHelp(true)}
          className="w-8 h-8 rounded-full bg-slate-700 hover:bg-slate-600 text-slate-400 hover:text-slate-200 text-sm font-bold transition-colors"
          aria-label="Show keyboard shortcuts"
          title="Keyboard Shortcuts (?)"
        >
          ?
        </button>
      </div>

      {/* Shortcut Help Overlay */}
      <ShortcutHelpOverlay
        visible={showShortcutHelp}
        onClose={() => setShowShortcutHelp(false)}
      />
    </AppShell>
  )
}

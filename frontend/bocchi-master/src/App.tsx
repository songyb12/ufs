import { useState, useCallback, useMemo, useEffect, useRef, lazy, Suspense } from 'react'
import type { Note, NoteName } from './types/music'
import { AppShell } from './components/layout/AppShell'
import { Fretboard } from './components/fretboard/Fretboard'
import { MetronomePanel } from './components/metronome/MetronomePanel'
import { MidiStatus } from './components/midi/MidiStatus'
import { ScaleSelector } from './components/scale/ScaleSelector'
import { ChordProgressionPanel } from './components/progression/ChordProgressionPanel'
import { useMetronome } from './hooks/useMetronome'
import {
  SCALES,
  CHORDS,
  getScaleNoteNames,
  type ScaleDefinition,
  type ChordDefinition,
  getKeySignature,
  getScaleFormula,
} from './utils/scaleCalculator'
import { useSoundEngine } from './hooks/useSoundEngine'
import { useMidi } from './hooks/useMidi'
import { CHROMATIC_SCALE } from './constants/notes'
import { getScaleSuggestions, type ScaleSuggestion } from './utils/scaleAdvisor'
import { ScaleSuggestionPanel } from './components/scale/ScaleSuggestionPanel'
import { useBackingTrack } from './hooks/useBackingTrack'
import { BackingTrackPanel } from './components/backing/BackingTrackPanel'
import { usePracticeMode } from './hooks/usePracticeMode'
import { useRhythmScore } from './hooks/useRhythmScore'
import { PracticePanel } from './components/practice/PracticePanel'
import { RhythmScorePanel } from './components/practice/RhythmScorePanel'
import { saveSettings } from './utils/storage'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { useIntervalTrainer } from './hooks/useIntervalTrainer'
import { IntervalTrainerPanel } from './components/trainer/IntervalTrainerPanel'
const PracticeHistoryPanel = lazy(() => import('./components/practice/PracticeHistoryPanel').then(m => ({ default: m.PracticeHistoryPanel })))
const WeaknessAnalysisPanel = lazy(() => import('./components/practice/WeaknessAnalysisPanel').then(m => ({ default: m.WeaknessAnalysisPanel })))
const ReminderSharePanel = lazy(() => import('./components/practice/ReminderSharePanel').then(m => ({ default: m.ReminderSharePanel })))
import { ShortcutHelpOverlay } from './components/help/ShortcutHelpOverlay'
import { ScaleFinderPanel } from './components/scale/ScaleFinderPanel'
import { FretboardQuizPanel, type FretboardQuizHandle } from './components/trainer/FretboardQuizPanel'
import { ScalePatternPanel } from './components/scale/ScalePatternPanel'
import { PracticeTimerPanel } from './components/practice/PracticeTimerPanel'
import { suggestEnharmonicMode } from './utils/enharmonic'
import { StrumPatternPanel } from './components/rhythm/StrumPatternPanel'
import { TempoTrainerPanel } from './components/metronome/TempoTrainerPanel'
import { TuningQuickSwitch } from './components/fretboard/TuningQuickSwitch'
import { ChordTransitionTimer } from './components/trainer/ChordTransitionTimer'
import { ChordToneDrillPanel } from './components/trainer/ChordToneDrillPanel'
const CallResponsePanel = lazy(() => import('./components/trainer/CallResponsePanel').then(m => ({ default: m.CallResponsePanel })))
const CircleOfFifths = lazy(() => import('./components/theory/CircleOfFifths').then(m => ({ default: m.CircleOfFifths })))
import { BeatFlash } from './components/metronome/BeatFlash'
import { DroneTonePanel } from './components/practice/DroneTonePanel'
const TunerPanel = lazy(() => import('./components/tuner/TunerPanel').then(m => ({ default: m.TunerPanel })))
import { NoteToast, type NoteToastHandle } from './components/ui/NoteToast'
const CurriculumMode = lazy(() => import('./components/curriculum/CurriculumMode').then(m => ({ default: m.CurriculumMode })))
const OnboardingWizard = lazy(() => import('./components/onboarding/OnboardingWizard').then(m => ({ default: m.OnboardingWizard })))
const SongChordPage = lazy(() => import('./components/song/SongChordPage').then(m => ({ default: m.SongChordPage })))
import { parseChordName } from './utils/transpose'
import { PANEL_TABS, SKILL_PROFILE_OPTIONS } from './utils/panelConfig'
import { CollapsibleSection } from './components/ui/CollapsibleSection'
import { useAppSettings, initialSettings } from './hooks/useAppSettings'
import { useFretboardSettings } from './hooks/useFretboardSettings'
import { useChordProgression } from './hooks/useChordProgression'

function resolveDefinition(
  name: string | null,
  mode: 'scale' | 'chord',
): ScaleDefinition | ChordDefinition | null {
  if (!name) return null
  const pool = mode === 'scale' ? SCALES : CHORDS
  return pool.find((d) => d.name === name) ?? pool[0]
}

export default function App() {
  // ── Extracted hooks ──
  const app = useAppSettings()
  const {
    appMode, switchToFree, switchToCurriculum,
    panelTab, handlePanelTabChange,
    skillProfile, visibleTabs, showPanel, handleSkillProfileChange,
    uiMode, handleUiModeChange, showFlatList,
    showOnboarding, handleOnboardingComplete,
    instrument, setInstrument,
    showShortcutHelp, setShowShortcutHelp,
    beatFlashEnabled, setBeatFlashEnabled,
  } = app

  const fb = useFretboardSettings(instrument)
  const {
    showChordTones, setShowChordTones,
    hideNoteLabels, setHideNoteLabels,
    showFingering, setShowFingering,
    compareScaleIdx, setCompareScaleIdx,
    capo, setCapo,
    effectiveInstrument,
    labelMode, setLabelMode,
    enharmonicMode, setEnharmonicMode,
    leftHanded, setLeftHanded,
    fretRange, setFretRange,
    autoZoom, setAutoZoom,
    fretControlsExpanded, toggleFretControls,
    dimmedStrings, toggleStringDim, clearDimmedStrings,
    patternPositions, setPatternPositions,
  } = fb

  const beginnerMode = uiMode === 'beginner'

  const [highlightedNotes, setHighlightedNotes] = useState<Note[]>([])
  const soundEngine = useSoundEngine()
  const midi = useMidi()
  const practice = usePracticeMode()
  const rhythmScore = useRhythmScore()
  const intervalTrainer = useIntervalTrainer()

  // Note click toast
  const noteToastRef = useRef<NoteToastHandle>(null)

  // Fretboard quiz state
  const [fretboardQuizActive, setFretboardQuizActive] = useState(false)
  const fretboardQuizRef = useRef<FretboardQuizHandle>(null)

  // Derive MIDI active note name for fretboard highlight
  const midiNoteName: NoteName | undefined = useMemo(() => {
    if (!midi.lastNote) return undefined
    return CHROMATIC_SCALE[midi.lastNote.note % 12]
  }, [midi.lastNote])

  // Stable refs for MIDI effect — soundEngine/practice return new object references
  // every render (App re-renders on every metronome beat via currentBeat state),
  // so we use refs to avoid replaying the last MIDI note on every beat tick.
  const soundEngineRef = useRef(soundEngine)
  soundEngineRef.current = soundEngine
  const practiceRef = useRef(practice)
  practiceRef.current = practice

  // Play sound + evaluate practice when MIDI note arrives
  useEffect(() => {
    if (!midi.lastNote) return
    const midiNum = midi.lastNote.note
    const name = CHROMATIC_SCALE[midiNum % 12]
    const octave = Math.floor(midiNum / 12) - 1
    soundEngineRef.current.playFretboardNote({ name, octave, midiNumber: midiNum })
    practiceRef.current.evaluateNote(midiNum)
    rhythmScore.evaluate()
  }, [midi.lastNote, rhythmScore.evaluate])

  // Scale/Chord overlay state
  const [selectedRoot, setSelectedRoot] = useState<NoteName | null>(
    (initialSettings.selectedRoot as NoteName) ?? null,
  )
  const [selectedDefinition, setSelectedDefinition] = useState<
    ScaleDefinition | ChordDefinition | null
  >(resolveDefinition(initialSettings.selectedDefinitionName, initialSettings.mode))
  const [mode, setMode] = useState<'scale' | 'chord'>(initialSettings.mode)

  // Refs for backing track getters (avoids circular dependency with useMetronome)
  const chordRootRef = useRef<NoteName | null>(null)
  const bpmRef = useRef(120)
  const getChordRoot = useCallback(() => chordRootRef.current, [])
  const getBpm = useCallback(() => bpmRef.current, [])

  // Backing track (must be before useMetronome so we can pass onBeatSchedule)
  const backingTrack = useBackingTrack(getChordRoot, getBpm)

  // Combined beat schedule callback: backing track + rhythm scoring
  const rhythmRecordBeatRef = useRef(rhythmScore.recordBeat)
  rhythmRecordBeatRef.current = rhythmScore.recordBeat
  const combinedOnBeatSchedule = useCallback(
    (beat: number, measure: number, time: number, ctx: AudioContext) => {
      backingTrack.onBeatSchedule(beat, measure, time, ctx)
      rhythmRecordBeatRef.current(beat, bpmRef.current)
    },
    [backingTrack.onBeatSchedule],
  )

  // Metronome state (lifted from MetronomePanel)
  const metronome = useMetronome(combinedOnBeatSchedule)

  // Restore persisted BPM + beats on mount
  useEffect(() => {
    if (initialSettings.bpm !== 120) metronome.setBpm(initialSettings.bpm)
    if (initialSettings.beatsPerMeasure !== 4) metronome.setBeatsPerMeasure(initialSettings.beatsPerMeasure)
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only: restores persisted settings once; metronome setters are stable but change identity on each render
  }, [])

  // ── Chord Progression (extracted hook) ──
  const chord = useChordProgression({
    initialSettings,
    effectiveInstrument,
    metronomeIsPlaying: metronome.isPlaying,
    metronomeMeasure: metronome.currentMeasure,
    metronomeStop: metronome.stop,
    showFingering,
    autoZoom,
    setFretRange,
  })
  const {
    progressionKey, setProgressionKey,
    progressionPreset, setProgressionPreset,
    activeChordIndex, setActiveChordIndex,
    loopCount, setLoopCount,
    isCustomProgression, handleCustomToggle,
    customSteps, handleCustomStepsChange,
    resolvedChords, activeChord, activeChordIntervals,
    voicingMode, setVoicingMode,
    voicingSource, setVoicingSource,
    voicingIndex, setVoicingIndex,
    isOptimized, setIsOptimized,
    allProgressionVoicings, availableVoicings,
    optimizedIndices, currentVoicing, fingeringNumbers,
    isAutoChordChange,
  } = chord

  // Auto-suggest enharmonic mode when root key changes
  useEffect(() => {
    const key = selectedRoot ?? progressionKey
    if (key) setEnharmonicMode(suggestEnharmonicMode(key))
  }, [selectedRoot, progressionKey, setEnharmonicMode])

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

  // Sync backing track refs
  chordRootRef.current = activeChord?.root ?? null
  bpmRef.current = metronome.bpm

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

  // Compare scale overlay notes
  const compareScaleNotes: NoteName[] = useMemo(() => {
    if (compareScaleIdx == null || !selectedRoot) return []
    const def = SCALES[compareScaleIdx]
    if (!def) return []
    return getScaleNoteNames(selectedRoot, def)
  }, [compareScaleIdx, selectedRoot])

  // Scale overlay note names (for fretboard amber overlay)
  const scaleOverlayNoteNames: NoteName[] = useMemo(() => {
    // Improv suggestions take priority
    if (activeScaleSuggestionIdx !== null) {
      return scaleSuggestions[activeScaleSuggestionIdx]?.noteNames ?? []
    }
    // Fallback: compare scale overlay
    return compareScaleNotes
  }, [activeScaleSuggestionIdx, scaleSuggestions, compareScaleNotes])

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
  }, [practiceTargetNotes, practice.active, practice.updateTarget])

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
        toggleMute: () => metronome.setVolume(metronome.volume > 0 ? 0 : 0.8),
      }),
      [metronome.toggle, metronome.stop, metronome.setBpm, metronome.subdivision, metronome.setSubdivision, metronome.countIn, metronome.setCountIn, metronome.volume, metronome.setVolume, backingTrack.toggle, handlePracticeToggle],
    ),
  )

  const handleNoteClick = useCallback(
    (note: Note, stringIndex: number, fret: number) => {
      soundEngine.playFretboardNote(note)

      // Show note info toast
      noteToastRef.current?.show(note, stringIndex, fret)

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
        if (v) soundEngine.playVoicing(v, effectiveInstrument)
      }
    },
    [allProgressionVoicings, isOptimized, optimizedIndices, soundEngine, effectiveInstrument],
  )

  // ── Inline useCallback 끌어올림 (조건부 렌더링 안에서 hook 호출 금지) ──
  const handlePlayAvailableVoicing = useCallback((idx: number) => {
    const v = availableVoicings[idx]
    if (v) soundEngine.playVoicing(v, effectiveInstrument)
  }, [availableVoicings, soundEngine, effectiveInstrument])

  const handleScaleFinderSelect = useCallback((root: NoteName, scaleName: string) => {
    setSelectedRoot(root)
    const foundDef = SCALES.find((s) => s.name === scaleName) ?? null
    if (foundDef) {
      setMode('scale')
      setSelectedDefinition(foundDef)
    }
  }, [])

  const handleCircleKeySelect = useCallback((key: NoteName) => {
    if (progressionPreset) {
      setProgressionKey(key)
    } else {
      setSelectedRoot(key)
    }
  }, [progressionPreset])

  const handleFretboardQuizToggle = useCallback(() => setFretboardQuizActive((v) => !v), [])

  // ── Song → Fretboard bridge ──
  const QUALITY_TO_CHORD: Record<string, string> = useMemo(() => ({
    '': 'Major', 'Major': 'Major',
    'm': 'Minor', 'min': 'Minor', 'minor': 'Minor',
    'dim': 'dim', 'aug': 'aug',
    'sus2': 'sus2', 'sus4': 'sus4',
    '7': '7th', '7th': '7th',
    'm7': 'm7', 'min7': 'm7',
    'maj7': 'Maj7', 'M7': 'Maj7', 'Maj7': 'Maj7',
    'mMaj7': 'mMaj7',
    'dim7': 'dim7',
    'm7b5': 'm7b5',
    '7sus4': '7sus4',
    'add9': 'add9', 'madd9': 'madd9',
    '9': '9th', '9th': '9th',
    'm9': 'm9', 'Maj9': 'Maj9',
    '5': '5 (Power)',
  }), [])

  const handleViewOnFretboard = useCallback((chordName: string) => {
    const parsed = parseChordName(chordName)
    if (!parsed) return
    const root = parsed.root as NoteName
    const chordDefName = QUALITY_TO_CHORD[parsed.quality] ?? 'Major'
    const def = CHORDS.find(c => c.name === chordDefName)
    if (!def) return
    setSelectedRoot(root)
    setSelectedDefinition(def)
    setMode('chord')
    handlePanelTabChange('play')
  }, [QUALITY_TO_CHORD, handlePanelTabChange])

  return (
    <>
    {showOnboarding && <Suspense fallback={null}><OnboardingWizard onComplete={handleOnboardingComplete} /></Suspense>}
    <AppShell instrument={instrument} onInstrumentChange={setInstrument}>
      {/* ── Mode Tabs ── */}
      <div className="flex items-center gap-1 mb-4 pb-3 border-b border-slate-700">
        <button
          onClick={switchToFree}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            appMode === 'free'
              ? 'bg-orange-600 text-white'
              : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
          }`}
        >
          🎸 자유 연습
        </button>
        <button
          onClick={switchToCurriculum}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            appMode === 'curriculum'
              ? 'bg-orange-600 text-white'
              : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
          }`}
        >
          📚 커리큘럼
        </button>

        {/* Skill Profile selector — pushed right */}
        {appMode === 'free' && (
          <div className="ml-auto flex items-center gap-0.5 bg-slate-700/50 rounded-lg p-0.5">
            {SKILL_PROFILE_OPTIONS.map(opt => (
              <button
                key={opt.id}
                onClick={() => handleSkillProfileChange(opt.id)}
                className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  skillProfile === opt.id
                    ? 'bg-slate-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                <span className="mr-0.5">{opt.icon}</span>
                <span className="hidden sm:inline">{opt.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Curriculum Mode ── */}
      {appMode === 'curriculum' ? (
        <Suspense fallback={<div className="text-slate-400 text-center py-8">Loading curriculum...</div>}>
          <CurriculumMode onSwitchToFreeMode={switchToFree} />
        </Suspense>
      ) : (
      <>
      {/* Note click info toast */}
      <NoteToast ref={noteToastRef} rootNote={selectedRoot ?? progressionKey ?? undefined} />

      {/* Visual beat flash overlay */}
      <BeatFlash
        currentBeat={metronome.currentBeat}
        isPlaying={metronome.isPlaying}
        enabled={beatFlashEnabled}
      />

      {/* Beginner guide text */}
      {showFlatList && (
        <div className="bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-300">
          <span className="text-orange-400 font-medium">🌱 초급 모드</span>
          <span className="mx-1.5 text-slate-600">|</span>
          루트음과 스케일을 선택하고, 프렛보드에서 음 위치를 확인해보세요. 아래 메트로놈과 퀴즈로 연습할 수 있습니다.
        </div>
      )}

      {/* Scale/Chord selector */}
      <ScaleSelector
        selectedRoot={selectedRoot}
        selectedDefinition={selectedDefinition}
        mode={mode}
        onRootChange={setSelectedRoot}
        onDefinitionChange={setSelectedDefinition}
        onModeChange={setMode}
        beginnerMode={beginnerMode}
      />

      {/* Fretboard */}
      <section>
        {/* Tuning quick-switch */}
        <div className="mb-1.5">
          <TuningQuickSwitch instrument={instrument} onInstrumentChange={setInstrument} />
        </div>
        {/* Fretboard controls bar — Row 1: core controls */}
        <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
          <span className="text-xs text-slate-500 mr-1">Labels:</span>
          {(beginnerMode ? (['name'] as const) : (['name', 'interval', 'degree'] as const)).map((m) => (
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
          {!beginnerMode && (
            <>
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
            </>
          )}
          <span className="text-xs text-slate-500">Frets:</span>
          <select
            value={fretRange[0]}
            onChange={(e) => setFretRange(([, end]) => [Number(e.target.value), end])}
            className="bg-slate-700 text-slate-300 text-xs rounded px-1.5 py-0.5 outline-none w-12"
          >
            {Array.from({ length: effectiveInstrument.fretCount }, (_, i) => (
              <option key={i} value={i}>{i}</option>
            ))}
          </select>
          <span className="text-xs text-slate-600">-</span>
          <select
            value={fretRange[1]}
            onChange={(e) => setFretRange(([start]) => [start, Number(e.target.value)])}
            className="bg-slate-700 text-slate-300 text-xs rounded px-1.5 py-0.5 outline-none w-12"
          >
            {Array.from({ length: effectiveInstrument.fretCount + 1 }, (_, i) => (
              <option key={i} value={i} disabled={i <= fretRange[0]}>{i}</option>
            ))}
          </select>
          {(fretRange[0] !== 0 || fretRange[1] !== effectiveInstrument.fretCount) && (
            <button
              onClick={() => { setFretRange([0, effectiveInstrument.fretCount]); setAutoZoom(false) }}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Reset
            </button>
          )}
          {!beginnerMode && (
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
          )}
          {/* Toggle for Row 2 */}
          {!beginnerMode && (
            <button
              onClick={toggleFretControls}
              className="ml-auto px-1.5 py-0.5 rounded text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors"
              title={fretControlsExpanded ? '컨트롤 접기' : '더보기'}
            >
              <svg className={`w-3.5 h-3.5 transition-transform ${fretControlsExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}
        </div>
        {/* Fretboard controls bar — Row 2: secondary controls (collapsible) */}
        {fretControlsExpanded && !beginnerMode && (
          <div className="flex items-center gap-1.5 mb-1 flex-wrap pl-1">
            <button
              onClick={() => setHideNoteLabels((v) => !v)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                hideNoteLabels
                  ? 'bg-rose-500/20 text-rose-400 ring-1 ring-rose-500/40'
                  : 'bg-slate-700 text-slate-500 hover:text-slate-300'
              }`}
              title="Ghost mode: hide note labels (dots only) for fretboard memorization"
            >
              👻 Ghost
            </button>
            {currentVoicing && (
              <button
                onClick={() => setShowFingering((v) => !v)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  showFingering
                    ? 'bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/40'
                    : 'bg-slate-700 text-slate-500 hover:text-slate-300'
                }`}
                title="Show suggested fingering numbers (1-4)"
              >
                1234
              </button>
            )}
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
            <span className="text-xs text-slate-500">Capo:</span>
            <select
              value={capo}
              onChange={(e) => setCapo(Number(e.target.value))}
              className={`text-xs rounded px-1.5 py-0.5 outline-none w-12 ${
                capo > 0
                  ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40'
                  : 'bg-slate-700 text-slate-300'
              }`}
            >
              <option value={0}>Off</option>
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>{i + 1}</option>
              ))}
            </select>
            <span className="text-slate-700 mx-1">|</span>
            <span className="text-xs text-slate-500">Strings:</span>
            {effectiveInstrument.tuning.map((openNote, si) => (
              <button
                key={si}
                onClick={() => toggleStringDim(si)}
                className={`w-6 h-5 rounded text-[10px] font-medium transition-colors ${
                  dimmedStrings.has(si)
                    ? 'bg-slate-800 text-slate-600 line-through'
                    : 'bg-slate-700 text-slate-400 hover:text-slate-200'
                }`}
                title={`${dimmedStrings.has(si) ? 'Show' : 'Dim'} string ${si + 1} (${openNote.name})`}
              >
                {openNote.name}
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
        )}
        {/* Compare scale overlay selector */}
        {!beginnerMode && selectedRoot && selectedDefinition && (
          <div className="flex items-center gap-1.5 px-1 py-0.5">
            <span className="text-[10px] text-slate-600">Compare:</span>
            <select
              value={compareScaleIdx ?? ''}
              onChange={(e) => setCompareScaleIdx(e.target.value === '' ? null : Number(e.target.value))}
              className="bg-slate-700/50 text-slate-400 text-[10px] rounded px-1.5 py-0.5 outline-none border border-slate-700"
            >
              <option value="">None</option>
              {SCALES.map((s, i) => (
                <option key={s.name} value={i} disabled={s.name === selectedDefinition.name}>
                  {s.name}
                </option>
              ))}
            </select>
            {compareScaleIdx != null && (
              <span className="text-[10px] text-amber-500/60">
                ({compareScaleNotes.length} notes, amber overlay)
              </span>
            )}
          </div>
        )}
        {/* Current chord/scale name overlay + key signature */}
        {(activeChord || (selectedRoot && selectedDefinition)) && (() => {
          const keyRoot = progressionKey ?? selectedRoot
          const isMinor = activeChord
            ? activeChord.quality === 'Minor' || activeChord.quality === 'm7'
            : selectedDefinition?.name.toLowerCase().includes('minor') ?? false
          const keySig = keyRoot ? getKeySignature(keyRoot, isMinor) : null
          return (
            <div className="flex items-center gap-2 px-1 py-0.5">
              {activeChord ? (
                <>
                  <span className="text-lg font-bold text-white">
                    {activeChord.chordName}
                  </span>
                  {currentVoicing && (
                    <span className="text-xs text-slate-500">{currentVoicing.name}</span>
                  )}
                  <span className="text-[10px] text-slate-600">
                    ({activeChordIndex + 1}/{resolvedChords.length})
                  </span>
                </>
              ) : (
                <>
                  <span className="text-sm font-semibold text-slate-400">
                    {selectedRoot} {selectedDefinition?.name}
                  </span>
                  {selectedDefinition && (
                    <span className="text-[10px] text-slate-600 font-mono">
                      {getScaleFormula(selectedDefinition)}
                    </span>
                  )}
                </>
              )}
              {keySig && (keySig.sharps.length > 0 || keySig.flats.length > 0) && (
                <span className="text-[10px] text-amber-500/70 ml-1">
                  {keySig.sharps.length > 0
                    ? `${keySig.sharps.length}# (${keySig.sharps.join(' ')})`
                    : `${keySig.flats.length}♭ (${keySig.flats.join(' ')})`}
                </span>
              )}
              {keySig && keySig.sharps.length === 0 && keySig.flats.length === 0 && keyRoot && (
                <span className="text-[10px] text-emerald-500/70 ml-1">no #/♭</span>
              )}
            </div>
          )
        })()}
        <Fretboard
          instrument={effectiveInstrument}
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
          fingeringNumbers={fingeringNumbers}
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

      {/* Scale Suggestions (shown when progression is active — always visible) */}
      {scaleSuggestions.length > 0 && (
        <ScaleSuggestionPanel
          suggestions={scaleSuggestions}
          activeIndex={activeScaleSuggestionIdx}
          onSelect={setActiveScaleSuggestionIdx}
        />
      )}

      {/* ── Panel Tab Bar (hidden only for advanced+beginner flat list) ── */}
      {!showFlatList && (
        <div className="flex items-center gap-1 bg-slate-800/80 backdrop-blur-sm rounded-xl p-1 sticky top-0 z-10">
          <div className="flex gap-1 flex-1">
            {PANEL_TABS.filter(tab => visibleTabs.includes(tab.id)).map(tab => (
              <button
                key={tab.id}
                onClick={() => handlePanelTabChange(tab.id)}
                className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-colors ${
                  panelTab === tab.id
                    ? 'bg-orange-600 text-white shadow-lg shadow-orange-600/20'
                    : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700/50'
                }`}
              >
                <span>{tab.icon}</span>
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            ))}
          </div>
          {/* UI Mode toggle */}
          <button
            onClick={() => handleUiModeChange(uiMode === 'beginner' ? 'advanced' : 'beginner')}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-colors whitespace-nowrap ${
              uiMode === 'beginner'
                ? 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30'
                : 'bg-slate-700/60 text-slate-400 hover:bg-slate-700'
            }`}
            title={uiMode === 'beginner' ? '고급 모드로 전환' : '초보자 모드로 전환'}
          >
            <span>{uiMode === 'beginner' ? '🌱' : '🌳'}</span>
            <span className="hidden sm:inline">{uiMode === 'beginner' ? '초보자' : '고급'}</span>
          </button>
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          TAB: 🎵 진행/반주 (play)
          ══════════════════════════════════════════════════ */}
      {(showFlatList || panelTab === 'play') && (
        <div className="space-y-4">
          {/* Chord Progression */}
          {showPanel('chordProgression') && <CollapsibleSection title="Chord Progression" icon="🎸" defaultExpanded>
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
              onPlayVoicing={handlePlayAvailableVoicing}
              loopCount={loopCount}
              onLoopCountChange={setLoopCount}
              isCustom={isCustomProgression}
              onCustomToggle={handleCustomToggle}
              customSteps={customSteps}
              onCustomStepsChange={handleCustomStepsChange}
            />
          </CollapsibleSection>}

          {showPanel('metronome') && <CollapsibleSection title="Metronome" icon="🥁" defaultExpanded>
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
              beatFlash={beatFlashEnabled}
              onBeatFlashChange={setBeatFlashEnabled}
              volume={metronome.volume}
              onVolumeChange={metronome.setVolume}
              beginnerMode={beginnerMode}
            />
          </CollapsibleSection>}
          {showPanel('backingTrack') && <CollapsibleSection title="Backing Track" icon="🎶">
            <BackingTrackPanel
              enabled={backingTrack.enabled}
              drumVolume={backingTrack.drumVolume}
              bassVolume={backingTrack.bassVolume}
              styleIndex={backingTrack.styleIndex}
              onToggle={backingTrack.toggle}
              onDrumVolumeChange={backingTrack.setDrumVolume}
              onBassVolumeChange={backingTrack.setBassVolume}
              onStyleChange={backingTrack.setStyleIndex}
            />
          </CollapsibleSection>}

          {showPanel('strumPattern') && <StrumPatternPanel
            currentBeat={metronome.currentBeat}
            beatsPerMeasure={metronome.beatsPerMeasure}
            isPlaying={metronome.isPlaying}
          />}

          {showPanel('tempoTrainer') && <TempoTrainerPanel
            currentBpm={metronome.bpm}
            isPlaying={metronome.isPlaying}
            currentMeasure={metronome.currentMeasure}
            onBpmChange={metronome.setBpm}
          />}
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          TAB: 🎯 연습/드릴 (drill)
          ══════════════════════════════════════════════════ */}
      {(showFlatList || panelTab === 'drill') && (
        <div className="space-y-4">
          {showPanel('practice') && <CollapsibleSection title="Practice Mode" icon="🎯" defaultExpanded>
            <PracticePanel
              active={practice.active}
              stats={practice.stats}
              lastResult={practice.lastResult}
              hasTarget={practiceTargetNotes.length > 0}
              onToggle={handlePracticeToggle}
              onReset={practice.reset}
            />
          </CollapsibleSection>}
          {showPanel('rhythmScore') && <CollapsibleSection title="Rhythm Score" icon="🥁">
            <RhythmScorePanel
              active={rhythmScore.active}
              stats={rhythmScore.stats}
              lastHit={rhythmScore.lastHit}
              isMetronomePlaying={metronome.isPlaying}
              onStart={rhythmScore.start}
              onStop={rhythmScore.stop}
              onReset={rhythmScore.reset}
            />
          </CollapsibleSection>}

          {showPanel('chordTransition') && <ChordTransitionTimer
            activeChordName={activeChord?.chordName}
            isPlaying={metronome.isPlaying}
          />}

          {showPanel('chordToneDrill') && <CollapsibleSection title="Chord Tone Drill" icon="🎹">
            <ChordToneDrillPanel
              chordRoot={activeChord?.root ?? null}
              chordQuality={activeChord?.quality ?? null}
              chordName={activeChord?.chordName ?? null}
              chordNotes={activeChord?.notes ?? []}
              chordIntervals={activeChordIntervals}
              midiConnected={midi.isConnected}
              lastMidiNote={midi.lastNote}
            />
          </CollapsibleSection>}

          {showPanel('callResponse') && <Suspense fallback={null}><CallResponsePanel
            midiConnected={midi.isConnected}
            lastMidiNote={midi.lastNote}
          /></Suspense>}

          {showPanel('fretboardQuiz') && <FretboardQuizPanel
            ref={fretboardQuizRef}
            active={fretboardQuizActive}
            onToggle={handleFretboardQuizToggle}
          />}

          {showPanel('intervalTrainer') && <CollapsibleSection title="Interval Trainer" icon="🎵">
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
          </CollapsibleSection>}
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          TAB: 📖 이론 (theory)
          ══════════════════════════════════════════════════ */}
      {(showFlatList || panelTab === 'theory') && (
        <div className="space-y-4">
          {showPanel('scaleFinder') && <ScaleFinderPanel
            onScaleSelect={handleScaleFinderSelect}
          />}

          {showPanel('circleOfFifths') && <Suspense fallback={null}><CircleOfFifths
            activeKey={progressionKey ?? selectedRoot}
            onKeySelect={handleCircleKeySelect}
          /></Suspense>}

          {showPanel('scalePattern') && <ScalePatternPanel
            instrument={instrument}
            selectedRoot={selectedRoot}
            onPatternPositionsChange={setPatternPositions}
          />}

          {showPanel('droneTone') && <DroneTonePanel activeRoot={progressionKey ?? selectedRoot} />}
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          TAB: 🔧 도구 (tools)
          ══════════════════════════════════════════════════ */}
      {(showFlatList || panelTab === 'tools') && (
        <div className="space-y-4">
          {showPanel('tuner') && <Suspense fallback={null}><TunerPanel instrument={effectiveInstrument} /></Suspense>}

          {showPanel('midiStatus') && <CollapsibleSection title="MIDI Status" icon="🎹">
            <MidiStatus
              isSupported={midi.isSupported}
              isConnected={midi.isConnected}
              devices={midi.devices}
              lastNote={midi.lastNote}
              error={midi.error}
              requestAccess={midi.requestAccess}
            />
          </CollapsibleSection>}

          {showPanel('practiceTimer') && <PracticeTimerPanel isActive={metronome.isPlaying || practice.active} />}
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          TAB: 📊 분석 (stats)
          ══════════════════════════════════════════════════ */}
      {(showFlatList || panelTab === 'stats') && (
        <div className="space-y-4">
          <Suspense fallback={null}>
            {showPanel('weaknessAnalysis') && <WeaknessAnalysisPanel />}

            {showPanel('reminderShare') && <ReminderSharePanel />}

            {showPanel('practiceHistory') && <PracticeHistoryPanel />}
          </Suspense>
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          TAB: 🎶 곡 (song)
          ══════════════════════════════════════════════════ */}
      {panelTab === 'song' && (
        <Suspense fallback={null}>
          <SongChordPage onViewOnFretboard={handleViewOnFretboard} />
        </Suspense>
      )}

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
      </>
      )}
    </AppShell>
    </>
  )
}

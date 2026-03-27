import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import type { InstrumentConfig, NoteName } from '../types/music'
import type { VoicingMode, VoicingSource } from '../components/progression/ChordProgressionPanel'
import {
  resolveProgression,
  PROGRESSION_PRESETS,
  type ProgressionPreset,
  type ProgressionStep,
} from '../utils/chordProgression'
import { CHORDS } from '../utils/scaleCalculator'
import { getCAGEDVoicings, suggestFingering, type ChordVoicing } from '../utils/voicingLibrary'
import { generateVoicings } from '../utils/voicingGenerator'
import { optimizeProgressionVoicings } from '../utils/voicingOptimizer'

interface UseChordProgressionOptions {
  initialSettings: {
    progressionKey: string | null
    progressionPresetName: string | null
    voicingMode: VoicingMode
    voicingSource: VoicingSource
    isOptimized: boolean
  }
  effectiveInstrument: InstrumentConfig
  metronomeIsPlaying: boolean
  metronomeMeasure: number
  metronomeStop: () => void
  showFingering: boolean
  autoZoom: boolean
  setFretRange: (fn: [number, number] | ((prev: [number, number]) => [number, number])) => void
}

function resolvePreset(name: string | null): ProgressionPreset | null {
  if (!name) return null
  return PROGRESSION_PRESETS.find((p) => p.name === name) ?? null
}

export function useChordProgression(opts: UseChordProgressionOptions) {
  const {
    initialSettings, effectiveInstrument,
    metronomeIsPlaying, metronomeMeasure, metronomeStop,
    showFingering, autoZoom, setFretRange,
  } = opts

  // Chord progression state
  const [progressionKey, setProgressionKey] = useState<NoteName | null>(
    (initialSettings.progressionKey as NoteName) ?? null,
  )
  const [progressionPreset, setProgressionPreset] = useState<ProgressionPreset | null>(
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

  const onCustomPresetUpdate = useCallback((steps: ProgressionStep[]) => {
    setCustomSteps(steps)
    if (steps.length > 0) {
      setProgressionPreset({ name: 'Custom', steps })
    } else {
      setProgressionPreset(null)
    }
  }, [])

  const handleCustomToggle = useCallback(() => {
    setIsCustomProgression((v) => {
      const next = !v
      if (next) {
        onCustomPresetUpdate(customSteps)
      }
      return next
    })
  }, [customSteps, onCustomPresetUpdate])

  const handleCustomStepsChange = useCallback((steps: ProgressionStep[]) => {
    onCustomPresetUpdate(steps)
  }, [onCustomPresetUpdate])

  // Voicing state
  const [voicingMode, setVoicingMode] = useState<VoicingMode>(initialSettings.voicingMode)
  const [voicingSource, setVoicingSource] = useState<VoicingSource>(initialSettings.voicingSource)
  const [voicingIndex, setVoicingIndex] = useState(0)
  const [isOptimized, setIsOptimized] = useState(initialSettings.isOptimized)

  // Resolve progression chords
  const resolvedChords = useMemo(() => {
    if (!progressionKey || !progressionPreset) return []
    return resolveProgression(progressionKey, progressionPreset)
  }, [progressionKey, progressionPreset])

  // Active chord info
  const activeChord = resolvedChords[activeChordIndex] ?? null

  // Active chord intervals for chord tone drill
  const activeChordIntervals = useMemo(() => {
    if (!activeChord) return []
    const def = CHORDS.find(c => c.name === activeChord.quality)
    return def?.intervals ?? [0, 4, 7]
  }, [activeChord])

  // Compute available voicings for ALL chords in the progression
  const allProgressionVoicings: ChordVoicing[][] = useMemo(() => {
    return resolvedChords.map((chord) => {
      if (voicingSource === 'caged') {
        return getCAGEDVoicings(chord.root, chord.quality, effectiveInstrument)
      }
      return generateVoicings(chord.root, chord.quality, effectiveInstrument)
    })
  }, [resolvedChords, voicingSource, effectiveInstrument])

  // Available voicings for the currently active chord
  const availableVoicings = allProgressionVoicings[activeChordIndex] ?? []

  // DP-optimized voicing indices for the entire progression
  const optimizedIndices = useMemo(() => {
    if (allProgressionVoicings.length === 0) return []
    return optimizeProgressionVoicings(allProgressionVoicings)
  }, [allProgressionVoicings])

  // Track whether chord change was auto (metronome) vs manual
  const isAutoChordChange = useRef(false)

  // When active chord or voicing source changes, apply optimized index if optimization is ON
  useEffect(() => {
    if (isOptimized && optimizedIndices.length > 0) {
      const optIdx = optimizedIndices[activeChordIndex] ?? 0
      setVoicingIndex(optIdx)
    } else if (isAutoChordChange.current) {
      setVoicingIndex(0)
    }
    isAutoChordChange.current = false
  }, [activeChordIndex, isOptimized, optimizedIndices, voicingSource])

  // Clamp voicingIndex when voicing list changes
  useEffect(() => {
    if (availableVoicings.length > 0 && voicingIndex >= availableVoicings.length) {
      setVoicingIndex(0)
    }
  }, [availableVoicings.length, voicingIndex])

  // Current voicing
  const currentVoicing =
    voicingMode === 'voicing' && availableVoicings.length > 0
      ? availableVoicings[voicingIndex] ?? null
      : null

  // Suggested fingering for current voicing
  const fingeringNumbers = useMemo(() => {
    if (!showFingering || !currentVoicing) return undefined
    return suggestFingering(currentVoicing)
  }, [showFingering, currentVoicing])

  // Auto-zoom fretboard to fit current voicing
  useEffect(() => {
    if (!autoZoom) return
    if (currentVoicing) {
      const frettedFrets = currentVoicing.frets.filter((f) => f > 0)
      if (frettedFrets.length > 0) {
        const min = Math.min(...frettedFrets)
        const max = Math.max(...frettedFrets)
        const hasOpen = currentVoicing.frets.some((f) => f === 0)
        const start = hasOpen ? 0 : Math.max(0, min - 1)
        const end = Math.min(effectiveInstrument.fretCount, max + 2)
        setFretRange([start, end])
      }
    } else {
      setFretRange([0, effectiveInstrument.fretCount])
    }
  }, [autoZoom, currentVoicing, effectiveInstrument.fretCount, setFretRange])

  // Sync activeChordIndex with metronome measure + auto-stop
  useEffect(() => {
    if (resolvedChords.length > 0 && metronomeIsPlaying) {
      const loopNum = Math.floor(metronomeMeasure / resolvedChords.length)
      if (loopCount > 0 && loopNum >= loopCount) {
        metronomeStop()
        return
      }
      isAutoChordChange.current = true
      setActiveChordIndex(metronomeMeasure % resolvedChords.length)
    }
  }, [metronomeMeasure, metronomeIsPlaying, resolvedChords.length, loopCount, metronomeStop])

  // Reset activeChordIndex when progression changes
  useEffect(() => {
    isAutoChordChange.current = true
    setActiveChordIndex(0)
  }, [progressionKey, progressionPreset])

  return {
    // Progression
    progressionKey, setProgressionKey,
    progressionPreset, setProgressionPreset,
    activeChordIndex, setActiveChordIndex,
    loopCount, setLoopCount,
    isCustomProgression, handleCustomToggle,
    customSteps, handleCustomStepsChange,
    resolvedChords, activeChord, activeChordIntervals,
    // Voicing
    voicingMode, setVoicingMode,
    voicingSource, setVoicingSource,
    voicingIndex, setVoicingIndex,
    isOptimized, setIsOptimized,
    allProgressionVoicings, availableVoicings,
    optimizedIndices, currentVoicing, fingeringNumbers,
    isAutoChordChange,
  }
}

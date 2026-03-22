import { useState, useCallback, useEffect, useMemo } from 'react'
import type { InstrumentConfig } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'
import type { NoteLabelMode } from '../utils/noteLabelFormatter'
import type { EnharmonicMode } from '../utils/enharmonic'

const FRETBOARD_CONTROLS_KEY = 'bocchi-fretboard-controls-expanded'

export function useFretboardSettings(instrument: InstrumentConfig) {
  // Chord tone highlighting toggle
  const [showChordTones, setShowChordTones] = useState(false)

  // Ghost mode: hide note labels (dots only)
  const [hideNoteLabels, setHideNoteLabels] = useState(false)

  // Fingering numbers overlay
  const [showFingering, setShowFingering] = useState(false)

  // Scale comparison: overlay a second scale on the fretboard
  const [compareScaleIdx, setCompareScaleIdx] = useState<number | null>(null)

  // Capo position (0 = no capo, 1-12 = capo at that fret)
  const [capo, setCapo] = useState(0)

  // Capo-adjusted instrument: shifts tuning up by capo semitones
  const effectiveInstrument = useMemo<InstrumentConfig>(() => {
    if (capo === 0) return instrument
    return {
      ...instrument,
      tuning: instrument.tuning.map((note) => ({
        name: CHROMATIC_SCALE[(note.midiNumber + capo) % 12],
        octave: Math.floor((note.midiNumber + capo) / 12) - 1,
        midiNumber: note.midiNumber + capo,
      })),
      fretCount: instrument.fretCount - capo,
    }
  }, [instrument, capo])

  // Note label mode (name / interval / degree)
  const [labelMode, setLabelMode] = useState<NoteLabelMode>('name')

  // Enharmonic display mode (sharp/flat)
  const [enharmonicMode, setEnharmonicMode] = useState<EnharmonicMode>('sharp')

  // Fretboard orientation
  const [leftHanded, setLeftHanded] = useState(false)

  // Fretboard zoom (fret range)
  const [fretRange, setFretRange] = useState<[number, number]>([0, effectiveInstrument.fretCount])
  const [autoZoom, setAutoZoom] = useState(false)

  // Fretboard controls bar: 2-tier expand/collapse
  const [fretControlsExpanded, setFretControlsExpanded] = useState(
    () => localStorage.getItem(FRETBOARD_CONTROLS_KEY) === 'true',
  )
  const toggleFretControls = useCallback(() => {
    setFretControlsExpanded(prev => {
      const next = !prev
      localStorage.setItem(FRETBOARD_CONTROLS_KEY, String(next))
      return next
    })
  }, [])

  // Reset fret range when instrument or capo changes
  useEffect(() => {
    setFretRange([0, effectiveInstrument.fretCount])
  }, [effectiveInstrument.fretCount])

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

  // Scale pattern positions (for box shapes on fretboard)
  const [patternPositions, setPatternPositions] = useState<{ stringIndex: number; fret: number }[] | null>(null)

  return {
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
  }
}

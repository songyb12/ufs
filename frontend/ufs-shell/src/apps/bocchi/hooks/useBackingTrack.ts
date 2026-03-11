import { useState, useCallback, useRef } from 'react'
import type { NoteName } from '../types/music'
import {
  BACKING_STYLES,
  schedulePatternBeat,
  type StylePattern,
} from '../utils/backingPatterns'

export interface BackingTrackState {
  enabled: boolean
  drumVolume: number
  bassVolume: number
  style: StylePattern
  styleIndex: number
  toggle: () => void
  setDrumVolume: (v: number) => void
  setBassVolume: (v: number) => void
  setStyleIndex: (idx: number) => void
  onBeatSchedule: (beat: number, measure: number, time: number, ctx: AudioContext) => void
}

/**
 * Backing track hook: provides a beat schedule callback for drums + bass.
 * Pass the returned onBeatSchedule to useMetronome's externalOnBeatSchedule.
 *
 * @param getChordRoot - function returning the current chord root note name
 * @param getBpm - function returning current BPM (for bass duration calc)
 */
export function useBackingTrack(
  getChordRoot: () => NoteName | null,
  getBpm: () => number,
): BackingTrackState {
  const [enabled, setEnabled] = useState(false)
  const [drumVolume, setDrumVolume] = useState(0.6)
  const [bassVolume, setBassVolume] = useState(0.5)
  const [styleIndex, setStyleIndex] = useState(0)

  // Use refs to avoid stale closures in the schedule callback
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled
  const drumVolRef = useRef(drumVolume)
  drumVolRef.current = drumVolume
  const bassVolRef = useRef(bassVolume)
  bassVolRef.current = bassVolume
  const styleRef = useRef(styleIndex)
  styleRef.current = styleIndex

  const toggle = useCallback(() => setEnabled((v) => !v), [])

  const style = BACKING_STYLES[styleIndex] ?? BACKING_STYLES[0]

  const onBeatSchedule = useCallback(
    (beat: number, _measure: number, time: number, ctx: AudioContext) => {
      if (!enabledRef.current) return

      const currentStyle = BACKING_STYLES[styleRef.current] ?? BACKING_STYLES[0]
      const secondsPerBeat = 60.0 / getBpm()

      schedulePatternBeat(
        ctx,
        currentStyle,
        beat,
        time,
        secondsPerBeat,
        getChordRoot(),
        drumVolRef.current,
        bassVolRef.current,
      )
    },
    [getChordRoot, getBpm],
  )

  return {
    enabled,
    drumVolume,
    bassVolume,
    style,
    styleIndex,
    toggle,
    setDrumVolume,
    setBassVolume,
    setStyleIndex,
    onBeatSchedule,
  }
}

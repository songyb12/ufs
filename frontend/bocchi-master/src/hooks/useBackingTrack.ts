import { useState, useCallback, useRef } from 'react'
import type { NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'
import {
  scheduleKick,
  scheduleSnare,
  scheduleHihat,
  scheduleBassNote,
} from '../utils/drumSynth'

interface BackingTrackState {
  enabled: boolean
  drumVolume: number
  bassVolume: number
  toggle: () => void
  setDrumVolume: (v: number) => void
  setBassVolume: (v: number) => void
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

  // Use refs to avoid stale closures in the schedule callback
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled
  const drumVolRef = useRef(drumVolume)
  drumVolRef.current = drumVolume
  const bassVolRef = useRef(bassVolume)
  bassVolRef.current = bassVolume

  const toggle = useCallback(() => setEnabled((v) => !v), [])

  const onBeatSchedule = useCallback(
    (beat: number, _measure: number, time: number, ctx: AudioContext) => {
      if (!enabledRef.current) return

      const dv = drumVolRef.current
      const bv = bassVolRef.current
      const secondsPerBeat = 60.0 / getBpm()

      // Drum pattern (4/4): kick+hihat on 1&3, snare+hihat on 2&4
      if (beat === 0 || beat === 2) {
        scheduleKick(ctx, time, dv)
        scheduleHihat(ctx, time, false, dv * 0.5)
      } else {
        scheduleSnare(ctx, time, dv * 0.8)
        scheduleHihat(ctx, time, false, dv * 0.5)
      }

      // Bass: root on beat 1 (2 beats), root on beat 3 (1 beat)
      const root = getChordRoot()
      if (root && bv > 0) {
        const rootIdx = CHROMATIC_SCALE.indexOf(root)
        // Bass octave: C2 region (MIDI 36 = C2)
        const bassMidi = 36 + rootIdx
        if (beat === 0) {
          scheduleBassNote(ctx, bassMidi, time, secondsPerBeat * 2, bv)
        } else if (beat === 2) {
          scheduleBassNote(ctx, bassMidi, time, secondsPerBeat, bv)
        }
      }
    },
    [getChordRoot, getBpm],
  )

  return {
    enabled,
    drumVolume,
    bassVolume,
    toggle,
    setDrumVolume,
    setBassVolume,
    onBeatSchedule,
  }
}

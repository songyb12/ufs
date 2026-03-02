import { useState, useRef, useCallback } from 'react'
import { AudioScheduler } from '../utils/audioScheduler'
import { useAudioContext } from './useAudioContext'

export function useMetronome() {
  const { ensureResumed } = useAudioContext()
  const schedulerRef = useRef<AudioScheduler | null>(null)

  const [bpm, setBpmState] = useState(120)
  const [beatsPerMeasure, setBeatsPerMeasureState] = useState(4)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentBeat, setCurrentBeat] = useState(-1)

  const start = useCallback(async () => {
    const ctx = await ensureResumed()

    if (schedulerRef.current) {
      schedulerRef.current.stop()
    }

    schedulerRef.current = new AudioScheduler(ctx, bpm, beatsPerMeasure, {
      onBeat: (beat) => setCurrentBeat(beat),
    })
    schedulerRef.current.start()
    setIsPlaying(true)
  }, [bpm, beatsPerMeasure, ensureResumed])

  const stop = useCallback(() => {
    schedulerRef.current?.stop()
    schedulerRef.current = null
    setIsPlaying(false)
    setCurrentBeat(-1)
  }, [])

  const toggle = useCallback(() => {
    if (isPlaying) stop()
    else start()
  }, [isPlaying, start, stop])

  const setBpm = useCallback(
    (newBpm: number) => {
      const clamped = Math.max(40, Math.min(240, newBpm))
      setBpmState(clamped)
      schedulerRef.current?.setBpm(clamped)
    },
    [],
  )

  const setBeatsPerMeasure = useCallback(
    (beats: number) => {
      setBeatsPerMeasureState(beats)
      schedulerRef.current?.setBeatsPerMeasure(beats)
    },
    [],
  )

  return {
    bpm,
    setBpm,
    isPlaying,
    start,
    stop,
    toggle,
    currentBeat,
    beatsPerMeasure,
    setBeatsPerMeasure,
  }
}

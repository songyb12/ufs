import { useState, useRef, useCallback } from 'react'
import { AudioScheduler } from '../utils/audioScheduler'
import { getSharedAudioContext } from '../utils/audioContextSingleton'

export function useMetronome(
  externalOnBeatSchedule?: (
    beat: number,
    measure: number,
    time: number,
    ctx: AudioContext,
  ) => void,
) {
  const schedulerRef = useRef<AudioScheduler | null>(null)

  const [bpm, setBpmState] = useState(120)
  const [beatsPerMeasure, setBeatsPerMeasureState] = useState(4)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentBeat, setCurrentBeat] = useState(-1)
  const [currentMeasure, setCurrentMeasure] = useState(0)
  const [countIn, setCountIn] = useState(false)     // count-in enabled
  const [isCountingIn, setIsCountingIn] = useState(false) // currently in count-in phase

  // Keep a ref to the latest callback to avoid stale closures
  const onBeatScheduleRef = useRef(externalOnBeatSchedule)
  onBeatScheduleRef.current = externalOnBeatSchedule

  // Keep countIn ref to avoid stale closure in start()
  const countInRef = useRef(countIn)
  countInRef.current = countIn

  const start = useCallback(async () => {
    const ctx = await getSharedAudioContext()

    if (schedulerRef.current) {
      schedulerRef.current.stop()
    }

    schedulerRef.current = new AudioScheduler(ctx, bpm, beatsPerMeasure, {
      onBeat: (beat) => setCurrentBeat(beat),
      onMeasureChange: (measure) => setCurrentMeasure(measure),
      onBeatSchedule: (beat, measure, time) => {
        onBeatScheduleRef.current?.(beat, measure, time, ctx)
      },
      onCountInChange: (counting) => setIsCountingIn(counting),
    })
    const countInBars = countInRef.current ? 1 : 0
    if (countInBars > 0) setIsCountingIn(true)
    schedulerRef.current.start(countInBars)
    setIsPlaying(true)
  }, [bpm, beatsPerMeasure])

  const stop = useCallback(() => {
    schedulerRef.current?.stop()
    schedulerRef.current = null
    setIsPlaying(false)
    setIsCountingIn(false)
    setCurrentBeat(-1)
    setCurrentMeasure(0)
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
    currentMeasure,
    beatsPerMeasure,
    setBeatsPerMeasure,
    countIn,
    setCountIn,
    isCountingIn,
  }
}

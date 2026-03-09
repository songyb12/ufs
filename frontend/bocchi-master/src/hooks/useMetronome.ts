import { useState, useRef, useCallback } from 'react'
import { AudioScheduler, type ClickSound, type Subdivision } from '../utils/audioScheduler'
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
  const [countIn, setCountIn] = useState(false)
  const [isCountingIn, setIsCountingIn] = useState(false)
  const [clickSound, setClickSoundState] = useState<ClickSound>('sine')
  const [subdivision, setSubdivisionState] = useState<Subdivision>(1)
  const [swing, setSwingState] = useState(0)

  // Keep refs to avoid stale closures
  const onBeatScheduleRef = useRef(externalOnBeatSchedule)
  onBeatScheduleRef.current = externalOnBeatSchedule
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
    schedulerRef.current.setClickSound(clickSound)
    schedulerRef.current.setSubdivision(subdivision)
    schedulerRef.current.setSwing(swing)
    const countInBars = countInRef.current ? 1 : 0
    if (countInBars > 0) setIsCountingIn(true)
    schedulerRef.current.start(countInBars)
    setIsPlaying(true)
  }, [bpm, beatsPerMeasure, clickSound, subdivision, swing])

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

  const setClickSound = useCallback(
    (sound: ClickSound) => {
      setClickSoundState(sound)
      schedulerRef.current?.setClickSound(sound)
    },
    [],
  )

  const setSubdivision = useCallback(
    (sub: Subdivision) => {
      setSubdivisionState(sub)
      schedulerRef.current?.setSubdivision(sub)
    },
    [],
  )

  const setSwing = useCallback(
    (amount: number) => {
      setSwingState(amount)
      schedulerRef.current?.setSwing(amount)
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
    clickSound,
    setClickSound,
    subdivision,
    setSubdivision,
    swing,
    setSwing,
  }
}

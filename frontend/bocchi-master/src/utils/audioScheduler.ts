/**
 * Lookahead Audio Scheduler
 *
 * CRITICAL: Never use setInterval/setTimeout for audio timing.
 * JavaScript timer resolution is ~4ms at best and degrades under load.
 *
 * This scheduler uses a two-tier approach:
 * 1. A JS timer runs frequently (~25ms) as a SCHEDULING loop
 * 2. Actual audio events are scheduled using AudioContext.currentTime
 *    which has sample-accurate precision (~0.02ms at 48kHz)
 */

const LOOKAHEAD = 0.1       // seconds to look ahead for scheduling
const SCHEDULE_INTERVAL = 25 // ms between scheduling checks

export interface SchedulerCallbacks {
  onBeat: (beatNumber: number, time: number) => void
  onMeasureChange?: (measure: number) => void
  /** Fires at scheduling time (in lookahead window) with precise audio time.
   *  Use for sample-accurate audio scheduling (backing track, etc.) */
  onBeatSchedule?: (beat: number, measure: number, time: number) => void
  /** Fires when count-in phase starts/ends */
  onCountInChange?: (isCountingIn: boolean) => void
}

export type ClickSound = 'sine' | 'wood' | 'hihat' | 'rimshot'

export class AudioScheduler {
  private audioContext: AudioContext
  private bpm: number
  private beatsPerMeasure: number
  private nextNoteTime: number = 0
  private currentBeat: number = 0
  private currentMeasure: number = 0
  private isFirstBeat: boolean = true
  private timerId: number | null = null
  private isPlaying: boolean = false
  private callbacks: SchedulerCallbacks
  private countInBeatsRemaining: number = 0
  private clickSound: ClickSound = 'sine'

  constructor(
    audioContext: AudioContext,
    bpm: number,
    beatsPerMeasure: number,
    callbacks: SchedulerCallbacks,
  ) {
    this.audioContext = audioContext
    this.bpm = bpm
    this.beatsPerMeasure = beatsPerMeasure
    this.callbacks = callbacks
  }

  private scheduleNote(time: number): void {
    const isCountIn = this.countInBeatsRemaining > 0

    // During normal play, fire scheduling callback for backing track etc.
    if (!isCountIn) {
      this.callbacks.onBeatSchedule?.(
        this.currentBeat,
        this.currentMeasure,
        time,
      )
    }

    const osc = this.audioContext.createOscillator()
    const gain = this.audioContext.createGain()
    osc.connect(gain)
    gain.connect(this.audioContext.destination)

    if (isCountIn) {
      // Count-in: higher-pitched staccato sound
      osc.frequency.value = 1200
      gain.gain.setValueAtTime(0.8, time)
      gain.gain.exponentialRampToValueAtTime(0.001, time + 0.05)
      osc.start(time)
      osc.stop(time + 0.05)
    } else {
      const isAccent = this.currentBeat === 0
      this.applyClickSound(osc, gain, time, isAccent)
    }

    this.callbacks.onBeat(this.currentBeat, time)
  }

  private scheduler = (): void => {
    while (
      this.nextNoteTime <
      this.audioContext.currentTime + LOOKAHEAD
    ) {
      if (this.countInBeatsRemaining > 0) {
        // Count-in phase
        this.scheduleNote(this.nextNoteTime)
        const secondsPerBeat = 60.0 / this.bpm
        this.nextNoteTime += secondsPerBeat
        this.countInBeatsRemaining--
        this.currentBeat = (this.currentBeat + 1) % this.beatsPerMeasure

        // Count-in finished — reset for normal play
        if (this.countInBeatsRemaining === 0) {
          this.currentBeat = 0
          this.currentMeasure = 0
          this.isFirstBeat = true
          this.callbacks.onCountInChange?.(false)
          this.callbacks.onMeasureChange?.(0)
        }
        continue
      }

      // Normal play: detect new measure on downbeat (beat 0)
      if (this.currentBeat === 0 && !this.isFirstBeat) {
        this.currentMeasure++
        this.callbacks.onMeasureChange?.(this.currentMeasure)
      }
      this.isFirstBeat = false

      this.scheduleNote(this.nextNoteTime)
      const secondsPerBeat = 60.0 / this.bpm
      this.nextNoteTime += secondsPerBeat
      this.currentBeat = (this.currentBeat + 1) % this.beatsPerMeasure
    }
  }

  start(countInBars: number = 0): void {
    if (this.isPlaying) return
    this.isPlaying = true
    this.currentBeat = 0
    this.currentMeasure = 0
    this.isFirstBeat = true
    this.countInBeatsRemaining = countInBars * this.beatsPerMeasure
    this.nextNoteTime = this.audioContext.currentTime + 0.05

    if (this.countInBeatsRemaining > 0) {
      this.callbacks.onCountInChange?.(true)
    } else {
      this.callbacks.onMeasureChange?.(0)
    }

    this.timerId = window.setInterval(this.scheduler, SCHEDULE_INTERVAL)
  }

  stop(): void {
    if (!this.isPlaying) return
    this.isPlaying = false
    if (this.timerId !== null) {
      clearInterval(this.timerId)
      this.timerId = null
    }
    this.currentBeat = 0
    this.currentMeasure = 0
  }

  setBpm(bpm: number): void {
    this.bpm = bpm
  }

  setBeatsPerMeasure(beats: number): void {
    this.beatsPerMeasure = beats
  }

  setClickSound(sound: ClickSound): void {
    this.clickSound = sound
  }

  getIsPlaying(): boolean {
    return this.isPlaying
  }

  /**
   * Apply click sound based on current clickSound type.
   * Each type creates a different timbre using Web Audio API synthesis.
   */
  private applyClickSound(
    osc: OscillatorNode,
    gain: GainNode,
    time: number,
    isAccent: boolean,
  ): void {
    const vol = isAccent ? 1.0 : 0.7

    switch (this.clickSound) {
      case 'wood': {
        // Woodblock: triangle wave, fast decay, resonant
        osc.type = 'triangle'
        osc.frequency.value = isAccent ? 900 : 700
        gain.gain.setValueAtTime(vol * 0.9, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + 0.04)
        osc.start(time)
        osc.stop(time + 0.04)
        break
      }
      case 'hihat': {
        // Hi-hat simulation: high frequency noise-like (square wave)
        osc.type = 'square'
        osc.frequency.value = isAccent ? 6000 : 5000
        gain.gain.setValueAtTime(vol * 0.4, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + (isAccent ? 0.1 : 0.06))
        osc.start(time)
        osc.stop(time + 0.12)
        break
      }
      case 'rimshot': {
        // Rim shot: short noise burst
        osc.type = 'sawtooth'
        osc.frequency.setValueAtTime(isAccent ? 2000 : 1500, time)
        osc.frequency.exponentialRampToValueAtTime(200, time + 0.02)
        gain.gain.setValueAtTime(vol * 0.8, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + 0.05)
        osc.start(time)
        osc.stop(time + 0.06)
        break
      }
      default: {
        // Sine (classic metronome): clean sine beep
        osc.frequency.value = isAccent ? 1000 : 800
        gain.gain.setValueAtTime(vol, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + 0.08)
        osc.start(time)
        osc.stop(time + 0.08)
        break
      }
    }
  }
}

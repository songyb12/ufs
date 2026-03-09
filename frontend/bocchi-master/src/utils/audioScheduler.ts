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

/** Subdivision level: how many clicks per beat */
export type Subdivision = 1 | 2 | 3 | 4

/**
 * Accent level per beat: 0=ghost (quieter), 1=normal, 2=accent (louder).
 * Pattern length should match beatsPerMeasure.
 */
export type AccentLevel = 0 | 1 | 2

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
  private subdivision: Subdivision = 1
  private swing: number = 0 // 0–100, 0=straight, 50+=swing feel
  private currentSubBeat: number = 0 // tracks subdivision within a beat
  private accentPattern: AccentLevel[] | null = null // null=default (beat 0 accented)
  private volume: number = 1.0 // 0.0 to 1.0 master volume

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

  /**
   * Schedule the main beat click + any subdivision clicks.
   * Subdivisions are scheduled at evenly-spaced intervals within the beat,
   * with optional swing applied to even-numbered sub-beats.
   */
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

    // Schedule the main beat click
    this.scheduleClick(time, isCountIn, /* isSubdivision */ false)
    this.callbacks.onBeat(this.currentBeat, time)

    // Schedule subdivision clicks (only during normal play, not count-in)
    if (!isCountIn && this.subdivision > 1) {
      const secondsPerBeat = 60.0 / this.bpm
      const subInterval = secondsPerBeat / this.subdivision

      for (let sub = 1; sub < this.subdivision; sub++) {
        // Swing: delay even-numbered sub-beats (2nd, 4th in groups of 2)
        let subTime = time + sub * subInterval
        if (this.swing > 0 && this.subdivision === 2 && sub === 1) {
          // For 8th notes: delay the "and" (offbeat)
          const swingRatio = 0.5 + (this.swing / 100) * 0.25 // 0.50–0.75
          subTime = time + secondsPerBeat * swingRatio
        } else if (this.swing > 0 && this.subdivision === 3 && sub === 2) {
          // For triplets: delay the last triplet slightly
          const swingOffset = (this.swing / 100) * subInterval * 0.3
          subTime += swingOffset
        }

        this.scheduleClick(subTime, false, /* isSubdivision */ true)
      }
    }
  }

  /** Schedule a single click (main beat or subdivision) */
  private scheduleClick(time: number, isCountIn: boolean, isSubdivision: boolean): void {
    const osc = this.audioContext.createOscillator()
    const gain = this.audioContext.createGain()
    // Master volume node
    const masterGain = this.audioContext.createGain()
    masterGain.gain.value = this.volume
    osc.connect(gain)
    gain.connect(masterGain)
    masterGain.connect(this.audioContext.destination)

    if (isCountIn) {
      // Count-in: higher-pitched staccato sound
      osc.frequency.value = 1200
      gain.gain.setValueAtTime(0.8, time)
      gain.gain.exponentialRampToValueAtTime(0.001, time + 0.05)
      osc.start(time)
      osc.stop(time + 0.05)
    } else if (isSubdivision) {
      // Subdivision: quieter, shorter version of current click sound
      this.applySubdivisionSound(osc, gain, time)
    } else {
      // Determine accent level from pattern or default (beat 0 = accent)
      const accentLevel: AccentLevel = this.accentPattern
        ? (this.accentPattern[this.currentBeat % this.accentPattern.length] ?? 1)
        : (this.currentBeat === 0 ? 2 : 1)
      if (accentLevel === 0) {
        // Ghost beat — use subdivision sound (quieter)
        this.applySubdivisionSound(osc, gain, time)
      } else {
        this.applyClickSound(osc, gain, time, accentLevel === 2)
      }
    }
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

  setSubdivision(sub: Subdivision): void {
    this.subdivision = sub
  }

  setSwing(amount: number): void {
    this.swing = Math.max(0, Math.min(100, amount))
  }

  setAccentPattern(pattern: AccentLevel[] | null): void {
    this.accentPattern = pattern
  }

  setVolume(vol: number): void {
    this.volume = Math.max(0, Math.min(1, vol))
  }

  getIsPlaying(): boolean {
    return this.isPlaying
  }

  /**
   * Subdivision sound: a quieter, shorter ghost note that fits between main beats.
   * Uses the same waveform family as the main click but softer + higher-pitched.
   */
  private applySubdivisionSound(
    osc: OscillatorNode,
    gain: GainNode,
    time: number,
  ): void {
    const vol = 0.3

    switch (this.clickSound) {
      case 'wood':
        osc.type = 'triangle'
        osc.frequency.value = 1100
        gain.gain.setValueAtTime(vol, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + 0.025)
        osc.start(time)
        osc.stop(time + 0.025)
        break
      case 'hihat':
        osc.type = 'square'
        osc.frequency.value = 8000
        gain.gain.setValueAtTime(vol * 0.5, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + 0.03)
        osc.start(time)
        osc.stop(time + 0.04)
        break
      case 'rimshot':
        osc.type = 'sawtooth'
        osc.frequency.setValueAtTime(2500, time)
        osc.frequency.exponentialRampToValueAtTime(400, time + 0.015)
        gain.gain.setValueAtTime(vol * 0.6, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + 0.03)
        osc.start(time)
        osc.stop(time + 0.04)
        break
      default:
        // Sine: quiet ghost click
        osc.frequency.value = 600
        gain.gain.setValueAtTime(vol, time)
        gain.gain.exponentialRampToValueAtTime(0.001, time + 0.04)
        osc.start(time)
        osc.stop(time + 0.04)
        break
    }
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

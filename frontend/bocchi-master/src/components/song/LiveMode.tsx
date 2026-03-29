import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import type { Song, SongSectionName } from '../../types/song'
import { transposeSong } from '../../utils/transpose'
import { useMetronome } from '../../hooks/useMetronome'

interface LiveModeProps {
  song: Song
  onExit: () => void
}

interface FlatChord {
  chord: string
  beats: number
  annotation?: string
  sectionIndex: number
  sectionName: SongSectionName
  chordIndex: number
  beatStart: number
}

const SECTION_COLORS: Record<SongSectionName, string> = {
  Intro: 'border-slate-500',
  Verse: 'border-sky-500',
  'Pre-Chorus': 'border-teal-500',
  Chorus: 'border-purple-500',
  Bridge: 'border-amber-500',
  Interlude: 'border-slate-500',
  Solo: 'border-rose-500',
  Outro: 'border-slate-500',
  Other: 'border-slate-600',
}

function flattenChords(song: Song): FlatChord[] {
  const result: FlatChord[] = []
  let beatStart = 0
  for (let sIdx = 0; sIdx < song.sections.length; sIdx++) {
    const section = song.sections[sIdx]
    for (let cIdx = 0; cIdx < section.chords.length; cIdx++) {
      const c = section.chords[cIdx]
      result.push({
        chord: c.chord,
        beats: c.beats,
        annotation: c.annotation,
        sectionIndex: sIdx,
        sectionName: section.name,
        chordIndex: cIdx,
        beatStart,
      })
      beatStart += c.beats
    }
  }
  return result
}

function findChordAtBeat(flat: FlatChord[], beat: number): number {
  for (let i = flat.length - 1; i >= 0; i--) {
    if (beat >= flat[i].beatStart) return i
  }
  return 0
}

export function LiveMode({ song, onExit }: LiveModeProps) {
  const [transpose, setTranspose] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [globalBeat, setGlobalBeat] = useState(0)
  const globalBeatRef = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const activeChordRef = useRef<HTMLDivElement>(null)

  const displayed = transposeSong(song, transpose)
  const flatChords = useMemo(() => flattenChords(displayed), [displayed])
  const totalBeats = flatChords.length > 0
    ? flatChords[flatChords.length - 1].beatStart + flatChords[flatChords.length - 1].beats
    : 0

  const metronome = useMetronome()
  const { isPlaying, currentBeat, bpm, setBpm, beatsPerMeasure } = metronome

  // Set BPM from song on mount
  useEffect(() => {
    if (song.bpm) setBpm(song.bpm)
  }, [song.bpm, setBpm])

  // Set time signature from song
  useEffect(() => {
    const ts = song.timeSignature
    if (ts) metronome.setBeatsPerMeasure(ts[0])
  }, [song.timeSignature]) // eslint-disable-line react-hooks/exhaustive-deps -- setBeatsPerMeasure is stable

  // Track global beat from metronome beat changes
  const prevBeatRef = useRef(-1)
  useEffect(() => {
    if (!isPlaying || currentBeat < 0) return
    // Detect actual beat tick (currentBeat changed)
    if (currentBeat !== prevBeatRef.current) {
      prevBeatRef.current = currentBeat
      globalBeatRef.current += 1
      // Loop back if past end
      if (globalBeatRef.current >= totalBeats) {
        globalBeatRef.current = 0
      }
      setGlobalBeat(globalBeatRef.current)
    }
  }, [currentBeat, isPlaying, totalBeats])

  const activeIdx = findChordAtBeat(flatChords, globalBeat)

  // Auto-scroll active chord into view
  useEffect(() => {
    activeChordRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [activeIdx])

  const handleToggle = useCallback(async () => {
    if (isPlaying) {
      metronome.stop()
    } else {
      await metronome.start()
    }
  }, [isPlaying, metronome])

  const handleRestart = useCallback(() => {
    metronome.stop()
    globalBeatRef.current = 0
    prevBeatRef.current = -1
    setGlobalBeat(0)
  }, [metronome])

  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return
    try {
      if (!document.fullscreenElement) {
        await containerRef.current.requestFullscreen()
      } else {
        await document.exitFullscreen()
      }
    } catch {
      // Fullscreen not supported
    }
  }, [])

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', handler)
    return () => document.removeEventListener('fullscreenchange', handler)
  }, [])

  const fsChord = isFullscreen ? 'text-5xl' : 'text-3xl'
  const fsDim = isFullscreen ? 'text-3xl' : 'text-xl'
  const fsBeat = isFullscreen ? 'text-sm' : 'text-[10px]'

  // Group flat chords by section for rendering
  const sections = displayed.sections

  let flatIdx = 0

  return (
    <div
      ref={containerRef}
      className={`flex flex-col ${isFullscreen ? 'bg-slate-950 h-screen' : 'h-full'}`}
    >
      {/* Top controls */}
      <div className="flex items-center gap-2 px-4 py-2 bg-slate-900/80 border-b border-slate-800 flex-shrink-0">
        <button
          onClick={onExit}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          코드 시트
        </button>

        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-slate-200 truncate block">{displayed.title}</span>
        </div>

        {/* Transpose */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setTranspose(p => p <= -11 ? 0 : p - 1)}
            className="w-6 h-6 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-bold transition-colors"
          >-</button>
          <span className="w-6 text-center text-xs font-mono text-slate-400">
            {transpose > 0 ? `+${transpose}` : transpose}
          </span>
          <button
            onClick={() => setTranspose(p => p >= 11 ? 0 : p + 1)}
            className="w-6 h-6 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-bold transition-colors"
          >+</button>
        </div>

        <button
          onClick={toggleFullscreen}
          className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 text-xs transition-colors"
        >
          {isFullscreen ? 'Exit' : 'Full'}
        </button>
      </div>

      {/* Chord display area */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <div className="flex flex-col gap-3">
          {sections.map((section, sIdx) => {
            const sectionStartIdx = flatIdx
            const chordElements = section.chords.map((c, cIdx) => {
              const fIdx = sectionStartIdx + cIdx
              const isActive = fIdx === activeIdx && isPlaying
              const isPast = fIdx < activeIdx
              flatIdx++

              return (
                <div
                  key={cIdx}
                  ref={isActive ? activeChordRef : undefined}
                  className={`flex flex-col items-center px-3 py-2 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'bg-orange-500/20 ring-2 ring-orange-500/60 scale-105'
                      : isPast && isPlaying
                        ? 'bg-slate-900/30 opacity-40'
                        : 'bg-slate-900/60'
                  }`}
                  style={{ minWidth: c.beats <= 2 ? '3.5rem' : c.beats <= 4 ? '4.5rem' : c.beats <= 6 ? '6rem' : '7.5rem' }}
                >
                  <span className={`font-mono font-bold ${isActive ? `${fsChord} text-orange-300` : `${fsDim} text-slate-300`}`}>
                    {c.chord}
                  </span>
                  <span className={`${fsBeat} text-slate-600 font-mono`}>
                    {c.beats}
                  </span>
                </div>
              )
            })

            return (
              <div
                key={sIdx}
                className={`border-l-4 ${SECTION_COLORS[section.name]} rounded-r-lg px-3 py-2`}
              >
                <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  {section.name}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {chordElements}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Bottom metronome bar */}
      <div className="flex items-center gap-3 px-4 py-3 bg-slate-900/90 border-t border-slate-800 flex-shrink-0">
        {/* Play/Stop */}
        <button
          onClick={handleToggle}
          className={`w-12 h-12 rounded-full flex items-center justify-center text-xl transition-colors ${
            isPlaying
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
              : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
          }`}
        >
          {isPlaying ? '■' : '▶'}
        </button>

        {/* Restart */}
        <button
          onClick={handleRestart}
          className="w-9 h-9 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 flex items-center justify-center text-sm transition-colors"
          title="처음부터"
        >
          ↺
        </button>

        {/* BPM */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setBpm(Math.max(20, bpm - 5))}
            className="w-7 h-7 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 text-sm font-bold transition-colors"
          >-</button>
          <span className="w-14 text-center text-lg font-mono font-bold text-slate-200">{bpm}</span>
          <button
            onClick={() => setBpm(Math.min(300, bpm + 5))}
            className="w-7 h-7 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 text-sm font-bold transition-colors"
          >+</button>
          <span className="text-[10px] text-slate-600">BPM</span>
        </div>

        {/* Beat indicator */}
        <div className="flex gap-1 ml-auto">
          {Array.from({ length: beatsPerMeasure }, (_, i) => (
            <div
              key={i}
              className={`w-3 h-3 rounded-full transition-colors ${
                isPlaying && currentBeat === i
                  ? i === 0 ? 'bg-orange-400' : 'bg-sky-400'
                  : 'bg-slate-700'
              }`}
            />
          ))}
        </div>

        {/* Progress */}
        {totalBeats > 0 && (
          <span className="text-[10px] font-mono text-slate-600">
            {globalBeat}/{totalBeats}
          </span>
        )}
      </div>
    </div>
  )
}

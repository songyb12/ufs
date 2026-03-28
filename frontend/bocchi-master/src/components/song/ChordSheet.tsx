import { useState, useCallback, useRef } from 'react'
import type { Song, SongSectionName } from '../../types/song'
import { transposeSong } from '../../utils/transpose'

interface ChordSheetProps {
  song: Song
  currentSectionIndex?: number
  onChordClick?: (chord: string) => void
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

const SECTION_BG: Record<SongSectionName, string> = {
  Intro: 'bg-slate-500/10',
  Verse: 'bg-sky-500/10',
  'Pre-Chorus': 'bg-teal-500/10',
  Chorus: 'bg-purple-500/10',
  Bridge: 'bg-amber-500/10',
  Interlude: 'bg-slate-500/10',
  Solo: 'bg-rose-500/10',
  Outro: 'bg-slate-500/10',
  Other: 'bg-slate-600/10',
}

export function ChordSheet({ song, currentSectionIndex, onChordClick }: ChordSheetProps) {
  const [transpose, setTranspose] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const displayed = transposeSong(song, transpose)

  const handleTransposeDown = () => setTranspose(p => p <= -11 ? 0 : p - 1)
  const handleTransposeUp = () => setTranspose(p => p >= 11 ? 0 : p + 1)
  const handleTransposeReset = () => setTranspose(0)

  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return
    try {
      if (!document.fullscreenElement) {
        await containerRef.current.requestFullscreen()
        setIsFullscreen(true)
      } else {
        await document.exitFullscreen()
        setIsFullscreen(false)
      }
    } catch {
      // Fullscreen not supported
    }
  }, [])

  const fsText = isFullscreen ? 'text-4xl' : 'text-2xl'
  const fsBeat = isFullscreen ? 'text-sm' : 'text-[10px]'
  const fsTitle = isFullscreen ? 'text-3xl' : 'text-xl'

  return (
    <div
      ref={containerRef}
      className={`flex flex-col gap-4 ${isFullscreen ? 'bg-slate-950 p-8 overflow-y-auto' : ''}`}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-2">
        <div className="flex-1 min-w-0">
          <h2 className={`${fsTitle} font-bold text-slate-100 truncate`}>{displayed.title}</h2>
          {displayed.artist && <p className="text-sm text-slate-400">{displayed.artist}</p>}
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500 flex-shrink-0">
          {displayed.key && (
            <span className="px-2 py-1 rounded bg-slate-800 text-slate-300 font-mono font-medium">
              Key: {displayed.key}
            </span>
          )}
          {displayed.bpm && (
            <span className="px-2 py-1 rounded bg-slate-800 text-slate-300 font-mono">
              {displayed.bpm} BPM
            </span>
          )}
          {displayed.timeSignature && (
            <span className="px-2 py-1 rounded bg-slate-800 text-slate-300 font-mono">
              {displayed.timeSignature[0]}/{displayed.timeSignature[1]}
            </span>
          )}
        </div>
      </div>

      {/* Transpose controls */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500 mr-1">Transpose</span>
        <button
          onClick={handleTransposeDown}
          className="w-7 h-7 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-bold transition-colors"
        >
          -
        </button>
        <span className="w-8 text-center text-sm font-mono text-slate-300">
          {transpose > 0 ? `+${transpose}` : transpose}
        </span>
        <button
          onClick={handleTransposeUp}
          className="w-7 h-7 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-bold transition-colors"
        >
          +
        </button>
        {transpose !== 0 && (
          <button
            onClick={handleTransposeReset}
            className="px-2 py-1 rounded text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
          >
            Reset
          </button>
        )}
        <div className="flex-1" />
        <button
          onClick={toggleFullscreen}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 text-xs transition-colors"
        >
          {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
        </button>
      </div>

      {/* Sections */}
      <div className="flex flex-col gap-3">
        {displayed.sections.map((section, sIdx) => (
          <div
            key={sIdx}
            className={`border-l-4 ${SECTION_COLORS[section.name]} ${SECTION_BG[section.name]} rounded-r-lg px-4 py-3 ${
              currentSectionIndex === sIdx ? 'ring-2 ring-orange-500/50' : ''
            }`}
          >
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              {section.name}
            </div>
            <div className="flex flex-wrap gap-1">
              {section.chords.map((c, cIdx) => {
                const widthClass = c.beats <= 2 ? 'min-w-[3.5rem]'
                  : c.beats <= 4 ? 'min-w-[4.5rem]'
                  : c.beats <= 6 ? 'min-w-[6rem]'
                  : 'min-w-[7.5rem]'

                return (
                  <div
                    key={cIdx}
                    onClick={() => onChordClick?.(c.chord)}
                    className={`${widthClass} flex flex-col items-center px-2 py-1.5 rounded bg-slate-900/60 ${
                      onChordClick ? 'cursor-pointer hover:bg-slate-800/80 active:scale-95 transition-all' : ''
                    }`}
                  >
                    <span className={`${fsText} font-mono font-bold text-slate-100`}>
                      {c.chord}
                    </span>
                    <span className={`${fsBeat} text-slate-600 font-mono`}>
                      {c.beats} beat{c.beats !== 1 ? 's' : ''}
                    </span>
                    {c.annotation && (
                      <span className="text-[10px] text-amber-500/70 mt-0.5">{c.annotation}</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {song.source === 'llm' && (
        <p className="text-[11px] text-slate-600 text-center mt-2">
          AI가 생성한 코드입니다. 실제 곡과 다를 수 있습니다.
        </p>
      )}
    </div>
  )
}

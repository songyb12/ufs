import { useCallback, useMemo } from 'react'
import type { InstrumentConfig, Note, NoteName } from '../../types/music'
import { getNoteAtFret, calculateFretX } from '../../utils/noteCalculator'
import { FretboardString } from './FretboardString'
import { FretMarker } from './FretMarker'
import { NoteLabel } from './NoteLabel'
import { getNoteLabel, type NoteLabelMode } from '../../utils/noteLabelFormatter'
import { getEnharmonicName, type EnharmonicMode } from '../../utils/enharmonic'

interface FretboardProps {
  instrument: InstrumentConfig
  highlightedNotes?: Note[]
  scaleNoteNames?: NoteName[]
  rootNote?: NoteName
  voicingPositions?: number[]  // per-string fret array. -1=mute, 0=open, 1+=fret
  midiNoteName?: NoteName      // currently active MIDI note (highlight all instances)
  scaleOverlayNoteNames?: NoteName[]  // improv scale overlay (amber)
  patternPositions?: { stringIndex: number; fret: number }[]  // scale pattern overlay (teal)
  chordToneNoteNames?: NoteName[]  // chord tone indicator ring (pink)
  labelMode?: NoteLabelMode    // 'name' | 'interval' | 'degree'
  enharmonicMode?: EnharmonicMode  // 'sharp' | 'flat'
  leftHanded?: boolean         // mirror fretboard horizontally
  fretRange?: [number, number] // [startFret, endFret] for zoom (inclusive)
  dimmedStrings?: Set<number>  // strings to visually dim (for focused practice)
  hideLabels?: boolean         // ghost mode: show dots only, hide text labels
  fingeringNumbers?: number[]  // per-string fingering (0=none, 1-4=finger)
  onNoteClick?: (note: Note, stringIndex: number, fret: number) => void
}

// Layout constants (SVG units)
const PADDING_LEFT = 50    // space for open string labels
const PADDING_RIGHT = 20
const PADDING_TOP = 20
const PADDING_BOTTOM = 20
const SCALE_LENGTH = 900   // fretboard playing area width
const STRING_SPACING = 28

export function Fretboard({
  instrument,
  highlightedNotes = [],
  scaleNoteNames = [],
  rootNote,
  voicingPositions,
  midiNoteName,
  scaleOverlayNoteNames = [],
  patternPositions,
  chordToneNoteNames = [],
  labelMode = 'name',
  enharmonicMode = 'sharp',
  leftHanded = false,
  fretRange,
  dimmedStrings,
  hideLabels = false,
  fingeringNumbers,
  onNoteClick,
}: FretboardProps) {
  const { stringCount, fretCount, tuning } = instrument

  const fretboardHeight = STRING_SPACING * (stringCount - 1)
  const svgWidth = PADDING_LEFT + SCALE_LENGTH + PADDING_RIGHT
  const svgHeight = PADDING_TOP + fretboardHeight + PADDING_BOTTOM

  // Fret range zoom (crop viewBox to show only selected frets)
  const startFret = fretRange?.[0] ?? 0
  const endFret = fretRange?.[1] ?? fretCount
  const isZoomed = startFret > 0 || endFret < fretCount

  // Y position for each string (top string = highest pitch = last in tuning array)
  const getStringY = (stringIndex: number) =>
    PADDING_TOP + (stringCount - 1 - stringIndex) * STRING_SPACING

  // X position for fret wire
  const getFretWireX = (fret: number) =>
    PADDING_LEFT + calculateFretX(fret, SCALE_LENGTH)

  // X center of a fret space (between fret n-1 and fret n)
  const getFretCenterX = (fret: number) => {
    if (fret === 0) return PADDING_LEFT - 20 // open string, left of nut
    const left = getFretWireX(fret - 1)
    const right = getFretWireX(fret)
    return (left + right) / 2
  }

  const isNoteHighlighted = useCallback(
    (note: Note) =>
      highlightedNotes.some(
        (h) => h.name === note.name && h.octave === note.octave,
      ),
    [highlightedNotes],
  )

  const scaleSet = useMemo(() => new Set(scaleNoteNames), [scaleNoteNames])
  const scaleOverlaySet = useMemo(() => new Set(scaleOverlayNoteNames), [scaleOverlayNoteNames])
  const chordToneSet = useMemo(() => new Set(chordToneNoteNames), [chordToneNoteNames])
  const patternPosSet = useMemo(() => {
    if (!patternPositions) return null
    const s = new Set<string>()
    for (const p of patternPositions) s.add(`${p.stringIndex}-${p.fret}`)
    return s
  }, [patternPositions])

  // Voicing mode: check if a specific (stringIndex, fret) is in the voicing
  const hasVoicing = voicingPositions != null && voicingPositions.length > 0
  const isVoicingPosition = useCallback(
    (stringIndex: number, fret: number): boolean => {
      if (!voicingPositions) return false
      return voicingPositions[stringIndex] === fret
    },
    [voicingPositions],
  )

  // Muted strings in voicing mode
  const mutedStrings = useMemo(() => {
    if (!voicingPositions) return new Set<number>()
    const muted = new Set<number>()
    voicingPositions.forEach((fret, idx) => {
      if (fret === -1) muted.add(idx)
    })
    return muted
  }, [voicingPositions])

  const yCenter = PADDING_TOP + fretboardHeight / 2
  const dotSpread = fretboardHeight * 0.3

  // Compute zoomed viewBox
  const zoomViewBox = useMemo(() => {
    if (!isZoomed) return `0 0 ${svgWidth} ${svgHeight}`
    // Left edge: for startFret=0, show from 0 (includes open position).
    // For startFret>0, crop to just before that fret wire.
    const xLeft = startFret === 0
      ? 0
      : PADDING_LEFT + calculateFretX(startFret - 1, SCALE_LENGTH) - 10
    // Right edge: fret wire of endFret + padding
    const xRight = PADDING_LEFT + calculateFretX(endFret, SCALE_LENGTH) + 20
    const width = xRight - xLeft
    return `${xLeft} 0 ${width} ${svgHeight}`
  }, [isZoomed, startFret, endFret, svgWidth, svgHeight])

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={zoomViewBox}
        preserveAspectRatio="xMinYMid meet"
        className="w-full min-w-[800px]"
        style={leftHanded ? { transform: 'scaleX(-1)' } : undefined}
        role="img"
        aria-label={`${instrument.name} fretboard${leftHanded ? ' (left-handed)' : ''}${isZoomed ? ` (frets ${startFret}-${endFret})` : ''}`}
      >
        {/* Background */}
        <rect
          x={PADDING_LEFT}
          y={PADDING_TOP - 10}
          width={SCALE_LENGTH}
          height={fretboardHeight + 20}
          rx={4}
          fill="#1e293b"
        />

        {/* Nut (fret 0 bar) */}
        <line
          x1={PADDING_LEFT}
          y1={PADDING_TOP - 10}
          x2={PADDING_LEFT}
          y2={PADDING_TOP + fretboardHeight + 10}
          stroke="#e2e8f0"
          strokeWidth={4}
        />

        {/* Fret markers (dots) */}
        {Array.from({ length: fretCount }, (_, i) => i + 1).map((fret) => (
          <FretMarker
            key={`marker-${fret}`}
            fret={fret}
            x={getFretCenterX(fret)}
            yCenter={yCenter}
            ySpread={dotSpread}
          />
        ))}

        {/* Fret wires */}
        {Array.from({ length: fretCount }, (_, i) => i + 1).map((fret) => {
          const x = getFretWireX(fret)
          return (
            <line
              key={`fret-${fret}`}
              x1={x}
              y1={PADDING_TOP - 10}
              x2={x}
              y2={PADDING_TOP + fretboardHeight + 10}
              stroke="#475569"
              strokeWidth={1.5}
            />
          )
        })}

        {/* Strings */}
        {tuning.map((_, stringIndex) => (
          <g
            key={`string-${stringIndex}`}
            opacity={dimmedStrings?.has(stringIndex) ? 0.2 : 1}
          >
            <FretboardString
              y={getStringY(stringIndex)}
              xStart={PADDING_LEFT}
              xEnd={PADDING_LEFT + SCALE_LENGTH}
              stringIndex={stringIndex}
              totalStrings={stringCount}
            />
          </g>
        ))}

        {/* Fret numbers (always shown for orientation) */}
        {Array.from({ length: (isZoomed ? endFret - startFret + 1 : fretCount) }, (_, i) => (isZoomed ? startFret : 1) + i)
          .filter((f) => f > 0 && f % (isZoomed ? 1 : 3) === 0) // every fret when zoomed, every 3rd when full
          .map((fret) => (
            <text
              key={`fretnum-${fret}`}
              x={getFretCenterX(fret)}
              y={PADDING_TOP + fretboardHeight + 18}
              textAnchor="middle"
              fontSize={9}
              fill="#475569"
              {...(leftHanded ? { transform: `translate(${2 * getFretCenterX(fret)}, 0) scale(-1, 1)` } : {})}
            >
              {fret}
            </text>
          ))}

        {/* String tuning labels (left edge, always visible) */}
        {tuning.map((openNote, stringIndex) => {
          const y = getStringY(stringIndex)
          // Position at the left edge of the visible area
          const x = isZoomed && startFret > 0
            ? PADDING_LEFT + calculateFretX(startFret - 1, SCALE_LENGTH) - 2
            : PADDING_LEFT - 34
          return (
            <text
              key={`tuning-${stringIndex}`}
              x={x}
              y={y}
              textAnchor="end"
              dominantBaseline="central"
              fontSize={9}
              fontWeight={500}
              fill="#64748b"
              {...(leftHanded ? { transform: `translate(${2 * x}, 0) scale(-1, 1)` } : {})}
            >
              {enharmonicMode === 'flat' ? getEnharmonicName(openNote, 'flat') : openNote}
            </text>
          )
        })}

        {/* Mute markers (X) for muted strings in voicing mode */}
        {hasVoicing &&
          tuning.map((_, stringIndex) => {
            if (!mutedStrings.has(stringIndex)) return null
            const y = getStringY(stringIndex)
            const x = PADDING_LEFT - 20 // same x as open string position
            return (
              <text
                key={`mute-${stringIndex}`}
                x={x}
                y={y}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={14}
                fontWeight={700}
                fill="#ef4444"
                opacity={0.8}
                {...(leftHanded ? { transform: `translate(${2 * x}, 0) scale(-1, 1)` } : {})}
              >
                X
              </text>
            )
          })}

        {/* Fingering numbers (shown below voicing dots) */}
        {fingeringNumbers && voicingPositions && fingeringNumbers.map((finger, stringIndex) => {
          if (finger === 0) return null
          const fret = voicingPositions[stringIndex]
          if (fret == null || fret <= 0) return null
          const x = getFretCenterX(fret)
          const y = getStringY(stringIndex) + 14
          return (
            <text
              key={`finger-${stringIndex}`}
              x={x}
              y={y}
              textAnchor="middle"
              fontSize={8}
              fontWeight={700}
              fill="#a78bfa"
              opacity={0.9}
              {...(leftHanded ? { transform: `translate(${2 * x}, 0) scale(-1, 1)` } : {})}
            >
              {finger}
            </text>
          )
        })}

        {/* Note labels (open string + each fret) */}
        {tuning.map((openNote, stringIndex) => {
          const y = getStringY(stringIndex)
          const isDimmed = dimmedStrings?.has(stringIndex) ?? false

          return (
            <g key={`notes-${stringIndex}`} opacity={isDimmed ? 0.15 : 1}>
              {Array.from({ length: fretCount + 1 }, (_, fret) => {
                // In voicing mode, skip rendering label on muted strings
                // (X marker is shown instead at open position)
                if (hasVoicing && mutedStrings.has(stringIndex) && fret === 0) {
                  return null
                }

                const note = getNoteAtFret(openNote, fret)
                const x = getFretCenterX(fret)
                const highlighted = isNoteHighlighted(note)
                const inScale = hasVoicing ? false : scaleSet.has(note.name)
                const isRoot = hasVoicing
                  ? isVoicingPosition(stringIndex, fret) && rootNote === note.name
                  : rootNote === note.name
                const isVoicing = hasVoicing && isVoicingPosition(stringIndex, fret)
                const isMidi = midiNoteName === note.name
                const isOverlay = scaleOverlaySet.has(note.name) && !inScale && !isVoicing
                const isPatternPos = patternPosSet?.has(`${stringIndex}-${fret}`) ?? false
                const isChordTone = chordToneSet.size > 0 && chordToneSet.has(note.name)

                // Compute display label based on mode (only for visible notes)
                const showLabel = highlighted || isMidi || isVoicing || inScale || isRoot || isOverlay || isPatternPos
                let displayLabel: string | undefined
                if (showLabel && labelMode !== 'name') {
                  displayLabel = getNoteLabel(note.name, rootNote, labelMode)
                } else if (enharmonicMode === 'flat') {
                  displayLabel = getEnharmonicName(note.name, 'flat')
                }

                return (
                  <NoteLabel
                    key={`note-${stringIndex}-${fret}`}
                    note={note}
                    x={x}
                    y={y}
                    isHighlighted={highlighted}
                    isInScale={inScale}
                    isRoot={isRoot}
                    isVoicing={isVoicing}
                    isMidiActive={isMidi}
                    isScaleOverlay={isOverlay}
                    isPattern={isPatternPos}
                    isChordTone={isChordTone}
                    hideLabel={hideLabels}
                    displayLabel={displayLabel}
                    leftHanded={leftHanded}
                    onClick={() => onNoteClick?.(note, stringIndex, fret)}
                  />
                )
              })}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

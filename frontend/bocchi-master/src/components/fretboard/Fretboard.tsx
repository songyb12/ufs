import { useCallback } from 'react'
import type { InstrumentConfig, Note } from '../../types/music'
import { getNoteAtFret, calculateFretX } from '../../utils/noteCalculator'
import { FretboardString } from './FretboardString'
import { FretMarker } from './FretMarker'
import { NoteLabel } from './NoteLabel'

interface FretboardProps {
  instrument: InstrumentConfig
  highlightedNotes?: Note[]
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
  onNoteClick,
}: FretboardProps) {
  const { stringCount, fretCount, tuning } = instrument

  const fretboardHeight = STRING_SPACING * (stringCount - 1)
  const svgWidth = PADDING_LEFT + SCALE_LENGTH + PADDING_RIGHT
  const svgHeight = PADDING_TOP + fretboardHeight + PADDING_BOTTOM

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

  const yCenter = PADDING_TOP + fretboardHeight / 2
  const dotSpread = fretboardHeight * 0.3

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        preserveAspectRatio="xMinYMid meet"
        className="w-full min-w-[800px]"
        role="img"
        aria-label={`${instrument.name} fretboard`}
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
          <FretboardString
            key={`string-${stringIndex}`}
            y={getStringY(stringIndex)}
            xStart={PADDING_LEFT}
            xEnd={PADDING_LEFT + SCALE_LENGTH}
            stringIndex={stringIndex}
            totalStrings={stringCount}
          />
        ))}

        {/* Note labels (open string + each fret) */}
        {tuning.map((openNote, stringIndex) => {
          const y = getStringY(stringIndex)

          return Array.from({ length: fretCount + 1 }, (_, fret) => {
            const note = getNoteAtFret(openNote, fret)
            const x = getFretCenterX(fret)
            const highlighted = isNoteHighlighted(note)

            return (
              <NoteLabel
                key={`note-${stringIndex}-${fret}`}
                note={note}
                x={x}
                y={y}
                isHighlighted={highlighted}
                onClick={() => onNoteClick?.(note, stringIndex, fret)}
              />
            )
          })
        })}
      </svg>
    </div>
  )
}

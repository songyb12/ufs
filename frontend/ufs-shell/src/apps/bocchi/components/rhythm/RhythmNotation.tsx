import { memo } from 'react'
import type { StrokeType } from '../../utils/strumPatterns'

interface RhythmNotationProps {
  strokes: StrokeType[]
  beatsPerMeasure: number
  activeIndex: number
  /** Width of each stroke cell */
  cellWidth?: number
}

const STAFF_Y = 30
const STEM_LENGTH = 22
const NOTEHEAD_RX = 5
const NOTEHEAD_RY = 3.5

/**
 * SVG rhythm notation renderer for strum patterns.
 * - Down strums: stems point down (standard notation convention)
 * - Up strums: stems point up
 * - Rests: standard rest symbol
 * - Beamed groups for 8th/16th notes within beats
 */
export const RhythmNotation = memo(function RhythmNotation({
  strokes,
  beatsPerMeasure,
  activeIndex,
  cellWidth = 28,
}: RhythmNotationProps) {
  const totalWidth = strokes.length * cellWidth + 20 // +padding
  const height = 70
  const strokesPerBeat = strokes.length / beatsPerMeasure

  // Determine note grouping: 8th notes (2 per beat) or 16th notes (4 per beat)
  const is16th = strokesPerBeat === 4
  const is8th = strokesPerBeat === 2
  const isTriplet = strokesPerBeat === 3

  return (
    <svg
      viewBox={`0 0 ${totalWidth} ${height}`}
      width={totalWidth}
      height={height}
      className="mx-auto"
    >
      {/* Single-line staff */}
      <line
        x1={8}
        y1={STAFF_Y}
        x2={totalWidth - 8}
        y2={STAFF_Y}
        stroke="#334155"
        strokeWidth={1}
      />

      {/* Beat dividers */}
      {Array.from({ length: beatsPerMeasure + 1 }, (_, i) => {
        const x = 10 + i * strokesPerBeat * cellWidth
        return (
          <line
            key={`div-${i}`}
            x1={x}
            y1={STAFF_Y - 12}
            x2={x}
            y2={STAFF_Y + 12}
            stroke={i === 0 || i === beatsPerMeasure ? '#475569' : '#1e293b'}
            strokeWidth={i === 0 || i === beatsPerMeasure ? 2 : 1}
          />
        )
      })}

      {/* Beat numbers */}
      {Array.from({ length: beatsPerMeasure }, (_, beat) => (
        <text
          key={`beat-${beat}`}
          x={10 + (beat * strokesPerBeat + strokesPerBeat / 2) * cellWidth}
          y={height - 2}
          textAnchor="middle"
          fontSize={8}
          fill="#475569"
        >
          {beat + 1}
        </text>
      ))}

      {/* Strokes */}
      {strokes.map((stroke, i) => {
        const cx = 10 + i * cellWidth + cellWidth / 2
        const isActive = activeIndex === i

        if (stroke === '-') {
          // Rest symbol: simple ∅ style
          return (
            <g key={i} opacity={isActive ? 1 : 0.5}>
              <text
                x={cx}
                y={STAFF_Y + 4}
                textAnchor="middle"
                fontSize={12}
                fill={isActive ? '#fbbf24' : '#475569'}
              >
                𝄾
              </text>
            </g>
          )
        }

        const isDown = stroke === 'D'
        // Down stroke: notehead on staff, stem goes down
        // Up stroke: notehead on staff, stem goes up
        const stemDir = isDown ? 1 : -1
        const stemTop = STAFF_Y + stemDir * STEM_LENGTH
        const noteColor = isActive
          ? isDown ? '#38bdf8' : '#a78bfa'
          : isDown ? '#64748b' : '#7c3aed50'
        const stemColor = isActive
          ? isDown ? '#38bdf8' : '#a78bfa'
          : '#475569'

        return (
          <g key={i}>
            {/* Active highlight glow */}
            {isActive && (
              <circle
                cx={cx}
                cy={STAFF_Y}
                r={10}
                fill={isDown ? '#38bdf820' : '#a78bfa20'}
              />
            )}
            {/* Notehead (filled ellipse) */}
            <ellipse
              cx={cx}
              cy={STAFF_Y}
              rx={NOTEHEAD_RX}
              ry={NOTEHEAD_RY}
              fill={noteColor}
              transform={`rotate(-15, ${cx}, ${STAFF_Y})`}
            />
            {/* Stem */}
            <line
              x1={cx + (isDown ? -NOTEHEAD_RX : NOTEHEAD_RX)}
              y1={STAFF_Y}
              x2={cx + (isDown ? -NOTEHEAD_RX : NOTEHEAD_RX)}
              y2={stemTop}
              stroke={stemColor}
              strokeWidth={1.5}
            />
            {/* Flag for 8th notes (if not beamed) */}
            {(is8th || isTriplet) && (
              <line
                x1={cx + (isDown ? -NOTEHEAD_RX : NOTEHEAD_RX)}
                y1={stemTop}
                x2={cx + (isDown ? -NOTEHEAD_RX + 6 : NOTEHEAD_RX - 6)}
                y2={stemTop + stemDir * (-5)}
                stroke={stemColor}
                strokeWidth={1.5}
              />
            )}
            {/* Double flag for 16th notes */}
            {is16th && (
              <>
                <line
                  x1={cx + (isDown ? -NOTEHEAD_RX : NOTEHEAD_RX)}
                  y1={stemTop}
                  x2={cx + (isDown ? -NOTEHEAD_RX + 6 : NOTEHEAD_RX - 6)}
                  y2={stemTop + stemDir * (-5)}
                  stroke={stemColor}
                  strokeWidth={1.5}
                />
                <line
                  x1={cx + (isDown ? -NOTEHEAD_RX : NOTEHEAD_RX)}
                  y1={stemTop + stemDir * (-4)}
                  x2={cx + (isDown ? -NOTEHEAD_RX + 6 : NOTEHEAD_RX - 6)}
                  y2={stemTop + stemDir * (-9)}
                  stroke={stemColor}
                  strokeWidth={1.5}
                />
              </>
            )}
            {/* Direction arrow indicator (tiny) */}
            <text
              x={cx}
              y={isDown ? STAFF_Y + STEM_LENGTH + 12 : STAFF_Y - STEM_LENGTH - 4}
              textAnchor="middle"
              fontSize={8}
              fill={isActive ? (isDown ? '#38bdf8' : '#a78bfa') : '#334155'}
            >
              {isDown ? '↓' : '↑'}
            </text>
          </g>
        )
      })}
    </svg>
  )
})

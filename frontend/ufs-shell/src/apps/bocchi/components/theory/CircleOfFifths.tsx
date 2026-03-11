import { useState, memo } from 'react'
import type { NoteName } from '../../types/music'

interface CircleOfFifthsProps {
  /** Currently selected key (highlighted) */
  activeKey?: NoteName | null
  /** Callback when a key segment is clicked */
  onKeySelect?: (key: NoteName) => void
}

// Circle of fifths: major keys ordered clockwise
const MAJOR_KEYS: NoteName[] = [
  'C', 'G', 'D', 'A', 'E', 'B',
  'F#', 'C#', 'G#', 'D#', 'A#', 'F',
]

// Relative minor keys (same position on circle)
const MINOR_KEYS: string[] = [
  'Am', 'Em', 'Bm', 'F#m', 'C#m', 'G#m',
  'D#m', 'A#m', 'Fm', 'Cm', 'Gm', 'Dm',
]

// Number of sharps/flats for each position
const KEY_SIGNATURES: string[] = [
  '0', '1♯', '2♯', '3♯', '4♯', '5♯',
  '6♯/6♭', '5♭', '4♭', '3♭', '2♭', '1♭',
]

const CENTER_X = 150
const CENTER_Y = 150
const OUTER_R = 130
const INNER_R = 90
const MINOR_R = 65
const TEXT_R = 110

/**
 * Interactive Circle of Fifths SVG diagram.
 * Shows major keys on outer ring, relative minors on inner ring,
 * key signatures, and highlights the active key + related keys.
 */
export const CircleOfFifths = memo(function CircleOfFifths({
  activeKey,
  onKeySelect,
}: CircleOfFifthsProps) {
  const [expanded, setExpanded] = useState(false)

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full text-xs text-slate-600 hover:text-slate-400 py-1 transition-colors"
      >
        Circle of Fifths (key reference)...
      </button>
    )
  }

  const activeIndex = activeKey ? MAJOR_KEYS.indexOf(activeKey) : -1
  // Related keys: IV (index-1), V (index+1), relative minor (same index)
  const relatedIndices = new Set<number>()
  if (activeIndex >= 0) {
    relatedIndices.add(activeIndex)
    relatedIndices.add((activeIndex + 1) % 12) // V
    relatedIndices.add((activeIndex - 1 + 12) % 12) // IV
    relatedIndices.add((activeIndex + 3) % 12) // vi relative major
  }

  const sliceAngle = (2 * Math.PI) / 12

  // Compute arc path for a ring segment
  function arcPath(
    centerAngle: number,
    innerRadius: number,
    outerRadius: number,
    halfAngle: number,
  ): string {
    const a1 = centerAngle - halfAngle
    const a2 = centerAngle + halfAngle
    const x1o = CENTER_X + outerRadius * Math.sin(a1)
    const y1o = CENTER_Y - outerRadius * Math.cos(a1)
    const x2o = CENTER_X + outerRadius * Math.sin(a2)
    const y2o = CENTER_Y - outerRadius * Math.cos(a2)
    const x1i = CENTER_X + innerRadius * Math.sin(a2)
    const y1i = CENTER_Y - innerRadius * Math.cos(a2)
    const x2i = CENTER_X + innerRadius * Math.sin(a1)
    const y2i = CENTER_Y - innerRadius * Math.cos(a1)
    return [
      `M ${x1o} ${y1o}`,
      `A ${outerRadius} ${outerRadius} 0 0 1 ${x2o} ${y2o}`,
      `L ${x1i} ${y1i}`,
      `A ${innerRadius} ${innerRadius} 0 0 0 ${x2i} ${y2i}`,
      'Z',
    ].join(' ')
  }

  return (
    <div className="bg-slate-800 rounded-lg px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Circle of Fifths
        </h2>
        <button
          onClick={() => setExpanded(false)}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          Collapse
        </button>
      </div>

      <div className="flex justify-center">
        <svg viewBox="0 0 300 300" width={280} height={280} role="img" aria-label="Circle of Fifths">
          {/* Background circle */}
          <circle cx={CENTER_X} cy={CENTER_Y} r={OUTER_R + 2} fill="#0f172a" stroke="#334155" strokeWidth={1} />

          {/* Major key segments (outer ring) */}
          {MAJOR_KEYS.map((key, i) => {
            const angle = i * sliceAngle
            const isActive = i === activeIndex
            const isRelated = relatedIndices.has(i) && !isActive
            const textX = CENTER_X + TEXT_R * Math.sin(angle)
            const textY = CENTER_Y - TEXT_R * Math.cos(angle)

            let fill = '#1e293b'
            if (isActive) fill = '#0ea5e9'
            else if (isRelated) fill = '#164e63'

            return (
              <g
                key={`major-${i}`}
                onClick={() => onKeySelect?.(key)}
                className="cursor-pointer"
              >
                <path
                  d={arcPath(angle, INNER_R, OUTER_R, sliceAngle / 2 - 0.02)}
                  fill={fill}
                  stroke="#334155"
                  strokeWidth={1}
                />
                <text
                  x={textX}
                  y={textY}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={isActive ? 14 : 12}
                  fontWeight={isActive ? 800 : 600}
                  fill={isActive ? '#fff' : isRelated ? '#67e8f9' : '#94a3b8'}
                >
                  {key}
                </text>
              </g>
            )
          })}

          {/* Minor key segments (inner ring) */}
          {MINOR_KEYS.map((key, i) => {
            const angle = i * sliceAngle
            const isActive = i === activeIndex
            const isRelated = relatedIndices.has(i) && !isActive
            const textX = CENTER_X + MINOR_R * Math.sin(angle)
            const textY = CENTER_Y - MINOR_R * Math.cos(angle)

            let fill = '#0f172a'
            if (isActive) fill = '#0369a1'
            else if (isRelated) fill = '#0c4a6e'

            return (
              <g key={`minor-${i}`}>
                <path
                  d={arcPath(angle, 45, INNER_R - 2, sliceAngle / 2 - 0.02)}
                  fill={fill}
                  stroke="#1e293b"
                  strokeWidth={0.5}
                />
                <text
                  x={textX}
                  y={textY}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={9}
                  fontWeight={isActive ? 700 : 400}
                  fill={isActive ? '#bae6fd' : isRelated ? '#7dd3fc' : '#475569'}
                >
                  {key}
                </text>
              </g>
            )
          })}

          {/* Key signature labels (outer) */}
          {KEY_SIGNATURES.map((sig, i) => {
            const angle = i * sliceAngle
            const r = OUTER_R + 14
            const textX = CENTER_X + r * Math.sin(angle)
            const textY = CENTER_Y - r * Math.cos(angle)
            return (
              <text
                key={`sig-${i}`}
                x={textX}
                y={textY}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={7}
                fill="#334155"
              >
                {sig}
              </text>
            )
          })}

          {/* Center label */}
          <text
            x={CENTER_X}
            y={CENTER_Y - 6}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={8}
            fill="#475569"
          >
            Major
          </text>
          <text
            x={CENTER_X}
            y={CENTER_Y + 6}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={7}
            fill="#334155"
          >
            minor
          </text>
        </svg>
      </div>

      {/* Active key info */}
      {activeKey && activeIndex >= 0 && (
        <div className="text-center text-xs text-slate-500">
          <span className="text-sky-400 font-bold">{activeKey} Major</span>
          {' / '}
          <span className="text-slate-400">{MINOR_KEYS[activeIndex]}</span>
          {' — '}
          <span className="text-slate-600">{KEY_SIGNATURES[activeIndex]}</span>
          {' — '}
          IV: <span className="text-cyan-400">{MAJOR_KEYS[(activeIndex - 1 + 12) % 12]}</span>
          {' | '}
          V: <span className="text-cyan-400">{MAJOR_KEYS[(activeIndex + 1) % 12]}</span>
        </div>
      )}
    </div>
  )
})

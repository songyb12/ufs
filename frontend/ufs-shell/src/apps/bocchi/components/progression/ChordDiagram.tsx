import { memo } from 'react'

interface ChordDiagramProps {
  frets: number[]        // per-string: -1=mute, 0=open, 1+=fret
  name?: string          // chord name label (e.g., "C Maj")
  rootStringIndex?: number  // which string has the root (for visual emphasis)
}

/**
 * Compact chord fingering diagram rendered as SVG.
 * Standard vertical "chord box" format:
 *  - Strings vertical (left=low, right=high)
 *  - Frets horizontal
 *  - Shows 4-5 fret window around the fingered positions
 *  - X for muted, O for open, dots for fingered notes
 */
export const ChordDiagram = memo(function ChordDiagram({
  frets,
  name,
  rootStringIndex,
}: ChordDiagramProps) {
  const stringCount = frets.length

  // Determine fret window to display
  const frettedFrets = frets.filter((f) => f > 0)
  const minFret = frettedFrets.length > 0 ? Math.min(...frettedFrets) : 1
  const maxFret = frettedFrets.length > 0 ? Math.max(...frettedFrets) : 4
  const windowSize = 4
  const startFret = minFret <= 3 ? 1 : minFret
  const endFret = Math.max(startFret + windowSize - 1, maxFret)
  const displayFrets = endFret - startFret + 1
  const showNut = startFret === 1

  // Layout
  const stringSpacing = 14
  const fretSpacing = 18
  const padLeft = 20
  const padTop = name ? 22 : 8
  const padBottom = 8
  const padRight = 8
  const headerHeight = 12  // space for O/X markers above nut

  const diagramWidth = padLeft + stringSpacing * (stringCount - 1) + padRight
  const diagramHeight = padTop + headerHeight + fretSpacing * displayFrets + padBottom

  const getStringX = (si: number) => padLeft + si * stringSpacing
  const getFretY = (fretOffset: number) => padTop + headerHeight + fretOffset * fretSpacing

  return (
    <svg
      viewBox={`0 0 ${diagramWidth} ${diagramHeight}`}
      width={diagramWidth}
      height={diagramHeight}
      className="flex-shrink-0"
    >
      {/* Chord name */}
      {name && (
        <text
          x={diagramWidth / 2}
          y={12}
          textAnchor="middle"
          fontSize={11}
          fontWeight={700}
          fill="#e2e8f0"
        >
          {name}
        </text>
      )}

      {/* Nut (thick top line) or fret number */}
      {showNut ? (
        <line
          x1={getStringX(0) - 2}
          y1={getFretY(0)}
          x2={getStringX(stringCount - 1) + 2}
          y2={getFretY(0)}
          stroke="#e2e8f0"
          strokeWidth={3}
        />
      ) : (
        <text
          x={padLeft - 14}
          y={getFretY(0.5) + 1}
          textAnchor="middle"
          fontSize={9}
          fill="#64748b"
        >
          {startFret}fr
        </text>
      )}

      {/* Fret lines */}
      {Array.from({ length: displayFrets + 1 }, (_, i) => (
        <line
          key={`fret-${i}`}
          x1={getStringX(0)}
          y1={getFretY(i)}
          x2={getStringX(stringCount - 1)}
          y2={getFretY(i)}
          stroke={i === 0 && showNut ? '#e2e8f0' : '#475569'}
          strokeWidth={i === 0 && showNut ? 0 : 1}
        />
      ))}

      {/* String lines */}
      {Array.from({ length: stringCount }, (_, si) => (
        <line
          key={`str-${si}`}
          x1={getStringX(si)}
          y1={getFretY(0)}
          x2={getStringX(si)}
          y2={getFretY(displayFrets)}
          stroke="#64748b"
          strokeWidth={1}
        />
      ))}

      {/* Open / mute markers above nut */}
      {frets.map((f, si) => {
        const x = getStringX(si)
        const y = getFretY(0) - 6
        if (f === -1) {
          return (
            <text
              key={`mx-${si}`}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={10}
              fontWeight={700}
              fill="#ef4444"
            >
              X
            </text>
          )
        }
        if (f === 0) {
          return (
            <circle
              key={`open-${si}`}
              cx={x}
              cy={y}
              r={4}
              fill="none"
              stroke="#94a3b8"
              strokeWidth={1.5}
            />
          )
        }
        return null
      })}

      {/* Fingered dots */}
      {frets.map((f, si) => {
        if (f <= 0) return null
        const x = getStringX(si)
        const fretOffset = f - startFret
        const y = getFretY(fretOffset) + fretSpacing / 2
        const isRoot = si === rootStringIndex
        return (
          <circle
            key={`dot-${si}`}
            cx={x}
            cy={y}
            r={5}
            fill={isRoot ? '#38bdf8' : '#e2e8f0'}
            stroke={isRoot ? '#0ea5e9' : 'none'}
            strokeWidth={isRoot ? 1.5 : 0}
          />
        )
      })}
    </svg>
  )
})

import { memo } from 'react'
import type { Note } from '../../types/music'

interface NoteLabelProps {
  note: Note
  x: number
  y: number
  isHighlighted: boolean
  isInScale?: boolean
  isRoot?: boolean
  onClick?: () => void
}

/**
 * Color priority:
 * 1. Click highlight — orange solid
 * 2. Root note      — sky-blue solid + thick stroke
 * 3. Scale/chord    — sky-blue translucent
 * 4. Default        — transparent
 */
export const NoteLabel = memo(function NoteLabel({
  note,
  x,
  y,
  isHighlighted,
  isInScale = false,
  isRoot = false,
  onClick,
}: NoteLabelProps) {
  const radius = 12
  const isSharp = note.name.includes('#')

  // Determine visual state
  const isVisible = isHighlighted || isInScale || isRoot

  let fillColor = 'transparent'
  let strokeColor = '#475569'
  let strokeWidth = 1
  let fillOpacity = 0
  let textColor = '#94a3b8'
  let textWeight = 400
  let textOpacity = 0.6

  if (isHighlighted) {
    // Click highlight — orange
    fillColor = '#f97316'
    strokeColor = '#f97316'
    fillOpacity = 1
    textColor = '#fff'
    textWeight = 700
    textOpacity = 1
  } else if (isRoot) {
    // Root note — solid sky-blue
    fillColor = '#38bdf8'
    strokeColor = '#0ea5e9'
    strokeWidth = 2
    fillOpacity = 1
    textColor = '#0f172a'
    textWeight = 700
    textOpacity = 1
  } else if (isInScale) {
    // Scale/chord note — translucent sky-blue
    fillColor = '#38bdf8'
    strokeColor = '#38bdf8'
    fillOpacity = 0.35
    textColor = '#7dd3fc'
    textWeight = 500
    textOpacity = 1
  }

  return (
    <g
      onClick={onClick}
      className="cursor-pointer"
      role="button"
      aria-label={`${note.name}${note.octave}`}
    >
      <circle
        cx={x}
        cy={y}
        r={radius}
        fill={fillColor}
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        opacity={isVisible ? fillOpacity : 0}
      />
      <text
        x={x}
        y={y}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={isSharp ? 9 : 10}
        fill={textColor}
        fontWeight={textWeight}
        opacity={isVisible ? textOpacity : 0.6}
      >
        {note.name}
      </text>
    </g>
  )
})

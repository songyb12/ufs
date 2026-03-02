import { memo } from 'react'
import type { Note } from '../../types/music'

interface NoteLabelProps {
  note: Note
  x: number
  y: number
  isHighlighted: boolean
  onClick?: () => void
}

export const NoteLabel = memo(function NoteLabel({
  note,
  x,
  y,
  isHighlighted,
  onClick,
}: NoteLabelProps) {
  const radius = 12
  const isSharp = note.name.includes('#')

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
        fill={isHighlighted ? '#f97316' : 'transparent'}
        stroke={isHighlighted ? '#f97316' : '#475569'}
        strokeWidth={1}
        opacity={isHighlighted ? 1 : 0}
      />
      <text
        x={x}
        y={y}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={isSharp ? 9 : 10}
        fill={isHighlighted ? '#fff' : '#94a3b8'}
        fontWeight={isHighlighted ? 700 : 400}
        opacity={isHighlighted ? 1 : 0.6}
      >
        {note.name}
      </text>
    </g>
  )
})

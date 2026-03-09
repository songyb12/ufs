import { memo } from 'react'
import type { Note } from '../../types/music'

interface NoteLabelProps {
  note: Note
  x: number
  y: number
  isHighlighted: boolean
  isInScale?: boolean
  isRoot?: boolean
  isVoicing?: boolean
  isMidiActive?: boolean
  isScaleOverlay?: boolean
  displayLabel?: string  // custom label (for interval/degree modes)
  leftHanded?: boolean   // counter-transform text when fretboard is mirrored
  onClick?: () => void
}

/**
 * Color priority:
 * 1. Click highlight     — orange solid
 * 2. MIDI active         — purple solid
 * 3. Voicing root        — emerald solid + thick stroke
 * 4. Voicing chord tone  — emerald translucent
 * 5. Root note           — sky-blue solid + thick stroke
 * 6. Scale/chord         — sky-blue translucent
 * 7. Scale overlay       — amber translucent (improv suggestions)
 * 8. Default             — transparent
 */
export const NoteLabel = memo(function NoteLabel({
  note,
  x,
  y,
  isHighlighted,
  isInScale = false,
  isRoot = false,
  isVoicing = false,
  isMidiActive = false,
  isScaleOverlay = false,
  displayLabel,
  leftHanded = false,
  onClick,
}: NoteLabelProps) {
  const radius = 12
  const label = displayLabel ?? note.name
  const isSharp = label.includes('#') || label.length > 2

  // Determine visual state
  const isVisible = isHighlighted || isMidiActive || isVoicing || isInScale || isRoot || isScaleOverlay

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
  } else if (isMidiActive) {
    // MIDI active — purple
    fillColor = '#a855f7'
    strokeColor = '#9333ea'
    strokeWidth = 2
    fillOpacity = 1
    textColor = '#fff'
    textWeight = 700
    textOpacity = 1
  } else if (isVoicing && isRoot) {
    // Voicing root — solid emerald + thick stroke
    fillColor = '#34d399'
    strokeColor = '#10b981'
    strokeWidth = 2
    fillOpacity = 1
    textColor = '#0f172a'
    textWeight = 700
    textOpacity = 1
  } else if (isVoicing) {
    // Voicing chord tone — emerald
    fillColor = '#34d399'
    strokeColor = '#34d399'
    fillOpacity = 0.6
    textColor = '#a7f3d0'
    textWeight = 600
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
  } else if (isScaleOverlay) {
    // Scale overlay — translucent amber (improv suggestions)
    fillColor = '#fbbf24'
    strokeColor = '#fbbf24'
    fillOpacity = 0.25
    textColor = '#fcd34d'
    textWeight = 400
    textOpacity = 0.85
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
        {...(leftHanded ? { transform: `translate(${2 * x}, 0) scale(-1, 1)` } : {})}
      >
        {label}
      </text>
    </g>
  )
})

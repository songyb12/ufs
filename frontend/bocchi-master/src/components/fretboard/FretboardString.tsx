import { memo } from 'react'

interface FretboardStringProps {
  y: number
  xStart: number
  xEnd: number
  stringIndex: number  // 0 = lowest (thickest)
  totalStrings: number
}

export const FretboardString = memo(function FretboardString({
  y,
  xStart,
  xEnd,
  stringIndex,
  totalStrings,
}: FretboardStringProps) {
  // Thicker strings at lower indices (bass strings)
  const maxWidth = 2.5
  const minWidth = 0.8
  const strokeWidth =
    maxWidth - ((maxWidth - minWidth) * stringIndex) / (totalStrings - 1)

  return (
    <line
      x1={xStart}
      y1={y}
      x2={xEnd}
      y2={y}
      stroke="#64748b"
      strokeWidth={strokeWidth}
    />
  )
})

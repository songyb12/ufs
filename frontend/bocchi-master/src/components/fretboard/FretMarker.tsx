import { memo } from 'react'

/** Fret positions that have single dot markers */
const SINGLE_DOT_FRETS = [3, 5, 7, 9, 15, 17, 19, 21]
/** Fret 12 has double dots */
const DOUBLE_DOT_FRET = 12

interface FretMarkerProps {
  fret: number
  x: number
  yCenter: number   // vertical center of the fretboard
  ySpread: number   // distance from center to place double dots
}

export const FretMarker = memo(function FretMarker({
  fret,
  x,
  yCenter,
  ySpread,
}: FretMarkerProps) {
  const dotRadius = 5
  const fill = '#334155'

  if (fret === DOUBLE_DOT_FRET) {
    return (
      <>
        <circle cx={x} cy={yCenter - ySpread} r={dotRadius} fill={fill} />
        <circle cx={x} cy={yCenter + ySpread} r={dotRadius} fill={fill} />
      </>
    )
  }

  if (SINGLE_DOT_FRETS.includes(fret)) {
    return <circle cx={x} cy={yCenter} r={dotRadius} fill={fill} />
  }

  return null
})

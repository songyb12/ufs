import { useEffect, useRef, memo } from 'react'

interface MetronomePendulumProps {
  bpm: number
  isPlaying: boolean
  currentBeat: number
}

const WIDTH = 200
const HEIGHT = 80
const PIVOT_X = WIDTH / 2
const PIVOT_Y = 8
const ARM_LENGTH = 60
const MAX_ANGLE = 35 // degrees

/**
 * Animated metronome pendulum that swings in sync with the beat.
 * Uses requestAnimationFrame for smooth 60fps motion with sinusoidal
 * easing to match natural pendulum physics.
 */
export const MetronomePendulum = memo(function MetronomePendulum({
  bpm,
  isPlaying,
  currentBeat,
}: MetronomePendulumProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number | null>(null)
  const phaseRef = useRef(0)
  const lastTimeRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    if (!isPlaying) {
      // Draw resting position (centered)
      ctx.clearRect(0, 0, WIDTH, HEIGHT)
      drawPendulum(ctx, 0, false)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
      phaseRef.current = 0
      lastTimeRef.current = 0
      return
    }

    const beatDuration = 60 / bpm // seconds per beat
    // Pendulum completes one full swing (left→right or right→left) per beat
    // So the period is 2 * beatDuration (full cycle = two beats)
    const angularVelocity = Math.PI / beatDuration // radians per second

    const animate = (timestamp: number) => {
      if (!lastTimeRef.current) lastTimeRef.current = timestamp
      const dt = (timestamp - lastTimeRef.current) / 1000
      lastTimeRef.current = timestamp

      phaseRef.current += angularVelocity * dt
      const angle = Math.sin(phaseRef.current) * MAX_ANGLE

      ctx.clearRect(0, 0, WIDTH, HEIGHT)
      const isDownbeat = currentBeat === 0
      drawPendulum(ctx, angle, isDownbeat)

      rafRef.current = requestAnimationFrame(animate)
    }

    rafRef.current = requestAnimationFrame(animate)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [bpm, isPlaying, currentBeat])

  return (
    <canvas
      ref={canvasRef}
      width={WIDTH}
      height={HEIGHT}
      className="mx-auto"
      style={{ imageRendering: 'auto' }}
    />
  )
})

function drawPendulum(
  ctx: CanvasRenderingContext2D,
  angleDeg: number,
  isDownbeat: boolean,
): void {
  const angleRad = (angleDeg * Math.PI) / 180
  const bobX = PIVOT_X + ARM_LENGTH * Math.sin(angleRad)
  const bobY = PIVOT_Y + ARM_LENGTH * Math.cos(angleRad)
  const bobRadius = 8

  // Subtle trail/blur effect
  const trailAlpha = Math.abs(angleDeg) / MAX_ANGLE
  const trailColor = isDownbeat
    ? `rgba(249, 115, 22, ${0.1 * trailAlpha})`
    : `rgba(56, 189, 248, ${0.08 * trailAlpha})`

  // Trail arc (faded)
  ctx.beginPath()
  ctx.arc(PIVOT_X, PIVOT_Y, ARM_LENGTH, Math.PI / 2 - 0.6, Math.PI / 2 + 0.6)
  ctx.strokeStyle = trailColor
  ctx.lineWidth = 3
  ctx.stroke()

  // Pivot dot
  ctx.beginPath()
  ctx.arc(PIVOT_X, PIVOT_Y, 3, 0, Math.PI * 2)
  ctx.fillStyle = '#475569'
  ctx.fill()

  // Arm
  ctx.beginPath()
  ctx.moveTo(PIVOT_X, PIVOT_Y)
  ctx.lineTo(bobX, bobY)
  ctx.strokeStyle = '#64748b'
  ctx.lineWidth = 2
  ctx.stroke()

  // Bob (weighted end)
  const bobColor = isDownbeat ? '#f97316' : '#38bdf8'
  const glowColor = isDownbeat
    ? 'rgba(249, 115, 22, 0.3)'
    : 'rgba(56, 189, 248, 0.2)'

  // Glow
  ctx.beginPath()
  ctx.arc(bobX, bobY, bobRadius + 4, 0, Math.PI * 2)
  ctx.fillStyle = glowColor
  ctx.fill()

  // Bob
  ctx.beginPath()
  ctx.arc(bobX, bobY, bobRadius, 0, Math.PI * 2)
  ctx.fillStyle = bobColor
  ctx.fill()
  ctx.strokeStyle = isDownbeat ? '#ea580c' : '#0ea5e9'
  ctx.lineWidth = 1.5
  ctx.stroke()

  // Tick marks at extremes
  const tickY = PIVOT_Y + ARM_LENGTH + bobRadius + 8
  const leftX = PIVOT_X - ARM_LENGTH * Math.sin((MAX_ANGLE * Math.PI) / 180)
  const rightX = PIVOT_X + ARM_LENGTH * Math.sin((MAX_ANGLE * Math.PI) / 180)

  ctx.beginPath()
  ctx.moveTo(leftX, tickY - 4)
  ctx.lineTo(leftX, tickY + 4)
  ctx.moveTo(rightX, tickY - 4)
  ctx.lineTo(rightX, tickY + 4)
  ctx.moveTo(PIVOT_X, tickY - 3)
  ctx.lineTo(PIVOT_X, tickY + 3)
  ctx.strokeStyle = '#334155'
  ctx.lineWidth = 1
  ctx.stroke()
}

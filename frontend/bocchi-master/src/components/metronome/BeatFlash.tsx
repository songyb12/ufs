import { useEffect, useRef, memo } from 'react'

interface BeatFlashProps {
  currentBeat: number
  isPlaying: boolean
  enabled: boolean
}

/**
 * Full-screen border flash on each metronome beat.
 * Downbeat (beat 0) flashes orange, other beats flash sky blue.
 * Uses CSS animation for smooth fade-out.
 */
export const BeatFlash = memo(function BeatFlash({
  currentBeat,
  isPlaying,
  enabled,
}: BeatFlashProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!enabled || !isPlaying || currentBeat < 0 || !ref.current) return

    const el = ref.current
    // Reset animation
    el.classList.remove('animate-beat-flash')
    el.style.setProperty('--flash-color', currentBeat === 0
      ? 'rgba(249, 115, 22, 0.4)'  // orange
      : 'rgba(56, 189, 248, 0.2)'  // sky blue
    )
    void el.offsetWidth // force reflow
    el.classList.add('animate-beat-flash')
  }, [currentBeat, isPlaying, enabled])

  if (!enabled) return null

  return (
    <div
      ref={ref}
      className="fixed inset-0 pointer-events-none z-50 border-4 border-transparent rounded-lg"
      style={{
        borderColor: 'var(--flash-color, transparent)',
        opacity: 0,
      }}
    />
  )
})

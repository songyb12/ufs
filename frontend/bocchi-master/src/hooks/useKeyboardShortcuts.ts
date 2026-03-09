import { useEffect, useCallback } from 'react'

export interface KeyboardShortcutActions {
  toggleMetronome: () => void
  increaseBpm: (amount?: number) => void
  decreaseBpm: (amount?: number) => void
  toggleBackingTrack: () => void
  nextChord: () => void
  prevChord: () => void
  togglePracticeMode: () => void
}

/**
 * Global keyboard shortcuts for hands-free control during practice.
 *
 * Shortcuts:
 *   Space       — Play / Stop metronome
 *   ↑ / ↓      — BPM +/- 5
 *   Shift+↑/↓  — BPM +/- 1 (fine)
 *   B           — Toggle backing track
 *   → / ←      — Next / Previous chord in progression
 *   P           — Toggle practice mode
 *   Escape      — Stop metronome
 */
export function useKeyboardShortcuts(actions: KeyboardShortcutActions): void {
  const handler = useCallback(
    (e: KeyboardEvent) => {
      // Skip if user is typing in an input/textarea/select
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      switch (e.code) {
        case 'Space':
          e.preventDefault()
          actions.toggleMetronome()
          break

        case 'ArrowUp':
          e.preventDefault()
          actions.increaseBpm(e.shiftKey ? 1 : 5)
          break

        case 'ArrowDown':
          e.preventDefault()
          actions.decreaseBpm(e.shiftKey ? 1 : 5)
          break

        case 'ArrowRight':
          if (!e.shiftKey && !e.ctrlKey && !e.metaKey) {
            e.preventDefault()
            actions.nextChord()
          }
          break

        case 'ArrowLeft':
          if (!e.shiftKey && !e.ctrlKey && !e.metaKey) {
            e.preventDefault()
            actions.prevChord()
          }
          break

        case 'KeyB':
          if (!e.ctrlKey && !e.metaKey) {
            actions.toggleBackingTrack()
          }
          break

        case 'KeyP':
          if (!e.ctrlKey && !e.metaKey) {
            actions.togglePracticeMode()
          }
          break

        case 'Escape':
          // Stop metronome on Escape (only stop, not toggle)
          actions.toggleMetronome()
          break
      }
    },
    [actions],
  )

  useEffect(() => {
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handler])
}

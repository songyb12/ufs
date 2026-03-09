import { useEffect, useCallback } from 'react'

interface ShortcutHelpOverlayProps {
  visible: boolean
  onClose: () => void
}

interface ShortcutEntry {
  keys: string[]
  description: string
}

const SHORTCUT_GROUPS: { title: string; entries: ShortcutEntry[] }[] = [
  {
    title: 'Playback',
    entries: [
      { keys: ['Space'], description: 'Play / Stop metronome' },
      { keys: ['Esc'], description: 'Stop metronome' },
      { keys: ['B'], description: 'Toggle backing track' },
    ],
  },
  {
    title: 'Tempo',
    entries: [
      { keys: ['↑'], description: 'BPM +5' },
      { keys: ['↓'], description: 'BPM -5' },
      { keys: ['Shift', '↑'], description: 'BPM +1 (fine)' },
      { keys: ['Shift', '↓'], description: 'BPM -1 (fine)' },
    ],
  },
  {
    title: 'Navigation',
    entries: [
      { keys: ['→'], description: 'Next chord in progression' },
      { keys: ['←'], description: 'Previous chord' },
    ],
  },
  {
    title: 'Tools',
    entries: [
      { keys: ['P'], description: 'Toggle practice mode' },
      { keys: ['?'], description: 'Show / hide this help' },
    ],
  },
]

function Key({ label }: { label: string }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[1.8rem] h-7 px-1.5 bg-slate-700 border border-slate-600 rounded text-xs font-mono text-slate-200 shadow-sm">
      {label}
    </kbd>
  )
}

export function ShortcutHelpOverlay({ visible, onClose }: ShortcutHelpOverlayProps) {
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === '?') {
        e.preventDefault()
        onClose()
      }
    },
    [onClose],
  )

  useEffect(() => {
    if (!visible) return
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [visible, handleKey])

  if (!visible) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">Keyboard Shortcuts</h2>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 text-xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="space-y-4">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title}>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                {group.title}
              </h3>
              <div className="space-y-1.5">
                {group.entries.map((entry, idx) => (
                  <div key={idx} className="flex items-center justify-between">
                    <span className="text-sm text-slate-300">{entry.description}</span>
                    <div className="flex items-center gap-1">
                      {entry.keys.map((k, ki) => (
                        <span key={ki} className="flex items-center gap-0.5">
                          {ki > 0 && <span className="text-slate-600 text-xs">+</span>}
                          <Key label={k} />
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-slate-600 mt-4 text-center">
          Press <Key label="?" /> or <Key label="Esc" /> to close
        </p>
      </div>
    </div>
  )
}

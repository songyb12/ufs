import { useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAppByShortcut } from './appRegistry.ts'

interface ShortcutOptions {
  onSearch?: () => void
  onToggleSidebar?: () => void
}

/**
 * Global keyboard shortcuts:
 * - Ctrl+K / Cmd+K → Search
 * - Ctrl+B / Cmd+B → Toggle sidebar
 * - Ctrl+<number> → Navigate to app by shortcut key
 * - Ctrl+H / Cmd+H → Go home
 */
export function useKeyboardShortcuts(options: ShortcutOptions = {}) {
  const navigate = useNavigate()

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Skip if user is typing in an input/textarea
      const target = e.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        return
      }

      const isMod = e.ctrlKey || e.metaKey

      // Ctrl/Cmd + K → Search
      if (isMod && e.key === 'k') {
        e.preventDefault()
        options.onSearch?.()
        return
      }

      // Ctrl/Cmd + B → Toggle sidebar
      if (isMod && e.key === 'b') {
        // Only if not in Bocchi (where it has its own shortcuts)
        if (!window.location.pathname.startsWith('/bocchi')) {
          e.preventDefault()
          options.onToggleSidebar?.()
        }
        return
      }

      // Ctrl/Cmd + H → Home
      if (isMod && e.key === 'h') {
        e.preventDefault()
        navigate('/')
        return
      }

      // Alt + letter → Navigate to app
      if (e.altKey && !isMod && !e.shiftKey) {
        const app = getAppByShortcut(e.key)
        if (app) {
          e.preventDefault()
          navigate(app.path)
        }
      }
    },
    [navigate, options],
  )

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])
}

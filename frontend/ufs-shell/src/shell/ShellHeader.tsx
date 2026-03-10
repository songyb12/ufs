import { useLocation } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'

interface ShellHeaderProps {
  sidebarOpen: boolean
  onToggleSidebar: () => void
}

export function ShellHeader({ sidebarOpen, onToggleSidebar }: ShellHeaderProps) {
  const location = useLocation()

  const currentApp = APP_REGISTRY.find((app) =>
    location.pathname.startsWith(app.path),
  )

  return (
    <header className="h-14 flex items-center justify-between px-4 bg-ufs-800 border-b border-ufs-600/50">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg hover:bg-ufs-700 text-ufs-400 hover:text-white transition-colors"
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {sidebarOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>

        {currentApp ? (
          <div className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: currentApp.color }}
            />
            <span className="text-sm font-medium text-white">
              {currentApp.name}
            </span>
          </div>
        ) : (
          <span className="text-sm font-medium text-white">Home</span>
        )}
      </div>

      <div className="flex items-center gap-2 text-ufs-400 text-xs">
        <span>UFS v0.1</span>
      </div>
    </header>
  )
}

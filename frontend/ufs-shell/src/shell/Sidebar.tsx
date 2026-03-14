import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'
import { useOnlineStatus } from '../shared/usePlatform.ts'

interface SidebarProps {
  open: boolean
  collapsed?: boolean
}

const STATUS_BADGE: Record<string, string> = {
  active: '',
  dev: 'bg-yellow-500/20 text-yellow-400',
  planned: 'bg-ufs-600 text-ufs-400',
}

export function Sidebar({ open, collapsed = false }: SidebarProps) {
  const location = useLocation()
  const isOnline = useOnlineStatus()
  const [filter, setFilter] = useState('')

  if (!open) return null

  const filteredApps = filter
    ? APP_REGISTRY.filter(
        (app) =>
          app.name.toLowerCase().includes(filter.toLowerCase()) ||
          app.tags?.some((t) => t.includes(filter.toLowerCase())),
      )
    : APP_REGISTRY

  const isCollapsed = collapsed

  return (
    <aside
      className={`${isCollapsed ? 'w-16' : 'w-56'} flex flex-col bg-ufs-800 border-r border-ufs-600/50 h-screen sticky top-0 transition-all duration-200 no-print`}
    >
      {/* Logo */}
      <NavLink
        to="/"
        className="flex items-center gap-2 px-4 py-3 border-b border-ufs-600/50 shrink-0"
      >
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm shrink-0">
          U
        </div>
        {!isCollapsed && (
          <div className="min-w-0">
            <div className="text-white font-semibold text-sm leading-tight">UFS</div>
            <div className="text-ufs-400 text-[10px] leading-tight">Personal AI OS</div>
          </div>
        )}
      </NavLink>

      {/* Search filter */}
      {!isCollapsed && (
        <div className="px-3 pt-3 pb-1">
          <div className="relative">
            <svg className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-ufs-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter apps..."
              className="w-full bg-ufs-700 text-xs text-white rounded-md py-1.5 pl-7 pr-2 outline-none placeholder:text-ufs-500 focus:ring-1 focus:ring-accent/50"
            />
            {filter && (
              <button
                onClick={() => setFilter('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-ufs-500 hover:text-white text-xs"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 py-2 px-2 space-y-0.5 overflow-y-auto">
        {/* Home */}
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `sidebar-item flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              isActive
                ? 'bg-accent/10 text-accent'
                : 'text-ufs-400 hover:bg-ufs-700 hover:text-white'
            }`
          }
          title="Home (Ctrl+H)"
        >
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
          </svg>
          {!isCollapsed && <span>Home</span>}
        </NavLink>

        {/* Apps section */}
        {!isCollapsed && (
          <div className="pt-3 pb-1 px-3">
            <span className="text-[10px] font-semibold text-ufs-500 uppercase tracking-wider">
              Apps ({filteredApps.length})
            </span>
          </div>
        )}

        {filteredApps.map((app) => {
          const isActive = location.pathname.startsWith(app.path)
          return (
            <div key={app.id} className="tooltip-trigger relative">
              <NavLink
                to={app.path}
                className={`sidebar-item flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                  isActive
                    ? 'bg-white/5 font-medium'
                    : 'text-ufs-400 hover:bg-ufs-700 hover:text-white'
                }`}
                style={isActive ? { color: app.color } : undefined}
                title={isCollapsed ? `${app.name} (Alt+${app.shortcut})` : `Alt+${app.shortcut}`}
              >
                <div className="relative shrink-0">
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
                  </svg>
                  {/* Active indicator dot */}
                  {isActive && (
                    <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full" style={{ backgroundColor: app.color }} />
                  )}
                </div>
                {!isCollapsed && (
                  <>
                    <span className="truncate flex-1">{app.name}</span>
                    {app.status !== 'active' && (
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 ${STATUS_BADGE[app.status]}`}
                      >
                        {app.status}
                      </span>
                    )}
                    {app.shortcut && (
                      <kbd className="text-[9px] text-ufs-600 px-1 rounded border border-ufs-700 bg-ufs-800 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        {app.shortcut}
                      </kbd>
                    )}
                  </>
                )}
              </NavLink>
              {/* Tooltip for collapsed mode */}
              {isCollapsed && (
                <div className="tooltip-content absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1 rounded bg-ufs-700 text-white text-xs whitespace-nowrap z-50 shadow-lg">
                  {app.name}
                </div>
              )}
            </div>
          )
        })}

        {filteredApps.length === 0 && (
          <div className="px-3 py-4 text-xs text-ufs-500 text-center">
            No matching apps
          </div>
        )}
      </nav>

      {/* Footer */}
      {!isCollapsed && (
        <div className="px-4 py-3 border-t border-ufs-600/50 space-y-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-400' : 'bg-red-400'}`} />
              <span className="text-[10px] text-ufs-500">{isOnline ? 'Connected' : 'Offline'}</span>
            </div>
            <span className="text-[10px] text-ufs-600">Local Server</span>
          </div>
          <div className="flex items-center gap-2 text-[9px] text-ufs-600">
            <span>⌘K Search</span>
            <span>⌘B Sidebar</span>
          </div>
        </div>
      )}
    </aside>
  )
}

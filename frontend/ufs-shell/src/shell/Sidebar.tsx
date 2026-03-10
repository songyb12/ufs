import { NavLink } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'

interface SidebarProps {
  open: boolean
}

const STATUS_BADGE: Record<string, string> = {
  active: '',
  dev: 'bg-yellow-500/20 text-yellow-400',
  planned: 'bg-ufs-600 text-ufs-400',
}

export function Sidebar({ open }: SidebarProps) {
  if (!open) return null

  return (
    <aside className="w-56 flex flex-col bg-ufs-800 border-r border-ufs-600/50">
      {/* Logo */}
      <NavLink
        to="/"
        className="flex items-center gap-2 px-5 py-4 border-b border-ufs-600/50"
      >
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm">
          U
        </div>
        <div>
          <div className="text-white font-semibold text-sm leading-tight">UFS</div>
          <div className="text-ufs-400 text-[10px] leading-tight">Personal AI OS</div>
        </div>
      </NavLink>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-3 space-y-1">
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
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
          </svg>
          Home
        </NavLink>

        <div className="pt-3 pb-1 px-3">
          <span className="text-[10px] font-semibold text-ufs-500 uppercase tracking-wider">
            Apps
          </span>
        </div>

        {APP_REGISTRY.map((app) => (
          <NavLink
            key={app.id}
            to={app.path}
            className={({ isActive }) =>
              `sidebar-item flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                isActive
                  ? 'bg-accent/10 text-accent'
                  : 'text-ufs-400 hover:bg-ufs-700 hover:text-white'
              }`
            }
          >
            <svg
              className="w-4 h-4 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
            </svg>
            <span className="truncate">{app.name}</span>
            {app.status !== 'active' && (
              <span
                className={`ml-auto text-[9px] px-1.5 py-0.5 rounded-full ${STATUS_BADGE[app.status]}`}
              >
                {app.status}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-ufs-600/50">
        <div className="text-[10px] text-ufs-500">
          Local Home Server
        </div>
      </div>
    </aside>
  )
}

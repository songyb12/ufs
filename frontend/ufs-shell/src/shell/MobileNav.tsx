import { NavLink } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'

export function MobileNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-ufs-800 border-t border-ufs-600/50 px-2 py-1 safe-area-bottom">
      <div className="flex items-center justify-around">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-[10px] ${
              isActive ? 'text-accent' : 'text-ufs-400'
            }`
          }
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
          </svg>
          Home
        </NavLink>

        {APP_REGISTRY.map((app) => (
          <NavLink
            key={app.id}
            to={app.path}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-[10px] ${
                isActive ? 'font-medium' : 'text-ufs-400'
              }`
            }
            style={({ isActive }) => isActive ? { color: app.color } : undefined}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
            </svg>
            {app.name.split('-')[0]}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}

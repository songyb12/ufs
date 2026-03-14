import { NavLink, useLocation } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'

export function MobileNav() {
  const location = useLocation()

  // Only show first 4 apps + home for mobile
  const visibleApps = APP_REGISTRY.slice(0, 4)

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-ufs-800/95 glass border-t border-ufs-600/50 px-2 py-1 safe-area-bottom no-print">
      <div className="flex items-center justify-around max-w-md mx-auto">
        {/* Home */}
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-[10px] transition-colors relative ${
              isActive ? 'text-accent' : 'text-ufs-400'
            }`
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span className="absolute -top-0.5 w-4 h-0.5 rounded-full bg-accent" />
              )}
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
              </svg>
              <span>Home</span>
            </>
          )}
        </NavLink>

        {/* App links */}
        {visibleApps.map((app) => {
          const isActive = location.pathname.startsWith(app.path)
          return (
            <NavLink
              key={app.id}
              to={app.path}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-[10px] transition-colors relative ${
                isActive ? 'font-medium' : 'text-ufs-400'
              }`}
              style={isActive ? { color: app.color } : undefined}
            >
              {isActive && (
                <span className="absolute -top-0.5 w-4 h-0.5 rounded-full" style={{ backgroundColor: app.color }} />
              )}
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d={app.icon} />
              </svg>
              <span className="truncate max-w-[48px]">{app.name.split('-')[0]}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}

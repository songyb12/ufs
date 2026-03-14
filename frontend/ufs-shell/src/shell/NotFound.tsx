import { Link, useLocation } from 'react-router-dom'
import { APP_REGISTRY } from '../shared/appRegistry.ts'

export default function NotFound() {
  const location = useLocation()
  const pathPart = location.pathname.split('/')[1] ?? ''
  const suggestions = APP_REGISTRY.filter(
    (app) =>
      app.id.includes(pathPart.toLowerCase()) ||
      app.name.toLowerCase().includes(pathPart.toLowerCase()) ||
      app.tags?.some((t) => t.includes(pathPart.toLowerCase())),
  ).slice(0, 3)

  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center animate-fade-in">
      <div className="relative mb-6">
        <div className="text-8xl font-bold text-ufs-700/50 select-none">404</div>
        <div className="absolute inset-0 flex items-center justify-center">
          <svg className="w-16 h-16 text-ufs-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
      </div>

      <h2 className="text-white font-semibold text-lg mb-2">Page Not Found</h2>
      <p className="text-ufs-400 text-sm mb-2 max-w-md">
        <code className="bg-ufs-700 px-2 py-0.5 rounded text-xs text-ufs-300">{location.pathname}</code>
      </p>
      <p className="text-ufs-500 text-xs mb-6">
        The page you're looking for doesn't exist or has been moved.
      </p>

      {suggestions.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-ufs-500 mb-2">Did you mean?</p>
          <div className="flex gap-2">
            {suggestions.map((app) => (
              <Link
                key={app.id}
                to={app.path}
                className="px-3 py-1.5 rounded-lg text-xs transition-colors border"
                style={{ color: app.color, borderColor: `${app.color}30`, backgroundColor: `${app.color}10` }}
              >
                {app.name}
              </Link>
            ))}
          </div>
        </div>
      )}

      <Link to="/" className="px-4 py-2 rounded-lg bg-accent text-white text-sm hover:bg-accent-hover transition-colors">
        Back to Home
      </Link>
    </div>
  )
}

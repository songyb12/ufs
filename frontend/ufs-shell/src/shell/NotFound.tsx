import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center">
      <div className="text-6xl font-bold text-ufs-600 mb-2">404</div>
      <h2 className="text-white font-semibold mb-2">Page Not Found</h2>
      <p className="text-ufs-400 text-sm mb-6">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="px-4 py-2 rounded-lg bg-accent text-white text-sm hover:bg-accent-hover transition-colors"
      >
        Back to Home
      </Link>
    </div>
  )
}

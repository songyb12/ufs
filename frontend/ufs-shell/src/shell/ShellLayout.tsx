import { useState, useCallback, useMemo } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar.tsx'
import { ShellHeader } from './ShellHeader.tsx'
import { MobileNav } from './MobileNav.tsx'
import { TVLayout } from './TVLayout.tsx'
import { SearchOverlay } from './SearchOverlay.tsx'
import { usePlatform } from '../shared/usePlatform.ts'
import { useKeyboardShortcuts } from '../shared/useKeyboardShortcuts.ts'

const SIDEBAR_KEY = 'ufs-sidebar-open'

export function ShellLayout() {
  const { platform, exitTvMode } = usePlatform()

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_KEY)
    return saved !== null ? saved === 'true' : true
  })

  const [searchOpen, setSearchOpen] = useState(false)

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => {
      const next = !prev
      localStorage.setItem(SIDEBAR_KEY, String(next))
      return next
    })
  }, [])

  const openSearch = useCallback(() => setSearchOpen(true), [])
  const closeSearch = useCallback(() => setSearchOpen(false), [])

  // Global keyboard shortcuts (memoize to avoid re-renders)
  const shortcutOptions = useMemo(() => ({
    onSearch: openSearch,
    onToggleSidebar: toggleSidebar,
  }), [openSearch, toggleSidebar])
  useKeyboardShortcuts(shortcutOptions)

  // TV mode — full-screen layout with keyboard navigation
  if (platform === 'tv') {
    return <TVLayout onExitTv={exitTvMode} />
  }

  // Mobile / Tablet — no sidebar, bottom nav
  if (platform === 'mobile' || platform === 'tablet') {
    return (
      <div className="min-h-screen flex flex-col bg-ufs-900">
        <ShellHeader sidebarOpen={false} onToggleSidebar={() => {}} onSearch={openSearch} />
        <main className="flex-1 p-4 pb-20 overflow-auto">
          <Outlet />
        </main>
        <MobileNav />
        <SearchOverlay open={searchOpen} onClose={closeSearch} />
      </div>
    )
  }

  // PC — sidebar + header
  return (
    <div className="min-h-screen flex bg-ufs-900">
      <Sidebar open={sidebarOpen} />

      <div className="flex-1 flex flex-col min-w-0">
        <ShellHeader
          sidebarOpen={sidebarOpen}
          onToggleSidebar={toggleSidebar}
          onSearch={openSearch}
        />

        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>

      <SearchOverlay open={searchOpen} onClose={closeSearch} />
    </div>
  )
}

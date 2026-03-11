import { useState, useCallback } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar.tsx'
import { ShellHeader } from './ShellHeader.tsx'
import { MobileNav } from './MobileNav.tsx'
import { TVLayout } from './TVLayout.tsx'
import { usePlatform } from '../shared/usePlatform.ts'

const SIDEBAR_KEY = 'ufs-sidebar-open'

export function ShellLayout() {
  const { platform, exitTvMode } = usePlatform()

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_KEY)
    return saved !== null ? saved === 'true' : true
  })

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => {
      const next = !prev
      localStorage.setItem(SIDEBAR_KEY, String(next))
      return next
    })
  }, [])

  // TV mode — full-screen layout with keyboard navigation
  if (platform === 'tv') {
    return <TVLayout onExitTv={exitTvMode} />
  }

  // Mobile — no sidebar, bottom nav
  if (platform === 'mobile') {
    return (
      <div className="min-h-screen flex flex-col bg-ufs-900">
        <ShellHeader sidebarOpen={false} onToggleSidebar={() => {}} />
        <main className="flex-1 p-4 pb-16 overflow-auto">
          <Outlet />
        </main>
        <MobileNav />
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
        />

        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

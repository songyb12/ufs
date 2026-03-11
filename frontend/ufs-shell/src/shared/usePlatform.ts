import { useState, useEffect } from 'react'

export type Platform = 'pc' | 'mobile' | 'tv'

const PLATFORM_KEY = 'ufs-platform-mode'

function detectPlatform(): Platform {
  // URL param override (sticky for TV kiosk)
  const params = new URLSearchParams(window.location.search)
  const mode = params.get('mode')
  if (mode === 'tv') {
    localStorage.setItem(PLATFORM_KEY, 'tv')
    return 'tv'
  }

  // Check cached TV mode
  const cached = localStorage.getItem(PLATFORM_KEY)
  if (cached === 'tv') return 'tv'

  // Screen width based
  if (window.innerWidth < 768) return 'mobile'
  return 'pc'
}

export function usePlatform() {
  const [platform, setPlatform] = useState<Platform>(detectPlatform)

  useEffect(() => {
    const handler = () => {
      const cached = localStorage.getItem(PLATFORM_KEY)
      if (cached === 'tv') return // TV mode is sticky
      setPlatform(window.innerWidth < 768 ? 'mobile' : 'pc')
    }
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  const exitTvMode = () => {
    localStorage.removeItem(PLATFORM_KEY)
    setPlatform(window.innerWidth < 768 ? 'mobile' : 'pc')
  }

  return { platform, exitTvMode }
}

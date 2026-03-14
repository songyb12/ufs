import { useState, useEffect, useCallback } from 'react'

export type Platform = 'pc' | 'mobile' | 'tablet' | 'tv'

const PLATFORM_KEY = 'ufs-platform-mode'

function detectPlatform(): Platform {
  const params = new URLSearchParams(window.location.search)
  const mode = params.get('mode')
  if (mode === 'tv') {
    localStorage.setItem(PLATFORM_KEY, 'tv')
    return 'tv'
  }
  const cached = localStorage.getItem(PLATFORM_KEY)
  if (cached === 'tv') return 'tv'
  const w = window.innerWidth
  if (w < 640) return 'mobile'
  if (w < 1024) return 'tablet'
  return 'pc'
}

export function usePlatform() {
  const [platform, setPlatform] = useState<Platform>(detectPlatform)

  useEffect(() => {
    const handler = () => {
      const cached = localStorage.getItem(PLATFORM_KEY)
      if (cached === 'tv') return
      const w = window.innerWidth
      if (w < 640) setPlatform('mobile')
      else if (w < 1024) setPlatform('tablet')
      else setPlatform('pc')
    }
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  const exitTvMode = useCallback(() => {
    localStorage.removeItem(PLATFORM_KEY)
    const w = window.innerWidth
    if (w < 640) setPlatform('mobile')
    else if (w < 1024) setPlatform('tablet')
    else setPlatform('pc')
  }, [])

  const enterTvMode = useCallback(() => {
    localStorage.setItem(PLATFORM_KEY, 'tv')
    setPlatform('tv')
  }, [])

  const isMobileOrTablet = platform === 'mobile' || platform === 'tablet'

  return { platform, exitTvMode, enterTvMode, isMobileOrTablet }
}

/** Hook for detecting online/offline status */
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  useEffect(() => {
    const on = () => setIsOnline(true)
    const off = () => setIsOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])
  return isOnline
}

/** Hook for reduced motion preference */
export function usePrefersReducedMotion() {
  const [prefers, setPrefers] = useState(() =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => setPrefers(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return prefers
}

import { useRef, useCallback } from 'react'

/**
 * Manages a single AudioContext instance.
 * Browsers require a user gesture to start AudioContext (Autoplay Policy).
 */
export function useAudioContext() {
  const ctxRef = useRef<AudioContext | null>(null)

  const ensureResumed = useCallback(async (): Promise<AudioContext> => {
    if (!ctxRef.current) {
      ctxRef.current = new AudioContext()
    }
    if (ctxRef.current.state === 'suspended') {
      await ctxRef.current.resume()
    }
    return ctxRef.current
  }, [])

  return {
    audioContext: ctxRef.current,
    ensureResumed,
  }
}

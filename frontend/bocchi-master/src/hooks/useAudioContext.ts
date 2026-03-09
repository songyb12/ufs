import { useCallback } from 'react'
import {
  getSharedAudioContext,
  getSharedAudioContextSync,
} from '../utils/audioContextSingleton'

/**
 * Hook that provides access to the shared AudioContext singleton.
 * Browsers require a user gesture to start AudioContext (Autoplay Policy).
 */
export function useAudioContext() {
  const ensureResumed = useCallback(async (): Promise<AudioContext> => {
    return getSharedAudioContext()
  }, [])

  return {
    audioContext: getSharedAudioContextSync(),
    ensureResumed,
  }
}

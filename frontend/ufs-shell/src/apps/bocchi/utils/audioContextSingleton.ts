/**
 * Module-level AudioContext singleton.
 *
 * Prevents multiple AudioContext instances (browser limit: ~6).
 * All consumers (metronome, sound engine, backing track) share one context.
 */

let sharedContext: AudioContext | null = null

export async function getSharedAudioContext(): Promise<AudioContext> {
  if (!sharedContext) {
    sharedContext = new AudioContext()
  }
  if (sharedContext.state === 'suspended') {
    await sharedContext.resume()
  }
  return sharedContext
}

export function getSharedAudioContextSync(): AudioContext | null {
  return sharedContext
}

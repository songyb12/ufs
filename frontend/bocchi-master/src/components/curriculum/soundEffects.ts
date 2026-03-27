/**
 * Curriculum Sound Effects — Web Audio API 기반 짧은 효과음
 *
 * audioContextSingleton을 사용하여 기존 오디오 시스템과 공유.
 * 모든 효과음은 100ms 이내, 사인파 기반.
 */

import { getSharedAudioContext } from '../../utils/audioContextSingleton'

function playTone(
  ctx: AudioContext,
  freq: number,
  startTime: number,
  duration: number,
  volume: number,
) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'sine'
  osc.frequency.value = freq
  osc.connect(gain)
  gain.connect(ctx.destination)

  gain.gain.setValueAtTime(0, startTime)
  gain.gain.linearRampToValueAtTime(volume, startTime + 0.008)
  gain.gain.setValueAtTime(volume, startTime + duration - 0.015)
  gain.gain.linearRampToValueAtTime(0, startTime + duration)

  osc.start(startTime)
  osc.stop(startTime + duration)
  osc.onended = () => { osc.disconnect(); gain.disconnect() }
}

/** 레슨/드릴 완료: 상승 2음 (C5 → E5) */
export async function playSuccessSound(): Promise<void> {
  const ctx = await getSharedAudioContext()
  const t = ctx.currentTime + 0.02
  playTone(ctx, 523.25, t, 0.08, 0.25)        // C5
  playTone(ctx, 659.25, t + 0.06, 0.08, 0.25) // E5
}

/** 레벨업: 상승 3음 아르페지오 (C5 → E5 → G5) */
export async function playLevelUpSound(): Promise<void> {
  const ctx = await getSharedAudioContext()
  const t = ctx.currentTime + 0.02
  playTone(ctx, 523.25, t, 0.10, 0.25)        // C5
  playTone(ctx, 659.25, t + 0.08, 0.10, 0.28) // E5
  playTone(ctx, 783.99, t + 0.16, 0.14, 0.30) // G5
}

/** 업적 달성: 팡파르 화음 (C5 + E5 + G5 동시) */
export async function playAchievementSound(): Promise<void> {
  const ctx = await getSharedAudioContext()
  const t = ctx.currentTime + 0.02
  playTone(ctx, 523.25, t, 0.15, 0.18) // C5
  playTone(ctx, 659.25, t, 0.15, 0.18) // E5
  playTone(ctx, 783.99, t, 0.15, 0.18) // G5
}

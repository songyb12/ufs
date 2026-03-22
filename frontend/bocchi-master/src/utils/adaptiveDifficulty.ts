/**
 * Adaptive Difficulty System
 *
 * Analyzes historical drill performance and adjusts drill config
 * (BPM, chord count, quiz difficulty, duration) accordingly.
 *
 * Difficulty tiers:
 *   - 'easier'  : accuracy < 60% — reduce demands to build confidence
 *   - 'normal'  : 60–80% — slight adjustments, learning zone
 *   - 'on-track': 80–95% — keep as-is, healthy challenge
 *   - 'harder'  : > 95% — increase demands to prevent plateau
 */

import type { Drill, DrillConfig, DrillScore } from '../data/curriculum'

// ─── Types ──────────────────────────────────────────

export type DifficultyTier = 'easier' | 'normal' | 'on-track' | 'harder'

export interface AdaptedDrill {
  /** The drill with adapted config */
  config: DrillConfig
  /** Which tier was applied */
  tier: DifficultyTier
  /** Human-readable changes (for UI display) */
  changes: string[]
  /** Original config for comparison */
  originalConfig: DrillConfig
}

// ─── Thresholds ─────────────────────────────────────

const TIER_THRESHOLDS = {
  easier: 60,   // below this → easier
  normal: 80,   // below this → normal (slight help)
  harder: 95,   // above this → harder
} as const

// ─── Core Function ──────────────────────────────────

/**
 * Adapt a drill's config based on historical performance.
 *
 * @param drill      The original drill definition
 * @param bestScore  Player's best score for this drill (if any)
 * @param recentScores  Last few scores for trend detection (optional)
 * @returns Adapted drill config with tier info and change descriptions
 */
export function adaptDrillConfig(
  drill: Drill,
  bestScore?: DrillScore,
  recentScores?: DrillScore[],
): AdaptedDrill {
  const originalConfig = { ...drill.config }
  const config = { ...drill.config }
  const changes: string[] = []

  // No history → no adaptation
  if (!bestScore) {
    return { config, tier: 'on-track', changes: [], originalConfig }
  }

  // Use recent trend if available (average of last 3), else use best
  const referenceAccuracy = recentScores && recentScores.length >= 2
    ? Math.round(recentScores.slice(-3).reduce((s, sc) => s + sc.accuracy, 0) / Math.min(recentScores.length, 3))
    : bestScore.accuracy

  const tier = determineTier(referenceAccuracy)

  // Apply tier-specific adjustments by drill type
  switch (tier) {
    case 'easier':
      applyEasier(drill, config, changes)
      break
    case 'normal':
      applyNormal(drill, config, changes)
      break
    case 'on-track':
      // No changes needed
      break
    case 'harder':
      applyHarder(drill, config, changes)
      break
  }

  return { config, tier, changes, originalConfig }
}

// ─── Tier Determination ─────────────────────────────

function determineTier(accuracy: number): DifficultyTier {
  if (accuracy < TIER_THRESHOLDS.easier) return 'easier'
  if (accuracy < TIER_THRESHOLDS.normal) return 'normal'
  if (accuracy > TIER_THRESHOLDS.harder) return 'harder'
  return 'on-track'
}

// ─── Tier Adjustments ───────────────────────────────

function applyEasier(drill: Drill, config: DrillConfig, changes: string[]) {
  // BPM: reduce by 20%
  if (config.bpm) {
    const newBpm = Math.max(40, Math.round(config.bpm * 0.8))
    if (newBpm !== config.bpm) {
      changes.push(`BPM ${config.bpm} → ${newBpm}`)
      config.bpm = newBpm
    }
  }
  if (config.targetBpm) {
    const newTarget = Math.max(40, Math.round(config.targetBpm * 0.8))
    if (newTarget !== config.targetBpm) {
      changes.push(`목표 BPM ${config.targetBpm} → ${newTarget}`)
      config.targetBpm = newTarget
    }
  }

  // Chords: limit to first 2-3
  if (config.chords && config.chords.length > 2) {
    const reduced = config.chords.slice(0, 2)
    changes.push(`코드 ${config.chords.length}개 → ${reduced.length}개`)
    config.chords = reduced
  }

  // Duration: increase by 30% (more time to practice)
  if (config.durationSeconds) {
    const newDuration = Math.round(config.durationSeconds * 1.3)
    changes.push(`시간 ${config.durationSeconds}초 → ${newDuration}초`)
    config.durationSeconds = newDuration
  }

  // Quiz: drop to beginner if not already
  if (drill.type === 'fretboard-quiz' && config.quizDifficulty !== 'beginner') {
    changes.push(`퀴즈 난이도 → beginner`)
    config.quizDifficulty = 'beginner'
  }

  // Loop count: reduce by 1 (min 1)
  if (config.loopCount && config.loopCount > 1) {
    const newLoop = config.loopCount - 1
    changes.push(`반복 ${config.loopCount}회 → ${newLoop}회`)
    config.loopCount = newLoop
  }
}

function applyNormal(_drill: Drill, config: DrillConfig, changes: string[]) {
  // BPM: reduce by 10%
  if (config.bpm) {
    const newBpm = Math.max(40, Math.round(config.bpm * 0.9))
    if (newBpm !== config.bpm) {
      changes.push(`BPM ${config.bpm} → ${newBpm}`)
      config.bpm = newBpm
    }
  }
  if (config.targetBpm) {
    const newTarget = Math.max(40, Math.round(config.targetBpm * 0.9))
    if (newTarget !== config.targetBpm) {
      changes.push(`목표 BPM ${config.targetBpm} → ${newTarget}`)
      config.targetBpm = newTarget
    }
  }

  // Chords: limit to first 3 if more than 4
  if (config.chords && config.chords.length > 3) {
    const reduced = config.chords.slice(0, 3)
    changes.push(`코드 ${config.chords.length}개 → ${reduced.length}개`)
    config.chords = reduced
  }
}

function applyHarder(drill: Drill, config: DrillConfig, changes: string[]) {
  // BPM: increase by 15%
  if (config.bpm) {
    const newBpm = Math.min(220, Math.round(config.bpm * 1.15))
    if (newBpm !== config.bpm) {
      changes.push(`BPM ${config.bpm} → ${newBpm}`)
      config.bpm = newBpm
    }
  }
  if (config.targetBpm) {
    const newTarget = Math.min(220, Math.round(config.targetBpm * 1.15))
    if (newTarget !== config.targetBpm) {
      changes.push(`목표 BPM ${config.targetBpm} → ${newTarget}`)
      config.targetBpm = newTarget
    }
  }

  // Duration: reduce by 20% (tighter window)
  if (config.durationSeconds && config.durationSeconds > 15) {
    const newDuration = Math.round(config.durationSeconds * 0.8)
    changes.push(`시간 ${config.durationSeconds}초 → ${newDuration}초`)
    config.durationSeconds = newDuration
  }

  // Quiz: advance difficulty
  if (drill.type === 'fretboard-quiz') {
    if (config.quizDifficulty === 'beginner') {
      changes.push(`퀴즈 난이도 → intermediate`)
      config.quizDifficulty = 'intermediate'
    } else if (config.quizDifficulty === 'intermediate') {
      changes.push(`퀴즈 난이도 → advanced`)
      config.quizDifficulty = 'advanced'
    }
  }

  // Loop count: increase by 1
  if (config.loopCount) {
    const newLoop = config.loopCount + 1
    changes.push(`반복 ${config.loopCount}회 → ${newLoop}회`)
    config.loopCount = newLoop
  }

  // Start BPM percent: increase (song sections)
  if (config.startBpmPercent && config.startBpmPercent < 100) {
    const newPercent = Math.min(100, config.startBpmPercent + 15)
    changes.push(`시작 속도 ${config.startBpmPercent}% → ${newPercent}%`)
    config.startBpmPercent = newPercent
  }
}

// ─── UI Helpers ─────────────────────────────────────

export const TIER_LABELS: Record<DifficultyTier, string> = {
  easier: '난이도 ↓',
  normal: '약간 조절',
  'on-track': '적정 난이도',
  harder: '난이도 ↑',
}

export const TIER_COLORS: Record<DifficultyTier, string> = {
  easier: 'text-sky-400 bg-sky-900/20 border-sky-700/40',
  normal: 'text-amber-400 bg-amber-900/20 border-amber-700/40',
  'on-track': 'text-emerald-400 bg-emerald-900/20 border-emerald-700/40',
  harder: 'text-rose-400 bg-rose-900/20 border-rose-700/40',
}

export const TIER_ICONS: Record<DifficultyTier, string> = {
  easier: '🛡️',
  normal: '📐',
  'on-track': '✅',
  harder: '🔥',
}

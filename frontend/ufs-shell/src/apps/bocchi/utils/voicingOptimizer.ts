import type { ChordVoicing } from './voicingLibrary'

/**
 * Voice Leading Optimizer
 *
 * Problem: independently selected voicings per chord can jump across
 * the fretboard, making progression transitions impractical.
 *
 * Solution: dynamic programming (Viterbi-style) finds the voicing
 * sequence that minimizes total hand-movement distance across
 * the entire progression, including wrap-around (last → first chord).
 */

// ----- Distance Metric -----

/**
 * Calculate movement distance between two voicings.
 *
 * Factors:
 * - Sum of absolute fret differences on matching strings
 * - Penalty for mute↔play state changes on a string
 * - Bonus for staying in the same position region
 */
export function voicingDistance(a: number[], b: number[]): number {
  const len = Math.min(a.length, b.length)
  let dist = 0

  for (let i = 0; i < len; i++) {
    const fa = a[i]
    const fb = b[i]

    if (fa === -1 && fb === -1) {
      // Both muted — no movement
      continue
    }

    if (fa === -1 || fb === -1) {
      // Mute ↔ play transition — moderate penalty
      dist += 3
      continue
    }

    // Both played — absolute fret difference
    dist += Math.abs(fa - fb)
  }

  // Position region penalty: if the overall "center of mass" shifts a lot
  const aCenter = avgFretPosition(a)
  const bCenter = avgFretPosition(b)
  dist += Math.abs(aCenter - bCenter) * 0.5

  return dist
}

/**
 * Average fret position of played (non-muted) strings.
 * Returns 0 for all-open or all-muted voicings.
 */
function avgFretPosition(frets: number[]): number {
  const played = frets.filter((f) => f >= 0)
  if (played.length === 0) return 0
  return played.reduce((sum, f) => sum + f, 0) / played.length
}

// ----- DP Optimization -----

/**
 * Find the optimal voicing index sequence for a chord progression.
 *
 * @param allVoicings - allVoicings[chordIndex] = available voicings for that chord
 * @returns Optimal voicing index per chord (same length as allVoicings).
 *          Returns [0,0,...] if optimization is impossible (e.g., some chord has 0 voicings).
 */
export function optimizeProgressionVoicings(
  allVoicings: ChordVoicing[][],
): number[] {
  const n = allVoicings.length
  if (n === 0) return []

  // If any chord has no voicings, fall back to all-zero
  if (allVoicings.some((v) => v.length === 0)) {
    return new Array(n).fill(0)
  }

  if (n === 1) return [0]

  // dp[i][j] = minimum total distance to reach chord i using voicing j
  const dp: number[][] = new Array(n)
  const parent: number[][] = new Array(n)

  // Initialize first chord — all voicings have cost 0
  dp[0] = allVoicings[0].map(() => 0)
  parent[0] = allVoicings[0].map(() => -1)

  // Forward pass
  for (let i = 1; i < n; i++) {
    const prevVoicings = allVoicings[i - 1]
    const currVoicings = allVoicings[i]

    dp[i] = new Array(currVoicings.length)
    parent[i] = new Array(currVoicings.length)

    for (let j = 0; j < currVoicings.length; j++) {
      let bestCost = Infinity
      let bestParent = 0

      for (let k = 0; k < prevVoicings.length; k++) {
        const cost =
          dp[i - 1][k] +
          voicingDistance(prevVoicings[k].frets, currVoicings[j].frets)

        if (cost < bestCost) {
          bestCost = cost
          bestParent = k
        }
      }

      dp[i][j] = bestCost
      parent[i][j] = bestParent
    }
  }

  // Factor in wrap-around cost (last → first) for looping progressions
  // Total cost = dp[n-1][j] + distance(last voicing j → first voicing result[0])
  // We pick the final voicing that minimizes total including wrap-around
  const firstVoicings = allVoicings[0]
  const lastVoicings = allVoicings[n - 1]

  let bestFinalIdx = 0
  let bestTotalCost = Infinity

  for (let j = 0; j < lastVoicings.length; j++) {
    // For each possible final voicing, find best wrap-around to some first voicing
    for (let f = 0; f < firstVoicings.length; f++) {
      const wrapCost = voicingDistance(
        lastVoicings[j].frets,
        firstVoicings[f].frets,
      )
      const total = dp[n - 1][j] + wrapCost
      if (total < bestTotalCost) {
        bestTotalCost = total
        bestFinalIdx = j
      }
    }
  }

  // Backtrack to build optimal index sequence
  const result: number[] = new Array(n)
  result[n - 1] = bestFinalIdx

  for (let i = n - 2; i >= 0; i--) {
    result[i] = parent[i + 1][result[i + 1]]
  }

  return result
}

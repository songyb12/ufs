/**
 * Scale Finder — Reverse lookup utility.
 *
 * Given a set of notes, find all scales that contain those notes.
 * Useful for identifying what key/scale a musical passage is in.
 */

import type { NoteName } from '../types/music'
import { CHROMATIC_SCALE } from '../constants/notes'
import { SCALES, getScaleNoteNames, type ScaleDefinition } from './scaleCalculator'

export interface ScaleMatch {
  root: NoteName
  scale: ScaleDefinition
  noteNames: NoteName[]
  matchCount: number     // how many of the input notes are in this scale
  totalNotes: number     // total notes in this scale
  coverage: number       // matchCount / inputNotes.length (0-1)
  extraNotes: NoteName[] // input notes NOT in this scale
}

/**
 * Find all scales that contain ALL the given input notes.
 * Returns matches sorted by: perfect matches first, then by fewest total notes.
 */
export function findScalesContaining(
  inputNotes: NoteName[],
  minCoverage: number = 1.0,  // 1.0 = must contain ALL input notes
): ScaleMatch[] {
  if (inputNotes.length === 0) return []

  const matches: ScaleMatch[] = []

  for (const root of CHROMATIC_SCALE) {
    for (const scale of SCALES) {
      const scaleNotes = getScaleNoteNames(root, scale)
      const scaleSet = new Set(scaleNotes)

      // Count how many input notes are in this scale
      let matchCount = 0
      const extraNotes: NoteName[] = []
      for (const note of inputNotes) {
        if (scaleSet.has(note)) {
          matchCount++
        } else {
          extraNotes.push(note)
        }
      }

      const coverage = matchCount / inputNotes.length

      if (coverage >= minCoverage) {
        matches.push({
          root,
          scale,
          noteNames: scaleNotes,
          matchCount,
          totalNotes: scaleNotes.length,
          coverage,
          extraNotes,
        })
      }
    }
  }

  // Sort: perfect coverage first, then by fewer total notes (simpler scales)
  matches.sort((a, b) => {
    if (b.coverage !== a.coverage) return b.coverage - a.coverage
    return a.totalNotes - b.totalNotes
  })

  return matches
}

/**
 * Find scales with at least the given coverage threshold.
 * Returns top N matches.
 */
export function findBestScales(
  inputNotes: NoteName[],
  topN: number = 10,
  minCoverage: number = 0.8,
): ScaleMatch[] {
  return findScalesContaining(inputNotes, minCoverage).slice(0, topN)
}

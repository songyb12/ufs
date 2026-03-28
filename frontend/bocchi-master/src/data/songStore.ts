import type { Song, SongSearchResult } from '../types/song'
import { SEED_SONGS } from './seedSongs'

const STORAGE_KEY = 'bocchi-songs'

function readAll(): Song[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Song[]) : []
  } catch {
    return []
  }
}

function writeAll(songs: Song[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(songs))
  } catch {
    // QuotaExceededError — silently fail
  }
}

export function getAllSongs(): Song[] {
  return readAll()
}

export function getSongById(id: string): Song | null {
  return readAll().find(s => s.id === id) ?? null
}

export function searchSongs(query: string): SongSearchResult[] {
  const normalized = query.trim().toLowerCase().replace(/\s+/g, ' ')
  if (!normalized) return []

  const songs = readAll()
  const results: SongSearchResult[] = []

  for (const song of songs) {
    const titleLower = song.title.toLowerCase()
    const artistLower = (song.artist ?? '').toLowerCase()
    let score = 0

    if (titleLower === normalized) score = 100
    else if (titleLower.startsWith(normalized)) score = 80
    else if (titleLower.includes(normalized)) score = 60
    else if (artistLower === normalized) score = 70
    else if (artistLower.startsWith(normalized)) score = 50
    else if (artistLower.includes(normalized)) score = 40

    if (score > 0) {
      results.push({
        id: song.id,
        title: song.title,
        artist: song.artist,
        source: song.source,
        matchScore: score,
      })
    }
  }

  return results.sort((a, b) => (b.matchScore ?? 0) - (a.matchScore ?? 0))
}

export function saveSong(song: Song): void {
  const songs = readAll()
  const idx = songs.findIndex(s => s.id === song.id)
  if (idx >= 0) {
    songs[idx] = song
  } else {
    songs.push(song)
  }
  writeAll(songs)
}

export function deleteSong(id: string): void {
  writeAll(readAll().filter(s => s.id !== id))
}

export function initializeSeedData(): void {
  const songs = readAll()
  const existingIds = new Set(songs.map(s => s.id))
  let added = false

  for (const seed of SEED_SONGS) {
    if (!existingIds.has(seed.id)) {
      songs.push(seed)
      added = true
    }
  }

  if (added) {
    writeAll(songs)
  }
}

// Auto-initialize on module load
initializeSeedData()

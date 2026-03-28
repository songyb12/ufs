export type SongSectionName =
  | 'Intro' | 'Verse' | 'Chorus' | 'Bridge' | 'Outro'
  | 'Pre-Chorus' | 'Interlude' | 'Solo' | 'Other'

export type SongSource = 'seed' | 'user' | 'llm' | 'api'

export interface SongChord {
  chord: string
  beats: number
  annotation?: string
}

export interface SongSection {
  name: SongSectionName
  chords: SongChord[]
}

export interface Song {
  id: string
  title: string
  artist?: string
  genre?: string
  key?: string
  bpm?: number
  timeSignature?: [number, number]
  sections: SongSection[]
  source: SongSource
  createdAt: string
  updatedAt: string
}

export interface SongSearchResult {
  id: string
  title: string
  artist?: string
  source: SongSource
  matchScore?: number
}

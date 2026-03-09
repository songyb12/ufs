import { useCallback } from 'react'
import { getSharedAudioContext } from '../utils/audioContextSingleton'
import { playNote, playChord, midiNoteToFrequency } from '../utils/synthEngine'
import type { Note, InstrumentConfig } from '../types/music'
import type { ChordVoicing } from '../utils/voicingLibrary'

export function useSoundEngine() {
  const playFretboardNote = useCallback(async (note: Note) => {
    const ctx = await getSharedAudioContext()
    playNote(ctx, { frequency: midiNoteToFrequency(note.midiNumber) })
  }, [])

  const playVoicing = useCallback(async (
    voicing: ChordVoicing,
    instrument: InstrumentConfig,
  ) => {
    const ctx = await getSharedAudioContext()
    // Collect MIDI numbers for non-muted strings, low to high
    const midiNotes = voicing.frets
      .map((fret, stringIdx) =>
        fret >= 0 ? instrument.tuning[stringIdx].midiNumber + fret : null,
      )
      .filter((n): n is number => n !== null)
    playChord(ctx, midiNotes)
  }, [])

  return { playFretboardNote, playVoicing }
}

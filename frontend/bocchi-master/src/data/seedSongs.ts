import type { Song } from '../types/song'

const now = new Date().toISOString()

function seed(id: string, data: Omit<Song, 'id' | 'source' | 'createdAt' | 'updatedAt'>): Song {
  return { id, ...data, source: 'seed', createdAt: now, updatedAt: now }
}

export const SEED_SONGS: Song[] = [
  seed('let-it-be', {
    title: 'Let It Be',
    artist: 'The Beatles',
    genre: 'Rock',
    key: 'C',
    bpm: 71,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'C', beats: 4 }, { chord: 'G', beats: 4 },
          { chord: 'Am', beats: 4 }, { chord: 'F', beats: 4 },
          { chord: 'C', beats: 4 }, { chord: 'G', beats: 4 },
          { chord: 'F', beats: 4 }, { chord: 'C', beats: 4 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'Am', beats: 4 }, { chord: 'G', beats: 4 },
          { chord: 'F', beats: 4 }, { chord: 'C', beats: 4 },
          { chord: 'C', beats: 4 }, { chord: 'G', beats: 4 },
          { chord: 'F', beats: 4 }, { chord: 'C', beats: 4 },
        ],
      },
    ],
  }),

  seed('wonderwall', {
    title: 'Wonderwall',
    artist: 'Oasis',
    genre: 'Britpop',
    key: 'Em',
    bpm: 87,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'Em7', beats: 4 }, { chord: 'G', beats: 4 },
          { chord: 'Dsus4', beats: 4 }, { chord: 'A7sus4', beats: 4 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'C', beats: 4 }, { chord: 'D', beats: 4 },
          { chord: 'Em', beats: 4 }, { chord: 'Em', beats: 4 },
          { chord: 'C', beats: 4 }, { chord: 'D', beats: 4 },
          { chord: 'G', beats: 4 }, { chord: 'G', beats: 4 },
        ],
      },
    ],
  }),

  seed('hotel-california', {
    title: 'Hotel California',
    artist: 'Eagles',
    genre: 'Rock',
    key: 'Bm',
    bpm: 75,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'Bm', beats: 8 }, { chord: 'F#7', beats: 8 },
          { chord: 'A', beats: 8 }, { chord: 'E', beats: 8 },
          { chord: 'G', beats: 8 }, { chord: 'D', beats: 8 },
          { chord: 'Em', beats: 8 }, { chord: 'F#7', beats: 8 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'G', beats: 8 }, { chord: 'D', beats: 8 },
          { chord: 'F#7', beats: 8 }, { chord: 'Bm', beats: 8 },
          { chord: 'G', beats: 8 }, { chord: 'D', beats: 8 },
          { chord: 'Em', beats: 8 }, { chord: 'F#7', beats: 8 },
        ],
      },
    ],
  }),

  seed('stand-by-me', {
    title: 'Stand By Me',
    artist: 'Ben E. King',
    genre: 'R&B',
    key: 'A',
    bpm: 120,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'A', beats: 8 }, { chord: 'A', beats: 8 },
          { chord: 'F#m', beats: 8 }, { chord: 'F#m', beats: 8 },
          { chord: 'D', beats: 4 }, { chord: 'E', beats: 4 },
          { chord: 'A', beats: 8 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'A', beats: 8 }, { chord: 'A', beats: 8 },
          { chord: 'F#m', beats: 8 }, { chord: 'F#m', beats: 8 },
          { chord: 'D', beats: 4 }, { chord: 'E', beats: 4 },
          { chord: 'A', beats: 8 },
        ],
      },
    ],
  }),

  seed('hey-jude', {
    title: 'Hey Jude',
    artist: 'The Beatles',
    genre: 'Rock',
    key: 'F',
    bpm: 74,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'F', beats: 8 }, { chord: 'C', beats: 8 },
          { chord: 'C7', beats: 8 }, { chord: 'F', beats: 8 },
          { chord: 'Bb', beats: 8 }, { chord: 'F', beats: 4 },
          { chord: 'C', beats: 4 }, { chord: 'F', beats: 8 },
        ],
      },
      {
        name: 'Outro',
        chords: [
          { chord: 'F', beats: 4 }, { chord: 'Eb', beats: 4 },
          { chord: 'Bb', beats: 4 }, { chord: 'F', beats: 4 },
        ],
      },
    ],
  }),

  seed('knockin-on-heavens-door', {
    title: "Knockin' on Heaven's Door",
    artist: 'Bob Dylan',
    genre: 'Folk Rock',
    key: 'G',
    bpm: 69,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'G', beats: 4 }, { chord: 'D', beats: 4 },
          { chord: 'Am', beats: 8 },
          { chord: 'G', beats: 4 }, { chord: 'D', beats: 4 },
          { chord: 'C', beats: 8 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'G', beats: 4 }, { chord: 'D', beats: 4 },
          { chord: 'Am', beats: 8 },
          { chord: 'G', beats: 4 }, { chord: 'D', beats: 4 },
          { chord: 'C', beats: 8 },
        ],
      },
    ],
  }),

  seed('perfect', {
    title: 'Perfect',
    artist: 'Ed Sheeran',
    genre: 'Pop',
    key: 'Ab',
    bpm: 63,
    timeSignature: [6, 8],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'Ab', beats: 6 }, { chord: 'Fm', beats: 6 },
          { chord: 'Db', beats: 6 }, { chord: 'Eb', beats: 6 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'Ab', beats: 6 }, { chord: 'Fm', beats: 6 },
          { chord: 'Db', beats: 6 }, { chord: 'Eb', beats: 6 },
          { chord: 'Ab', beats: 6 }, { chord: 'Fm', beats: 6 },
          { chord: 'Db', beats: 3 }, { chord: 'Eb', beats: 3 },
          { chord: 'Ab', beats: 6 },
        ],
      },
    ],
  }),

  seed('someone-like-you', {
    title: 'Someone Like You',
    artist: 'Adele',
    genre: 'Pop',
    key: 'A',
    bpm: 68,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'A', beats: 4 }, { chord: 'E', beats: 4 },
          { chord: 'F#m', beats: 4 }, { chord: 'D', beats: 4 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'A', beats: 4 }, { chord: 'E', beats: 4 },
          { chord: 'F#m', beats: 4 }, { chord: 'D', beats: 4 },
          { chord: 'A', beats: 4 }, { chord: 'E', beats: 4 },
          { chord: 'F#m', beats: 4 }, { chord: 'D', beats: 4 },
        ],
      },
    ],
  }),

  seed('hallelujah', {
    title: 'Hallelujah',
    artist: 'Leonard Cohen',
    genre: 'Folk',
    key: 'C',
    bpm: 56,
    timeSignature: [6, 8],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'C', beats: 6 }, { chord: 'Am', beats: 6 },
          { chord: 'C', beats: 6 }, { chord: 'Am', beats: 6 },
          { chord: 'F', beats: 6 }, { chord: 'G', beats: 6 },
          { chord: 'C', beats: 6 }, { chord: 'G', beats: 6 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'F', beats: 6 }, { chord: 'Am', beats: 6 },
          { chord: 'F', beats: 6 }, { chord: 'C', beats: 6 },
          { chord: 'G', beats: 6 }, { chord: 'C', beats: 6 },
          { chord: 'G', beats: 6 },
        ],
      },
    ],
  }),

  seed('autumn-leaves', {
    title: 'Autumn Leaves',
    artist: 'Jazz Standard',
    genre: 'Jazz',
    key: 'Gm',
    bpm: 120,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'Cm7', beats: 4 }, { chord: 'F7', beats: 4 },
          { chord: 'BbMaj7', beats: 4 }, { chord: 'EbMaj7', beats: 4 },
          { chord: 'Am7b5', beats: 4 }, { chord: 'D7', beats: 4 },
          { chord: 'Gm', beats: 4 }, { chord: 'Gm', beats: 4 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'Cm7', beats: 4 }, { chord: 'F7', beats: 4 },
          { chord: 'BbMaj7', beats: 4 }, { chord: 'EbMaj7', beats: 4 },
          { chord: 'Am7b5', beats: 4 }, { chord: 'D7', beats: 4 },
          { chord: 'Gm6', beats: 4 }, { chord: 'Gm6', beats: 4 },
        ],
      },
    ],
  }),

  seed('spring-day', {
    title: '봄날',
    artist: 'BTS',
    genre: 'K-Pop',
    key: 'Ab',
    bpm: 103,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'Ab', beats: 4 }, { chord: 'Eb', beats: 4 },
          { chord: 'Fm', beats: 4 }, { chord: 'Db', beats: 4 },
        ],
      },
      {
        name: 'Pre-Chorus',
        chords: [
          { chord: 'Db', beats: 4 }, { chord: 'Ab', beats: 4 },
          { chord: 'Eb', beats: 4 }, { chord: 'Fm', beats: 4 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'Ab', beats: 4 }, { chord: 'Eb', beats: 4 },
          { chord: 'Fm', beats: 4 }, { chord: 'Db', beats: 4 },
          { chord: 'Ab', beats: 4 }, { chord: 'Eb', beats: 4 },
          { chord: 'Fm', beats: 4 }, { chord: 'Db', beats: 4 },
        ],
      },
    ],
  }),

  seed('mikrokosmos', {
    title: '소우주 (Mikrokosmos)',
    artist: 'BTS',
    genre: 'K-Pop',
    key: 'E',
    bpm: 81,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'E', beats: 4 }, { chord: 'B', beats: 4 },
          { chord: 'C#m', beats: 4 }, { chord: 'A', beats: 4 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'E', beats: 4 }, { chord: 'B', beats: 4 },
          { chord: 'C#m', beats: 4 }, { chord: 'A', beats: 4 },
          { chord: 'E', beats: 4 }, { chord: 'B', beats: 4 },
          { chord: 'A', beats: 8 },
        ],
      },
    ],
  }),

  seed('love-yourself', {
    title: 'Love Yourself',
    artist: 'Justin Bieber',
    genre: 'Pop',
    key: 'E',
    bpm: 100,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'E', beats: 8 }, { chord: 'B', beats: 4 },
          { chord: 'C#m', beats: 4 }, { chord: 'A', beats: 8 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'E', beats: 4 }, { chord: 'B', beats: 4 },
          { chord: 'A', beats: 8 },
          { chord: 'E', beats: 4 }, { chord: 'B', beats: 4 },
          { chord: 'C#m', beats: 4 }, { chord: 'A', beats: 4 },
        ],
      },
    ],
  }),

  seed('shape-of-you', {
    title: 'Shape of You',
    artist: 'Ed Sheeran',
    genre: 'Pop',
    key: 'C#m',
    bpm: 96,
    timeSignature: [4, 4],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'C#m', beats: 4 }, { chord: 'F#m', beats: 4 },
          { chord: 'A', beats: 4 }, { chord: 'B', beats: 4 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'C#m', beats: 4 }, { chord: 'F#m', beats: 4 },
          { chord: 'A', beats: 4 }, { chord: 'B', beats: 4 },
          { chord: 'C#m', beats: 4 }, { chord: 'F#m', beats: 4 },
          { chord: 'A', beats: 4 }, { chord: 'B', beats: 4 },
        ],
      },
    ],
  }),

  seed('cant-help-falling-in-love', {
    title: "Can't Help Falling in Love",
    artist: 'Elvis Presley',
    genre: 'Pop',
    key: 'C',
    bpm: 65,
    timeSignature: [6, 8],
    sections: [
      {
        name: 'Verse',
        chords: [
          { chord: 'C', beats: 6 }, { chord: 'Em', beats: 6 },
          { chord: 'Am', beats: 3 }, { chord: 'Am7', beats: 3 },
          { chord: 'F', beats: 6 }, { chord: 'C', beats: 6 },
          { chord: 'G', beats: 6 }, { chord: 'G7', beats: 6 },
        ],
      },
      {
        name: 'Bridge',
        chords: [
          { chord: 'Am', beats: 6 }, { chord: 'Em', beats: 6 },
          { chord: 'Am', beats: 6 }, { chord: 'Em', beats: 6 },
          { chord: 'Am', beats: 6 }, { chord: 'Em', beats: 6 },
          { chord: 'A7', beats: 6 }, { chord: 'Dm7', beats: 3 },
          { chord: 'G7', beats: 3 },
        ],
      },
      {
        name: 'Chorus',
        chords: [
          { chord: 'C', beats: 6 }, { chord: 'Em', beats: 6 },
          { chord: 'Am', beats: 3 }, { chord: 'Am7', beats: 3 },
          { chord: 'F', beats: 6 }, { chord: 'G', beats: 6 },
          { chord: 'Am', beats: 3 }, { chord: 'F', beats: 3 },
          { chord: 'C', beats: 6 }, { chord: 'G7', beats: 3 },
          { chord: 'C', beats: 3 },
        ],
      },
    ],
  }),
]

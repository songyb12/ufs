/**
 * Bocchi-master sub-app entry point.
 *
 * Migration path:
 * 1. [Current] Placeholder with feature overview
 * 2. [Next] Move bocchi-master/src/ components here and adapt imports
 * 3. [Final] Full integration with shared shell utilities
 */
export default function BocchiApp() {
  const features = [
    { name: 'Fretboard', desc: 'SVG fretboard with multi-overlay (scale, voicing, pattern, chord-tone)', done: true },
    { name: 'Metronome', desc: 'Web Audio metronome with accent, subdivision, swing, pendulum', done: true },
    { name: 'Theory', desc: 'Circle of Fifths, scale library, chord voicing DB', done: true },
    { name: 'Practice', desc: 'Fretboard quiz, chord transition timer, practice log', done: true },
    { name: 'Progression', desc: 'Markov-chain random generation, presets, voicing compare', done: true },
    { name: 'Rhythm', desc: 'Strum pattern (arrow + notation view)', done: true },
    { name: 'MIDI', desc: 'WebMIDI input integration', done: true },
  ]

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-white mb-1">
          Bocchi<span className="text-orange-500">-master</span>
        </h1>
        <p className="text-ufs-400 text-sm">Guitar & Bass Practice Studio</p>
      </div>

      <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-5 mb-6">
        <p className="text-orange-300 text-sm">
          Integration in progress - Bocchi-master components will be migrated into this shell.
          Currently available as standalone at <code className="bg-ufs-700 px-1.5 py-0.5 rounded text-xs">localhost:3000</code>
        </p>
      </div>

      <div className="space-y-2">
        {features.map((f) => (
          <div
            key={f.name}
            className="flex items-start gap-3 p-3 rounded-lg bg-ufs-800 border border-ufs-600/30"
          >
            <span className="mt-0.5 text-green-400 text-xs">
              {f.done ? '\u2713' : '\u25CB'}
            </span>
            <div>
              <div className="text-sm font-medium text-white">{f.name}</div>
              <div className="text-xs text-ufs-400">{f.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

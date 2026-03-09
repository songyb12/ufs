import type { InstrumentConfig } from '../../types/music'
import { GUITAR_TUNINGS, BASS_TUNINGS } from '../../constants/tunings'

interface HeaderProps {
  instrument: InstrumentConfig
  onInstrumentChange: (config: InstrumentConfig) => void
}

const ALL_INSTRUMENTS = [...GUITAR_TUNINGS, ...BASS_TUNINGS]

export function Header({ instrument, onInstrumentChange }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-3 bg-slate-800/50 border-b border-slate-700">
      <h1 className="text-xl font-bold text-white tracking-tight">
        Bocchi<span className="text-orange-500">-master</span>
      </h1>

      <select
        value={instrument.name}
        onChange={(e) => {
          const found = ALL_INSTRUMENTS.find((i) => i.name === e.target.value)
          if (found) onInstrumentChange(found)
        }}
        className="bg-slate-700 text-slate-300 text-sm rounded px-3 py-1.5 outline-none border border-slate-600 hover:border-slate-500"
      >
        <optgroup label="Guitar">
          {GUITAR_TUNINGS.map((inst) => (
            <option key={inst.name} value={inst.name}>
              🎸 {inst.name}
            </option>
          ))}
        </optgroup>
        <optgroup label="Bass">
          {BASS_TUNINGS.map((inst) => (
            <option key={inst.name} value={inst.name}>
              🎸 {inst.name}
            </option>
          ))}
        </optgroup>
      </select>
    </header>
  )
}

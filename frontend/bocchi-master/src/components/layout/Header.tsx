import type { InstrumentConfig } from '../../types/music'
import { INSTRUMENTS } from '../../constants/tunings'

interface HeaderProps {
  instrument: InstrumentConfig
  onInstrumentChange: (config: InstrumentConfig) => void
}

export function Header({ instrument, onInstrumentChange }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-3 bg-slate-800/50 border-b border-slate-700">
      <h1 className="text-xl font-bold text-white tracking-tight">
        Bocchi<span className="text-orange-500">-master</span>
      </h1>

      <select
        value={instrument.name}
        onChange={(e) => {
          const found = INSTRUMENTS.find((i) => i.name === e.target.value)
          if (found) onInstrumentChange(found)
        }}
        className="bg-slate-700 text-slate-300 text-sm rounded px-3 py-1.5 outline-none border border-slate-600 hover:border-slate-500"
      >
        {INSTRUMENTS.map((inst) => (
          <option key={inst.name} value={inst.name}>
            {inst.name}
          </option>
        ))}
      </select>
    </header>
  )
}

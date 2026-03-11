import type { ReactNode } from 'react'
import type { InstrumentConfig } from '../../types/music'
import { Header } from './Header'

interface AppShellProps {
  instrument: InstrumentConfig
  onInstrumentChange: (config: InstrumentConfig) => void
  children: ReactNode
}

export function AppShell({
  instrument,
  onInstrumentChange,
  children,
}: AppShellProps) {
  return (
    <div className="min-h-screen flex flex-col bg-slate-900">
      <Header
        instrument={instrument}
        onInstrumentChange={onInstrumentChange}
      />
      <main className="flex-1 flex flex-col gap-4 p-4 max-w-7xl mx-auto w-full">
        {children}
      </main>
    </div>
  )
}

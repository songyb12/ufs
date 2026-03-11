import type { MidiDeviceInfo, MidiNoteEvent } from '../../types/midi'
import { MidiDeviceList } from './MidiDeviceList'

interface MidiStatusProps {
  isSupported: boolean
  isConnected: boolean
  devices: MidiDeviceInfo[]
  lastNote: MidiNoteEvent | null
  error: string | null
  requestAccess: () => void
}

export function MidiStatus({
  isSupported,
  isConnected,
  devices,
  lastNote,
  error,
  requestAccess,
}: MidiStatusProps) {
  if (!isSupported) {
    return (
      <div className="bg-slate-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
          MIDI
        </h2>
        <p className="text-sm text-slate-500">
          WebMIDI not supported. Use Chrome or Edge.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          MIDI
        </h2>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-slate-600'
            }`}
          />
          <span className="text-xs text-slate-500">
            {isConnected ? 'Connected' : 'No device'}
          </span>
        </div>
      </div>

      {devices.length === 0 ? (
        <button
          onClick={requestAccess}
          className="px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 text-sm text-slate-300 transition-colors"
        >
          Connect MIDI Device
        </button>
      ) : (
        <MidiDeviceList devices={devices} />
      )}

      {lastNote && (
        <div className="text-xs text-slate-500">
          Last note: <span className="text-slate-300">{lastNote.note}</span>{' '}
          vel: <span className="text-slate-300">{lastNote.velocity}</span>
        </div>
      )}

      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}

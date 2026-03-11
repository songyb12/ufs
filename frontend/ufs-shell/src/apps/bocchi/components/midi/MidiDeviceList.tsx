import type { MidiDeviceInfo } from '../../types/midi'

interface MidiDeviceListProps {
  devices: MidiDeviceInfo[]
}

export function MidiDeviceList({ devices }: MidiDeviceListProps) {
  const inputs = devices.filter((d) => d.type === 'input')

  if (inputs.length === 0) {
    return <p className="text-sm text-slate-500">No input devices detected.</p>
  }

  return (
    <ul className="space-y-1">
      {inputs.map((device) => (
        <li
          key={device.id}
          className="flex items-center gap-2 text-sm text-slate-300"
        >
          <div
            className={`w-2 h-2 rounded-full ${
              device.state === 'connected' ? 'bg-green-500' : 'bg-slate-600'
            }`}
          />
          <span>{device.name}</span>
          {device.manufacturer !== 'Unknown' && (
            <span className="text-slate-500 text-xs">
              ({device.manufacturer})
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

import { useState, useCallback, useRef, useEffect } from 'react'
import type { MidiDeviceInfo, MidiNoteEvent } from '../types/midi'

export function useMidi() {
  const [isSupported] = useState(() => !!navigator.requestMIDIAccess)
  const [isConnected, setIsConnected] = useState(false)
  const [devices, setDevices] = useState<MidiDeviceInfo[]>([])
  const [lastNote, setLastNote] = useState<MidiNoteEvent | null>(null)
  const [error, setError] = useState<string | null>(null)

  const midiAccessRef = useRef<MIDIAccess | null>(null)

  const updateDevices = useCallback((access: MIDIAccess) => {
    const deviceList: MidiDeviceInfo[] = []

    access.inputs.forEach((input) => {
      deviceList.push({
        id: input.id,
        name: input.name ?? 'Unknown',
        manufacturer: input.manufacturer ?? 'Unknown',
        state: input.state,
        type: 'input',
      })
    })

    access.outputs.forEach((output) => {
      deviceList.push({
        id: output.id,
        name: output.name ?? 'Unknown',
        manufacturer: output.manufacturer ?? 'Unknown',
        state: output.state,
        type: 'output',
      })
    })

    setDevices(deviceList)
    setIsConnected(deviceList.some((d) => d.state === 'connected'))
  }, [])

  const handleMidiMessage = useCallback((event: MIDIMessageEvent) => {
    const data = event.data
    if (!data || data.length < 3) return

    const status = data[0] & 0xf0
    const channel = data[0] & 0x0f

    // Note On (0x90) with velocity > 0
    if (status === 0x90 && data[2] > 0) {
      setLastNote({
        note: data[1],
        velocity: data[2],
        channel,
        timestamp: event.timeStamp,
      })
    }
  }, [])

  const requestAccess = useCallback(async () => {
    if (!isSupported) {
      setError('WebMIDI is not supported in this browser (Chrome/Edge only)')
      return
    }

    try {
      const access = await navigator.requestMIDIAccess()
      midiAccessRef.current = access

      updateDevices(access)

      // Listen for device connect/disconnect
      access.onstatechange = () => updateDevices(access)

      // Attach message listeners to all inputs
      access.inputs.forEach((input) => {
        input.onmidimessage = handleMidiMessage
      })

      setError(null)
    } catch (err) {
      setError(`MIDI access denied: ${err}`)
    }
  }, [isSupported, updateDevices, handleMidiMessage])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (midiAccessRef.current) {
        midiAccessRef.current.inputs.forEach((input) => {
          input.onmidimessage = null
        })
      }
    }
  }, [])

  return {
    isSupported,
    isConnected,
    devices,
    lastNote,
    error,
    requestAccess,
  }
}

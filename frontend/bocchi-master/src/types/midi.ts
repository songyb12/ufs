export interface MidiDeviceInfo {
  id: string
  name: string
  manufacturer: string
  state: 'connected' | 'disconnected'
  type: 'input' | 'output'
}

export interface MidiNoteEvent {
  note: number    // MIDI note number 0-127
  velocity: number // 0-127
  channel: number  // 0-15
  timestamp: number
}

export interface AppInfo {
  id: string
  name: string
  description: string
  path: string
  icon: string
  color: string
  status: 'active' | 'dev' | 'planned'
  apiBase: string
  shortcut?: string       // keyboard shortcut key
  tags?: string[]          // searchable tags
  port?: number            // backend port
  features?: string[]      // feature highlights
}

export const APP_REGISTRY: AppInfo[] = [
  {
    id: 'bocchi',
    name: 'Bocchi-master',
    description: 'Guitar & Bass Practice Studio',
    path: '/bocchi',
    icon: 'M9 19V6l12-3v13',
    color: '#f97316',
    status: 'active',
    apiBase: '/api/bocchi',
    shortcut: 'b',
    port: 3001,
    tags: ['music', 'guitar', 'bass', 'practice', 'metronome', 'fretboard'],
    features: ['Fretboard SVG', 'Metronome', 'MIDI', 'Chord Progressions', 'Quiz'],
  },
  {
    id: 'vibe',
    name: 'VIBE',
    description: 'Investment Intelligence Dashboard',
    path: '/vibe',
    icon: 'M3 3v18h18',
    color: '#3b82f6',
    status: 'active',
    apiBase: '/api/vibe',
    shortcut: 'v',
    port: 8001,
    tags: ['investment', 'trading', 'signals', 'portfolio', 'backtest', 'SOXL', 'macro'],
    features: ['Portfolio', 'Signals', 'SOXL Live', 'Backtest', 'Macro Analysis'],
  },
  {
    id: 'eng-ops',
    name: 'Engineering-Ops',
    description: 'HW Verification Log Analysis',
    path: '/eng-ops',
    icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
    color: '#10b981',
    status: 'dev',
    apiBase: '/api/eng-ops',
    shortcut: 'e',
    port: 8003,
    tags: ['engineering', 'logs', 'hardware', 'verification', 'analysis'],
    features: ['Log Parser', 'Daily Report', 'Pattern Detection'],
  },
  {
    id: 'life',
    name: 'Life-Master',
    description: 'Routine & Schedule Optimizer',
    path: '/life',
    icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
    color: '#8b5cf6',
    status: 'dev',
    apiBase: '/api/life',
    shortcut: 'l',
    port: 8004,
    tags: ['routine', 'habits', 'goals', 'schedule', 'japanese', 'gamification'],
    features: ['Routines', 'Habits', 'Goals', 'Japanese SRS', 'Gamification'],
  },
  {
    id: 'claude',
    name: 'Claude',
    description: 'AI Session Manager (Claude CLI Web UI)',
    path: '/claude',
    icon: 'M8.5 14.5A2.5 2.5 0 0011 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 11-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 002.5 2.5z',
    color: '#d97706',
    status: 'active',
    apiBase: '/api/claude',
    shortcut: 'c',
    port: 8006,
    tags: ['claude', 'ai', 'session', 'chat', 'llm', 'agent'],
    features: ['Session Management', 'Multi-Session', 'WebSocket Streaming', 'Queue'],
  },
]

/** Search apps by query (matches name, description, tags) */
export function searchApps(query: string): AppInfo[] {
  if (!query.trim()) return APP_REGISTRY
  const q = query.toLowerCase()
  return APP_REGISTRY.filter(
    (app) =>
      app.name.toLowerCase().includes(q) ||
      app.description.toLowerCase().includes(q) ||
      app.tags?.some((t) => t.includes(q)) ||
      app.features?.some((f) => f.toLowerCase().includes(q)),
  )
}

/** Get app by shortcut key */
export function getAppByShortcut(key: string): AppInfo | undefined {
  return APP_REGISTRY.find((app) => app.shortcut === key.toLowerCase())
}

/** Get app by path */
export function getAppByPath(pathname: string): AppInfo | undefined {
  return APP_REGISTRY.find((app) => pathname.startsWith(app.path))
}

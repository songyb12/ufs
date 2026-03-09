export interface AppInfo {
  id: string
  name: string
  description: string
  path: string
  icon: string
  color: string
  status: 'active' | 'dev' | 'planned'
  apiBase: string
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
  },
  {
    id: 'life',
    name: 'Life-Master',
    description: 'Routine & Schedule Optimizer',
    path: '/life',
    icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
    color: '#8b5cf6',
    status: 'planned',
    apiBase: '/api/life',
  },
]

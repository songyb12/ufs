// ── Panel Tab & Skill Profile Configuration ──
// Extracted from App.tsx to reduce file size

export type PanelTab = 'play' | 'drill' | 'theory' | 'tools' | 'stats' | 'song'
export const PANEL_TAB_KEY = 'bocchi-panel-tab'

export const PANEL_TABS: { id: PanelTab; label: string; icon: string }[] = [
  { id: 'play', label: '진행/반주', icon: '🎵' },
  { id: 'drill', label: '연습/드릴', icon: '🎯' },
  { id: 'theory', label: '이론', icon: '📖' },
  { id: 'tools', label: '도구', icon: '🔧' },
  { id: 'stats', label: '분석', icon: '📊' },
  { id: 'song', label: '곡', icon: '🎶' },
]

// ── Skill Profile System ──
export type SkillProfile = 'beginner' | 'intermediate' | 'advanced'
export const SKILL_PROFILE_KEY = 'bocchi-skill-profile'
export const SKILL_LEVELS: Record<SkillProfile, number> = { beginner: 0, intermediate: 1, advanced: 2 }

export const SKILL_PROFILE_OPTIONS: { id: SkillProfile; label: string; icon: string }[] = [
  { id: 'beginner', label: '초급', icon: '🌱' },
  { id: 'intermediate', label: '중급', icon: '🌿' },
  { id: 'advanced', label: '고급', icon: '🌳' },
]

// Panel visibility: minimum skill profile required for each panel
export type PanelId =
  // play tab
  | 'chordProgression' | 'metronome' | 'backingTrack' | 'strumPattern' | 'tempoTrainer'
  // drill tab
  | 'practice' | 'rhythmScore' | 'chordTransition' | 'chordToneDrill' | 'callResponse'
  | 'fretboardQuiz' | 'intervalTrainer'
  // theory tab
  | 'scaleFinder' | 'circleOfFifths' | 'scalePattern' | 'droneTone'
  // tools tab
  | 'tuner' | 'midiStatus' | 'practiceTimer'
  // stats tab
  | 'weaknessAnalysis' | 'reminderShare' | 'practiceHistory'
  // song tab
  | 'songChord'

export const PANEL_MIN_LEVEL: Record<PanelId, SkillProfile> = {
  // play — beginner gets metronome + chordProgression
  chordProgression: 'beginner',
  metronome: 'beginner',
  backingTrack: 'intermediate',
  strumPattern: 'intermediate',
  tempoTrainer: 'intermediate',
  // drill — beginner gets fretboardQuiz only
  practice: 'intermediate',
  rhythmScore: 'intermediate',
  chordTransition: 'intermediate',
  chordToneDrill: 'advanced',
  callResponse: 'advanced',
  fretboardQuiz: 'beginner',
  intervalTrainer: 'intermediate',
  // theory
  scaleFinder: 'intermediate',
  circleOfFifths: 'intermediate',
  scalePattern: 'intermediate',
  droneTone: 'advanced',
  // tools — beginner gets tuner + practiceTimer
  tuner: 'beginner',
  midiStatus: 'intermediate',
  practiceTimer: 'beginner',
  // stats — beginner gets practiceHistory
  weaknessAnalysis: 'advanced',
  reminderShare: 'intermediate',
  practiceHistory: 'beginner',
  // song
  songChord: 'beginner',
}

// Which tab each panel belongs to
export const PANEL_TAB_MAP: Record<PanelId, PanelTab> = {
  chordProgression: 'play', metronome: 'play', backingTrack: 'play',
  strumPattern: 'play', tempoTrainer: 'play',
  practice: 'drill', rhythmScore: 'drill', chordTransition: 'drill',
  chordToneDrill: 'drill', callResponse: 'drill', fretboardQuiz: 'drill',
  intervalTrainer: 'drill',
  scaleFinder: 'theory', circleOfFifths: 'theory', scalePattern: 'theory',
  droneTone: 'theory',
  tuner: 'tools', midiStatus: 'tools', practiceTimer: 'tools',
  weaknessAnalysis: 'stats', reminderShare: 'stats', practiceHistory: 'stats',
  songChord: 'song',
}

export function isPanelVisible(panelId: PanelId, profile: SkillProfile): boolean {
  return SKILL_LEVELS[profile] >= SKILL_LEVELS[PANEL_MIN_LEVEL[panelId]]
}

export function getVisibleTabs(profile: SkillProfile): PanelTab[] {
  const visibleTabs = new Set<PanelTab>()
  for (const [panelId, tab] of Object.entries(PANEL_TAB_MAP) as [PanelId, PanelTab][]) {
    if (isPanelVisible(panelId, profile)) visibleTabs.add(tab)
  }
  return PANEL_TABS.map(t => t.id).filter(id => visibleTabs.has(id))
}

import { useState, useCallback, useMemo } from 'react'
import type { InstrumentConfig } from '../types/music'
import { INSTRUMENTS, STANDARD_GUITAR } from '../constants/tunings'
import { loadSettings, saveSettings, isOnboardingDone, markOnboardingDone } from '../utils/storage'
import {
  type PanelTab, type SkillProfile, type PanelId,
  PANEL_TAB_KEY, SKILL_PROFILE_KEY,
  isPanelVisible, getVisibleTabs,
} from '../utils/panelConfig'

// App mode: 'free' = 기존 자유 연습, 'curriculum' = 커리큘럼 학습
type AppMode = 'free' | 'curriculum'
const APP_MODE_KEY = 'bocchi-app-mode'

function resolveInstrument(name: string, type: string): InstrumentConfig {
  return INSTRUMENTS.find((i) => i.name === name)
    ?? INSTRUMENTS.find((i) => i.type === type)
    ?? STANDARD_GUITAR
}

// Read initial settings once at module load
const initialSettings = loadSettings()

export { initialSettings }

export function useAppSettings() {
  // ── App Mode Toggle ──
  const [appMode, setAppMode] = useState<AppMode>(
    () => { const v = localStorage.getItem(APP_MODE_KEY); return v === 'free' || v === 'curriculum' ? v : 'free' },
  )
  const switchToFree = useCallback(() => { setAppMode('free'); localStorage.setItem(APP_MODE_KEY, 'free') }, [])
  const switchToCurriculum = useCallback(() => { setAppMode('curriculum'); localStorage.setItem(APP_MODE_KEY, 'curriculum') }, [])

  // ── Panel Tab ──
  const [panelTab, setPanelTab] = useState<PanelTab>(
    () => { const v = localStorage.getItem(PANEL_TAB_KEY); return (v === 'play' || v === 'drill' || v === 'theory' || v === 'tools' || v === 'stats') ? v : 'play' },
  )
  const handlePanelTabChange = useCallback((tab: PanelTab) => {
    setPanelTab(tab)
    localStorage.setItem(PANEL_TAB_KEY, tab)
  }, [])

  // ── Skill Profile ──
  const [skillProfile, setSkillProfile] = useState<SkillProfile>(
    () => {
      const v = localStorage.getItem(SKILL_PROFILE_KEY)
      return (v === 'beginner' || v === 'intermediate' || v === 'advanced') ? v : 'beginner'
    },
  )
  const visibleTabs = useMemo(() => getVisibleTabs(skillProfile), [skillProfile])
  const showPanel = useCallback((id: PanelId) => isPanelVisible(id, skillProfile), [skillProfile])

  const handleSkillProfileChange = useCallback((profile: SkillProfile) => {
    setSkillProfile(profile)
    localStorage.setItem(SKILL_PROFILE_KEY, profile)
    const newVisible = getVisibleTabs(profile)
    setPanelTab(prev => {
      if (!newVisible.includes(prev)) {
        const next = newVisible[0] ?? 'play'
        localStorage.setItem(PANEL_TAB_KEY, next)
        return next
      }
      return prev
    })
  }, [])

  // ── Onboarding Wizard ──
  const [showOnboarding, setShowOnboarding] = useState(() => !isOnboardingDone())

  // ── Instrument ──
  const [instrument, setInstrument] = useState<InstrumentConfig>(
    resolveInstrument(initialSettings.instrumentName, initialSettings.instrumentType),
  )

  const handleOnboardingComplete = useCallback((selectedInstrument: InstrumentConfig, goToCurriculum: boolean) => {
    markOnboardingDone()
    setShowOnboarding(false)
    setInstrument(selectedInstrument)
    saveSettings({ instrumentType: selectedInstrument.type, instrumentName: selectedInstrument.name })
    if (goToCurriculum) {
      setAppMode('curriculum')
      localStorage.setItem(APP_MODE_KEY, 'curriculum')
    }
  }, [])

  // ── UI toggles ──
  const [showShortcutHelp, setShowShortcutHelp] = useState(false)
  const [beatFlashEnabled, setBeatFlashEnabled] = useState(false)

  return {
    // App mode
    appMode, switchToFree, switchToCurriculum,
    // Panel tab
    panelTab, handlePanelTabChange,
    // Skill profile
    skillProfile, visibleTabs, showPanel, handleSkillProfileChange,
    // Onboarding
    showOnboarding, handleOnboardingComplete,
    // Instrument
    instrument, setInstrument,
    // UI
    showShortcutHelp, setShowShortcutHelp,
    beatFlashEnabled, setBeatFlashEnabled,
  }
}

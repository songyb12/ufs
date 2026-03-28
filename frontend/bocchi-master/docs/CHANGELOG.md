# Changelog

All notable changes to bocchi-master are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [2026-03-27] Quality Audit & Type Safety Session

### Added
- **ChordQuality literal union type** (19 literals) in `types/music.ts` — compile-time validation for all chord quality strings
- **Hook return type interfaces**: `UseMetronomeReturn` (22 props), `UseFretboardSettingsReturn` (30 props), `UseAppSettingsReturn` (18 props)
- **Code splitting**: 8 heavy components lazy-loaded via `React.lazy()` + `Suspense` (CircleOfFifths, CurriculumMode, OnboardingWizard, PracticeHistoryPanel, WeaknessAnalysisPanel, CallResponsePanel, TunerPanel, ReminderSharePanel)
- **Ref-based cleanup patterns**: `stopDroneRef` / `stopListeningRef` for safe useEffect teardown without stale closures

### Changed
- **5 eslint-disable comments removed** via proper dependency management and ref patterns:
  - `PracticeTimerPanel`: guard values (running, expanded) read via refs to avoid unintended auto-start
  - `TempoTrainerPanel`: added stable useCallback deps (active, handleStop)
  - `useChordProgression`: merged duplicate useEffect, added voicingSource to deps
  - `DroneTonePanel`: stopDroneRef pattern replaces eslint-disable on cleanup effect
  - `TunerPanel`: stopListeningRef pattern replaces eslint-disable on cleanup effect
- **Record key types strengthened** across 4 files:
  - `DrillType` keys in DrillRunner, LessonView, WeaknessAnalysisPanel
  - `AchievementRarity` keys in CurriculumMode
  - `ChordQuality` keys in chordProgression (shortQuality, qualitySuffix), voicingLibrary (CAGED_SHAPES), scaleAdvisor (QUALITY_SCALE_MAP)
- **ChordQuality type propagated** through interfaces: DegreeInfo, ProgressionStep, ResolvedChord, JPopChordStep and function params across 8 files
- **State setter types**: `Dispatch<SetStateAction<T>>` for all useState-derived setters in hook interfaces (updater function compatibility)

### Fixed

#### Critical (data corruption / wrong output)
- **8 chord quality comparison bugs in App.tsx**: `'minor'`→`'Minor'`, `'minor7'`→`'m7'`, `'diminished'`→`'dim'`, `'augmented'`→`'aug'`, `'dominant7'`→`'7th'`, `'major7'`→`'Maj7'` — mismatched strings caused chord tone highlighting and suffix display to silently fail
- **qualitySuffix `'m'` key removed**: not a valid ChordQuality, dead code in chordProgression.ts
- **Redundant ternary chain replaced** in App.tsx: `activeChord.quality === 'minor' ? 'm' : ...` → `activeChord.chordName` (already formatted correctly)
- **AudioNode leak**: oscillator/gain nodes not disconnected after playback — added `onended` cleanup
- **AudioContext resume**: added `ctx.resume()` guard for browsers requiring user-gesture activation
- **Metronome accent array**: out-of-bounds access when beatsPerMeasure changes — added length guard
- **Circle of Fifths SVG**: `<text>` elements missing `key` prop in `.map()` — React reconciliation issue
- **Strum pattern arrow offset**: down-arrow SVG path y-coordinate off by 2px

#### Warning (UX / correctness)
- **MIDI velocity mapping**: linear `vel / 127` → perceptual curve `(vel / 127)^2` for natural dynamics
- **Metronome BPM validation**: clamped to 20–300 range on input blur
- **Quiz timer cleanup**: `clearInterval` on unmount to prevent ghost timer updates
- **localStorage quota**: added try-catch around all `setItem` calls to handle QuotaExceededError
- **Scale comparison reset**: `compareScaleIdx` reset to `null` when root/scale changes
- **Fretboard auto-zoom bounds**: clamped fret range to `[0, fretCount]` to prevent negative indices
- **Practice history export**: added BOM (`\uFEFF`) to CSV export for proper Korean text display in Excel
- **Chord progression Markov**: fallback to uniform distribution when transition row sums to zero
- **useEffect dependency**: multiple missing/incorrect deps fixed across 12+ hooks and components
- **SVG accessibility**: added `role="img"` and `aria-label` to fretboard and circle-of-fifths SVGs
- **Touch target sizing**: increased small buttons to minimum 44×44px for mobile usability
- **Color contrast**: improved low-contrast text in dark theme (muted labels, disabled states)
- **Keyboard navigation**: added `onKeyDown` Enter/Space handlers to clickable non-button elements

### Commits
1. `7b86d2e` fix(bocchi): comprehensive bug audit - 37 fixes across 6 categories
2. `5f060f5` refactor(bocchi): remove 5 eslint-disable comments via proper deps and ref patterns
3. `9b3400b` feat(bocchi): add ChordQuality literal union type and strengthen Record key types
4. `537f68a` refactor(bocchi): add explicit return type interfaces for 3 complex hooks

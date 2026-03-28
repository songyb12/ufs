# Bocchi-master 교육자 관점 분석 리포트

> 분석 일자: 2026-03-22
> 코드베이스: `frontend/bocchi-master/src/` (~18K lines, ~82 files)

---

## 1. 현재 구현된 기능 전체 목록

### 1.1 프렛보드 & 시각화

| 기능 | 위치 | 설명 |
|------|------|------|
| SVG 프렛보드 | `components/fretboard/Fretboard.tsx` | 인터랙티브 프렛보드, 클릭으로 노트 선택 |
| 다중 오버레이 | 위와 동일 | 스케일(파랑), 보이싱(녹색), 패턴(청록), 코드톤(분홍), MIDI(밝은색) |
| 자동 줌 | 위와 동일 | 보이싱 선택 시 해당 프렛 범위로 뷰박스 크롭 |
| 왼손잡이 미러 | 위와 동일 | `scaleX(-1)` 변환으로 좌우 반전 |
| 고스트 모드 | 위와 동일 | 특정 줄 흐리게 표시 (집중 연습용) |
| 노트 라벨 모드 | `utils/noteLabelFormatter.ts` | 음이름 / 인터벌(R, m3, P5) / 로마숫자(I, II, III) |
| 이명동음 전환 | `utils/enharmonic.ts` | C# ↔ Db 전환, 조성별 자동 추천 |
| 프렛 마커 | `components/fretboard/FretMarker.tsx` | 3, 5, 7, 9, 12프렛 인레이 |
| 튜닝 퀵스위치 | `components/fretboard/TuningQuickSwitch.tsx` | Standard, Drop D, Open G 등 원클릭 전환 |

### 1.2 메트로놈 & 리듬

| 기능 | 위치 | 설명 |
|------|------|------|
| 메트로놈 | `hooks/useMetronome.ts` + `utils/audioScheduler.ts` | 샘플 정확도 타이밍, 40-240 BPM |
| 박자 설정 | 위와 동일 | 2/4 ~ 7/8, 악센트 패턴 커스텀 |
| 서브디비전 | 위와 동일 | 4분음표/8분음표/셋잇단/16분음표 |
| 스윙 | 위와 동일 | 0-100% 스윙 비율 |
| 클릭 사운드 | 위와 동일 | Sine, Wood, Hihat, Rimshot (합성음) |
| 카운트인 | 위와 동일 | 1마디 카운트 후 시작 |
| 탭 템포 | `components/metronome/TapTempo.tsx` | 4탭 평균으로 BPM 계산 |
| 펜듈럼 | `components/metronome/MetronomePendulum.tsx` | SVG 진자 애니메이션 |
| 비트 플래시 | `components/metronome/BeatFlash.tsx` | 비트에 맞춘 테두리 점멸 |
| 템포 트레이너 | `components/metronome/TempoTrainer.tsx` | 메트로놈 없이 템포 유지 훈련 |
| 스트럼 패턴 | `components/rhythm/StrumPatternPanel.tsx` | 13개 패턴 (Basic/Pop/Folk/Funk/Blues) |
| 리듬 노테이션 | `components/rhythm/RhythmNotation.tsx` | SVG 음표 머리+줄기+빔 표기 |

### 1.3 코드 & 보이싱

| 기능 | 위치 | 설명 |
|------|------|------|
| CAGED 보이싱 | `utils/voicingLibrary.ts` | E/A/D/C/G 폼, Major/Minor/7th/m7/Maj7 |
| 자동 보이싱 생성 | `utils/voicingGenerator.ts` | 백트래킹 DFS, 프렛 스팬 ≤4 제약 |
| 보이스 리딩 최적화 | `utils/voicingOptimizer.ts` | Viterbi DP, 최소 이동 거리 |
| 코드 다이어그램 | `components/progression/ChordDiagram.tsx` | SVG 그리드 + 핑거링 번호 |
| 보이싱 비교 | `components/progression/VoicingComparePanel.tsx` | 캐러셀 UI, 난이도 뱃지, 오디오 프리뷰 |
| 핑거링 추천 | `utils/voicingLibrary.ts:suggestFingering` | 1-4 손가락 배정 |
| 난이도 분류 | `utils/voicingLibrary.ts:classifyDifficulty` | Open / Barre / Advanced |

### 1.4 코드 진행 & 반주

| 기능 | 위치 | 설명 |
|------|------|------|
| 13개 프리셋 | `utils/chordProgression.ts` | Pop/Blues/Jazz/Funk/Bossa/J-Pop |
| 커스텀 진행 편집 | `components/progression/CustomProgressionEditor.tsx` | 로마숫자 + 퀄리티 오버라이드 |
| 랜덤 진행 생성 | `utils/chordProgression.ts:generateRandom` | Markov chain 기반 |
| 드럼+베이스 반주 | `hooks/useBackingTrack.ts` + `utils/backingPatterns.ts` | 7스타일 (Rock/Jazz/Funk/Bossa/Reggae/Waltz/Click) |
| 드럼 합성 | `utils/drumSynth.ts` | 킥/스네어/하이햇 (Web Audio 합성) |
| J-Pop 진행 | `data/jpopProgressions.ts` | 왕도/소악마/카논 진행 |

### 1.5 스케일 & 이론

| 기능 | 위치 | 설명 |
|------|------|------|
| 20+ 스케일 | `utils/scaleCalculator.ts` | 7모드 + Pentatonic + Blues + Jazz 스케일 |
| 20+ 코드 | 위와 동일 | Triad + 7th + Extensions + Power |
| 스케일 공식 표시 | 위와 동일 | W W H W W W H 형태 |
| 조표 계산 | 위와 동일 | 샵/플랫 개수 표시 |
| 스케일 파인더 | `utils/scaleFinder.ts` | 입력 노트 → 가능한 스케일 역검색 |
| 스케일 어드바이저 | `utils/scaleAdvisor.ts` | 코드 위 즉흥연주 스케일 추천 + 이유 |
| 박스 패턴 | `utils/scalePatterns.ts` | CAGED 포지션별 시각 오버레이 |
| 5도권 | `components/theory/CircleOfFifths.tsx` | 인터랙티브 원형 차트 |

### 1.6 연습 & 훈련

| 기능 | 위치 | 설명 |
|------|------|------|
| 프렛보드 퀴즈 | `components/trainer/FretboardQuizPanel.tsx` | 3단계 난이도, 타이머 모드, 스트릭 추적 |
| 인터벌 트레이너 | `hooks/useIntervalTrainer.ts` | 6개 난이도 세트, 인터벌별 정확도 추적 |
| 연습 모드 | `hooks/usePracticeMode.ts` | MIDI 입력 기반 노트 정확도 평가 |
| 연습 타이머 | `components/practice/PracticeTimerPanel.tsx` | 스톱워치/카운트다운, 일일 목표, 주간 스트릭 |
| 연습 기록 | `utils/storage.ts` | 100세션 히스토리, JSON export/import |
| 드론 톤 | `components/practice/DroneTonePanel.tsx` | 지속음 재생 (피치 레퍼런스) |
| 코드 전환 타이머 | `components/trainer/ChordTransitionTimer.tsx` | BPM 기반 코드 체인지 속도 훈련 |

### 1.7 커리큘럼 & 게이미피케이션

| 기능 | 위치 | 설명 |
|------|------|------|
| 기타 커리큘럼 | `data/curriculum.ts` | 6레벨, ~23레슨, ~70드릴 |
| 베이스 커리큘럼 | 위와 동일 | 8레벨, ~30레슨, ~100드릴 |
| 10종 드릴 타입 | `components/curriculum/DrillRunner.tsx` | chord-change, strum, quiz, ear-training 등 |
| 27단계 레벨 시스템 | `data/gamification.ts` | "완전 초보" → "봇치 마스터", XP 기반 |
| 24+ 업적 | 위와 동일 | 6카테고리, 4등급 레어리티 |
| 데일리 미션 | 위와 동일 | 날짜 시드 기반 3미션/일 |
| 진도 맵 | `components/curriculum/CurriculumView.tsx` | 레벨 트리, 잠금/완료 상태, XP 바 |
| 사운드 이펙트 | `components/curriculum/soundEffects.ts` | 성공/레벨업/업적 효과음 |
| 업적 갤러리 | `components/curriculum/AchievementGallery.tsx` | 카테고리별 카드, 레어리티 테두리 |

### 1.8 MIDI & 오디오

| 기능 | 위치 | 설명 |
|------|------|------|
| WebMIDI 입력 | `hooks/useMidi.ts` | 핫플러그, 멀티 디바이스, Note On/Off |
| 기타 합성 | `utils/synthEngine.ts` | Dual sawtooth + pluck noise + LP filter |
| 코드 재생 | 위와 동일 | Strum(30ms)/Arpeggiate(100ms)/Simultaneous |
| MIDI 상태 표시 | `components/midi/MidiStatus.tsx` | 연결 뱃지 + 디바이스 리스트 |

### 1.9 기타

| 기능 | 위치 | 설명 |
|------|------|------|
| 키보드 단축키 | `hooks/useKeyboardShortcuts.ts` | Space/↑↓/←→/B/P/S/C/M/? |
| 카포 지원 | `App.tsx` | 카포 위치에 따른 이펙티브 튜닝 조정 |
| 다크 테마 | `index.css` + Tailwind | 슬레이트 900 기반 다크 UI |
| localStorage 자동저장 | `utils/storage.ts` | 500ms 디바운스, 전체 설정 영속화 |
| 악기 전환 | `components/layout/Header.tsx` | 기타 8종 + 베이스 5종 튜닝 |
| 곡 데이터베이스 | `data/songDatabase.ts` | J-Pop 곡 메타데이터 |

---

## 2. 교육학적 갭 분석

### 학습 여정 매핑: 현재 커버리지

```
학습 단계                  커버리지      평가
─────────────────────────────────────────────
1. 악기 잡는 법/자세       ❌ 없음       텍스트/영상 가이드 부재
2. 튜닝                    ✅ 양호       YIN 피치 감지 튜너 구현 (#3)
3. 첫 오픈 코드            ✅ 양호       C/G/Am/Em/D + 다이어그램
4. 기본 스트럼             ✅ 양호       13패턴, 노테이션 뷰
5. 코드 전환 연습          ✅ 양호       타이머 + 메트로놈 연동
6. 바레 코드               ✅ 양호       F/Am폼 + CAGED 시스템
7. 파워 코드               ✅ 양호       E5/A5/D5/G5/B5
8. 펜타토닉 스케일         ✅ 양호       박스 패턴, 포지션 오버레이
9. 블루스 스케일           ✅ 양호       블루스 + 메이저 블루스
10. 솔로잉 기초            ⚠️ 약함       스케일 어드바이저 있으나 실전 훈련 부재
11. 테크닉 (H-on/P-off)   ⚠️ 약함       커리큘럼 언급만, 인터랙티브 드릴 없음
12. 리듬 정확도 훈련       ✅ 양호       MIDI 비트 오프셋 채점 구현 (#1)
13. 즉흥연주               ⚠️ 개선       코드톤 드릴(#4) + 콜앤리스폰스(#8) 추가
14. 곡 완주                ⚠️ 부분       곡 DB 있으나 섹션 연습만 지원
15. 음악 이론 심화         ⚠️ 부분       5도권, 스케일 공식 있으나 설명 부족
16. 앙상블/밴드 연습       ⚠️ 약함       반주 트랙만, 파트별 분리 없음
```

### 핵심 공백 상세 분석

#### GAP-1: 절대 초보자 온보딩 부재
**현황**: 앱을 처음 여는 사용자를 위한 가이드가 없음. 자유 연습 모드에 40+ UI 요소가 한꺼번에 노출됨.
**영향**: 초보자가 어디서 시작해야 할지 모름. 커리큘럼 모드로의 유도도 약함.
**필요한 것**: 첫 실행 온보딩 위저드, 단계적 UI 노출, "오늘 뭐 연습할까?" 추천.

#### GAP-2: 리듬 정확도 평가 시스템 부재
**현황**: 메트로놈과 스트럼 패턴은 있지만, 사용자가 실제로 정박에 맞추는지 평가하는 메커니즘이 없음.
**영향**: 리듬 연습의 피드백 루프가 닫히지 않음. "잘하고 있는지" 알 수 없음.
**필요한 것**: MIDI/마이크 입력 타이밍 분석 → 비트 대비 오프셋(ms) 측정 → 리듬 정확도 %.

#### GAP-3: 테크닉 드릴 인터랙티브 부재
**현황**: 해머온/풀오프, 슬라이드, 뮤팅 등이 커리큘럼 텍스트로만 존재. 실제 감지/피드백 불가.
**영향**: 가장 어려운 물리적 테크닉이 셀프 평가에만 의존.
**필요한 것**: 최소한 MIDI velocity 변화 감지(해머온은 약한 velocity), 패턴 시퀀스 드릴.

#### GAP-4: 솔로잉/즉흥연주 가이드
**현황**: 스케일 어드바이저가 "이 코드 위에 이 스케일" 추천은 해주지만, 실제로 솔로를 구성하는 방법(프레이징, 타깃 노트, 텐션-리졸브)에 대한 연습이 없음.
**영향**: 스케일을 알아도 "무엇을 연주해야 하는지" 모르는 단계에서 정체.
**필요한 것**: 코드톤 타깃팅 드릴, 콜-앤-리스폰스 연습, 프레이즈 빌더.

#### GAP-5: 곡 기반 학습 경로 미완성
**현황**: `songDatabase.ts` 존재, 커리큘럼에 song-section 드릴 정의됨. 하지만 실제 곡 재생/싱크 기능 없음.
**영향**: "곡을 칠 수 있게 되고 싶다"는 가장 보편적인 학습 동기를 충족 못함.
**필요한 것**: 곡별 코드 진행 타임라인, 구간 반복, 속도 조절 재생.

#### GAP-6: 튜너 기능 부재
**현황**: 튜닝 정보 표시만 가능, 실제 피치 감지 없음.
**영향**: 매 연습 시작 전 외부 튜너 앱 필요 — 사용자 이탈점.
**필요한 것**: Web Audio API `AnalyserNode` + autocorrelation 피치 감지.

---

## 3. 커리큘럼 모드 구현 수준 평가

### 3.1 구조적 완성도: ★★★★☆ (4/5)

**잘 된 점**:
- 기타 6레벨/23레슨/70드릴, 베이스 8레벨/30레슨/100드릴로 콘텐츠 양 충분
- 레벨 잠금 → XP 기반 해제 시스템으로 자연스러운 진행
- 10종 드릴 타입으로 다양한 연습 형태 지원
- J-Pop 특화 콘텐츠 (왕도/소악마/카논 진행)가 차별점

**부족한 점**:
- 레벨 간 난이도 곡선이 급격함 (Level 3 → 4에서 스트럼 → 테크닉으로 점프)
- 레슨 내 이론 콘텐츠가 간단한 마크다운 텍스트 — 시각적 예시 부족

### 3.2 드릴 인터랙티비티: ★★★☆☆ (3/5)

**자동 채점 가능 (2/10 타입)**:
- `fretboard-quiz`: 10문제 객관식, 정확도 자동 채점
- `ear-training`: 인터벌 퀴즈, 자동 채점

**셀프 평가 의존 (8/10 타입)**:
- `chord-change`, `strum-pattern`, `arpeggio`, `scale-run`, `rhythm`, `song-section`, `voicing-match`, `progression-play`
- 3단계 자기 평가: "어려웠음"(60%) / "괜찮았음"(80%) / "완벽함!"(95%)

**문제점**: 드릴 10종 중 8종이 셀프 평가 — 객관적 피드백 부재. 초보자는 자신의 수준을 정확히 판단하기 어려움. 특히 `chord-change`와 `strum-pattern`은 MIDI 타이밍 분석으로 자동 채점 가능한 영역.

### 3.3 진도 추적: ★★★★☆ (4/5)

**잘 된 점**:
- 레슨/드릴별 완료 상태 + 베스트 스코어 영속 저장
- XP 누적 → 27단계 레벨 시스템 → 레벨 자동 해제
- 데일리 미션 3개 (날짜 시드 기반 결정론적 생성)
- 스트릭 추적 (연속 일수, 최고 기록)

**부족한 점**:
- `totalPracticeMinutes`가 프로필에 정의되어 있지만 실제 누적되지 않음
- `completedSongs` 배열이 있지만 곡 완주를 트리거하는 경로 없음
- `dailyPracticeLog`가 정의만 되고 사용되지 않음
- 히든 업적(`night-owl`, `bocchi-reference`)의 트리거 로직 미구현

### 3.4 게이미피케이션: ★★★★☆ (4/5)

**잘 된 점**:
- 27단계 RPG 칭호 시스템 (한/영/일 3개국어)
- 24+ 업적, 6카테고리, 4등급 레어리티 (common → legendary)
- 업적 달성 시 사운드 이펙트 + 팝업 + XP 보상
- 레벨업 축하 모달 + 애니메이션

**부족한 점**:
- 업적 조건 중 `chord_count`가 추정치 기반 (드릴당 ~3코드 가정)
- 챌린지 카테고리가 비어있음 (0개 정의)
- 베이스 전용 업적 없음

### 3.5 종합 평가

| 항목 | 점수 | 비고 |
|------|------|------|
| 콘텐츠 양 | ★★★★☆ | 기타 23+, 베이스 30+ 레슨 |
| 교육 순서 | ★★★★☆ | Open → Barre → Progression → Technique 자연스러움 |
| 인터랙티비티 | ★★★☆☆ | 자동 채점 2/10, 나머지 셀프 평가 |
| 피드백 품질 | ★★★☆☆ | 정확도 % 제공, 구체적 교정 피드백 없음 |
| 동기부여 | ★★★★☆ | XP/레벨/업적/미션 시스템 양호 |
| 개인화 | ★★★★☆ | 약점 분석(#7) + 적응형 난이도(#5) 구현 완료 |

---

## 4. 추가 기능 아이디어 10선

### 우선순위 + 구현 난이도 기준

- **Impact**: 학습 효과 향상도 (H=High, M=Medium, L=Low)
- **Size**: 구현 난이도 (S=Small ~1-2일, M=Medium ~3-5일, L=Large ~1-2주)

| # | 기능 | Impact | Size | 상태 | 설명 |
|---|------|--------|------|------|------|
| 1 | **리듬 정확도 채점** | H | M | ✅ 완료 | `hooks/useRhythmScore.ts` + `components/practice/RhythmScorePanel.tsx`. performance.now() 기반 비트 오프셋 계산, PERFECT/GOOD/OK/MISS 4등급 채점. |
| 2 | **초보자 온보딩 위저드** | H | S | ✅ 완료 | `components/onboarding/OnboardingWizard.tsx`. 5단계 대화형 가이드 (악기→튜닝→첫코드→다음단계). localStorage 플래그로 1회만 표시. |
| 3 | **내장 크로매틱 튜너** | H | M | ✅ 완료 | `components/tuner/TunerPanel.tsx` + `utils/pitchDetector.ts`. YIN autocorrelation, 센트 오프셋 바, 줄별 하이라이트. 별도 AudioContext로 마이크 격리. |
| 4 | **코드톤 타깃팅 드릴** | H | S | ✅ 완료 | `components/trainer/ChordToneDrillPanel.tsx`. sequence/free 모드, MIDI 입력으로 R→3→5→7 연주, 톤별 정확도 추적. |
| 5 | **적응형 난이도 시스템** | M | M | ✅ 완료 | `utils/adaptiveDifficulty.ts` + `DrillRunner.tsx` 통합. 4단계 티어(easier/normal/on-track/harder), BPM·코드 수·퀴즈 난이도·시간 자동 조절. |
| 6 | **곡 플레이어 + 구간 반복** | H | L | ❌ 미구현 | L 난이도로 스코프가 큼. 곡 타임라인 싱크, A-B 반복, 속도 조절 등 오디오 동기화 복잡도가 높아 추후 구현 예정. |
| 7 | **약점 분석 대시보드** | M | M | ✅ 완료 | `components/practice/WeaknessAnalysisPanel.tsx`. 4개 localStorage 소스 병합, 드릴별 정확도 바, 주간 활동 차트, 7종 자동 인사이트. |
| 8 | **콜-앤-리스폰스 연습** | M | M | ✅ 완료 | `components/trainer/CallResponsePanel.tsx`. 3단계 난이도 (19개 패턴), synthEngine 재생 → MIDI 입력 채점, 음 단위 시각 비교. |
| 9 | **연습 리마인더 + 소셜 공유** | L | S | ✅ 완료 | `components/practice/ReminderSharePanel.tsx` + `storage.ts` 확장. Notification API 리마인더 (요일/시간 설정), Web Share API + 클립보드 폴백 공유. |
| 10 | **마이크 입력 음 감지** | M | L | ❌ 미구현 | L 난이도. 튜너(#3)의 단음 감지는 구현되었으나, 연습 모드에서의 실시간 음 매핑은 다성음 처리·레이턴시 문제로 추후 구현 예정. |

### 구현 추천 순서 및 진행 상태

```
Phase 1 (즉시 효과, 작은 투자):               ✅ 완료
  #2 초보자 온보딩 (S) ✅ → #4 코드톤 타깃팅 (S) ✅

Phase 2 (핵심 피드백 루프 완성):               ✅ 완료
  #1 리듬 정확도 채점 (M) ✅ → #3 크로매틱 튜너 (M) ✅

Phase 3 (학습 경험 심화):                      ✅ 완료
  #5 적응형 난이도 (M) ✅ → #7 약점 분석 (M) ✅ → #8 콜앤리스폰스 (M) ✅

Phase 4 (콘텐츠 확장):                         ❌ 미구현
  #6 곡 플레이어 (L) ❌ → #10 마이크 입력 (L) ❌
  사유: 둘 다 L 난이도. #6은 곡 타임라인 싱크/A-B 반복의 오디오 동기화 복잡도,
  #10은 다성음 감지/레이턴시 문제로 별도 스프린트 필요.

Phase 5 (리텐션):                              ✅ 완료
  #9 리마인더/공유 (S) ✅

총 진행률: 8/10 완료 (80%)
```

---

## 부록: 기술 스택 요약

| 계층 | 기술 |
|------|------|
| UI | React 19 + TypeScript 5.9 + Tailwind 4 |
| 빌드 | Vite 7 |
| 오디오 | Web Audio API (합성음, 샘플 무사용) |
| MIDI | WebMIDI API |
| 렌더링 | SVG (프렛보드, 다이어그램, 노테이션) |
| 영속화 | localStorage (설정, 진도, 히스토리) |
| 최적화 | Viterbi DP (보이스리딩), 백트래킹 DFS (보이싱) |

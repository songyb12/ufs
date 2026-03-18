# UFS Shell 멀티플랫폼 통합 플랜 (v2 — 머지 반영)

## 목표
UFS Shell(`:3000`)을 멀티플랫폼(PC/Mobile/TV+RPi3) 통합 프론트엔드로 완성한다.
모든 서브앱은 **overview + iframe 하이브리드** 패턴으로 통일한다.

## 설계 원칙
- **각 서비스 독립 개발** — Shell은 overview 래퍼 + iframe 컨테이너 역할만
- **VIBE 패턴 통일** — overview 모드(모듈 목록 + health) ↔ 앱 모드(iframe full-screen) 전환
- **하나의 코드베이스** — 반응형 + URL 파라미터(`?mode=tv`)로 플랫폼 분기
- **RPi3 1GB RAM 고려** — Shell 자체를 가볍게 유지

## 현재 상태 (머지 후)
- ✅ Home: 실시간 health check (6개 서비스 + MCP)
- ✅ ShellLayout: 모바일 반응형 (768px 미만 sidebar overlay)
- ✅ ErrorBoundary + NotFound 라우팅
- ✅ VIBE: overview + iframe 하이브리드 (패턴 기준)
- ✅ Life-Master: API 연동 대시보드 (routines/habits/goals/completion)
- ✅ Eng-Ops: health check + planned features
- ❌ Bocchi: 70+ 파일 직접 복사 (독립 개발 원칙 위반) → **정리 필요**
- ❌ TV/Kiosk 레이아웃 없음
- ❌ PWA 없음

---

## Phase 1: Bocchi 코드 정리 — VIBE 패턴 통일

### 1-1. `apps/bocchi/` 디렉토리 정리
- `apps/bocchi/components/`, `hooks/`, `utils/`, `types/`, `constants/` 전부 삭제 (70+ 파일)
- `apps/bocchi/BocchiApp.tsx`를 VIBE 패턴의 가벼운 래퍼로 교체

### 1-2. BocchiApp.tsx 재작성 (VIBE 패턴)
```
overview 모드:
  - health check (/api/bocchi/health)
  - "Open Studio" 버튼 → 앱 모드 전환
  - feature 목록 (Fretboard, Metronome, Theory, Practice, etc.)

앱 모드:
  - 상단 바: "Bocchi-master" 제목 + "Back to Overview" 버튼
  - iframe src="/svc/bocchi/" (full-screen, allow="autoplay;midi")
```

### 1-3. nginx.conf 프록시 추가
기존 `/api/*`(백엔드 API)에 더해 `/svc/*`(프론트엔드 서비스) 프록시:
```
/svc/bocchi/  → http://bocchi-frontend:3000/
/svc/vibe/    → http://vibe:8001/ui/
/svc/life/    → http://life-master:8004/ui/
```
→ 같은 origin에서 iframe 로드 (CORS 회피)

### 1-4. vite.config.ts 개발 프록시 추가
```
'/svc/bocchi': { target: 'http://localhost:3001', rewrite: strip prefix }
'/svc/vibe':   { target: 'http://localhost:8001', rewrite: → /ui/ }
'/svc/life':   { target: 'http://localhost:8004', rewrite: → /ui/ }
```

### 1-5. VibeApp iframe src 수정
현재 `/api/vibe/ui/` → `/svc/vibe/` (일관된 프록시 경로)

### 1-6. LifeApp에 iframe 앱 모드 추가
현재 API 대시보드만 있음 → VIBE처럼 overview + iframe 전환 추가

---

## Phase 2: 반응형 레이아웃 (PC / Mobile / TV)

### 2-1. `shared/usePlatform.ts` 훅
```
type Platform = 'pc' | 'mobile' | 'tv'
- URL param ?mode=tv → 'tv' (localStorage 캐시)
- width < 768 → 'mobile'
- else → 'pc'
```

### 2-2. PC (현행 유지)
- Sidebar + Header + Main — 변경 없음

### 2-3. Mobile 개선
- 현행 sidebar overlay 유지
- 하단 네비게이션 바 추가 (Home + 4앱 아이콘)
- iframe 모드에서 하단 nav 숨김 (full-screen)

### 2-4. TV/Kiosk 레이아웃 (`shell/TVLayout.tsx`)
- Sidebar/Header 제거 → full-screen
- Home: 2×2 대형 앱 카드 + 시스템 상태 바
- 대시보드 모드: VIBE 시그널 + Life-Master 오늘 루틴 요약 자동 로테이션 (30s)
- 인터랙티브 모드: 방향키 + Enter 네비게이션
- 상단 바: 시계 + 서비스 상태 LED

### 2-5. ShellLayout 분기
- usePlatform → pc: 현행 / mobile: 현행+하단nav / tv: TVLayout

---

## Phase 3: PWA

### 3-1. manifest.json + 아이콘
### 3-2. Service Worker (vite-plugin-pwa, 정적 자산 캐싱)
### 3-3. index.html PWA 메타태그

---

## Phase 4: 보안 강화 (master-core)

### 4-1. MCP Server 바인딩: 0.0.0.0 → 127.0.0.1
### 4-2. CORS origins 환경변수화
### 4-3. 프록시 헤더 화이트리스트 전환

---

## 파일 변경 목록

### 삭제 (~70개)
- `frontend/ufs-shell/src/apps/bocchi/components/**` (전체)
- `frontend/ufs-shell/src/apps/bocchi/hooks/**` (전체)
- `frontend/ufs-shell/src/apps/bocchi/utils/**` (전체)
- `frontend/ufs-shell/src/apps/bocchi/types/**` (전체)
- `frontend/ufs-shell/src/apps/bocchi/constants/**` (전체)

### 신규 생성 (~5개)
1. `src/shared/usePlatform.ts` — 플랫폼 감지 훅
2. `src/shell/MobileNav.tsx` — 모바일 하단 네비게이션
3. `src/shell/TVLayout.tsx` — TV/키오스크 레이아웃
4. `public/manifest.json` — PWA 매니페스트

### 수정 (~8개)
1. `src/apps/bocchi/BocchiApp.tsx` — 70+ 파일 → 단일 래퍼 (~80줄)
2. `src/apps/vibe/VibeApp.tsx` — iframe src `/api/vibe/ui/` → `/svc/vibe/`
3. `src/apps/life/LifeApp.tsx` — iframe 앱 모드 추가
4. `src/shell/ShellLayout.tsx` — 플랫폼별 레이아웃 분기
5. `src/shell/Home.tsx` — TV 모드 대형 카드
6. `nginx.conf` — /svc/* 프록시 추가
7. `vite.config.ts` — /svc/* 개발 프록시 추가
8. `index.html` — PWA 메타태그

## 실행 순서
1. Phase 1 (Bocchi 정리 + iframe 통일) → TS 빌드 확인
2. Phase 2 (반응형 레이아웃) → 프리뷰 검증
3. Phase 3 (PWA) → 모바일 테스트
4. Phase 4 (보안) → master-core 수정
5. Docker rebuild → 전체 서비스 검증

# Session Manager — 함정 & 작업 규칙

AI 보조 개발 시 반복되는 실수 패턴과 예방 규칙을 기록한다.
버그를 수정하거나 새 기능을 추가할 때 **먼저 이 파일을 읽고**, 작업 후 **새로운 교훈이 생기면 추가**한다.

---

## 1. 임포트 누락 (NameError at runtime)

**사례**: `routes_api.py`에서 `string.ascii_uppercase`를 사용했지만 `import string`이 없어 `/api/browse?path=` 가 500.
테스트는 있었지만 빈 path 케이스(드라이브 목록 코드경로)만 커버가 안 됐다.

**패턴**: 표준 라이브러리 모듈(`string`, `math`, `textwrap` 등)은 흔히 쓰이기 때문에 다른 파일에서 이미 임포트됐다고 착각하기 쉽다.

**예방**:
- 새 stdlib 함수 사용 시 해당 파일 맨 위 import 블록을 직접 확인
- 새 엔드포인트/함수 추가 후 해당 코드경로를 직접 호출하는 테스트가 있는지 확인
- `python -c "from app.routes_api import router"` 로 임포트 에러 조기 발견 가능

---

## 2. 테스트 코드경로 커버리지 공백

**사례**: `/api/browse?path=` (빈 path, Windows 드라이브 열거) 코드경로는 테스트 없음 → 버그가 490 테스트를 통과.

**패턴**: 조건 분기(`if not path`, `if sys.platform == "win32"`)로 나뉘는 코드경로 중 한쪽이 누락되는 경우.

**예방**:
- 분기가 있는 엔드포인트는 각 분기마다 테스트 케이스 1개 이상
- 새 엔드포인트 추가 시 해당 파일에 테스트 추가 (PR 단위가 아니더라도 같은 커밋에)

---

## 3. 유령 세션 (Ghost Session)

**사례**: `s1`, `sess-p-resume` — 과거 작업에서 고정 ID로 세션을 생성하고 `data/sessions/`에 persist됨. 서버 재시작마다 복원돼 UI에 표시.

**패턴**: 테스트 또는 일회성 스크립트에서 고정 ID(`"s1"`, `"test-session"`)로 실제 세션을 만들면 JSON persist 파일이 남는다.

**예방**:
- 테스트에서 `ClaudeSession` 생성 시 `ephemeral=True` 또는 UUID 기반 ID 사용
- `lifespan` 좀비 세션 필터에 테스트 ID 패턴(`^test-`, `^s\d+$`) 추가 고려
- 직접 삭제: `DELETE /api/sessions/{id}` 또는 `data/sessions/{id}.json` 삭제

---

## 4. `textContent` → `innerHTML` 전환 시 XSS

**사례**: 세션 채팅 출력을 `el.textContent`에서 `el.innerHTML`로 바꿀 때 이미지 인라인 렌더를 위해 전환.

**패턴**: 성능/기능을 위해 `textContent`를 `innerHTML`로 교체할 때 escaping이 누락되면 XSS 취약점.

**규칙**:
- `innerHTML`에 삽입되는 모든 사용자/CLI 데이터는 반드시 `escapeHtml()` 통과
- 이미지 URL은 `/uploads/` 또는 `/screenshots/` prefix 화이트리스트로만 허용
- `renderTextWithImages()` 패턴: "escape 먼저, img 태그만 후처리"

---

## 5. `supervisor_model` 기본값 drift

**사례**: `sonnet`이 여러 곳에 기본값으로 하드코딩 → `opus`로 일괄 변경 시 누락 발생 가능.

**위치 목록** (변경 시 전부 확인):
- `models.py`: `PipelineStartRequest.supervisor_model`, `PlanPhaseStartRequest.supervisor_model`
- `pipeline.py`: `PlanPhase.__init__`, `_validate_recommended` setdefault
- `pipeline_configs.py`: 4개 builtin 프리셋
- `index.html`: 감독자 모델 드롭다운 첫 번째 옵션

---

## 6. index.html 단일 파일 SPA 작업 규칙

파일이 ~4000줄이라 구조 파악이 중요.

**주요 섹션 위치** (줄 번호는 대략적):
- CSS 변수 (`:root`): 14~27번
- 탭 정의 (`tab-bar`): ~1030번
- 모달 HTML: ~1343~1460번
- WS 메시지 핸들러: ~1760번
- `switchTab()`: ~2530번
- Pipeline 함수들: ~3000번
- `renderPipelineHistory()`: ~3420번
- `escapeHtml()`, `renderTextWithImages()`: ~3500번

**규칙**:
- 새 탭 추가 시: tab-bar HTML + 컨테이너 div + `switchTab()` 분기 + hide 로직 (4곳 모두)
- `innerHTML` 사용 시 항상 `escapeHtml()` 또는 `renderTextWithImages()` 경유
- 새 JS 함수는 관련 섹션 주석(`// ─── ...`) 아래에 배치

---

## 작업 전 체크리스트

새 기능 추가 또는 버그 수정 전:

```
[ ] 관련 파일의 import 블록 확인 (누락된 stdlib 없는지)
[ ] 수정하는 코드경로에 테스트가 있는지 확인
[ ] index.html 수정 시: 탭/모달/switchTab 4곳 일관성 확인
[ ] innerHTML 사용 시: escapeHtml 경유 여부 확인
[ ] 모델명 기본값 변경 시: 위 5번 목록 전체 확인
[ ] 수정 후: python -m pytest tests/ -q 통과 확인
```

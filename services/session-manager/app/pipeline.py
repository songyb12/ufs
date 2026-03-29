"""
app/pipeline.py — PipelineRunner and PlanPhase classes.
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import Optional

import app.state as _state
from app.session import ClaudeSession
from app.models import TASK_TIMEOUTS, LOGS_DIR
from app.pipeline_store import (
    create_run, update_stage, save_checkpoint,
    mark_complete, mark_failed,
)

logger = logging.getLogger(__name__)


def _tail_lines(text: str, max_chars: int = 3000) -> str:
    """Return up to max_chars from the end of text, starting at a line boundary.

    Avoids cutting in the middle of a line (semantic boundary preservation).
    """
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    newline_pos = tail.find("\n")
    if newline_pos > 0:
        tail = tail[newline_pos + 1:]
    return tail


# 개선 제안 감지 패턴 (supervisor / worker 출력에서 추출)
_SUGGESTION_RE = re.compile(
    r"^(?:💡\s*|제안\s*[:\-]\s*|Suggestion\s*[:\-]\s*|권장\s*[:\-]\s*"
    r"|개선\s*제안\s*[:\-]\s*|Note\s*[:\-]\s*|참고\s*[:\-]\s*|추천\s*[:\-]\s*)(.+)",
    re.IGNORECASE,
)

# 자동 결정 감지 패턴 (supervisor 출력에서 추출)
# 형식: "[결정] 설명 → 선택" 또는 "결정: 설명" 등
_AUTO_DECISION_RE = re.compile(
    r"^(?:\[(?:결정|선택|자동선택|decision|auto)\]\s*"
    r"|결정\s*[:\-]\s*|선택\s*[:\-]\s*|자동\s*선택\s*[:\-]\s*"
    r"|Decision\s*[:\-]\s*|자동으로\s+)(.+)",
    re.IGNORECASE,
)

# 사용자 확인 요청 감지 패턴 (worker / supervisor 출력에서 추출)
# AskUserQuestion 도구 외의 자유 형식 텍스트 패턴
_QUESTION_RE = re.compile(
    r"^(?:확인\s*(?:필요|해\s*주세요|바랍니다)\s*[:\-]?\s*"
    r"|선택해?\s*(?:주세요|주십시오|주시기\s*바랍니다)\s*[:\-]?\s*"
    r"|어떻게\s*하시겠습니까\??\s*"
    r"|어떤\s*(?:것|방법|방안|옵션)을?\s*원하시나요\??\s*"
    r"|\[(?:질문|확인|confirm|question)\]\s*"
    r"|Please\s+(?:confirm|choose|select|decide)\s*[:\-]?\s*)(.+)",
    re.IGNORECASE,
)


# 기본 사이클 페이즈 (사용자 미지정 시 순환 적용)
_DEFAULT_CYCLE_PHASES: list[str] = [
    "탐색/분석",
    "구현",
    "테스트/검증",
    "정리/마무리",
]


def _fmt_duration(secs: float) -> str:
    """소요 시간을 사람이 읽기 쉬운 문자열로 변환."""
    if secs < 60:
        return f"{secs:.0f}초"
    m, s = divmod(int(secs), 60)
    if m < 60:
        return (f"{m}분 {s}초" if s else f"{m}분") + f" ({secs:.0f}초)"
    h, rem_m = divmod(m, 60)
    base = f"{h}시간 {rem_m}분" if rem_m else f"{h}시간"
    return base + f" ({secs:.0f}초)"


# ─── 파이프라인 엔진 (LLM API / CLI → CLI 루프) ──────────────────────────────────


# 감독자 시스템 프롬프트 템플릿
_SUPERVISOR_SYSTEM = """당신은 텍스트 생성기입니다. 도구를 사용하지 마세요. 코드를 실행하지 마세요. 파일을 읽지 마세요.
오직 일반 텍스트만 출력하세요.

당신의 역할: 별도의 Claude Code CLI 작업자에게 보낼 프롬프트를 생성하는 것입니다.

## 목표
{goal}

## 출력 형식 (반드시 준수)
- 도구 호출(function_calls, Bash, Read, Glob 등)을 절대 하지 마세요
- XML 태그, 코드 블록, 함수 호출 형식을 절대 사용하지 마세요
- 한 번에 하나의 구체적인 프롬프트를 일반 텍스트로만 출력하세요
- 설명이나 머리말을 붙이지 마세요. 프롬프트 본문만 출력하세요

## 진행 규칙
- 이전 CLI 결과를 분석하여 다음 단계를 결정하세요
- 에러가 발생했으면 복구/수정 프롬프트를 생성하세요
- 사이클이 마지막({cycle}/{max_cycles})이 아닌 이상 절대 PIPELINE_DONE을 출력하지 마세요
- 진행 중인 작업이 없더라도 목표를 더 완성도 있게 다듬는 다음 프롬프트를 계속 생성하세요
- 목표가 완전히 달성되었고 마지막 사이클이면: PIPELINE_DONE: [완료 요약]

## AskUserQuestion 자동 처리 (중요)
작업자 CLI 출력 끝에 아래와 같은 블록이 나타나면, 작업자가 당신의 답변을 기다리고 있는 것입니다:

  ══ AskUserQuestion 대기 중 ══
  Q: [질문 내용]
  옵션: A) ... / B) ... / ...
  ══════════════════════════════

이 경우 당신의 응답은 반드시 해당 질문에 대한 직접 답변이어야 합니다.
- 목표와 계획에 가장 부합하는 옵션의 레이블을 선택하거나, 직접 답변 텍스트를 작성하세요
- 다음 작업 지시가 아닌, 질문에 대한 답변만 출력하세요
- 여러 질문이 있으면 각 질문에 대해 한 줄씩 답변하세요
- 예시: "A" 또는 "옵션1" 또는 "네, 진행하세요"

## 현재 상태
- 사이클: {cycle}/{max_cycles}  |  페이즈: {cycle_phase}
- 반복: {iteration}/{max_iterations}
- 작업자 CLI 작업 디렉토리: {work_dir}"""


# ─── 사이클 반성 프롬프트 ─────────────────────────────────────────────────────────

_CYCLE_REFLECTION_SYSTEM = """당신은 텍스트 생성기입니다. 도구를 사용하지 마세요. 오직 일반 텍스트만 출력하세요.

## 역할
방금 완료된 사이클을 분석하고, 다음 사이클의 실행 전략을 수립하세요.

## 전체 목표
{goal}

## 방금 완료한 사이클
- 사이클 번호: {completed_cycle}/{max_cycles}
- 페이즈: {completed_phase}
- 총 반복 횟수: {iterations}

## 마지막 작업 결과 (요약)
{last_output_tail}

## 출력 형식 (반드시 준수)
아래 4개 섹션을 순서대로 출력하세요. XML 태그나 코드 블록 없이 평문으로만 작성하세요.

[사이클 {completed_cycle} 성과 요약]
이번 사이클에서 달성한 것을 2~4줄로 서술하세요.

[미완료 항목]
아직 달성하지 못한 것, 발견된 문제점을 항목별로 나열하세요. 없으면 "없음"으로 표기.

[다음 사이클 ({next_cycle}/{max_cycles}) 전략]
페이즈: {next_phase}
다음 사이클에서 집중해야 할 작업과 접근 방식을 3~5줄로 구체적으로 서술하세요.

[주의 사항]
다음 사이클 작업자에게 전달할 중요 컨텍스트나 함정(pitfall)을 1~3줄로 서술하세요. 없으면 "없음"."""


# ─── 계획 수립 시스템 프롬프트 ────────────────────────────────────────────────────

_PLAN_QUESTIONS_SYSTEM = """당신은 소프트웨어 프로젝트 분석가입니다. 도구를 사용하지 마세요. 코드를 실행하지 마세요.
오직 JSON만 출력하세요.

사용자의 목표를 분석하고, 실행 계획을 세우기 전에 명확히 해야 할 질문들을 생성하세요.
사람은 실수하거나 놓치는 부분이 있으므로, 다양한 관점에서 질문하세요.

## 목표
{goal}

## 작업 디렉토리
{work_dir}

## 프로젝트 컨텍스트
{project_context}

## 출력 형식 (반드시 JSON만 출력)
```json
{{
  "questions": [
    {{
      "id": "q1",
      "question": "구체적인 질문 텍스트",
      "why": "이 질문이 중요한 이유 (한 줄)",
      "options": [
        {{"label": "선택지 제목", "description": "선택지 설명"}},
        {{"label": "선택지 제목", "description": "선택지 설명"}}
      ]
    }}
  ]
}}
```

## 규칙
- 5~10개의 질문을 생성하세요
- 각 질문에 2~4개의 예상 답변(options)을 제공하세요
- 프로젝트 컨텍스트를 참고하여 현실적인 옵션을 추천하세요
- 질문은 구체적이고 실행 가능해야 합니다
- 아키텍처, 기술 선택, 범위, 우선순위, 에러 처리, 테스트 등 다양한 관점을 포함하세요
- JSON 외의 텍스트(설명, 머리말, 꼬리말)를 절대 출력하지 마세요"""

_PLAN_GENERATION_SYSTEM = """당신은 소프트웨어 프로젝트 설계자입니다. 도구를 사용하지 마세요. 코드를 실행하지 마세요.
오직 마크다운 형식의 실행 계획만 출력하세요.

사용자의 목표와 질의응답 결과를 바탕으로, 구체적인 단계별 실행 계획을 생성하세요.

## 목표
{goal}

## 작업 디렉토리
{work_dir}

## 프로젝트 컨텍스트
{project_context}

## 질의응답 결과
{qa_summary}

## 출력 형식 (마크다운)
실행 계획을 다음 구조로 작성하세요:

### 요약
- 한 줄 요약

### 단계별 계획
1. **단계 제목** - 설명
   - 대상 파일/경로
   - 구체적 작업 내용
2. **단계 제목** - 설명
   ...

### 주의사항
- 리스크, 의존성, 주의점

### 예상 결과
- 완료 시 기대 결과

## 규칙
- 각 단계는 Claude CLI가 한 번의 프롬프트로 수행할 수 있는 크기여야 합니다
- 파일 경로와 작업 내용을 구체적으로 명시하세요
- 불필요한 단계를 추가하지 마세요
- 설명이나 머리말 없이 바로 계획을 출력하세요"""


class PipelineRunner:
    """감독자(API 또는 CLI)가 작업자 CLI를 반복 구동하는 파이프라인

    mode:
    - "api": Anthropic API (AsyncAnthropic)를 감독자로 사용
    - "cli": 별도 Claude CLI 세션을 감독자로 사용 (API Key 불필요)

    흐름:
    1. 감독자에게 질의 → 다음 프롬프트(또는 DONE) 생성
    2. 작업자 CLI 세션에 프롬프트 전달 → 실행 완료 대기
    3. 작업자 CLI 출력 수집 → 감독자에 전달
    4. 목표 달성 또는 최대 반복 시 종료
    """

    def __init__(self, source_session: ClaudeSession, goal: str,
                 supervisor_model: str, max_iterations: int,
                 mode: str = "api", max_cycles: int = 100,
                 cycle_phases: Optional[list[str]] = None,
                 cycle_reflection: bool = True,
                 cycle_checkpoint: bool = False):
        self.id = str(uuid.uuid4())[:8]
        self.session = source_session  # 선택한 세션을 직접 worker로 사용 (pw- 미생성)
        self.goal = goal
        self.supervisor_model = supervisor_model
        self.max_iterations = max_iterations
        self.max_cycles = max_cycles
        self.current_cycle = 1
        self.mode = mode                # "api" | "cli"
        self.iteration = 0
        # Cycle 고급 기능
        self.cycle_phases: list[str] = cycle_phases or _DEFAULT_CYCLE_PHASES
        self.cycle_reflection = cycle_reflection      # 사이클 종료 시 반성/재계획
        self.cycle_checkpoint = cycle_checkpoint      # 사이클 시작 전 사용자 확인 대기
        self.cycle_summaries: list[dict] = []         # 사이클별 반성 결과 누적
        self._cycle_confirm_event: Optional[asyncio.Event] = None  # checkpoint 대기 이벤트
        self.status = "idle"            # idle | running | completed | failed | stopped
        self.history: list[dict] = []
        self.summary = ""
        self.created_at = datetime.now().isoformat()
        self.started_at: str = ""
        self.ended_at: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_flag = False
        self._soft_stop_flag = False    # soft stop: 현재 단계 완료 후 중단
        self.stop_type: Optional[str] = None  # "hard" | "soft"
        # 단계별 실행 로그
        self._step_log: list[dict] = []
        # 후속 조치 항목 수집
        self.pending_items: dict = {
            "questions": [],       # 사용자 확인이 필요한 질문
            "auto_decisions": [],  # 시스템이 자동으로 선택한 항목
            "suggestions": [],     # 개선 제안
        }
        self.report: Optional[dict] = None   # 완료/중단 후 생성되는 최종 리포트
        self._resume_count: int = 0          # resume() 호출 횟수
        self._resumed_from_step: int = 0     # 마지막 resume 시점의 step_log 길이
        # CLI 감독자 전용
        self._supervisor_session: Optional[ClaudeSession] = None
        self._supervisor_retries = 0
        self._max_supervisor_retries = 3

    def start(self):
        self.status = "running"
        self.started_at = datetime.now().isoformat()
        # 선택한 세션에 파이프라인 바인딩 (별도 worker 생성 안함)
        self.session.pipeline_id = self.id
        self.session.pipeline_role = "worker"
        self.session.save_state()
        # DB에 run 레코드 생성 (checkpoint/상태 추적의 전제조건)
        create_run(self.id, self.session.id, self.max_iterations * self.max_cycles)
        if self.mode == "cli":
            try:
                self._create_supervisor_session()
            except Exception:
                # 감독자 생성 실패 → 세션 바인딩 롤백
                self.session.pipeline_id = None
                self.session.pipeline_role = None
                self.session.save_state()
                self.status = "failed"
                raise
        self._task = asyncio.create_task(self._run_loop())

    def _create_supervisor_session(self):
        """감독자용 CLI 세션 생성 (도구 차단 — 텍스트만 출력)

        감독자 세션은 sessions dict에 등록하지 않고, save_state를 no-op으로
        오버라이드하여 좀비 파일을 방지한다.
        """
        sid = f"sv-{self.id}"
        sv = ClaudeSession(sid, self.session.work_dir, self.supervisor_model,
                           no_tools=True,
                           skip_permissions=self.session.skip_permissions)
        sv.pipeline_id = self.id
        sv.pipeline_role = "supervisor"
        sv.save_state = lambda: None  # 디스크에 좀비 파일 방지
        sv.start_worker()
        self._supervisor_session = sv
        self._add_history("system", f"감독자 CLI 세션 생성: {sid} (no-tools)")

    async def stop(self, stop_type: str = "hard"):
        """파이프라인 중단.

        stop_type="hard": 즉시 중단 — 진행 중인 단계 취소, 리포트 생성.
        stop_type="soft": 현재 단계 완료 후 중단 — resumable 상태 보존, 리포트 생성.
        """
        self.stop_type = stop_type
        if stop_type == "soft":
            self._soft_stop_flag = True
            self._add_history("system",
                "⏸ Soft stop 요청: 현재 단계 완료 후 중단합니다. "
                "리포트 생성 후 세션은 resumable 상태로 보존됩니다.")
        else:
            self._stop_flag = True
            self.status = "stopped"
            self._add_history("system", "🛑 Hard stop: 즉시 중단합니다.")
            # 감독자/worker 세션 실행 중단 (finally에서 완전 정리됨)
            if self._supervisor_session:
                await self._supervisor_session.kill()
            if self.session:
                await self.session.interrupt()

    def resume(self):
        """soft_stop으로 중단된 파이프라인을 이어서 실행.

        재개 조건:
        - status == "stopped" AND _soft_stop_flag == True (soft stop으로 중단)
        - session이 여전히 alive

        _step_log, pending_items, current_cycle, iteration은 보존하여 이어서 기록.
        ended_at, report, stop_type은 재실행 후 새로 생성.
        세션 바인딩(pipeline_id/pipeline_role)은 soft_stop 시 이미 유지되어 있음.
        """
        if self.status != "stopped":
            raise RuntimeError(
                f"재개 불가: status={self.status!r} — stopped 상태여야 합니다")
        if not self._soft_stop_flag:
            raise RuntimeError(
                "hard stop으로 중단된 파이프라인은 재개할 수 없습니다 (soft_stop만 재개 가능)")
        if not self.session or not self.session.alive:
            raise RuntimeError(
                "worker 세션이 종료되어 재개할 수 없습니다")

        # 플래그 리셋
        self._stop_flag = False
        self._soft_stop_flag = False
        self.stop_type = None
        self.status = "running"
        self.ended_at = None
        self.report = None

        # resume 메타데이터 갱신
        self._resume_count += 1
        self._resumed_from_step = len(self._step_log)

        # 세션 바인딩 재확인 (soft stop 시 유지되었어야 하나 방어적으로 재설정)
        self.session.pipeline_id = self.id
        self.session.pipeline_role = "worker"
        self.session.save_state()

        # CLI 모드: 감독자 세션 재생성 (이전 감독자는 stop() 시 kill됨)
        if self.mode == "cli":
            try:
                self._create_supervisor_session()
            except Exception:
                # 롤백: resumable 상태로 복원
                self.status = "stopped"
                self._soft_stop_flag = True
                raise

        self._add_history(
            "system",
            f"▶ 재개: 사이클 {self.current_cycle}, "
            f"반복 {self.iteration + 1}부터 이어서 실행합니다.")
        self._task = asyncio.create_task(self._run_loop())

    def _add_history(self, role: str, content: str):
        self.history.append({
            "role": role,
            "content": content,
            "iteration": self.iteration,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })

    # ─── 리포트 보조 메서드 ─────────────────────────────

    def _log_step(self, step_idx: int, status: str, output: str, *,
                  start: float, error: Optional[str] = None):
        """단계별 실행 결과 기록."""
        elapsed = time.time() - start
        preview = output[:200].replace("\n", " ").strip() if output else ""
        self._step_log.append({
            "step_idx": step_idx,
            "cycle": self.current_cycle,
            "iteration": self.iteration,
            "started_at": datetime.fromtimestamp(start).isoformat(),
            "ended_at": datetime.now().isoformat(),
            "duration_seconds": round(elapsed, 1),
            "status": status,           # completed | failed | aborted
            "output_preview": preview,
            "error": error,
        })

    def _collect_pending_question(self, step_idx: int):
        """세션의 pending_question을 pending_items.questions에 수집."""
        pq = self.session.pending_question if self.session else None
        if not pq or not pq.get("questions"):
            return
        for q in pq["questions"]:
            self.pending_items["questions"].append({
                "step": step_idx,
                "cycle": self.current_cycle,
                "iteration": self.iteration,
                "content": q.get("question", ""),
                "options": q.get("options", []),
                "severity": "medium",
                "note": "감독자(supervisor)가 다음 단계에서 자동 답변 예정",
            })

    def _parse_suggestions_from_output(self, step_idx: int, text: str,
                                        source: str = "worker"):
        """supervisor/worker 출력에서 개선 제안 패턴을 감지하여 suggestions에 추가.

        source: "supervisor" | "worker" — 어느 쪽 출력에서 감지됐는지 기록.
        이미 수집된 content와 중복이면 건너뜀.
        """
        if not text:
            return
        seen = {s["content"] for s in self.pending_items["suggestions"]}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = _SUGGESTION_RE.match(line)
            if m:
                content = m.group(1).strip()
                if len(content) > 8 and content not in seen:
                    seen.add(content)
                    self.pending_items["suggestions"].append({
                        "step": step_idx,
                        "cycle": self.current_cycle,
                        "iteration": self.iteration,
                        "content": content[:300],
                        "priority": "low",
                        "source": source,
                    })

    def _parse_auto_decisions_from_output(self, step_idx: int, text: str):
        """supervisor 출력에서 자동 결정 패턴을 감지하여 auto_decisions에 추가.

        형식 예시:
          [결정] A 방안 선택 → 파일 덮어쓰기
          결정: 기존 파일 삭제 후 재생성
          자동으로 최신 버전 사용
        """
        if not text:
            return
        seen = {(d["description"], d["choice"]) for d in self.pending_items["auto_decisions"]}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = _AUTO_DECISION_RE.match(line)
            if m:
                content = m.group(1).strip()
                if len(content) <= 5:
                    continue
                # "설명 → 선택" 형식 파싱
                if " → " in content or " -> " in content:
                    sep = " → " if " → " in content else " -> "
                    desc, choice = content.split(sep, 1)
                    desc, choice = desc.strip(), choice.strip()
                else:
                    desc, choice = content, ""
                if (desc, choice) not in seen:
                    seen.add((desc, choice))
                    self.pending_items["auto_decisions"].append({
                        "step": step_idx,
                        "cycle": self.current_cycle,
                        "iteration": self.iteration,
                        "description": desc[:200],
                        "choice": choice[:200],
                        "alternatives": [],
                        "severity": "medium",
                        "source": "text_pattern",
                    })

    def _parse_questions_from_output(self, step_idx: int, text: str,
                                      source: str = "worker"):
        """worker/supervisor 출력에서 사용자 확인 요청 패턴을 감지하여 questions에 추가.

        AskUserQuestion 도구 이외의 자유 형식 텍스트 패턴 감지.
        형식 예시:
          확인 필요: 기존 파일을 삭제할까요?
          선택해 주세요: A 또는 B
          [질문] 어떤 방식으로 진행할까요?
        """
        if not text:
            return
        seen = {q["content"] for q in self.pending_items["questions"]}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = _QUESTION_RE.match(line)
            if m:
                content = m.group(1).strip()
                if len(content) > 5 and content not in seen:
                    seen.add(content)
                    self.pending_items["questions"].append({
                        "step": step_idx,
                        "cycle": self.current_cycle,
                        "iteration": self.iteration,
                        "content": content[:300],
                        "options": [],
                        "severity": "medium",
                        "note": f"{source} 출력 텍스트에서 감지",
                        "source": "text_pattern",
                    })

    def _record_auto_decision(self, step_idx: int, description: str,
                               choice: str, alternatives: Optional[list] = None,
                               severity: str = "low"):
        """시스템이 자동으로 내린 결정을 pending_items.auto_decisions에 기록."""
        self.pending_items["auto_decisions"].append({
            "step": step_idx,
            "cycle": self.current_cycle,
            "iteration": self.iteration,
            "description": description,
            "choice": choice,
            "alternatives": alternatives or [],
            "severity": severity,
        })

    def _save_report_log(self, text_summary: str) -> None:
        """text_summary를 data/logs/pipeline_{id}_{timestamp}.txt 파일로 저장."""
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pipeline_{self.id}_{ts}.txt"
            (LOGS_DIR / filename).write_text(text_summary, encoding="utf-8")
            logger.info("Pipeline report saved: %s", filename)
        except Exception as e:
            logger.warning("Failed to save pipeline report log: %s", e)

    def _generate_report(self) -> dict:
        """파이프라인 최종 리포트 생성 (완료/실패/중단 시 호출)."""
        steps = list(self._step_log)
        completed = [s for s in steps if s["status"] == "completed"]
        failed = [s for s in steps if s["status"] == "failed"]
        aborted = [s for s in steps if s["status"] == "aborted"]
        errors = [s["error"] for s in steps if s.get("error")]

        try:
            duration = round(
                (datetime.fromisoformat(self.ended_at) -
                 datetime.fromisoformat(self.started_at)).total_seconds(), 1
            ) if self.ended_at and self.started_at else 0.0
        except Exception:
            duration = 0.0

        clean_errors = [e for e in errors if e]
        text_summary = self._generate_text_summary(steps, duration, clean_errors)
        self._save_report_log(text_summary)
        return {
            "pipeline_id": self.id,
            "session_id": self.session.id if self.session else None,
            "goal": self.goal,
            "status": self.status,
            "stop_type": self.stop_type,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": duration,
            "pipeline_config": {
                "supervisor_model": self.supervisor_model,
                "mode": self.mode,
                "max_iterations": self.max_iterations,
                "max_cycles": self.max_cycles,
                "reached_cycle": self.current_cycle,
                "reached_iteration": self.iteration,
            },
            "steps": steps,
            "total_steps": len(steps),
            "completed_steps": len(completed),
            "failed_steps": len(failed),
            "aborted_steps": len(aborted),
            "errors": clean_errors,
            "pending_items": self.pending_items,
            "pending_items_count": {
                "questions": len(self.pending_items.get("questions", [])),
                "auto_decisions": len(self.pending_items.get("auto_decisions", [])),
                "suggestions": len(self.pending_items.get("suggestions", [])),
            },
            "resume_info": {
                "resume_count": self._resume_count,
                "resumed_from_step": self._resumed_from_step,
            } if self._resume_count > 0 else None,
            "summary": self.summary,
            "text_summary": text_summary,
        }

    def _generate_text_summary(self, steps: list, duration: float,
                                errors: list) -> str:
        """사람이 읽기 쉬운 리포트 텍스트 생성."""
        status_icon = {
            "completed": "✅", "failed": "❌", "stopped": "⏹", "running": "⏳",
        }.get(self.status, "?")
        stop_note = f" ({self.stop_type} stop)" if self.stop_type else ""

        resume_note = (
            f" | 재개된 파이프라인 ({self._resume_count}번 재개, "
            f"Step {self._resumed_from_step}부터)"
            if self._resume_count > 0 else ""
        )

        lines = [
            f"# Pipeline {self.id} 최종 리포트 {status_icon}{resume_note}",
            "",
            f"**목표:** {self.goal[:120]}{'...' if len(self.goal) > 120 else ''}",
            f"**상태:** {self.status}{stop_note}",
            f"**세션:** {self.session.id if self.session else '-'}",
            f"**시작:** {self.started_at or '-'}",
            f"**종료:** {self.ended_at or '-'}",
            f"**소요:** {_fmt_duration(duration)}",
            f"**설정:** {self.supervisor_model} / {self.mode} 모드 / "
            f"최대 {self.max_iterations}회×{self.max_cycles}사이클 "
            f"(실행: 사이클 {self.current_cycle} [{self._get_cycle_phase()}], 반복 {self.iteration})",
            "",
        ]

        if self.summary:
            lines += [f"**요약:** {self.summary}", ""]

        n_ok = len([s for s in steps if s["status"] == "completed"])
        n_fail = len([s for s in steps if s["status"] == "failed"])
        n_abort = len([s for s in steps if s["status"] == "aborted"])

        lines += [
            "## 실행 결과",
            f"| 구분 | 수 |",
            f"|------|---|",
            f"| ✅ 완료 | {n_ok} |",
            f"| ❌ 실패 | {n_fail} |",
            f"| ⏹ 중단 | {n_abort} |",
            f"| 합계 | {len(steps)} |",
            "",
        ]

        if steps:
            lines += ["## 단계별 상세", ""]
            for s in steps:
                icon = {"completed": "✅", "failed": "❌", "aborted": "⏹"}.get(s["status"], "?")
                ci = f"C{s['cycle']}-I{s['iteration']}"
                dur = f"{s.get('duration_seconds', 0):.1f}초"
                preview = s.get("output_preview", "")[:80]
                lines.append(f"- {icon} Step {s['step_idx']} ({ci}, {dur}): {preview}")
                if s.get("error"):
                    lines.append(f"  ⚠ {s['error'][:150]}")
            lines.append("")

        if errors:
            lines += ["## 오류 목록", ""]
            for e in errors[:10]:
                lines.append(f"- {e[:200]}")
            lines.append("")

        # 사이클 반성 요약 섹션
        if self.cycle_summaries:
            lines += [f"## 사이클 반성 요약 ({len(self.cycle_summaries)}개 사이클)", ""]
            for cs in self.cycle_summaries:
                lines.append(
                    f"### 사이클 {cs['cycle']} → {cs['next_phase']} "
                    f"[{cs['phase']} 완료]")
                # 반성 텍스트의 앞 300자만 요약
                reflection_preview = cs.get("reflection", "")[:300].replace("\n", " ")
                lines.append(reflection_preview)
                lines.append("")

        questions = self.pending_items.get("questions", [])
        auto_decs = self.pending_items.get("auto_decisions", [])
        suggestions = self.pending_items.get("suggestions", [])

        if questions or auto_decs or suggestions:
            total_n = len(questions) + len(auto_decs) + len(suggestions)
            lines += [f"## 후속 조치 항목 (총 {total_n}건)", ""]
            if questions:
                lines.append(f"### ❓ 질문/확인 사항 ({len(questions)}건)")
                for q in questions:
                    sev = q.get("severity", "medium").upper()
                    lines.append(
                        f"- [{sev}] Step {q.get('step', '?')}: {q.get('content', '')[:120]}")
                    if q.get("options"):
                        opts = ", ".join(o.get("label", "") for o in q["options"])
                        lines.append(f"  옵션: {opts}")
                lines.append("")
            if auto_decs:
                lines.append(f"### 🔧 자동 결정 사항 ({len(auto_decs)}건)")
                for d in auto_decs:
                    sev = d.get("severity", "low").upper()
                    lines.append(
                        f"- [{sev}] Step {d.get('step', '?')}: "
                        f"{d.get('description', '')} → {d.get('choice', '')}")
                lines.append("")
            if suggestions:
                lines.append(f"### 💡 개선 제안 ({len(suggestions)}건)")
                for sg in suggestions:
                    pri = sg.get("priority", "low").upper()
                    step_ref = f"Step {sg['step']}: " if sg.get("step") else ""
                    lines.append(f"- [{pri}] {step_ref}{sg.get('content', '')[:120]}")
                lines.append("")

        return "\n".join(lines)

    # ─── Cycle 고급 기능 ────────────────────────────────────

    def _get_cycle_phase(self, cycle: Optional[int] = None) -> str:
        """사이클 번호 → 현재 페이즈 이름 (순환)."""
        c = (cycle if cycle is not None else self.current_cycle)
        return self.cycle_phases[(c - 1) % len(self.cycle_phases)]

    def confirm_cycle(self) -> bool:
        """Checkpoint 대기 중인 사이클을 확인하고 재개.

        Returns True if confirmation was accepted, False if pipeline is not paused.
        """
        if self._cycle_confirm_event and not self._cycle_confirm_event.is_set():
            self._cycle_confirm_event.set()
            return True
        return False

    async def _run_cycle_reflection(self, completed_cycle: int,
                                     last_output: str, step: int) -> str:
        """사이클 종료 시 감독자에게 반성/재계획을 요청하고 결과를 반환.

        결과는 cycle_summaries에 저장되고, 다음 사이클의 초기 컨텍스트로 주입된다.
        실패 시 빈 문자열 반환 (non-fatal).
        """
        completed_phase = self._get_cycle_phase(completed_cycle)
        next_cycle = completed_cycle + 1
        next_phase = self._get_cycle_phase(next_cycle)

        reflection_prompt = _CYCLE_REFLECTION_SYSTEM.format(
            goal=self.goal,
            completed_cycle=completed_cycle,
            max_cycles=self.max_cycles,
            completed_phase=completed_phase,
            iterations=self.iteration,
            last_output_tail=_tail_lines(last_output, 1500),
            next_cycle=next_cycle,
            next_phase=next_phase,
        )

        self._add_history("system",
            f"📝 사이클 {completed_cycle} 반성 중 (→ 사이클 {next_cycle} 준비)...")

        try:
            if self.mode == "api":
                reflection = await self._call_reflection_api(reflection_prompt)
            else:
                reflection = await self._call_reflection_cli(reflection_prompt)
        except Exception as e:
            self._add_history("system", f"⚠ 반성 생성 실패 (non-fatal): {e}")
            return last_output  # 실패 시 기존 컨텍스트 유지

        summary = {
            "cycle": completed_cycle,
            "phase": completed_phase,
            "next_phase": next_phase,
            "reflection": reflection,
            "timestamp": datetime.now().isoformat(),
        }
        self.cycle_summaries.append(summary)
        self._add_history("system",
            f"✅ 사이클 {completed_cycle} 반성 완료 → 다음 페이즈: {next_phase}")

        # 반성 결과를 다음 사이클 컨텍스트로 패키징
        return (
            f"=== 사이클 {completed_cycle} 반성 결과 ===\n"
            f"{reflection}\n"
            f"=== 위 결과를 바탕으로 사이클 {next_cycle} ({next_phase})을 시작하세요 ==="
        )

    async def _call_reflection_api(self, prompt: str) -> str:
        """API 모드: 반성 프롬프트를 단독 호출."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic 패키지 미설치")

        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 미설정")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=self.supervisor_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        if not response.content:
            raise RuntimeError("빈 응답")
        return response.content[0].text.strip()

    async def _call_reflection_cli(self, prompt: str) -> str:
        """CLI 모드: 감독자 CLI 세션에 반성 프롬프트 전송."""
        sv = self._supervisor_session
        if not sv or not sv.alive:
            raise RuntimeError("감독자 세션 없음")
        await sv.send_prompt(prompt)
        result = await self._wait_for_session(sv, timeout=120)
        if result in ("[시간 초과]", "[파이프라인 중단됨]"):
            raise RuntimeError(f"반성 CLI 시간 초과: {result}")
        return self._extract_cli_response(sv)

    async def _wait_for_session(self, session: ClaudeSession,
                                 timeout: int = TASK_TIMEOUTS["default"]) -> str:
        """특정 CLI 세션이 busy=False가 될 때까지 대기

        _output_version 기반으로 새 출력이 나오고 + busy가 끝날 때까지 대기.
        기존 방식(busy=True 감지 5초 대기)은 CLI 시작이 느릴 때 race condition 발생.
        """
        start = time.time()
        version_before = session._output_version

        # Phase 1: busy=True 또는 새 출력이 나올 때까지 대기 (최대 30초)
        for _ in range(60):
            if self._stop_flag:
                return "[파이프라인 중단됨]"
            if not session.alive:
                return "[세션 종료]"
            if session.busy or session._output_version != version_before:
                break
            await asyncio.sleep(0.5)

        # Phase 2: busy=False가 될 때까지 대기 (30초마다 heartbeat 로그)
        _last_hb = time.time()
        while session.busy:
            if self._stop_flag:
                return "[파이프라인 중단됨]"
            if not session.alive:
                return "[세션 종료]"
            elapsed = time.time() - start
            if elapsed > timeout:
                self._add_history("system", f"세션 실행 시간 초과 ({timeout}초)")
                return "[시간 초과]"
            if time.time() - _last_hb >= 30:
                _last_hb = time.time()
                self._add_history("system", f"⏳ 작업 진행 중... ({int(elapsed)}s / {timeout}s)")
            await asyncio.sleep(1)

        output = session.get_formatted_output(100)

        # pending_question이 있으면 감독자가 인식할 수 있도록 구조화된 블록 추가
        pq = session.pending_question
        if pq and pq.get("questions"):
            lines = ["\n\n══ AskUserQuestion 대기 중 ══"]
            for q in pq["questions"]:
                lines.append(f"Q: {q.get('question', '')}")
                opts = q.get("options", [])
                if opts:
                    opt_str = " / ".join(
                        f"{chr(65+i)}) {o.get('label','')}: {o.get('description','')}"
                        for i, o in enumerate(opts)
                    )
                    lines.append(f"옵션: {opt_str}")
            lines.append("══════════════════════════════")
            lines.append("※ 위 질문에 직접 답변하세요. 다음 작업 지시가 아닙니다.")
            output += "\n".join(lines)

        return output

    # ─── 메인 루프 ─────────────────────────────────────

    async def _run_loop(self):
        """메인 파이프라인 루프 — mode에 따라 감독자 방식 분기, 자동 사이클"""
        last_output = ""
        _step = 0  # 전역 누적 스텝 (DB checkpoint 키)
        _step_start: float = 0.0
        try:
            while not self._stop_flag:
                # 사이클 내 max_iterations 도달 → 자동 사이클 전환
                if self.iteration >= self.max_iterations:
                    if self.current_cycle < self.max_cycles:
                        old_cycle = self.current_cycle

                        # Option A: 사이클 종료 반성/재계획
                        if self.cycle_reflection:
                            last_output = await self._run_cycle_reflection(
                                old_cycle, last_output, _step)
                            if self._stop_flag:
                                return

                        self.current_cycle += 1
                        self.iteration = 0
                        self._supervisor_retries = 0

                        # Option B: Human checkpoint — 사이클 시작 전 사용자 확인 대기
                        if self.cycle_checkpoint:
                            self._cycle_confirm_event = asyncio.Event()
                            self.status = "paused"
                            self._add_history("system",
                                f"⏸ Cycle checkpoint: 사이클 {self.current_cycle}/{self.max_cycles} "
                                f"({self._get_cycle_phase()}) 시작 전 확인을 기다립니다. "
                                f"POST /api/pipelines/{self.id}/cycle-confirm 으로 승인하세요.")
                            try:
                                await asyncio.wait_for(
                                    self._cycle_confirm_event.wait(), timeout=300)
                                self.status = "running"
                                self._add_history("system",
                                    f"▶ 사이클 {self.current_cycle} 승인됨, 계속 진행합니다.")
                            except asyncio.TimeoutError:
                                self.status = "stopped"
                                self.summary = (
                                    f"Cycle checkpoint 시간 초과 (5분) — "
                                    f"사이클 {self.current_cycle} 시작 전 중단")
                                self._add_history("system", self.summary)
                                return

                        # Option C: Phase 태그 history 기록
                        phase = self._get_cycle_phase()
                        self._add_history("system",
                            f"=== 사이클 {self.current_cycle}/{self.max_cycles} 시작 "
                            f"[페이즈: {phase}] ===")
                        self._record_auto_decision(
                            _step,
                            f"사이클 {old_cycle} 최대 반복({self.max_iterations}) 도달",
                            f"사이클 {self.current_cycle} 자동 시작 (페이즈: {phase})",
                            severity="low",
                        )
                        continue
                    else:
                        total = (self.current_cycle - 1) * self.max_iterations + self.iteration
                        self.status = "completed"
                        self.summary = f"최대 사이클({self.max_cycles})×반복({self.max_iterations})={total}회 도달하여 종료"
                        self._add_history("system", self.summary)
                        mark_complete(self.id)
                        return

                self.iteration += 1
                _step = (self.current_cycle - 1) * self.max_iterations + self.iteration
                update_stage(self.id, _step, "running")
                _step_start = time.time()

                # 1. 감독자 호출
                try:
                    supervisor_response = await self._call_supervisor(last_output)
                except Exception as e:
                    # CLI 모드: 감독자 hang/crash 시 자동 복구 시도
                    if self.mode == "cli" and self._supervisor_retries < self._max_supervisor_retries:
                        self._supervisor_retries += 1
                        self._add_history("system",
                            f"감독자 CLI 오류 → 복구 시도 ({self._supervisor_retries}/{self._max_supervisor_retries}): {str(e)}")
                        self._record_auto_decision(
                            _step,
                            f"감독자 CLI 오류: {str(e)[:80]}",
                            "감독자 세션 재생성",
                            severity="medium",
                        )
                        await self._recover_supervisor()
                        continue  # 같은 iteration 재시도
                    self._log_step(_step, "failed", "", start=_step_start, error=f"감독자 호출 실패: {str(e)}")
                    self._add_history("error", f"감독자 호출 실패: {str(e)}")
                    self.status = "failed"
                    mark_failed(self.id, _step, str(e))
                    return

                # 성공 시 재시도 카운터 리셋
                self._supervisor_retries = 0
                self._add_history("supervisor", supervisor_response)

                # 2. DONE 체크 — 사이클 제한 없이 즉시 수락
                # 시스템 프롬프트가 조기 DONE을 금지하므로 코드 레벨 차단 불필요.
                # 이중 차단 시 슈퍼바이저가 실제 완료 후에도 루프를 탈출하지 못하는 버그 발생.
                if "PIPELINE_DONE:" in supervisor_response:
                    idx = supervisor_response.index("PIPELINE_DONE:")
                    self.summary = supervisor_response[idx + len("PIPELINE_DONE:"):].strip()
                    self.status = "completed"
                    self._add_history("system", f"파이프라인 완료 (사이클 {self.current_cycle}/{self.max_cycles}): {self.summary}")
                    mark_complete(self.id)
                    return

                # 3. 작업자 CLI에 프롬프트 전달 (선택한 세션에 직접)
                await self.session.send_prompt(supervisor_response)

                # 4. 작업자 CLI 완료 대기
                last_output = await self._wait_for_session(self.session)

                # 단계 상태 판정 및 로깅
                if last_output == "[세션 종료]":
                    self._log_step(_step, "failed", last_output, start=_step_start,
                                   error="worker 세션 비정상 종료")
                    self.status = "failed"
                    self._add_history("error", "worker 세션(pw-*)이 예기치 않게 종료되었습니다.")
                    mark_failed(self.id, _step, "worker 세션 비정상 종료")
                    return
                elif last_output == "[파이프라인 중단됨]":
                    self._log_step(_step, "aborted", last_output, start=_step_start)
                elif last_output == "[시간 초과]":
                    self._log_step(_step, "failed", last_output, start=_step_start, error="시간 초과")
                else:
                    self._log_step(_step, "completed", last_output, start=_step_start)

                # pending_question 수집 (감독자가 다음 단계에서 자동 답변할 예정)
                self._collect_pending_question(_step)
                # supervisor 출력 파싱: 개선 제안, 자동 결정
                self._parse_suggestions_from_output(_step, supervisor_response, source="supervisor")
                self._parse_auto_decisions_from_output(_step, supervisor_response)
                # worker 출력 파싱: 개선 제안, 사용자 질문 (텍스트 패턴)
                self._parse_suggestions_from_output(_step, last_output, source="worker")
                self._parse_questions_from_output(_step, last_output, source="worker")

                self._add_history("cli_result", last_output)
                save_checkpoint(self.id, _step, {
                    "output": last_output,
                    "cycle": self.current_cycle,
                    "iteration": self.iteration,
                })

                # soft stop: 현재 단계 완료 후 중단
                if self._soft_stop_flag:
                    self.status = "stopped"
                    self._add_history("system",
                        "⏸ Soft stop: 현재 단계 완료 후 중단되었습니다. "
                        "세션은 resumable 상태로 보존됩니다.")
                    return

        except asyncio.CancelledError:
            # 외부 태스크 취소(서버 shutdown 등) — finally 정리 후 재전파
            self.status = "stopped"
            raise
        except Exception as e:
            # stop()이 이미 status="stopped"를 설정한 경우 덮어쓰지 않음
            if not self._stop_flag:
                self.status = "failed"
                mark_failed(self.id, _step, str(e))
            self._add_history("error", f"파이프라인 오류: {str(e)}")
        finally:
            # 종료 시각 기록 + 최종 리포트 생성
            self.ended_at = datetime.now().isoformat()
            self.report = self._generate_report()

            # 감독자 CLI 세션 정리 (kill + 디스크에서 삭제)
            if self._supervisor_session:
                await self._supervisor_session.kill()
                self._supervisor_session.delete_state()

            # soft stop: 세션 바인딩 유지 (resumable), hard stop/complete/fail: 해제
            if self.session:
                if not self._soft_stop_flag:
                    self.session.pipeline_id = None
                    self.session.pipeline_role = None
                self.session.save_state()

    # ─── 감독자 호출 (모드별 분기) ─────────────────────

    async def _call_supervisor(self, last_output: str) -> str:
        if self.mode == "api":
            return await self._call_supervisor_api(last_output)
        else:
            return await self._call_supervisor_cli(last_output)

    async def _call_supervisor_api(self, last_output: str) -> str:
        """Anthropic API 비동기 호출"""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic 패키지 미설치. pip install anthropic")

        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 환경변수 미설정")
        client = anthropic.AsyncAnthropic(api_key=api_key)

        system_prompt = _SUPERVISOR_SYSTEM.format(
            goal=self.goal,
            cycle=self.current_cycle,
            max_cycles=self.max_cycles,
            cycle_phase=self._get_cycle_phase(),
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            work_dir=self.session.work_dir,
        )

        messages = self._build_messages(last_output)

        response = await client.messages.create(
            model=self.supervisor_model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )

        if not response.content:
            raise RuntimeError("Anthropic API가 빈 content를 반환했습니다")
        return response.content[0].text.strip()

    async def _call_supervisor_cli(self, last_output: str) -> str:
        """감독자 CLI 세션에 프롬프트 전달 → 결과 파싱"""
        sv = self._supervisor_session
        if not sv or not sv.alive:
            raise RuntimeError("감독자 CLI 세션이 종료됨")

        # 감독자에게 보낼 메시지 구성
        system_context = _SUPERVISOR_SYSTEM.format(
            goal=self.goal,
            cycle=self.current_cycle,
            max_cycles=self.max_cycles,
            cycle_phase=self._get_cycle_phase(),
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            work_dir=self.session.work_dir,
        )

        # pending_question 여부 확인 (출력 내 AskUserQuestion 블록 감지)
        _has_question = (
            self.session.pending_question is not None
            and bool(self.session.pending_question.get("questions"))
        )
        _task_hint = (
            "⚠️ 작업자가 질문에 대한 답변을 기다리고 있습니다. "
            "출력 끝의 AskUserQuestion 블록을 읽고 직접 답변하세요. 다음 작업 지시가 아닌 답변만 출력하세요."
            if _has_question else
            "위 결과를 분석하고, 다음에 작업자 CLI에 보낼 프롬프트를 생성하세요. 프롬프트 본문만 출력하세요."
        )

        if last_output:
            prompt = (
                f"{system_context}\n\n"
                f"---\n[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n"
                f"작업자 CLI 실행 결과 (최근):\n"
                f"{_tail_lines(last_output)}\n\n"
                f"{_task_hint}"
            )
        else:
            prompt = (
                f"{system_context}\n\n"
                f"---\n[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n"
                f"목표를 달성하기 위한 첫 번째 작업자 CLI 프롬프트를 생성하세요. "
                f"프롬프트 본문만 출력하세요."
            )

        # 감독자 CLI에 전송
        await sv.send_prompt(prompt)

        # 감독자 CLI 완료 대기 (타임아웃 3분 — 감독자는 빨리 끝나야 함)
        result = await self._wait_for_session(sv, timeout=180)

        if result in ("[시간 초과]", "[파이프라인 중단됨]"):
            raise RuntimeError(f"감독자 CLI: {result}")

        # 결과에서 실제 응답 텍스트 추출
        # CLI output에는 시스템 메시지(">>> ...", "--- Done ---" 등)가 포함됨
        # assistant 타입의 마지막 출력만 추출
        return self._extract_cli_response(sv)

    def _extract_cli_response(self, sv: ClaudeSession) -> str:
        """감독자 CLI 세션의 출력에서 assistant 응답만 추출

        도구 호출 XML이 텍스트로 출력된 경우 필터링.
        """
        response_parts = []
        for entry in reversed(sv.output_lines):
            if entry["type"] in ("assistant", "result"):
                response_parts.insert(0, entry["text"])
            elif entry["type"] == "system" and ">>>" in entry["text"]:
                break  # 이전 프롬프트 경계에서 중단

        text = "\n".join(response_parts).strip()

        # function_calls XML 블록 제거
        text = re.sub(
            r'<function_calls>.*?</function_calls>',
            '', text, flags=re.DOTALL
        )
        # 잔여 XML 태그 제거
        text = re.sub(
            r'<function_response>.*?</function_response>',
            '', text, flags=re.DOTALL
        )
        # invoke 태그 등 잔여물
        text = re.sub(r'</?(?:invoke|parameter|function_calls|function_response)[^>]*>', '', text)

        text = text.strip()
        if not text:
            raise RuntimeError("감독자 CLI에서 응답을 추출하지 못함")
        return text

    async def _recover_supervisor(self):
        """감독자 CLI 세션 복구 — kill 후 재생성"""
        self._add_history("system", "감독자 CLI 세션 복구 중...")
        if self._supervisor_session:
            await self._supervisor_session.kill()
        self._create_supervisor_session()
        self._add_history("system", "감독자 CLI 세션 복구 완료")

    # ─── 유틸리티 ──────────────────────────────────────

    def _build_messages(self, last_output: str) -> list[dict]:
        """API 모드용 대화 히스토리 구성"""
        messages = []
        recent = [h for h in self.history if h["role"] in ("supervisor", "cli_result")]
        for h in recent[-10:]:
            if h["role"] == "supervisor":
                messages.append({"role": "assistant", "content": h["content"]})
            elif h["role"] == "cli_result":
                messages.append({"role": "user", "content": h["content"]})

        _has_question = (
            self.session.pending_question is not None
            and bool(self.session.pending_question.get("questions"))
        )
        _question_hint = (
            "\n\n⚠️ 작업자가 질문에 대한 답변을 기다리고 있습니다. "
            "출력 끝의 AskUserQuestion 블록을 읽고 직접 답변하세요."
            if _has_question else ""
        )

        if last_output:
            user_msg = (
                f"[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n"
                f"CLI 실행 결과:\n{_tail_lines(last_output)}{_question_hint}"
            )
        else:
            user_msg = f"[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n목표를 달성하기 위한 첫 번째 프롬프트를 생성하세요."
        messages.append({"role": "user", "content": user_msg})
        return messages

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session.id if self.session else None,
            "goal": self.goal,
            "supervisor_model": self.supervisor_model,
            "mode": self.mode,
            "status": self.status,
            "stop_type": self.stop_type,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "current_cycle": self.current_cycle,
            "max_cycles": self.max_cycles,
            "current_phase": self._get_cycle_phase(),
            "cycle_phases": self.cycle_phases,
            "cycle_reflection": self.cycle_reflection,
            "cycle_checkpoint": self.cycle_checkpoint,
            "cycle_summaries_count": len(self.cycle_summaries),
            "total_iterations": (self.current_cycle - 1) * self.max_iterations + self.iteration,
            "summary": self.summary,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "history": self.history[-50:],
            "supervisor_retries": self._supervisor_retries,
            "pending_items_count": {
                "questions": len(self.pending_items.get("questions", [])),
                "auto_decisions": len(self.pending_items.get("auto_decisions", [])),
                "suggestions": len(self.pending_items.get("suggestions", [])),
            },
            "report": self.report,
        }


# ─── 계획 수립 엔진 (Plan Phase) ──────────────────────────────────────────────────


class PlanPhase:
    """목표 분석 → 질의 생성 → 답변 수집 → 실행계획 생성 → 승인 → 파이프라인 실행

    상태 머신:
    questions_generating → questions_ready → plan_generating → plan_ready → approved / error
    """

    def __init__(self, source_session: ClaudeSession, goal: str,
                 mode: str = "cli", supervisor_model: str = "sonnet"):
        self.id = f"plan-{str(uuid.uuid4())[:8]}"
        self._source_session = source_session
        self.goal = goal
        self.mode = mode
        self.supervisor_model = supervisor_model
        self.status = "idle"
        self.questions: list[dict] = []
        self.answers: dict[str, str] = {}
        self.plan_text = ""
        self.error = ""
        self.pipeline_id: str | None = None
        self.created_at = datetime.now().isoformat()
        self._task: Optional[asyncio.Task] = None
        self._supervisor_session: Optional[ClaudeSession] = None
        self.qa_round: int = 0
        self.max_rounds: int = 3
        self.qa_history: list[dict] = []
        self.plan_draft: str | None = None
        self.user_requested_more: bool = False
        self.rejection_rounds: int = 0
        self.max_rejection_rounds: int = 1

    def start(self):
        """질문 생성 시작"""
        self.status = "questions_generating"
        self._task = asyncio.create_task(self._generate_questions())

    async def submit_answers(self, answers: dict[str, str]):
        """답변 제출 → 다회차 판단 후 추가 질의 또는 플랜 생성"""
        self.answers = answers
        self.status = "processing_answers"
        self._task = asyncio.create_task(self._process_answers())

    async def _process_answers(self):
        """답변 처리 — 라운드 카운트, 요약, 추가 질의 여부 결정 후 라우팅"""
        self.qa_round += 1

        # 현재 라운드 Q&A 요약 (실패해도 빈 문자열로 폴백)
        summary = await self._summarize_qa_round()
        self.qa_history.append({"round": self.qa_round, "summary": summary})

        # 사용자 명시 요청 확인 및 플랜 컨텍스트에서 제거
        user_more = bool(self.answers.pop("_request_more", None))
        if user_more:
            self.user_requested_more = True

        # 추가 질의 필요 여부 판단
        need_more = self.user_requested_more
        if not need_more:
            self.status = "checking_need_more"
            need_more = await self._check_need_more_questions()

        if need_more and self.qa_round < self.max_rounds:
            self.status = "questions_generating"
            await self._generate_questions()
            return

        self.status = "plan_generating"
        await self._generate_plan()

    async def approve(self, plan_text: str | None,
                      max_iterations: int, max_cycles: int) -> str:
        """계획 승인 → PipelineRunner 생성/시작"""
        if plan_text is not None:
            self.plan_text = plan_text

        # enriched goal 구성
        qa_text = "\n".join(
            f"Q: {self._find_question_text(qid)}\nA: {ans}"
            for qid, ans in self.answers.items()
        )
        if self.qa_history:
            history_text = "\n".join(
                f"[라운드 {h['round']}] {h['summary']}"
                for h in self.qa_history
            )
            enriched_goal = (
                f"## 원래 목표\n{self.goal}\n\n"
                f"## 명확화 Q&A (전체 라운드 요약)\n{history_text}\n\n"
                f"## 최종 라운드 상세 Q&A\n{qa_text}\n\n"
                f"## 실행 계획\n{self.plan_text}"
            )
        else:
            enriched_goal = (
                f"## 원래 목표\n{self.goal}\n\n"
                f"## 명확화 Q&A\n{qa_text}\n\n"
                f"## 실행 계획\n{self.plan_text}"
            )

        session = self._source_session
        runner = PipelineRunner(session, enriched_goal, self.supervisor_model,
                                max_iterations, self.mode, max_cycles)
        _state.pipelines[runner.id] = runner
        try:
            runner.start()
        except Exception:
            _state.pipelines.pop(runner.id, None)
            raise
        self.pipeline_id = runner.id
        self.status = "approved"
        return runner.id

    async def regenerate(self):
        """계획 재생성"""
        self.status = "plan_generating"
        self._task = asyncio.create_task(self._generate_plan())

    async def reject_and_refine(self, feedback: str):
        """플랜 거부 + 피드백 기반 추가 질의 (최대 1회)

        rejection_rounds >= max_rejection_rounds이면 거부 불가.
        피드백을 qa_history에 추가 후 _generate_questions() 재호출.
        """
        if self.rejection_rounds >= self.max_rejection_rounds:
            raise RuntimeError(
                f"최대 거부 횟수({self.max_rejection_rounds})를 초과했습니다."
            )
        self.rejection_rounds += 1
        self.qa_history.append({
            "round": f"reject-{self.rejection_rounds}",
            "summary": f"[플랜 거부 피드백] {feedback}",
        })
        self.status = "questions_generating"
        self._task = asyncio.create_task(self._generate_questions())

    # ─── LLM 호출 ──────────────────────────────────────

    async def _generate_questions(self):
        """LLM으로 질의 생성 — qa_round > 0이면 이전 라운드 요약 포함"""
        try:
            project_context = self._get_project_context()
            system_prompt = _PLAN_QUESTIONS_SYSTEM.format(
                goal=self.goal,
                work_dir=self._source_session.work_dir,
                project_context=project_context,
            )
            if self.qa_round > 0 and self.qa_history:
                history_text = "\n".join(
                    f"[라운드 {h['round']}] {h['summary']}" for h in self.qa_history
                )
                user_content = (
                    f"다음 목표에 대해 명확화 질문을 생성해주세요:\n{self.goal}\n\n"
                    f"이전 질의 라운드 요약:\n{history_text}\n\n"
                    f"이미 답변된 내용은 다시 묻지 말고, 아직 불명확한 부분에 대해서만 추가 질문을 생성하세요."
                )
            else:
                user_content = f"다음 목표에 대해 명확화 질문을 생성해주세요:\n{self.goal}"
            messages = [{"role": "user", "content": user_content}]
            raw = await self._call_llm(system_prompt, messages)
            self.questions = self._parse_questions_json(raw)
            self.status = "questions_ready"
        except Exception as e:
            self.error = str(e)
            self.status = "error"
        finally:
            await self._cleanup_supervisor()

    async def _generate_plan(self):
        """LLM으로 실행계획 생성 — 전체 qa_history + 최종 라운드 answers 포함"""
        try:
            project_context = self._get_project_context()
            # qa_history 전체 요약 + 마지막 라운드 상세 answers
            qa_parts = []
            for h in self.qa_history:
                qa_parts.append(f"[라운드 {h['round']} 요약] {h['summary']}")
            if self.answers:
                current_qa = "\n".join(
                    f"Q: {self._find_question_text(qid)}\nA: {ans}"
                    for qid, ans in self.answers.items()
                )
                qa_parts.append(f"[최종 라운드 상세]\n{current_qa}")
            qa_summary = "\n\n".join(qa_parts) if qa_parts else "(Q&A 없음)"
            system_prompt = _PLAN_GENERATION_SYSTEM.format(
                goal=self.goal,
                work_dir=self._source_session.work_dir,
                project_context=project_context,
                qa_summary=qa_summary,
            )
            messages = [{"role": "user", "content": "목표와 Q&A를 바탕으로 실행 계획을 생성해주세요."}]
            raw = await self._call_llm(system_prompt, messages)
            self.plan_text = raw.strip()
            self.plan_draft = self.plan_text
            self.status = "plan_ready"
        except Exception as e:
            self.error = str(e)
            self.status = "error"
        finally:
            await self._cleanup_supervisor()

    async def _summarize_qa_round(self) -> str:
        """현재 라운드 Q&A를 1-2문장으로 요약. 실패 시 빈 문자열 반환."""
        try:
            qa_text = "\n".join(
                f"Q: {self._find_question_text(qid)}\nA: {ans}"
                for qid, ans in self.answers.items()
            )
            if not qa_text.strip():
                return ""
            system_prompt = "당신은 요약 전문가입니다. 오직 요약 텍스트만 출력하세요. 마크다운, 머리말, 꼬리말 없이 순수 텍스트만 출력하세요."
            messages = [{"role": "user", "content": f"다음 Q&A를 1-2문장으로 요약하세요:\n{qa_text}"}]
            return await self._call_llm(system_prompt, messages)
        except Exception:
            return ""
        finally:
            await self._cleanup_supervisor()

    async def _check_need_more_questions(self) -> bool:
        """AI 판단: 추가 질의 라운드 필요 여부. 실패 시 False 반환 (플랜 생성으로 진행)."""
        try:
            history_text = "\n".join(
                f"[라운드 {h['round']}] {h['summary']}" for h in self.qa_history
            ) or "(요약 없음)"
            system_prompt = "당신은 소프트웨어 프로젝트 분석가입니다. 오직 JSON만 출력하세요. 다른 텍스트는 절대 출력하지 마세요."
            messages = [{
                "role": "user",
                "content": (
                    f"원래 목표: {self.goal}\n\n"
                    f"지금까지의 Q&A 요약:\n{history_text}\n\n"
                    f"이 정보로 구체적인 실행 계획을 세우기에 충분한가? "
                    f"정보가 부족하면 추가 질문이 필요하다. "
                    f'JSON으로만 응답하라: {{"need_more": bool, "reason": "str"}}'
                ),
            }]
            raw = await self._call_llm(system_prompt, messages)
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                data = json.loads(match.group())
                return bool(data.get("need_more", False))
            return False
        except Exception:
            return False
        finally:
            await self._cleanup_supervisor()

    async def _call_llm(self, system_prompt: str, messages: list[dict]) -> str:
        """API/CLI 모드 분기 LLM 호출"""
        if self.mode == "api":
            return await self._call_llm_api(system_prompt, messages)
        else:
            return await self._call_llm_cli(system_prompt, messages)

    async def _call_llm_api(self, system_prompt: str, messages: list[dict]) -> str:
        """Anthropic API 비동기 호출"""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic 패키지 미설치. pip install anthropic")

        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 환경변수 미설정")
        client = anthropic.AsyncAnthropic(api_key=api_key)

        response = await client.messages.create(
            model=self.supervisor_model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        if not response.content:
            raise RuntimeError("Anthropic API가 빈 content를 반환했습니다")
        return response.content[0].text.strip()

    async def _call_llm_cli(self, system_prompt: str, messages: list[dict]) -> str:
        """CLI 세션으로 LLM 호출"""
        if not _state.CLAUDE_EXE:
            raise RuntimeError("Claude CLI를 찾을 수 없습니다")

        sid = f"plan-sv-{self.id}"
        sv = ClaudeSession(sid, self._source_session.work_dir, self.supervisor_model,
                           no_tools=True,
                           skip_permissions=self._source_session.skip_permissions)
        sv.save_state = lambda: None
        sv.start_worker()
        self._supervisor_session = sv

        prompt = f"{system_prompt}\n\n---\n{messages[0]['content']}"
        await sv.send_prompt(prompt)

        # 완료 대기 — Phase 1: 세션 시작 감지, Phase 2: 완료 대기
        start_wait = time.time()
        version_before = sv._output_version

        # Phase 1: busy=True 또는 새 출력이 나올 때까지 최대 30초 대기 (CLI 시작 지연 대비)
        for _ in range(60):
            if sv.busy or sv._output_version != version_before:
                break
            await asyncio.sleep(0.5)

        # Phase 2: busy=False가 될 때까지 최대 3분 대기
        while sv.busy:
            if time.time() - start_wait > 180:
                break
            await asyncio.sleep(1)

        # 응답 추출: 마지막 프롬프트 경계(>>> 시스템 메시지) 이후의 assistant/result만 수집
        response_parts = []
        for entry in reversed(sv.output_lines):
            if entry["type"] in ("assistant", "result"):
                response_parts.insert(0, entry["text"])
            elif entry["type"] == "system" and ">>>" in entry["text"]:
                break  # 프롬프트 전송 경계 — 이전 출력 제외
        result = "\n".join(response_parts).strip()

        if not result:
            raise RuntimeError("CLI 감독자가 빈 응답을 반환했습니다")
        return result

    async def _cleanup_supervisor(self):
        """CLI 감독자 세션 정리"""
        if self._supervisor_session:
            sv = self._supervisor_session
            self._supervisor_session = None  # 중복 정리 방지
            try:
                await sv.kill()
            except Exception:
                pass

    # ─── 유틸리티 ──────────────────────────────────────

    def _get_project_context(self) -> str:
        """CLAUDE.md 등에서 프로젝트 컨텍스트 추출"""
        context_parts = []
        work_dir = self._source_session.work_dir
        for name in ["CLAUDE.md", "README.md"]:
            fpath = os.path.join(work_dir, name)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read(3000)
                    context_parts.append(f"=== {name} ===\n{content}")
                except Exception:
                    pass
        return "\n\n".join(context_parts) if context_parts else "(프로젝트 컨텍스트 없음)"

    def _find_question_text(self, qid: str) -> str:
        """질문 ID로 질문 텍스트 찾기"""
        for q in self.questions:
            if q.get("id") == qid:
                return q.get("question", qid)
        return qid

    def _parse_questions_json(self, raw: str) -> list[dict]:
        """LLM 응답에서 질문 JSON 파싱"""
        # markdown code fence 제거
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
        text = match.group(1) if match else raw

        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError:
            # 한 번 더 시도: 앞뒤 텍스트 제거 후 JSON 블록만 추출
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise RuntimeError(f"JSON 파싱 실패: {text[:200]}")

        questions = data.get("questions", [])
        for i, q in enumerate(questions):
            q.setdefault("id", f"q{i+1}")
            q.setdefault("question", "")
            q.setdefault("why", "")
            q.setdefault("options", [])
        return questions

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self._source_session.id,
            "goal": self.goal,
            "mode": self.mode,
            "supervisor_model": self.supervisor_model,
            "status": self.status,
            "questions": self.questions,
            "answers": self.answers,
            "plan_text": self.plan_text,
            "error": self.error,
            "pipeline_id": self.pipeline_id,
            "created_at": self.created_at,
            "qa_round": self.qa_round,
            "max_rounds": self.max_rounds,
            "qa_history": self.qa_history,
            "rejection_rounds": self.rejection_rounds,
            "max_rejection_rounds": self.max_rejection_rounds,
        }

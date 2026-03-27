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

## 현재 상태
- 사이클: {cycle}/{max_cycles}
- 반복: {iteration}/{max_iterations}
- 작업자 CLI 작업 디렉토리: {work_dir}"""


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
                 mode: str = "api", max_cycles: int = 100):
        self.id = str(uuid.uuid4())[:8]
        self.session = source_session  # 선택한 세션을 직접 worker로 사용 (pw- 미생성)
        self.goal = goal
        self.supervisor_model = supervisor_model
        self.max_iterations = max_iterations
        self.max_cycles = max_cycles
        self.current_cycle = 1
        self.mode = mode                # "api" | "cli"
        self.iteration = 0
        self.status = "idle"            # idle | running | completed | failed | stopped
        self.history: list[dict] = []
        self.summary = ""
        self.created_at = datetime.now().isoformat()
        self._task: Optional[asyncio.Task] = None
        self._stop_flag = False
        # CLI 감독자 전용
        self._supervisor_session: Optional[ClaudeSession] = None
        self._supervisor_retries = 0
        self._max_supervisor_retries = 3

    def start(self):
        self.status = "running"
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

    async def stop(self):
        self._stop_flag = True
        self.status = "stopped"
        self._add_history("system", "파이프라인이 사용자에 의해 중단되었습니다.")
        # 감독자/worker 세션 실행 중단 (finally에서 완전 정리됨)
        if self._supervisor_session:
            await self._supervisor_session.kill()
        if self.session:
            await self.session.interrupt()

    def _add_history(self, role: str, content: str):
        self.history.append({
            "role": role,
            "content": content,
            "iteration": self.iteration,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })

    async def _wait_for_session(self, session: ClaudeSession,
                                 timeout: int = 600) -> str:
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

        # Phase 2: busy=False가 될 때까지 대기
        while session.busy:
            if self._stop_flag:
                return "[파이프라인 중단됨]"
            if not session.alive:
                return "[세션 종료]"
            if time.time() - start > timeout:
                self._add_history("system", f"세션 실행 시간 초과 ({timeout}초)")
                return "[시간 초과]"
            await asyncio.sleep(1)

        return session.get_formatted_output(100)

    # ─── 메인 루프 ─────────────────────────────────────

    async def _run_loop(self):
        """메인 파이프라인 루프 — mode에 따라 감독자 방식 분기, 자동 사이클"""
        last_output = ""
        _step = 0  # 전역 누적 스텝 (DB checkpoint 키)
        try:
            while not self._stop_flag:
                # 사이클 내 max_iterations 도달 → 자동 사이클 전환
                if self.iteration >= self.max_iterations:
                    if self.current_cycle < self.max_cycles:
                        self.current_cycle += 1
                        self.iteration = 0
                        self._supervisor_retries = 0
                        self._add_history("system",
                            f"=== 사이클 {self.current_cycle}/{self.max_cycles} 시작 ===")
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

                # 1. 감독자 호출
                try:
                    supervisor_response = await self._call_supervisor(last_output)
                except Exception as e:
                    # CLI 모드: 감독자 hang/crash 시 자동 복구 시도
                    if self.mode == "cli" and self._supervisor_retries < self._max_supervisor_retries:
                        self._supervisor_retries += 1
                        self._add_history("system",
                            f"감독자 CLI 오류 → 복구 시도 ({self._supervisor_retries}/{self._max_supervisor_retries}): {str(e)}")
                        await self._recover_supervisor()
                        continue  # 같은 iteration 재시도
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
                # worker 세션이 비정상 종료된 경우 파이프라인 실패 처리
                if last_output == "[세션 종료]":
                    self.status = "failed"
                    self._add_history("error", "worker 세션(pw-*)이 예기치 않게 종료되었습니다.")
                    mark_failed(self.id, _step, "worker 세션 비정상 종료")
                    return
                self._add_history("cli_result", last_output)
                save_checkpoint(self.id, _step, {
                    "output": last_output,
                    "cycle": self.current_cycle,
                    "iteration": self.iteration,
                })

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
            # 감독자 CLI 세션 정리 (kill + 디스크에서 삭제)
            if self._supervisor_session:
                await self._supervisor_session.kill()
                self._supervisor_session.delete_state()

            # 세션의 파이프라인 바인딩 해제 (세션 자체는 유지)
            if self.session:
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
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            work_dir=self.session.work_dir,
        )

        if last_output:
            prompt = (
                f"{system_context}\n\n"
                f"---\n[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\n"
                f"작업자 CLI 실행 결과 (최근):\n"
                f"{_tail_lines(last_output)}\n\n"
                f"위 결과를 분석하고, 다음에 작업자 CLI에 보낼 프롬프트를 생성하세요. "
                f"프롬프트 본문만 출력하세요."
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

        if last_output:
            user_msg = f"[사이클 {self.current_cycle}/{self.max_cycles} | 반복 {self.iteration}/{self.max_iterations}]\nCLI 실행 결과:\n{_tail_lines(last_output)}"
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
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "current_cycle": self.current_cycle,
            "max_cycles": self.max_cycles,
            "total_iterations": (self.current_cycle - 1) * self.max_iterations + self.iteration,
            "summary": self.summary,
            "created_at": self.created_at,
            "history": self.history[-50:],
            "supervisor_retries": self._supervisor_retries,
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

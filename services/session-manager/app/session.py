"""
app/session.py — ClaudeSession class, rate limiting, and session cleanup.
"""

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

import app.state as _state
from app.models import (
    APP_DIR, LOGS_DIR, SESSIONS_DIR,
    SESSION_TTL_SECONDS, CLEANUP_INTERVAL, CMP_SESSION_TTL_SECONDS,
    MAX_SESSION_CREATES_PER_MINUTE, MAX_SESSIONS_PER_CLIENT,
)
from app.pipeline_store import (
    create_run, update_stage, save_checkpoint,
    mark_complete, mark_failed, mark_interrupted,
)

logger = logging.getLogger("session-manager.session")


async def _cleanup_dead_sessions():
    """비활성 세션 자동 정리 태스크"""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        now = datetime.now()
        to_remove = []
        for sid, session in _state.sessions.items():
            # supervisor 세션이 sessions dict에 남아있으면 즉시 정리 (TTL 무시)
            if session.pipeline_role == "supervisor":
                to_remove.append(sid)
                continue

            try:
                created = datetime.fromisoformat(session.created_at)
                elapsed = (now - created).total_seconds()
            except Exception:
                continue

            if not session.alive and not session.busy:
                # 죽은 세션 — 일반/cmp TTL 적용
                ttl = CMP_SESSION_TTL_SECONDS if sid.startswith("cmp-") else SESSION_TTL_SECONDS
                if elapsed > ttl:
                    to_remove.append(sid)
            elif sid.startswith("cmp-") and not session.busy and session._queue.empty():
                # cmp-* 세션: alive이지만 비교 완료(idle) → 단기 TTL 적용
                if elapsed > CMP_SESSION_TTL_SECONDS:
                    to_remove.append(sid)
            elif (sid.startswith("pw-") and not session.pipeline_id
                  and not session.busy and session._queue.empty()):
                # pw-* 세션: 파이프라인 종료 후 바인딩 해제된 idle worker → 단기 TTL 적용
                if elapsed > CMP_SESSION_TTL_SECONDS:
                    to_remove.append(sid)

        for sid in to_remove:
            s = _state.sessions.pop(sid, None)
            if s is None:
                continue
            try:
                if s.alive:
                    await s.kill()
                s.delete_state()
            except Exception as e:
                logger.error("[cleanup] error removing session %s: %s", sid, e)
        if to_remove:
            logger.info("[cleanup] %d dead session(s) removed", len(to_remove))

        # 완료된 파이프라인도 정리
        pipe_remove = []
        for pid, pipe in list(_state.pipelines.items()):
            if pipe.status in ("completed", "failed", "stopped"):
                try:
                    created = datetime.fromisoformat(pipe.created_at)
                    if (now - created).total_seconds() > SESSION_TTL_SECONDS:
                        pipe_remove.append(pid)
                except Exception:
                    pass
        for pid in pipe_remove:
            _state.pipelines.pop(pid, None)
        if pipe_remove:
            logger.info("[cleanup] %d finished pipeline(s) removed", len(pipe_remove))

        # 죽은 Shell 세션 정리
        shell_remove = [sid for sid, sh in _state.shell_sessions.items() if not sh.alive]
        for sid in shell_remove:
            _state.shell_sessions.pop(sid, None)
        if shell_remove:
            logger.info("[cleanup] %d dead shell(s) removed", len(shell_remove))

        # _session_create_log 오래된 IP 항목 정리 (1시간 이상 된 타임스탬프 제거)
        old_threshold = time.time() - 3600
        stale_ips = []
        for ip, timestamps in _state._session_create_log.items():
            _state._session_create_log[ip] = [t for t in timestamps if t > old_threshold]
            if not _state._session_create_log[ip]:
                stale_ips.append(ip)
        for ip in stale_ips:
            del _state._session_create_log[ip]




def _check_rate_limit(client_ip: str):
    """세션 생성 rate limit 체크. 초과 시 HTTPException(429) raise."""
    now = time.time()

    # 1) 분당 생성 수 제한
    timestamps = _state._session_create_log.get(client_ip, [])
    timestamps = [t for t in timestamps if now - t < 60]  # 최근 1분만 유지
    if len(timestamps) >= MAX_SESSION_CREATES_PER_MINUTE:
        raise HTTPException(status_code=429, detail=f"분당 최대 {MAX_SESSION_CREATES_PER_MINUTE}개 세션 생성 제한 초과")

    # 2) 활성 Claude 세션 수 제한 (Shell은 별도 — CLI 프로세스 부하가 다름)
    active_count = sum(1 for s in _state.sessions.values() if s.alive)
    if active_count >= MAX_SESSIONS_PER_CLIENT:
        raise HTTPException(status_code=429, detail=f"최대 활성 세션 수 초과 ({MAX_SESSIONS_PER_CLIENT}개, 현재 {active_count}개 활성)")

    # 기록 추가
    timestamps.append(now)
    _state._session_create_log[client_ip] = timestamps



# ─── 세션 클래스 ─────────────────────────────────────────────────────────────────


class ClaudeSession:
    """Claude CLI 세션 관리 (print 모드 + stream-json)

    각 세션은 작업 큐를 가지며, 프롬프트를 보내면 Claude CLI를
    -p --output-format stream-json 모드로 실행하여 결과를 스트리밍합니다.
    여러 프롬프트를 보내면 순차적으로 처리됩니다.
    --continue 옵션으로 이전 대화를 이어갑니다.
    """

    def __init__(self, session_id: str, work_dir: str, model: str = "",
                 no_tools: bool = False, skip_permissions: bool = False,
                 mcp_config: str = "", ephemeral: bool = False):
        self.id = session_id
        self.name = f"claude-{session_id}"
        self.work_dir = work_dir
        self.model = model  # e.g. "opus", "sonnet", "" = CLI default
        self.no_tools = no_tools  # True면 --tools "" (감독자용)
        self.skip_permissions = skip_permissions  # True면 --dangerously-skip-permissions
        self.mcp_config = mcp_config  # MCP 설정 파일 경로
        self.ephemeral = ephemeral  # True면 디스크 저장/로그 기록 없는 임시 세션
        self.created_at = datetime.now().isoformat()
        self.alive = True
        self.busy = False  # 현재 Claude 실행 중인지
        self.process: Optional[asyncio.subprocess.Process] = None
        self.output_lines: list[dict] = []  # {type, text, timestamp}
        self.max_lines = 5000
        self.session_uuid: Optional[str] = None  # Claude 세션 ID (--continue 용)
        self.log_filename = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_path = LOGS_DIR / self.log_filename
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._output_version = 0  # WebSocket 변경 감지용
        self.pending_question: Optional[dict] = None  # AskUserQuestion 대기 중
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.pipeline_id: Optional[str] = None       # 바인딩된 파이프라인 ID
        self.pipeline_role: Optional[str] = None      # None | "worker" | "supervisor"
        self._output_event: asyncio.Event = asyncio.Event()  # WS 이벤트 기반 wake-up

    @property
    def _save_path(self) -> Path:
        return SESSIONS_DIR / f"{self.id}.json"

    def save_state(self):
        """세션 상태를 디스크에 저장 (output_lines, session_uuid 등)
        ephemeral 세션은 디스크에 저장하지 않는다."""
        if self.ephemeral:
            return
        try:
            state = {
                "id": self.id,
                "name": self.name,
                "work_dir": self.work_dir,
                "model": self.model,
                "skip_permissions": self.skip_permissions,
                "mcp_config": self.mcp_config,
                "session_uuid": self.session_uuid,
                "created_at": self.created_at,
                "output_lines": self.output_lines[-500:],  # 최근 500줄만 저장
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "pipeline_id": self.pipeline_id,
                "pipeline_role": self.pipeline_role,
            }
            self._save_path.write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass  # 저장 실패가 메인 동작 방해 금지

    @classmethod
    def load_state(cls, session_id: str) -> "ClaudeSession":
        """디스크에서 세션 복원"""
        path = SESSIONS_DIR / f"{session_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        session = cls(
            data["id"], data["work_dir"], data.get("model", ""),
            skip_permissions=data.get("skip_permissions", False),
            mcp_config=data.get("mcp_config", ""),
        )
        session.name = data.get("name", session.name)
        session.session_uuid = data.get("session_uuid")
        session.output_lines = data.get("output_lines", [])
        session.created_at = data.get("created_at", session.created_at)
        session.total_input_tokens = data.get("total_input_tokens", 0)
        session.total_output_tokens = data.get("total_output_tokens", 0)
        session.pipeline_id = data.get("pipeline_id")
        session.pipeline_role = data.get("pipeline_role")
        session._output_version = len(session.output_lines)
        return session

    def delete_state(self):
        """디스크에서 세션 상태 삭제"""
        try:
            self._save_path.unlink(missing_ok=True)
        except Exception:
            pass

    def start_worker(self):
        self._worker_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """큐에서 프롬프트를 꺼내 순차적으로 실행"""
        while self.alive:
            try:
                prompt = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            self.busy = True
            self.pending_question = None
            self._append_output("system", f">>> {prompt}")
            try:
                await self._run_claude(prompt)
            except Exception as e:
                self._append_output("error", f"예상치 못한 오류: {str(e)}")
            finally:
                # busy 상태가 절대 stuck 되지 않도록 보장
                self.busy = False
                self.process = None

    async def _run_claude(self, prompt: str, _retry_without_model: bool = False, _uuid_reset: bool = False):
        """Claude CLI를 print 모드로 실행하여 결과 스트리밍

        안정성 개선:
        - stdout/stderr 동시 읽기 (deadlock 방지)
        - readline에 타임아웃 적용 (무한 대기 방지)
        - process.wait()에 타임아웃 적용
        - 프로세스 확실한 정리 보장
        """
        if not _state.CLAUDE_EXE:
            self._append_output("error", "Claude CLI를 찾을 수 없습니다 (CLAUDE_EXE not set)")
            return

        use_model = self.model if not _retry_without_model else ""

        cmd = [_state.CLAUDE_EXE, "-p", "--output-format", "stream-json", "--verbose"]
        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        if self.no_tools:
            cmd.extend(["--tools", ""])

        if use_model:
            cmd.extend(["--model", use_model])

        if self.mcp_config:
            _mcp_path = Path(self.mcp_config).resolve()
            _allowed_mcp = (APP_DIR, Path.home() / ".claude")
            if not any(_mcp_path.is_relative_to(base) for base in _allowed_mcp):
                raise RuntimeError(f"mcp_config 경로가 허용 범위 밖입니다: {_mcp_path}")
            cmd.extend(["--mcp-config", str(_mcp_path)])

        # 이전 세션 이어가기
        if self.session_uuid:
            cmd.extend(["--resume", self.session_uuid])

        cmd.append(prompt)

        stderr_lines = []

        try:
            # 중첩 세션 감지 방지: CLAUDECODE 환경변수 제거
            # ANTHROPIC_API_KEY 제거 → CLI가 OAuth 토큰(Pro/Max 구독) 사용
            env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "ANTHROPIC_API_KEY", "LLM_API_KEY")}
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path(self.work_dir).expanduser()) if self.work_dir not in (".",) else None,
                env=env,
                limit=10 * 1024 * 1024,  # 10MB - 큰 출력 처리
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )

            all_output = []

            async def _drain_stderr():
                """stderr를 별도로 비동기 읽기 (deadlock 방지)"""
                try:
                    while True:
                        line = await self.process.stderr.readline()
                        if not line:
                            break
                        decoded = line.decode("utf-8", errors="replace").strip()
                        if decoded:
                            stderr_lines.append(decoded)
                except Exception:
                    pass

            # stderr를 별도 태스크로 동시 읽기 시작
            stderr_task = asyncio.create_task(_drain_stderr())

            # stdout에서 stream-json 읽기 (타임아웃 적용)
            idle_timeout = 600  # 10분 무응답이면 포기
            while True:
                try:
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=idle_timeout
                    )
                except asyncio.TimeoutError:
                    self._append_output("error",
                        f"Claude CLI가 {idle_timeout}초 동안 응답이 없어 중단합니다.")
                    await self._force_kill_process()
                    break

                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                all_output.append(decoded)
                try:
                    event = json.loads(decoded)
                    if isinstance(event, dict):
                        self._handle_stream_event(event)
                    else:
                        self._append_output("text", decoded)
                except json.JSONDecodeError:
                    self._append_output("text", decoded)

            # stderr 태스크 완료 대기 (최대 5초)
            try:
                await asyncio.wait_for(stderr_task, timeout=5)
            except asyncio.TimeoutError:
                stderr_task.cancel()

            # 프로세스 종료 대기 (최대 10초)
            if self.process and self.process.returncode is None:
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    self._append_output("system", "프로세스 종료 대기 시간 초과 → 강제 종료")
                    await self._force_kill_process()

            stderr_text = "\n".join(stderr_lines)

            # 모델 에러 감지 → 기본 모델로 자동 재시도
            combined = stderr_text + " " + " ".join(all_output)
            model_error = (
                "issue with the selected model" in combined
                or "model not found" in combined.lower()
                or "you may not have access" in combined
            )

            if model_error and use_model and not _retry_without_model:
                self._append_output("system",
                    f"모델 '{use_model}' 사용 불가 (구독 플랜 미지원 또는 모델명 오류) → 기본 모델로 전환합니다...")
                # 이후 프롬프트에서도 같은 에러 반복 방지 — 모델 설정 영구 변경
                self.model = ""
                self.process = None
                await self._run_claude(prompt, _retry_without_model=True)
                self.save_state()
                return

            # 만료/손상된 세션 UUID 감지 → 자동 리셋 후 재시도
            # --resume {uuid}로 호출했는데 출력이 전혀 없으면 세션이 만료된 것
            # _uuid_reset=True를 전달해 재귀 깊이를 1로 제한 (무한루프 방지)
            if self.session_uuid and not all_output and not _retry_without_model and not _uuid_reset:
                self._append_output("system",
                    f"세션 UUID 만료 감지 (출력 없음) → UUID 리셋 후 재시도합니다...")
                self.session_uuid = None
                self.process = None
                self.save_state()
                await self._run_claude(prompt, _uuid_reset=True)
                return

            if stderr_text:
                self._append_output("error", stderr_text)

        except asyncio.CancelledError:
            # 태스크 취소 시 프로세스 정리
            await self._force_kill_process()
            raise
        except Exception as e:
            self._append_output("error", f"실행 오류: {str(e)}")
            await self._force_kill_process()
        finally:
            self.process = None

    async def _force_kill_process(self):
        """프로세스를 확실하게 종료"""
        if not self.process:
            return
        try:
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    self.process.kill()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        pass  # 최후의 수단 - OS가 정리하도록
        except ProcessLookupError:
            pass  # 이미 종료됨

    def _handle_stream_event(self, event: dict):
        """stream-json 이벤트 처리"""
        if not isinstance(event, dict):
            return
        etype = event.get("type", "")

        if etype == "system":
            # 세션 ID 캡처
            sid = event.get("session_id")
            if sid:
                self.session_uuid = sid
            return

        if etype == "assistant":
            msg = event.get("message", {})
            content_blocks = msg.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    self._append_output("assistant", block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    # 간결하게 표시
                    if tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        self._append_output("tool", f"[Bash] {cmd}")
                    elif tool_name in ("Read", "Write", "Edit"):
                        path = tool_input.get("file_path", "")
                        self._append_output("tool", f"[{tool_name}] {path}")
                    elif tool_name == "AskUserQuestion":
                        # 질문 내용을 풀어서 표시 + 클릭 가능 옵션 저장
                        questions = tool_input.get("questions", [])
                        self.pending_question = tool_input
                        for q in questions:
                            qtext = q.get("question", "")
                            self._append_output("tool", f"[질문] {qtext}")
                            options = q.get("options", [])
                            for i, opt in enumerate(options):
                                label = opt.get("label", "")
                                desc = opt.get("description", "")
                                self._append_output("tool", f"  {i+1}. {label} — {desc}")
                    elif tool_name == "Glob":
                        pattern = tool_input.get("pattern", "")
                        self._append_output("tool", f"[Glob] {pattern}")
                    elif tool_name == "Grep":
                        pattern = tool_input.get("pattern", "")
                        self._append_output("tool", f"[Grep] {pattern}")
                    elif tool_name == "Agent":
                        desc = tool_input.get("description", "")
                        self._append_output("tool", f"[Agent] {desc}")
                    elif tool_name == "TodoWrite":
                        todos = tool_input.get("todos", [])
                        items = ", ".join(t.get("content", "")[:40] for t in todos[:5])
                        self._append_output("tool", f"[TodoWrite] {items}")
                    else:
                        self._append_output("tool", f"[{tool_name}]")
            return

        if etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    # 마지막 라인이 스트리밍 중이면 이어붙이기
                    if self.output_lines and self.output_lines[-1].get("streaming"):
                        self.output_lines[-1]["text"] += text
                        self._output_version += 1
                        self._output_event.set()  # WebSocket 즉시 전달
                    else:
                        self._append_output("assistant", text, streaming=True)
            return

        if etype == "content_block_stop":
            # 스트리밍 완료
            if self.output_lines and self.output_lines[-1].get("streaming"):
                self.output_lines[-1]["streaming"] = False
                self._output_version += 1
                self._output_event.set()  # WebSocket 즉시 전달
            return

        if etype == "result":
            # 최종 결과
            result_text = event.get("result", "")
            sid = event.get("session_id")
            if sid:
                self.session_uuid = sid
            # 토큰 사용량 추적
            usage = event.get("usage", {})
            if usage:
                self.total_input_tokens += usage.get("input_tokens", 0)
                self.total_output_tokens += usage.get("output_tokens", 0)
            if result_text and not any(l["text"] == result_text for l in self.output_lines[-5:]):
                self._append_output("result", result_text)
            self._append_output("system", "--- Done ---")
            self.save_state()  # 실행 완료 시 상태 저장
            return

    def _append_output(self, otype: str, text: str, streaming: bool = False):
        """출력 라인 추가"""
        entry = {
            "type": otype,
            "text": text,
            "time": datetime.now().strftime("%H:%M:%S"),
            "streaming": streaming,
        }
        self.output_lines.append(entry)

        if len(self.output_lines) > self.max_lines:
            self.output_lines = self.output_lines[-self.max_lines:]

        self._output_version += 1
        self._output_event.set()  # WS 핸들러 즉시 wake-up

        # 로그 파일 기록 (ephemeral 세션은 로그 미생성)
        if not self.ephemeral:
            try:
                _LOG_MAX = 10 * 1024 * 1024  # 10MB
                if self.log_path.exists() and self.log_path.stat().st_size >= _LOG_MAX:
                    rotated = self.log_path.with_suffix(".log.1")
                    self.log_path.replace(rotated)
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{entry['time']}] [{otype}] {text}\n")
            except Exception:
                pass

    async def send_prompt(self, prompt: str):
        """프롬프트를 큐에 추가"""
        if not self.alive:
            raise RuntimeError(f"세션 {self.id}가 종료된 상태입니다")
        await self._queue.put(prompt)

    async def interrupt(self):
        """현재 실행 중인 프로세스 중단"""
        if self.process and self.process.returncode is None:
            self._append_output("system", "--- Interrupting ---")
            try:
                if sys.platform == "win32":
                    self.process.terminate()
                else:
                    self.process.send_signal(signal.SIGINT)
                # 프로세스 종료 대기
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.process.kill()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=3)
                    except asyncio.TimeoutError:
                        pass
            except ProcessLookupError:
                pass  # 이미 종료됨
            self._append_output("system", "--- Interrupted ---")

    async def kill(self):
        """세션 종료"""
        self.alive = False
        await self._force_kill_process()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        self.busy = False
        self._output_event.set()  # 대기 중인 WebSocket 핸들러를 즉시 깨워 종료 감지

    def get_formatted_output(self, lines: int = 200) -> str:
        """포맷된 출력 텍스트"""
        recent = self.output_lines[-lines:]
        parts = []
        for entry in recent:
            t = entry["time"]
            tp = entry["type"]
            text = entry["text"]
            if tp == "system":
                parts.append(f"\n{text}\n")
            elif tp == "assistant" or tp == "result":
                parts.append(text)
            elif tp == "tool":
                parts.append(f"\n  {text}\n")
            elif tp == "error":
                parts.append(f"\n[ERROR] {text}\n")
            else:
                parts.append(text)
        return "".join(parts)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "work_dir": self.work_dir,
            "model": self.model,
            "created_at": self.created_at,
            "alive": self.alive,
            "busy": self.busy,
            "log_file": self.log_filename,
            "has_session": self.session_uuid is not None,
            "queue_size": self._queue.qsize(),
            "skip_permissions": self.skip_permissions,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "pipeline_id": self.pipeline_id,
            "pipeline_role": self.pipeline_role,
            "ephemeral": self.ephemeral,
        }

    def export_markdown(self) -> str:
        """대화 내역을 Markdown 형태로 내보내기"""
        lines = [f"# {self.name}", f"- Created: {self.created_at}",
                 f"- Model: {self.model or 'default'}",
                 f"- Working Dir: {self.work_dir}",
                 f"- Tokens: {self.total_input_tokens:,} in / {self.total_output_tokens:,} out",
                 "", "---", ""]
        for entry in self.output_lines:
            t = entry.get("time", "")
            tp = entry.get("type", "")
            text = entry.get("text", "")
            if tp == "system":
                lines.append(f"\n**{text}**\n")
            elif tp == "assistant" or tp == "result":
                lines.append(text)
            elif tp == "tool":
                lines.append(f"\n`{text}`\n")
            elif tp == "error":
                lines.append(f"\n> **ERROR:** {text}\n")
        return "\n".join(lines)



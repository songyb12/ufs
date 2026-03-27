"""
tests/test_plan_phase.py

PlanPhase 다회차 질의 로직 단위 테스트:
  1. test_single_round_no_more_needed — AI 추가 질의 불필요 판단 시 1라운드 후 플랜 생성
  2. test_ai_requests_more_questions — AI 추가 질의 필요 판단 시 2라운드 진행
  3. test_user_requests_more — 사용자 _request_more로 추가 질의 요청
  4. test_max_rounds_enforced — max_rounds 도달 시 강제 플랜 생성
  5. test_qa_history_accumulates — qa_history에 라운드별 요약 누적 확인
  6. test_to_dict_includes_new_fields — to_dict에 qa_round/max_rounds/qa_history 포함 확인

실행:
    .venv/Scripts/pytest tests/test_plan_phase.py -v
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.pipeline import PlanPhase


# ════════════════════════════════════════════════════════════════════════════════
# 공통 헬퍼
# ════════════════════════════════════════════════════════════════════════════════

def _make_session() -> MagicMock:
    """테스트용 ClaudeSession 목 생성"""
    session = MagicMock()
    session.id = "test-session"
    session.work_dir = "."
    session.skip_permissions = False
    return session


def _make_phase(max_rounds: int = 3, mode: str = "api") -> PlanPhase:
    """기본 PlanPhase 인스턴스 생성 (LLM 호출 없이)"""
    session = _make_session()
    phase = PlanPhase(session, "테스트 목표", mode, "sonnet")
    phase.max_rounds = max_rounds
    phase.questions = [
        {"id": "q1", "question": "질문1", "why": "이유1", "options": []},
    ]
    return phase


def _patch_llm_methods(phase: PlanPhase,
                       summarize_return=None,
                       check_more_side_effect=None,
                       check_more_return: bool = False) -> None:
    """LLM 호출 메서드 전체를 목으로 교체 (실제 API 호출 방지)"""
    phase._summarize_qa_round = AsyncMock(return_value=summarize_return or "요약")
    if check_more_side_effect is not None:
        phase._check_need_more_questions = AsyncMock(side_effect=check_more_side_effect)
    else:
        phase._check_need_more_questions = AsyncMock(return_value=check_more_return)
    phase._generate_questions = AsyncMock()
    phase._generate_plan = AsyncMock()


async def _submit_and_wait(phase: PlanPhase, answers: dict) -> None:
    """submit_answers 호출 후 백그라운드 태스크 완료까지 대기"""
    await phase.submit_answers(answers)
    if phase._task:
        await phase._task


# ════════════════════════════════════════════════════════════════════════════════
# 테스트 1: AI가 추가 질의 불필요 판단 → 1라운드 후 플랜 생성
# ════════════════════════════════════════════════════════════════════════════════

class TestSingleRoundNoMoreNeeded:

    def test_status_becomes_plan_generating(self):
        """AI need_more=False → submit_answers 후 plan_generating으로 전환"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, summarize_return="요약", check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1"})

            assert phase.status == "plan_generating"

        asyncio.run(_run())

    def test_qa_round_incremented_to_one(self):
        """1라운드 완료 후 qa_round == 1"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1"})

            assert phase.qa_round == 1

        asyncio.run(_run())

    def test_qa_history_has_one_entry(self):
        """1라운드 완료 후 qa_history 길이 == 1, 내용 확인"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, summarize_return="1라운드 요약", check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1"})

            assert len(phase.qa_history) == 1
            assert phase.qa_history[0]["round"] == 1
            assert phase.qa_history[0]["summary"] == "1라운드 요약"

        asyncio.run(_run())

    def test_generate_plan_called_once(self):
        """plan_generating 경로: _generate_plan이 정확히 1회 호출되어야 한다"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1"})

            phase._generate_plan.assert_called_once()
            phase._generate_questions.assert_not_called()

        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 테스트 2: AI가 추가 질의 필요 판단 → 2라운드 진행
# ════════════════════════════════════════════════════════════════════════════════

class TestAiRequestsMoreQuestions:

    def test_status_becomes_questions_generating(self):
        """AI need_more=True → 첫 submit 후 questions_generating으로 전환"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_side_effect=[True, False])

            await _submit_and_wait(phase, {"q1": "답변1"})

            assert phase.status == "questions_generating"

        asyncio.run(_run())

    def test_qa_round_is_one_after_first_submission(self):
        """첫 번째 제출 후 qa_round == 1"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_side_effect=[True, False])

            await _submit_and_wait(phase, {"q1": "답변1"})

            assert phase.qa_round == 1

        asyncio.run(_run())

    def test_generate_questions_called_not_generate_plan(self):
        """need_more=True 경로: _generate_questions 호출, _generate_plan 미호출"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_side_effect=[True])

            await _submit_and_wait(phase, {"q1": "답변1"})

            phase._generate_questions.assert_called_once()
            phase._generate_plan.assert_not_called()

        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 테스트 3: 사용자가 _request_more로 추가 질의 명시 요청
# ════════════════════════════════════════════════════════════════════════════════

class TestUserRequestsMore:

    def test_status_becomes_questions_generating(self):
        """_request_more=true → questions_generating으로 전환"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1", "_request_more": "true"})

            assert phase.status == "questions_generating"

        asyncio.run(_run())

    def test_ai_check_is_skipped(self):
        """사용자 명시 요청 시 AI 판단(_check_need_more_questions) 호출되면 안 된다"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1", "_request_more": "true"})

            phase._check_need_more_questions.assert_not_called()

        asyncio.run(_run())

    def test_user_requested_more_flag_set(self):
        """_request_more 제출 후 user_requested_more == True"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1", "_request_more": "true"})

            assert phase.user_requested_more is True

        asyncio.run(_run())

    def test_request_more_key_removed_from_answers(self):
        """_request_more 키는 플랜 컨텍스트에서 제거되어야 한다 (LLM에 노출 방지)"""
        async def _run():
            phase = _make_phase()
            _patch_llm_methods(phase, check_more_return=False)

            await _submit_and_wait(phase, {"q1": "답변1", "_request_more": "true"})

            assert "_request_more" not in phase.answers

        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 테스트 4: max_rounds 도달 시 강제 플랜 생성
# ════════════════════════════════════════════════════════════════════════════════

class TestMaxRoundsEnforced:

    def test_request_more_ignored_at_max_rounds(self):
        """이미 max_rounds 완료 상태에서 _request_more 제출해도 plan_generating 전환"""
        async def _run():
            phase = _make_phase(max_rounds=2)
            phase.qa_round = 1  # 1라운드 이미 완료된 상태
            _patch_llm_methods(phase, check_more_return=True)

            # _request_more 포함해도 qa_round가 2로 올라가면 2 < 2 = False
            await _submit_and_wait(phase, {"q1": "답변2", "_request_more": "true"})

            assert phase.qa_round == 2
            assert phase.status == "plan_generating"

        asyncio.run(_run())

    def test_ai_need_more_ignored_at_max_rounds(self):
        """max_rounds 도달 시 AI가 need_more=True 반환해도 플랜 생성으로 진행"""
        async def _run():
            phase = _make_phase(max_rounds=1)
            # qa_round는 0, submit 후 1이 됨 → 1 < 1 = False
            _patch_llm_methods(phase, check_more_return=True)

            await _submit_and_wait(phase, {"q1": "답변1"})

            assert phase.qa_round == 1
            assert phase.status == "plan_generating"
            phase._generate_questions.assert_not_called()

        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 테스트 5: qa_history에 라운드별 요약이 누적되는지
# ════════════════════════════════════════════════════════════════════════════════

class TestQaHistoryAccumulates:

    def test_two_rounds_accumulate_correctly(self):
        """2라운드 진행 후 qa_history에 2개 항목, 각 round/summary 확인"""
        async def _run():
            phase = _make_phase()
            # 첫 요약: "라운드1 요약", 두번째: "라운드2 요약"
            phase._summarize_qa_round = AsyncMock(
                side_effect=["라운드1 요약", "라운드2 요약"]
            )
            # 첫 AI 판단: need_more=True → 2라운드, 두번째: False → 플랜
            phase._check_need_more_questions = AsyncMock(side_effect=[True, False])
            phase._generate_questions = AsyncMock()
            phase._generate_plan = AsyncMock()

            # 1라운드 제출
            await _submit_and_wait(phase, {"q1": "답변1"})
            assert len(phase.qa_history) == 1
            assert phase.qa_history[0] == {"round": 1, "summary": "라운드1 요약"}

            # 2라운드 제출
            phase.questions = [{"id": "q2", "question": "질문2", "why": "", "options": []}]
            await _submit_and_wait(phase, {"q2": "답변2"})
            assert len(phase.qa_history) == 2
            assert phase.qa_history[1] == {"round": 2, "summary": "라운드2 요약"}

        asyncio.run(_run())

    def test_round_numbers_are_sequential(self):
        """qa_history의 round 번호가 1, 2, ... 순서로 증가해야 한다"""
        async def _run():
            phase = _make_phase(max_rounds=3)
            phase._summarize_qa_round = AsyncMock(side_effect=["요약A", "요약B"])
            phase._check_need_more_questions = AsyncMock(side_effect=[True, False])
            phase._generate_questions = AsyncMock()
            phase._generate_plan = AsyncMock()

            await _submit_and_wait(phase, {"q1": "답변1"})
            await _submit_and_wait(phase, {"q1": "답변2"})

            rounds = [h["round"] for h in phase.qa_history]
            assert rounds == [1, 2]

        asyncio.run(_run())


# ════════════════════════════════════════════════════════════════════════════════
# 테스트 6: to_dict에 qa_round, max_rounds, qa_history 포함 확인
# ════════════════════════════════════════════════════════════════════════════════

class TestToDictIncludesNewFields:

    def test_new_fields_present_in_fresh_phase(self):
        """초기 PlanPhase의 to_dict에 3개 신규 필드가 존재해야 한다"""
        session = _make_session()
        phase = PlanPhase(session, "목표", "api", "sonnet")

        d = phase.to_dict()

        assert "qa_round" in d, "qa_round 필드 없음"
        assert "max_rounds" in d, "max_rounds 필드 없음"
        assert "qa_history" in d, "qa_history 필드 없음"

    def test_initial_values_are_correct(self):
        """초기 값: qa_round=0, max_rounds=3, qa_history=[]"""
        session = _make_session()
        phase = PlanPhase(session, "목표", "api", "sonnet")

        d = phase.to_dict()

        assert d["qa_round"] == 0
        assert d["max_rounds"] == 3
        assert d["qa_history"] == []

    def test_existing_fields_still_present(self):
        """기존 필드(id, goal, status, questions, answers 등)가 그대로 존재해야 한다"""
        session = _make_session()
        phase = PlanPhase(session, "목표", "api", "sonnet")

        d = phase.to_dict()

        for key in ("id", "session_id", "goal", "mode", "supervisor_model",
                    "status", "questions", "answers", "plan_text",
                    "error", "pipeline_id", "created_at"):
            assert key in d, f"기존 필드 '{key}' 누락"

    def test_values_reflect_mutations(self):
        """qa_round/qa_history 값이 변경 후 to_dict에 반영되어야 한다"""
        session = _make_session()
        phase = PlanPhase(session, "목표", "api", "sonnet")
        phase.qa_round = 2
        phase.qa_history = [
            {"round": 1, "summary": "첫 요약"},
            {"round": 2, "summary": "두 번째 요약"},
        ]

        d = phase.to_dict()

        assert d["qa_round"] == 2
        assert len(d["qa_history"]) == 2
        assert d["qa_history"][0]["summary"] == "첫 요약"

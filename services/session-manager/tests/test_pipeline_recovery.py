"""
tests/test_pipeline_recovery.py

app/pipeline_store.py 전체 함수 단위 테스트.

격리 전략
---------
pipeline_store._connect()는 매 호출마다 sqlite3.connect(_DB_PATH)를 실행하므로
:memory: 는 연결별로 독립된 DB가 생성되어 사용 불가.
→ 각 테스트마다 tmp_path 아래 임시 파일 DB를 사용하고
  monkeypatch로 _DB_PATH를 교체한 뒤 _init_db로 스키마 초기화.

실행:
    .venv/Scripts/pytest tests/test_pipeline_recovery.py -v
"""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import app.pipeline_store as ps


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """각 테스트에 격리된 임시 SQLite DB를 사용.

    _DB_PATH를 tmp_path 아래 파일로 교체하고 스키마를 초기화한다.
    yield 후 cleanup은 tmp_path가 자동 처리.
    """
    db_file = tmp_path / "test_pipeline.db"
    monkeypatch.setattr(ps, "_DB_PATH", db_file)

    # 모듈 로드 시 실행되는 init과 동일하게 스키마 생성
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    ps._init_db(conn)
    conn.close()

    yield db_file


def _raw_row(run_id: str) -> sqlite3.Row:
    """테스트에서 DB를 직접 조회 (검증용)."""
    conn = sqlite3.connect(str(ps._DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()
    return row


# ─── Test Cases ──────────────────────────────────────────────────────────────

def test_create_run_and_get_resumable():
    """create_run 호출 후 get_resumable_runs 결과에 해당 run이 포함된다 (status=running)."""
    ps.create_run("run1", "ses1", 5)

    runs = ps.get_resumable_runs()

    assert len(runs) == 1
    assert runs[0]["id"] == "run1"
    assert runs[0]["session_id"] == "ses1"
    assert runs[0]["status"] == "running"
    assert runs[0]["total_stages"] == 5


def test_save_and_get_checkpoint():
    """save_checkpoint → get_checkpoint 라운드트립이 정확히 복원된다."""
    ps.create_run("run1", "ses1", 5)
    ps.save_checkpoint("run1", 0, {"result": "stage0"})

    cp = ps.get_checkpoint("run1", 0)

    assert cp == {"result": "stage0"}


def test_checkpoint_resume_from_last_completed():
    """여러 스테이지 체크포인트가 모두 독립적으로 저장되고,
    current_stage는 update_stage 호출 값을 반영한다."""
    ps.create_run("run1", "ses1", 5)

    ps.save_checkpoint("run1", 0, {"output": "out0"})
    ps.update_stage("run1", 1, "running")
    ps.save_checkpoint("run1", 1, {"output": "out1"})

    # current_stage가 1로 갱신됐는지
    runs = ps.get_resumable_runs()
    assert len(runs) == 1
    assert runs[0]["current_stage"] == 1

    # 두 체크포인트가 모두 복원되는지
    cp0 = ps.get_checkpoint("run1", 0)
    cp1 = ps.get_checkpoint("run1", 1)
    assert cp0 == {"output": "out0"}
    assert cp1 == {"output": "out1"}


def test_mark_complete_removes_from_resumable():
    """mark_complete 후 get_resumable_runs 목록에서 제거된다."""
    ps.create_run("run1", "ses1", 5)
    ps.mark_complete("run1")

    runs = ps.get_resumable_runs()

    assert all(r["id"] != "run1" for r in runs)


def test_mark_failed():
    """mark_failed 후 DB에 status=failed, error, current_stage가 기록되고
    get_resumable_runs에는 포함되지 않는다."""
    ps.create_run("run1", "ses1", 5)
    ps.mark_failed("run1", 2, "timeout")

    row = _raw_row("run1")
    assert row["status"] == "failed"
    assert row["error"] == "timeout"
    assert row["current_stage"] == 2

    runs = ps.get_resumable_runs()
    assert all(r["id"] != "run1" for r in runs)


def test_mark_interrupted_is_resumable():
    """mark_interrupted 후 get_resumable_runs에 포함되고 status가 interrupted다."""
    ps.create_run("run1", "ses1", 5)
    ps.mark_interrupted("run1")

    runs = ps.get_resumable_runs()

    matched = [r for r in runs if r["id"] == "run1"]
    assert len(matched) == 1
    assert matched[0]["status"] == "interrupted"


def test_parallel_checkpoints():
    """두 run의 체크포인트가 서로 독립적으로 저장된다."""
    ps.create_run("a", "ses1", 5)
    ps.create_run("b", "ses2", 5)

    ps.save_checkpoint("a", 0, {"src": "a_data"})
    ps.save_checkpoint("b", 0, {"src": "b_data"})

    cp_a = ps.get_checkpoint("a", 0)
    cp_b = ps.get_checkpoint("b", 0)

    assert cp_a == {"src": "a_data"}
    assert cp_b == {"src": "b_data"}
    assert cp_a != cp_b


def test_update_stage_status():
    """update_stage 호출 후 DB의 current_stage가 지정한 값으로 갱신된다."""
    ps.create_run("run1", "ses1", 10)
    ps.update_stage("run1", 3, "running")

    row = _raw_row("run1")
    assert row["current_stage"] == 3
    assert row["status"] == "running"


def test_json_default_serialization():
    """JSON 직렬화 불가 타입(datetime)이 output에 포함돼도 예외 없이 저장되고,
    get_checkpoint 복원 시 문자열로 반환된다."""
    ps.create_run("run1", "ses1", 5)
    now = datetime.now()
    # datetime은 기본 json.dumps로 직렬화 불가 — default=str 폴백 검증
    ps.save_checkpoint("run1", 0, {"ts": now})

    cp = ps.get_checkpoint("run1", 0)

    assert cp is not None
    assert isinstance(cp["ts"], str)  # str(now) 로 폴백됐는지
    assert str(now) in cp["ts"] or cp["ts"] == str(now)


def test_cleanup_old_runs():
    """completed run의 updated_at을 8일 전으로 설정하면
    cleanup_old_runs(days=7)이 1을 반환하고 get_resumable_runs에서 사라진다."""
    ps.create_run("run1", "ses1", 5)
    ps.mark_complete("run1")

    # updated_at을 8일 전으로 직접 패치
    old_ts = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    conn = sqlite3.connect(str(ps._DB_PATH), check_same_thread=False)
    conn.execute(
        "UPDATE pipeline_runs SET updated_at = ? WHERE id = ?",
        (old_ts, "run1"),
    )
    conn.commit()
    conn.close()

    deleted = ps.cleanup_old_runs(days=7)

    assert deleted == 1
    # completed run은 get_resumable_runs 대상이 아니지만, 삭제됐으므로 DB에도 없어야 함
    conn2 = sqlite3.connect(str(ps._DB_PATH), check_same_thread=False)
    conn2.row_factory = sqlite3.Row
    row = conn2.execute(
        "SELECT * FROM pipeline_runs WHERE id = ?", ("run1",)
    ).fetchone()
    conn2.close()
    assert row is None

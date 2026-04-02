"""
pipeline_store.py — SQLite 기반 파이프라인 실행 상태 영속 저장소
=====================================================================

목적
----
PipelineRunner의 실행 상태(진행 스테이지, 각 스테이지 출력)를 SQLite에
체크포인트로 저장한다. 서버가 재시작되더라도 중단된 파이프라인을 식별하고
사용자에게 재개 힌트를 제공할 수 있다.

DB 위치
-------
    services/session-manager/data/pipeline_state.db
    (모듈 로드 시 data/ 디렉토리와 테이블을 자동 생성)

정상 실행 흐름
--------------
    create_run(run_id, session_id, total_stages)   ← 파이프라인 시작 시
        │
        ├─ [iteration 루프]
        │      update_stage(run_id, step, "running")   ← 각 스텝 진입
        │      save_checkpoint(run_id, step, output)   ← 스텝 완료 후
        │
        ├─ 정상 완료: mark_complete(run_id)
        ├─ 오류 종료: mark_failed(run_id, step, error_msg)
        └─ 서버 종료: mark_interrupted(run_id)          ← lifespan shutdown

재시작 후 복구 흐름
-------------------
    lifespan startup에서 get_resumable_runs() 조회
    → status="running" 또는 "interrupted"인 run 목록 반환
    → 각 run을 mark_interrupted()로 상태 확정 후 로그 출력

    사용자 확인 엔드포인트:
        GET  /admin/status          → resumable_runs 목록 + safe_to_restart 플래그
        POST /admin/resume/{run_id} → 해당 run의 체크포인트 + 재개 힌트 반환

WAL 모드를 사용하는 이유
------------------------
SQLite 기본 모드(DELETE journal)에서는 Writer가 DB 전체를 잠근다.
병렬 파이프라인이 동시에 save_checkpoint를 호출하면 SQLITE_BUSY가 발생할 수 있다.
WAL(Write-Ahead Logging) 모드에서는 Reader가 Writer를 차단하지 않아
동시 접근 충돌을 최소화한다. threading.Lock은 Python 프로세스 내 동시 write를
직렬화하여 WAL과 이중으로 보호한다.

주의사항
--------
- stage_outputs 컬럼은 JSON dict로 관리, 키는 stage_idx 문자열 ("0", "1", ...)
- JSON 직렬화 불가 타입(datetime 등)은 default=str으로 문자열 폴백
- cleanup_old_runs(days)로 completed/failed run 주기적 정리 (lifespan startup 호출)
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from app.models import DATA_DIR

_DB_PATH = DATA_DIR / "pipeline_state.db"
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _get_conn():
    """Open a connection, yield it, and ensure it is closed on exit."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id            TEXT PRIMARY KEY,
            session_id    TEXT NOT NULL,
            status        TEXT NOT NULL,
            current_stage INTEGER NOT NULL DEFAULT 0,
            total_stages  INTEGER NOT NULL DEFAULT 0,
            stage_outputs TEXT NOT NULL DEFAULT '{}',
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            error         TEXT
        )
    """)
    conn.commit()


# 모듈 로드 시 data/ 디렉토리 보장 후 DB 초기화
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
with _lock:
    _conn = _connect()
    _init_db(_conn)
    _conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Public API ───────────────────────────────────────────────────────────────

def create_run(run_id: str, session_id: str, total_stages: int) -> None:
    """신규 파이프라인 실행 레코드 생성."""
    now = _now_iso()
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs
                (id, session_id, status, current_stage, total_stages,
                 stage_outputs, created_at, updated_at, error)
            VALUES (?, ?, 'running', 0, ?, '{}', ?, ?, NULL)
            """,
            (run_id, session_id, total_stages, now, now),
        )
        conn.commit()


def update_stage(run_id: str, stage_idx: int, status: str) -> None:
    """현재 실행 중인 스테이지 인덱스와 상태 갱신."""
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET current_stage = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (stage_idx, status, _now_iso(), run_id),
        )
        conn.commit()


def save_checkpoint(run_id: str, stage_idx: int, output: dict) -> None:
    """스테이지 출력 체크포인트 저장.

    stage_outputs 컬럼은 JSON dict로 관리되며, 키는 stage_idx 문자열.
    기존 체크포인트는 덮어쓰지 않고 병합(merge).
    """
    key = str(stage_idx)
    with _lock, _get_conn() as conn:
        row = conn.execute(
            "SELECT stage_outputs FROM pipeline_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return

        existing: dict = json.loads(row["stage_outputs"] or "{}")
        existing[key] = output

        conn.execute(
            """
            UPDATE pipeline_runs
            SET stage_outputs = ?, updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(existing, ensure_ascii=False, default=str), _now_iso(), run_id),
        )
        conn.commit()


def get_checkpoint(run_id: str, stage_idx: int) -> Optional[dict]:
    """저장된 스테이지 체크포인트 반환. 없으면 None."""
    key = str(stage_idx)
    with _lock, _get_conn() as conn:
        row = conn.execute(
            "SELECT stage_outputs FROM pipeline_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        outputs: dict = json.loads(row["stage_outputs"] or "{}")
        return outputs.get(key)


def get_resumable_runs() -> list[dict]:
    """status가 'running' 또는 'interrupted'인 파이프라인 목록 반환."""
    with _lock, _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, status, current_stage, total_stages,
                   stage_outputs, created_at, updated_at, error
            FROM pipeline_runs
            WHERE status IN ('running', 'interrupted')
            ORDER BY created_at ASC
            """,
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["stage_outputs"] = json.loads(d["stage_outputs"] or "{}")
            result.append(d)
        return result


def mark_complete(run_id: str) -> None:
    """파이프라인을 completed 상태로 마킹."""
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET status = 'completed', updated_at = ?, error = NULL
            WHERE id = ?
            """,
            (_now_iso(), run_id),
        )
        conn.commit()


def mark_failed(run_id: str, stage_idx: int, error_msg: str) -> None:
    """파이프라인을 failed 상태로 마킹. 실패 스테이지와 에러 메시지 기록."""
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET status = 'failed', current_stage = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (stage_idx, error_msg, _now_iso(), run_id),
        )
        conn.commit()


def mark_interrupted(run_id: str) -> None:
    """서버 종료 등으로 중단된 파이프라인을 interrupted 상태로 마킹."""
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET status = 'interrupted', updated_at = ?
            WHERE id = ?
            """,
            (_now_iso(), run_id),
        )
        conn.commit()


def cleanup_interrupted_runs(run_ids: list[str] | None = None) -> int:
    """interrupted 상태 파이프라인 run을 삭제.

    Args:
        run_ids: 특정 run만 삭제. None이면 모든 interrupted run 삭제.

    Returns:
        삭제된 행 수.
    """
    with _lock, _get_conn() as conn:
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            cur = conn.execute(
                f"""
                DELETE FROM pipeline_runs
                WHERE status = 'interrupted' AND id IN ({placeholders})
                """,
                run_ids,
            )
        else:
            cur = conn.execute(
                "DELETE FROM pipeline_runs WHERE status = 'interrupted'"
            )
        conn.commit()
        return cur.rowcount


def cleanup_old_runs(days: int = 7) -> int:
    """completed/failed 상태이고 updated_at이 days일 이전인 run을 삭제.

    Returns:
        삭제된 행 수.
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _lock, _get_conn() as conn:
        cur = conn.execute(
            """
            DELETE FROM pipeline_runs
            WHERE status IN ('completed', 'failed')
              AND updated_at < ?
            """,
            (cutoff,),
        )
        conn.commit()
        return cur.rowcount

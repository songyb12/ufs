"""
app/routes_ws.py — WebSocket endpoints.

/ws/shell/{shell_id}  : PTY 셸 양방향 브릿지 (xterm.js)
/ws/{session_id}      : Claude 세션 출력 스트리밍
"""

import asyncio
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.state import sessions, shell_sessions

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


def _ws_auth_ok(token: str) -> bool:
    """ADMIN_API_KEY 미설정 시 인증 비활성화. 설정 시 token과 일치해야 통과."""
    key = os.environ.get("ADMIN_API_KEY", "")
    return not key or token == key


# /ws/shell/{shell_id} 를 /ws/{session_id} 보다 먼저 등록 (더 구체적인 경로 우선)
@router.websocket("/ws/shell/{shell_id}")
async def websocket_shell(
    websocket: WebSocket,
    shell_id: str,
    token: str = Query(default=""),
):
    """Shell PTY와 xterm.js 사이의 양방향 WebSocket 브릿지"""
    await websocket.accept()

    if not _ws_auth_ok(token):
        await websocket.send_json({"error": "인증 실패"})
        await websocket.close(code=4003)
        return

    if shell_id not in shell_sessions:
        await websocket.send_json({"error": "Shell 세션 없음"})
        await websocket.close()
        return

    shell = shell_sessions[shell_id]
    if not shell.alive:
        await websocket.send_json({"error": "Shell 세션이 종료됨"})
        await websocket.close()
        return

    output_queue = shell.subscribe()

    async def _send_output():
        """PTY → WebSocket (stdout 스트리밍)"""
        try:
            while True:
                data = await output_queue.get()
                if data is None:
                    break  # 세션 종료
                await websocket.send_text(data)
        except Exception:
            pass

    send_task = asyncio.create_task(_send_output())

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            # 텍스트: 키 입력
            if "text" in msg:
                text = msg["text"]
                # resize JSON 메시지 감지: {"type": "resize", "rows": N, "cols": N}
                if text.startswith('{"'):
                    try:
                        payload = json.loads(text)
                        if payload.get("type") == "resize":
                            cols = max(40, min(400, int(payload["cols"])))
                            rows = max(10, min(200, int(payload["rows"])))
                            shell.resize(cols, rows)
                        else:
                            shell.write(text)
                    except Exception:
                        shell.write(text)
                else:
                    shell.write(text)
            elif "bytes" in msg:
                shell.write(msg["bytes"].decode("utf-8", errors="replace"))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("[ws/shell:%s] unexpected error: %s", shell_id, e)
    finally:
        shell.unsubscribe(output_queue)
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass


@router.websocket("/ws/{session_id}")
async def websocket_output(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(default=""),
):
    await websocket.accept()

    if not _ws_auth_ok(token):
        await websocket.send_json({"error": "인증 실패"})
        await websocket.close(code=4003)
        return

    if session_id not in sessions:
        await websocket.send_json({"error": "세션 없음"})
        await websocket.close()
        return

    session = sessions[session_id]
    last_version = -1
    dead_count = 0  # 죽은 세션 감지 카운터 (각 카운트 ≈ 30초)

    try:
        while True:
            # 세션이 목록에서 제거되었으면 종료
            if session_id not in sessions:
                await websocket.send_json({"error": "세션 제거됨"})
                break

            if session._output_version != last_version:
                # 새 출력 있음 → 이벤트 클리어 후 즉시 전송
                session._output_event.clear()
                try:
                    output = session.get_formatted_output(200)
                    raw_lines = session.output_lines[-200:]
                    msg = {
                        "output": output,
                        "output_lines": raw_lines,
                        "alive": session.alive,
                        "busy": session.busy,
                        "queue_size": session._queue.qsize(),
                        "tokens": {
                            "input": session.total_input_tokens,
                            "output": session.total_output_tokens,
                        },
                    }
                    if session.pending_question:
                        msg["pending_question"] = session.pending_question
                    await asyncio.wait_for(
                        websocket.send_json(msg),
                        timeout=5,
                    )
                    last_version = session._output_version
                    dead_count = 0
                except asyncio.TimeoutError:
                    break
            else:
                # 변경 없음 → 이벤트 대기 (최대 30초, 연결 유지 ping 역할)
                session._output_event.clear()
                try:
                    await asyncio.wait_for(session._output_event.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass

                if not session.alive and not session.busy:
                    dead_count += 1
                    if dead_count > 3:
                        break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("[ws/output:%s] unexpected error: %s", session_id, e)

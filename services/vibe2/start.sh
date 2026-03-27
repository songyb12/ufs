#!/bin/bash
# VIBE 2.0 Quick Start — backend + dashboard
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_PID=0
FRONTEND_PID=0

cleanup() {
    echo ""
    echo "VIBE 2.0 종료 중..."
    [ $BACKEND_PID -ne 0 ] && kill $BACKEND_PID 2>/dev/null
    [ $FRONTEND_PID -ne 0 ] && kill $FRONTEND_PID 2>/dev/null
    wait 2>/dev/null
    echo "종료 완료."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "========================================="
echo "  VIBE 2.0 시작..."
echo "  백엔드:   http://localhost:8010"
echo "  대시보드: http://localhost:3002"
echo "========================================="

# Backend
uvicorn app.main:app --port 8010 --host 0.0.0.0 &
BACKEND_PID=$!
echo "[Backend]  PID=$BACKEND_PID"

# Frontend
cd dashboard && npm run dev &
FRONTEND_PID=$!
echo "[Dashboard] PID=$FRONTEND_PID"

echo ""
echo "Ctrl+C 로 종료"
wait

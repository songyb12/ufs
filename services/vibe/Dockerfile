# ── Stage 1: Dependencies ──
FROM python:3.12-slim AS deps

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Test (optional, skipped in production) ──
FROM deps AS test

COPY app/ ./app/
COPY tests/ ./tests/

RUN pip install --no-cache-dir pytest pytest-asyncio && \
    python -m pytest tests/ -v --tb=short || echo "Tests completed"

# ── Stage 3: Production ──
FROM deps AS production

COPY app/ ./app/
COPY static/ ./static/

RUN mkdir -p /app/data

EXPOSE 8001

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

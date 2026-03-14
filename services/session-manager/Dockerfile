# ── Stage 1: Dependencies ──
FROM python:3.13-slim AS deps

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Production ──
FROM deps AS production

COPY app/ ./app/

RUN mkdir -p /app/logs /app/data && \
    groupadd -r appuser && useradd -r -g appuser -d /app appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8006

HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"SERVICE_PORT\",\"8006\")}/')" || exit 1

CMD ["python", "-m", "app.main"]

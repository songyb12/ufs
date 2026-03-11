"""
UFS Master Core - API Gateway (Level 0)

All Level 1 service requests are proxied through this gateway.
Endpoints:
  GET  /                    -> System info
  GET  /health              -> Aggregated health of all services
  GET  /services            -> List registered services + status
  ANY  /api/v1/{service}/** -> Proxy to target service
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import SERVICE_REGISTRY, settings

logger = logging.getLogger("ufs.gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared HTTP client lifecycle."""
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("Master Core v%s started — %d services registered", settings.VERSION, len(SERVICE_REGISTRY))
    yield
    await app.state.http_client.aclose()
    logger.info("Master Core shutdown")


app = FastAPI(
    title="UFS Master Core",
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS — allow Shell and dev frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    if not request.url.path.startswith("/health"):
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method, request.url.path, response.status_code, elapsed,
        )
    response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"
    return response


# --------------------------------------------------
# Core endpoints
# --------------------------------------------------
@app.get("/")
async def root():
    return {
        "system": "UFS Master Core Ecosystem",
        "version": settings.VERSION,
        "level": 0,
        "services": list(SERVICE_REGISTRY.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
async def health_aggregated():
    """Check health of all Level 1 services and return aggregated status."""
    client: httpx.AsyncClient = app.state.http_client
    results: dict[str, dict] = {}

    for name, url in SERVICE_REGISTRY.items():
        try:
            resp = await client.get(f"{url}/health", timeout=5.0)
            results[name] = {
                "status": "healthy" if resp.status_code == 200 else "unhealthy",
                "code": resp.status_code,
            }
        except httpx.RequestError:
            results[name] = {"status": "unreachable", "code": None}

    all_healthy = all(s["status"] == "healthy" for s in results.values())

    return {
        "gateway": "healthy",
        "services": results,
        "overall": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/services")
async def list_services():
    """List all registered Level 1 services with their URLs."""
    return {
        "services": [
            {"name": name, "url": url}
            for name, url in SERVICE_REGISTRY.items()
        ]
    }


# --------------------------------------------------
# API Gateway proxy: /api/v1/{service}/{path}
# --------------------------------------------------
@app.api_route(
    "/api/v1/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def gateway_proxy(service: str, path: str, request: Request):
    """
    Proxy requests to Level 1 services.

    Example: GET /api/v1/vibe/dashboard -> GET http://vibe:8001/dashboard
    """
    if service not in SERVICE_REGISTRY:
        return JSONResponse(
            status_code=404,
            content={"error": f"Service '{service}' not found", "available": list(SERVICE_REGISTRY.keys())},
        )

    target_url = f"{SERVICE_REGISTRY[service]}/{path}"
    client: httpx.AsyncClient = app.state.http_client

    # Forward request
    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    try:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=request.query_params,
        )
        content_type = resp.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return JSONResponse(
                status_code=resp.status_code,
                content=resp.json(),
            )
        return JSONResponse(
            status_code=resp.status_code,
            content={"raw": resp.text},
        )
    except httpx.RequestError as e:
        logger.warning("Proxy to %s failed: %s", service, e)
        return JSONResponse(
            status_code=502,
            content={"error": f"Service '{service}' unreachable", "detail": str(e)},
        )

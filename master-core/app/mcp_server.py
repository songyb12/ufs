"""
UFS Master Core — MCP (Model Context Protocol) Server.

Exposes all Level 1 services as MCP tools so that Claude Desktop,
Claude Code, or any MCP-compatible agent can interact with UFS.

Run standalone:  python -m app.mcp_server          (stdio transport)
Run SSE:         python -m app.mcp_server --sse     (HTTP SSE transport)
"""

import asyncio
import json
import logging
import sys
from typing import Any

import httpx

from app.config import SERVICE_REGISTRY, settings

logger = logging.getLogger("ufs.mcp")

# ---------------------------------------------------------------------------
# Tool definitions — each maps to a Level 1 service endpoint
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # ── VIBE (Investment Intelligence) ──
    {
        "name": "vibe_market_briefing",
        "description": "Get today's AI-powered market briefing from VIBE. Returns macro, signals, top movers, and upcoming events.",
        "service": "vibe",
        "method": "GET",
        "path": "briefing/today",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "vibe_signals",
        "description": "Get latest trading signals for all watched stocks. Returns signal type (BUY/SELL/HOLD), scores, RSI, confidence.",
        "service": "vibe",
        "method": "GET",
        "path": "dashboard/signals",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "Market filter: KR or US",
                    "enum": ["KR", "US"],
                },
            },
        },
    },
    {
        "name": "vibe_portfolio",
        "description": "Get current portfolio positions with P&L and latest signals.",
        "service": "vibe",
        "method": "GET",
        "path": "dashboard/portfolio",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "vibe_guru_insights",
        "description": "Get famous investor (guru) perspectives on current market. Includes Buffett, Lynch, Dalio, etc.",
        "service": "vibe",
        "method": "GET",
        "path": "guru/insights",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "vibe_run_pipeline",
        "description": "Run the VIBE analysis pipeline for a specific market. Executes data collection, analysis, signal generation.",
        "service": "vibe",
        "method": "POST",
        "path": "pipeline/run",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "Target market: KR or US",
                    "enum": ["KR", "US"],
                },
            },
            "required": ["market"],
        },
    },
    {
        "name": "vibe_ai_analysis",
        "description": "Run AI analysis on VIBE data with a custom question. Gathers all DB context and generates Korean market commentary.",
        "service": "vibe",
        "method": "POST",
        "path": "briefing/ai-analyze",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to analyze (Korean preferred). Default: 오늘의 시장 상황을 종합 분석해주세요.",
                },
            },
        },
    },
    {
        "name": "vibe_rag_query",
        "description": "Ask natural language questions about VIBE investment data. Converts to SQL, executes, and returns Korean answer. Example: '삼성전자 최근 RSI 추이는?'",
        "service": "vibe",
        "method": "POST",
        "path": "briefing/query",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question about investment data (Korean or English)",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "vibe_watchlist",
        "description": "Get the current stock watchlist with active/inactive status.",
        "service": "vibe",
        "method": "GET",
        "path": "watchlist",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "Market filter: KR or US",
                    "enum": ["KR", "US"],
                },
            },
        },
    },
    # ── Life-Master ──
    {
        "name": "life_dashboard",
        "description": "Get Life-Master dashboard: routines, habits, goals, and daily progress.",
        "service": "life-master",
        "method": "GET",
        "path": "dashboard",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "life_schedule_today",
        "description": "Get today's optimized schedule from Life-Master.",
        "service": "life-master",
        "method": "GET",
        "path": "schedule/today",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "life_japanese_stats",
        "description": "Get Japanese language study statistics: vocabulary progress, SRS stats, JLPT level breakdown.",
        "service": "life-master",
        "method": "GET",
        "path": "japanese/stats",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    # ── Engineering-Ops ──
    {
        "name": "engops_status",
        "description": "Get Engineering-Ops service status and recent log analysis results.",
        "service": "engineering-ops",
        "method": "GET",
        "path": "status",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    # ── System ──
    {
        "name": "ufs_health",
        "description": "Check health of all UFS services. Returns aggregated status of gateway and all Level 1 services.",
        "service": "__gateway__",
        "method": "GET",
        "path": "health",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

# Build lookup
_TOOL_MAP: dict[str, dict] = {t["name"]: t for t in TOOL_DEFINITIONS}


# ---------------------------------------------------------------------------
# HTTP client for calling services
# ---------------------------------------------------------------------------

async def _call_service(tool_def: dict, arguments: dict) -> str:
    """Forward a tool call to the appropriate Level 1 service via HTTP."""
    service = tool_def["service"]
    method = tool_def["method"]
    path = tool_def["path"]

    # Determine base URL
    if service == "__gateway__":
        base_url = f"http://localhost:{8000}"
    else:
        base_url = SERVICE_REGISTRY.get(service)
        if not base_url:
            return json.dumps({"error": f"Service '{service}' not registered"})

    url = f"{base_url}/{path}"

    # Add query params from arguments for GET, body for POST
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if method == "GET":
                params = {k: v for k, v in arguments.items() if v is not None}
                resp = await client.get(url, params=params)
            else:
                resp = await client.request(method, url, json=arguments)

            if resp.headers.get("content-type", "").startswith("application/json"):
                return json.dumps(resp.json(), ensure_ascii=False, default=str)
            return resp.text
        except httpx.RequestError as e:
            return json.dumps({"error": f"Service unreachable: {e}"})


# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------

def create_mcp_server():
    """Create and configure the MCP server with all UFS tools."""
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    server = Server("ufs-master-core")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["input_schema"],
            )
            for t in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        tool_def = _TOOL_MAP.get(name)
        if not tool_def:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}),
            )]

        result = await _call_service(tool_def, arguments or {})
        return [TextContent(type="text", text=result)]

    return server


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run_stdio():
    """Run MCP server with stdio transport (for Claude Desktop)."""
    from mcp.server.stdio import stdio_server

    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def run_sse(host: str = "0.0.0.0", port: int = 8005):
    """Run MCP server with SSE transport (for HTTP access)."""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route
    import uvicorn

    server = create_mcp_server()
    sse = SseServerTransport("/messages")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    async def handle_messages(request):
        await sse.handle_post_message(request.scope, request.receive, request._send)

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
        ],
    )

    config = uvicorn.Config(starlette_app, host=host, port=port)
    uvicorn_server = uvicorn.Server(config)
    logger.info("MCP SSE server starting on %s:%d", host, port)
    await uvicorn_server.serve()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if "--sse" in sys.argv:
        asyncio.run(run_sse())
    else:
        asyncio.run(run_stdio())

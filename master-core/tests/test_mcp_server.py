"""Tests for MCP Server — tool definitions, routing, and _call_service."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.mcp_server import (
    TOOL_DEFINITIONS,
    _TOOL_MAP,
    _call_service,
)


# ── Tool definition validation ──


class TestToolDefinitions:
    """Verify all tool definitions have required fields and correct structure."""

    def test_all_tools_have_required_fields(self):
        required = {"name", "description", "service", "method", "path", "input_schema"}
        for tool in TOOL_DEFINITIONS:
            missing = required - set(tool.keys())
            assert not missing, f"Tool '{tool.get('name', '?')}' missing: {missing}"

    def test_all_tool_names_unique(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_tool_map_matches_definitions(self):
        assert len(_TOOL_MAP) == len(TOOL_DEFINITIONS)
        for tool in TOOL_DEFINITIONS:
            assert tool["name"] in _TOOL_MAP

    def test_methods_are_valid(self):
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH"}
        for tool in TOOL_DEFINITIONS:
            assert tool["method"] in valid_methods, f"Tool '{tool['name']}' has invalid method: {tool['method']}"

    def test_services_are_known(self):
        known = {"vibe", "lab-studio", "engineering-ops", "life-master", "__gateway__"}
        for tool in TOOL_DEFINITIONS:
            assert tool["service"] in known, f"Tool '{tool['name']}' has unknown service: {tool['service']}"

    def test_input_schema_is_object_type(self):
        for tool in TOOL_DEFINITIONS:
            schema = tool["input_schema"]
            assert schema["type"] == "object", f"Tool '{tool['name']}' schema not object type"
            assert "properties" in schema

    def test_minimum_tool_count(self):
        """Should have at least 10 tools covering core services."""
        assert len(TOOL_DEFINITIONS) >= 10

    def test_vibe_tools_present(self):
        vibe_tools = [t["name"] for t in TOOL_DEFINITIONS if t["service"] == "vibe"]
        assert "vibe_market_briefing" in vibe_tools
        assert "vibe_signals" in vibe_tools
        assert "vibe_portfolio" in vibe_tools
        assert "vibe_rag_query" in vibe_tools

    def test_life_master_tools_present(self):
        life_tools = [t["name"] for t in TOOL_DEFINITIONS if t["service"] == "life-master"]
        assert len(life_tools) >= 2

    def test_health_tool_present(self):
        assert "ufs_health" in _TOOL_MAP
        assert _TOOL_MAP["ufs_health"]["service"] == "__gateway__"


# ── _call_service tests ──


class TestCallService:
    """Verify HTTP routing in _call_service."""

    @pytest.mark.asyncio
    async def test_get_request_with_params(self):
        """GET requests pass arguments as query params."""
        tool_def = {
            "service": "vibe",
            "method": "GET",
            "path": "dashboard/signals",
        }
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"signals": []}

        with patch("app.mcp_server.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _call_service(tool_def, {"market": "KR"})

        data = json.loads(result)
        assert data == {"signals": []}
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs.get("params") == {"market": "KR"} or call_kwargs[1].get("params") == {"market": "KR"}

    @pytest.mark.asyncio
    async def test_post_request_with_body(self):
        """POST requests pass arguments as JSON body."""
        tool_def = {
            "service": "vibe",
            "method": "POST",
            "path": "pipeline/run",
        }
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"status": "ok"}

        with patch("app.mcp_server.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _call_service(tool_def, {"market": "KR"})

        data = json.loads(result)
        assert data == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_unknown_service_returns_error(self):
        """Unknown service in tool_def returns error JSON."""
        tool_def = {
            "service": "nonexistent",
            "method": "GET",
            "path": "anything",
        }
        result = await _call_service(tool_def, {})
        data = json.loads(result)
        assert "error" in data
        assert "nonexistent" in data["error"]

    @pytest.mark.asyncio
    async def test_gateway_uses_localhost(self):
        """__gateway__ service uses localhost:8000."""
        tool_def = {
            "service": "__gateway__",
            "method": "GET",
            "path": "health",
        }
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"status": "ok"}

        with patch("app.mcp_server.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _call_service(tool_def, {})

        # Verify it called localhost:8000
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "localhost" in url and "8000" in url

    @pytest.mark.asyncio
    async def test_get_filters_none_params(self):
        """GET requests should not include None-valued params."""
        tool_def = {
            "service": "vibe",
            "method": "GET",
            "path": "watchlist",
        }
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = []

        with patch("app.mcp_server.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            await _call_service(tool_def, {"market": None, "active": True})

        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        assert "market" not in params
        assert params.get("active") is True

    @pytest.mark.asyncio
    async def test_text_response_handling(self):
        """Non-JSON response returns raw text."""
        tool_def = {
            "service": "vibe",
            "method": "GET",
            "path": "health",
        }
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.text = "OK"

        with patch("app.mcp_server.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _call_service(tool_def, {})

        assert result == "OK"

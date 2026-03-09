"""Tests for strategy settings API endpoints."""

import pytest
import pytest_asyncio

from tests.conftest import cleanup_all


@pytest.fixture(autouse=True)
def _cleanup(event_loop, setup_db):
    """Clean runtime_config before each test."""
    event_loop.run_until_complete(cleanup_all())


class TestGetStrategySettings:
    """GET /settings/strategy — retrieve all parameters."""

    @pytest.mark.asyncio
    async def test_get_defaults(self, client):
        resp = await client.get("/settings/strategy")
        assert resp.status_code == 200
        data = resp.json()

        assert "params" in data
        assert "categories" in data
        assert "change_log" in data
        assert data["modified_count"] == 0

        # Verify all 14 params present
        keys = [p["key"] for p in data["params"]]
        assert "hard_limit_rsi_hold" in keys
        assert "stop_loss_pct" in keys
        assert "cash_ratio_panic" in keys
        assert len(keys) >= 14  # At least 14 params, may grow

    @pytest.mark.asyncio
    async def test_default_values_match(self, client):
        resp = await client.get("/settings/strategy")
        data = resp.json()
        for p in data["params"]:
            assert p["current_value"] == p["default"]
            assert p["is_modified"] is False

    @pytest.mark.asyncio
    async def test_categories_present(self, client):
        resp = await client.get("/settings/strategy")
        cats = resp.json()["categories"]
        assert set(cats.keys()) == {"hard_limit", "stance", "position", "cash"}


class TestUpdateStrategySettings:
    """PUT /settings/strategy — update parameters."""

    @pytest.mark.asyncio
    async def test_update_single_param(self, client):
        resp = await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": 70}
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied_count"] == 1
        assert body["applied"][0]["key"] == "hard_limit_rsi_hold"
        assert body["applied"][0]["new_value"] == 70

        # Verify persisted
        get_resp = await client.get("/settings/strategy")
        param = next(p for p in get_resp.json()["params"] if p["key"] == "hard_limit_rsi_hold")
        assert param["current_value"] == 70
        assert param["is_modified"] is True

    @pytest.mark.asyncio
    async def test_update_float_param(self, client):
        resp = await client.put("/settings/strategy", json={
            "changes": {"stop_loss_pct": -10.5}
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 1

        get_resp = await client.get("/settings/strategy")
        param = next(p for p in get_resp.json()["params"] if p["key"] == "stop_loss_pct")
        assert param["current_value"] == -10.5

    @pytest.mark.asyncio
    async def test_update_multiple_params(self, client):
        resp = await client.put("/settings/strategy", json={
            "changes": {
                "hard_limit_rsi_hold": 75,
                "cash_ratio_panic": 60,
            }
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 2

    @pytest.mark.asyncio
    async def test_skip_invalid_key(self, client):
        resp = await client.put("/settings/strategy", json={
            "changes": {"nonexistent_param": 42}
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 0

    @pytest.mark.asyncio
    async def test_skip_out_of_range(self, client):
        # hard_limit_rsi_hold has min=50, max=90
        resp = await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": 100}
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 0

    @pytest.mark.asyncio
    async def test_skip_below_min(self, client):
        resp = await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": 10}
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 0

    @pytest.mark.asyncio
    async def test_skip_non_numeric(self, client):
        resp = await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": "not_a_number"}
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 0

    @pytest.mark.asyncio
    async def test_no_changes_body(self, client):
        resp = await client.put("/settings/strategy", json={"changes": {}})
        assert resp.status_code == 200
        assert resp.json()["message"] == "No changes"

    @pytest.mark.asyncio
    async def test_no_change_same_value(self, client):
        """Updating to default value (no prior override) = no change applied."""
        resp = await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": 65}  # 65 is default
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 0

    @pytest.mark.asyncio
    async def test_changelog_persisted(self, client):
        await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": 70}
        })
        resp = await client.get("/settings/strategy")
        log = resp.json()["change_log"]
        assert len(log) >= 1
        assert log[-1]["key"] == "hard_limit_rsi_hold"
        assert log[-1]["new_value"] == 70
        assert "changed_at" in log[-1]


class TestResetStrategyParam:
    """POST /settings/strategy/reset — reset to default."""

    @pytest.mark.asyncio
    async def test_reset_modified_param(self, client):
        # Set then reset
        await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": 80}
        })
        resp = await client.post("/settings/strategy/reset", json={"key": "hard_limit_rsi_hold"})
        assert resp.status_code == 200

        # Verify back to default
        get_resp = await client.get("/settings/strategy")
        param = next(p for p in get_resp.json()["params"] if p["key"] == "hard_limit_rsi_hold")
        assert param["current_value"] == 65  # default
        assert param["is_modified"] is False

    @pytest.mark.asyncio
    async def test_reset_already_default(self, client):
        resp = await client.post("/settings/strategy/reset", json={"key": "hard_limit_rsi_hold"})
        assert resp.status_code == 200
        assert "default" in resp.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_reset_unknown_key(self, client):
        resp = await client.post("/settings/strategy/reset", json={"key": "fake_key"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_missing_key(self, client):
        resp = await client.post("/settings/strategy/reset", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_logs_to_changelog(self, client):
        await client.put("/settings/strategy", json={
            "changes": {"stop_loss_pct": -15.0}
        })
        await client.post("/settings/strategy/reset", json={"key": "stop_loss_pct"})

        resp = await client.get("/settings/strategy")
        log = resp.json()["change_log"]
        reset_entry = [e for e in log if e.get("reset")]
        assert len(reset_entry) >= 1
        assert reset_entry[-1]["key"] == "stop_loss_pct"


class TestParseValue:
    """Test _parse_value edge cases via API round-trips."""

    @pytest.mark.asyncio
    async def test_string_coercion(self, client):
        """String numbers should be coerced correctly."""
        resp = await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": "75"}
        })
        assert resp.status_code == 200
        assert resp.json()["applied_count"] == 1

    @pytest.mark.asyncio
    async def test_float_to_int_coercion(self, client):
        """Float value for int param should be truncated."""
        resp = await client.put("/settings/strategy", json={
            "changes": {"hard_limit_rsi_hold": 75.9}
        })
        assert resp.status_code == 200

        get_resp = await client.get("/settings/strategy")
        param = next(p for p in get_resp.json()["params"] if p["key"] == "hard_limit_rsi_hold")
        assert param["current_value"] == 75  # int truncation

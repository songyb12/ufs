"""Tests for SQL-RAG query engine — validation and security."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.briefing.rag_query import validate_sql, ALLOWED_TABLES


class TestValidateSql:
    """SQL validation security tests."""

    def test_valid_select(self):
        ok, result = validate_sql("SELECT * FROM signals LIMIT 10")
        assert ok is True
        assert "SELECT" in result

    def test_valid_select_adds_limit(self):
        ok, result = validate_sql("SELECT * FROM signals")
        assert ok is True
        assert "LIMIT 100" in result

    def test_respects_existing_limit(self):
        ok, result = validate_sql("SELECT * FROM signals LIMIT 5")
        assert ok is True
        assert "LIMIT 5" in result
        assert "LIMIT 100" not in result

    def test_rejects_insert(self):
        ok, msg = validate_sql("INSERT INTO signals VALUES (1, 2, 3)")
        assert ok is False

    def test_rejects_update(self):
        ok, msg = validate_sql("UPDATE signals SET raw_score = 0")
        assert ok is False

    def test_rejects_delete(self):
        ok, msg = validate_sql("DELETE FROM signals")
        assert ok is False

    def test_rejects_drop(self):
        ok, msg = validate_sql("DROP TABLE signals")
        assert ok is False

    def test_rejects_alter(self):
        ok, msg = validate_sql("ALTER TABLE signals ADD COLUMN x TEXT")
        assert ok is False

    def test_rejects_non_select(self):
        ok, msg = validate_sql("CREATE TABLE test (id INTEGER)")
        assert ok is False

    def test_rejects_disallowed_table(self):
        ok, msg = validate_sql("SELECT * FROM users")
        assert ok is False
        assert "users" in msg.lower()

    def test_rejects_runtime_config(self):
        ok, msg = validate_sql("SELECT * FROM runtime_config")
        assert ok is False

    def test_allows_signals_table(self):
        ok, _ = validate_sql("SELECT * FROM signals")
        assert ok is True

    def test_allows_watchlist_table(self):
        ok, _ = validate_sql("SELECT * FROM watchlist")
        assert ok is True

    def test_allows_macro_indicators(self):
        ok, _ = validate_sql("SELECT * FROM macro_indicators")
        assert ok is True

    def test_allows_join(self):
        ok, result = validate_sql(
            "SELECT s.*, w.name FROM signals s JOIN watchlist w ON s.symbol = w.symbol"
        )
        assert ok is True

    def test_rejects_join_with_forbidden_table(self):
        ok, msg = validate_sql(
            "SELECT * FROM signals JOIN users ON 1=1"
        )
        assert ok is False
        assert "users" in msg.lower()

    def test_rejects_truncate(self):
        ok, _ = validate_sql("TRUNCATE TABLE signals")
        assert ok is False

    def test_rejects_attach(self):
        ok, _ = validate_sql("ATTACH DATABASE 'other.db' AS other")
        assert ok is False

    def test_strips_semicolon(self):
        ok, result = validate_sql("SELECT * FROM signals;")
        assert ok is True
        assert not result.endswith(";")

    def test_case_insensitive_rejection(self):
        ok, _ = validate_sql("select * from USERS")
        assert ok is False


class TestAllowedTables:
    """Verify the table allowlist is correct."""

    def test_users_not_in_allowlist(self):
        assert "users" not in ALLOWED_TABLES

    def test_runtime_config_not_in_allowlist(self):
        assert "runtime_config" not in ALLOWED_TABLES

    def test_signals_in_allowlist(self):
        assert "signals" in ALLOWED_TABLES

    def test_watchlist_in_allowlist(self):
        assert "watchlist" in ALLOWED_TABLES

    def test_portfolio_state_in_allowlist(self):
        assert "portfolio_state" in ALLOWED_TABLES

    def test_price_history_in_allowlist(self):
        assert "price_history" in ALLOWED_TABLES

    def test_allowlist_count(self):
        # Should have ~28 tables (all except users, runtime_config, alert_config, schema_version)
        assert len(ALLOWED_TABLES) >= 25

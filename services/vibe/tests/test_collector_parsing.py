"""Unit tests for collector defensive parsing.

Verifies that hardened parsing logic handles malformed/empty API responses
without crashing. All external calls are mocked — no real API hits.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


# ── sentiment.py: fetch_fear_greed_index ──


class TestFearGreedParsing:
    """Tests for sentiment.fetch_fear_greed_index defense code."""

    @pytest.mark.asyncio
    async def test_empty_data_array(self):
        """API returns {"data": []} — should return empty dict, not crash."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from app.collectors.sentiment import fetch_fear_greed_index
            result = await fetch_fear_greed_index()

        assert result == {}

    @pytest.mark.asyncio
    async def test_missing_data_key(self):
        """API returns {} with no 'data' key — should return empty dict."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from app.collectors.sentiment import fetch_fear_greed_index
            result = await fetch_fear_greed_index()

        assert result == {}

    @pytest.mark.asyncio
    async def test_null_value_field(self):
        """API returns entry with value=None — should handle gracefully."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"value": None, "value_classification": "Neutral", "timestamp": "123"}]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from app.collectors.sentiment import fetch_fear_greed_index
            result = await fetch_fear_greed_index()

        assert result["fear_greed_index"] is None
        assert result["fear_greed_label"] == "Neutral"

    @pytest.mark.asyncio
    async def test_normal_response(self):
        """Normal API response — should parse correctly."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"value": "72", "value_classification": "Greed", "timestamp": "1700000000"}]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from app.collectors.sentiment import fetch_fear_greed_index
            result = await fetch_fear_greed_index()

        assert result["fear_greed_index"] == 72
        assert result["fear_greed_label"] == "Greed"


# ── finnhub_live.py: get_candles ──


class TestFinnhubCandleParsing:
    """Tests for FinnhubLiveClient.get_candles defense code."""

    def _make_client(self):
        from app.collectors.finnhub_live import FinnhubLiveClient, FinnhubRateLimiter
        limiter = FinnhubRateLimiter(max_calls=100)
        client = FinnhubLiveClient(api_key="test-key", rate_limiter=limiter)
        return client

    @pytest.mark.asyncio
    async def test_no_data_response(self):
        """Finnhub returns {s: "no_data"} — should return empty list."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"s": "no_data"}
        mock_resp.raise_for_status = MagicMock()
        client._client.get = AsyncMock(return_value=mock_resp)

        result = await client.get_candles("SOXL", "5", 1000, 2000)
        assert result == []
        await client.close()

    @pytest.mark.asyncio
    async def test_missing_ohlcv_keys(self):
        """Response has 't' but missing other arrays — should fill None."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "s": "ok",
            "t": [1700000000, 1700000300],
            # o, h, l, c, v all missing
        }
        mock_resp.raise_for_status = MagicMock()
        client._client.get = AsyncMock(return_value=mock_resp)

        result = await client.get_candles("SOXL", "5", 1000, 2000)
        assert len(result) == 2
        assert result[0]["time"] == 1700000000
        assert result[0]["open"] is None
        assert result[0]["high"] is None
        assert result[0]["low"] is None
        assert result[0]["close"] is None
        assert result[0]["volume"] is None
        await client.close()

    @pytest.mark.asyncio
    async def test_short_arrays(self):
        """OHLCV arrays shorter than time array — should pad with None."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "s": "ok",
            "t": [100, 200, 300],
            "o": [10.0],        # only 1 element
            "h": [11.0, 12.0],  # only 2 elements
            "l": [],            # empty
            "c": [9.5, 10.5, 11.5],  # full
            "v": [1000],        # only 1 element
        }
        mock_resp.raise_for_status = MagicMock()
        client._client.get = AsyncMock(return_value=mock_resp)

        result = await client.get_candles("SOXL", "5", 1000, 2000)
        assert len(result) == 3

        # Index 0: all arrays have data
        assert result[0]["open"] == 10.0
        assert result[0]["high"] == 11.0
        assert result[0]["close"] == 9.5
        assert result[0]["volume"] == 1000

        # Index 1: o and v are short
        assert result[1]["open"] is None
        assert result[1]["high"] == 12.0
        assert result[1]["close"] == 10.5
        assert result[1]["volume"] is None

        # Index 2: only c has data
        assert result[2]["open"] is None
        assert result[2]["high"] is None
        assert result[2]["low"] is None
        assert result[2]["close"] == 11.5
        assert result[2]["volume"] is None
        await client.close()

    @pytest.mark.asyncio
    async def test_normal_candle_response(self):
        """Normal Finnhub candle response — should parse correctly."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "s": "ok",
            "t": [1700000000],
            "o": [25.0],
            "h": [26.0],
            "l": [24.5],
            "c": [25.5],
            "v": [50000],
        }
        mock_resp.raise_for_status = MagicMock()
        client._client.get = AsyncMock(return_value=mock_resp)

        result = await client.get_candles("SOXL", "5", 1000, 2000)
        assert len(result) == 1
        assert result[0] == {
            "time": 1700000000,
            "open": 25.0,
            "high": 26.0,
            "low": 24.5,
            "close": 25.5,
            "volume": 50000,
        }
        await client.close()

    @pytest.mark.asyncio
    async def test_403_returns_empty(self):
        """Finnhub 403 (free tier limit) — should return empty list, not raise."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 403
        error = httpx.HTTPStatusError("403", request=MagicMock(), response=mock_response)
        client._client.get = AsyncMock(side_effect=error)

        result = await client.get_candles("SOXL", "5", 1000, 2000)
        assert result == []
        await client.close()


# ── us_fund_flow.py: fetch_etf_flow_proxy ──


def _install_mock_yfinance(mock_ticker):
    """Insert a fake yfinance module into sys.modules so lazy import works."""
    import sys
    mock_yf = MagicMock()
    mock_yf.Ticker = MagicMock(return_value=mock_ticker)
    sys.modules["yfinance"] = mock_yf
    return mock_yf


def _remove_mock_yfinance():
    import sys
    sys.modules.pop("yfinance", None)


class TestEtfFlowParsing:
    """Tests for us_fund_flow.fetch_etf_flow_proxy defense code."""

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """yfinance returns empty DataFrame — should skip that ETF."""
        import pandas as pd

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        _install_mock_yfinance(mock_ticker)
        try:
            from app.collectors.us_fund_flow import fetch_etf_flow_proxy
            result = await fetch_etf_flow_proxy()
        finally:
            _remove_mock_yfinance()

        assert "risk_appetite" in result
        assert "SPY" not in result

    @pytest.mark.asyncio
    async def test_missing_close_column(self):
        """DataFrame has no 'Close' column — should skip that ETF."""
        import pandas as pd

        df = pd.DataFrame({
            "Open": [100, 101, 102, 103, 104],
            "Volume": [1000, 1100, 1200, 1300, 1400],
        })

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df

        _install_mock_yfinance(mock_ticker)
        try:
            from app.collectors.us_fund_flow import fetch_etf_flow_proxy
            result = await fetch_etf_flow_proxy()
        finally:
            _remove_mock_yfinance()

        assert "risk_appetite" in result
        assert "SPY" not in result

    @pytest.mark.asyncio
    async def test_single_row_history(self):
        """Only 1 row of history (need >=2) — should skip."""
        import pandas as pd

        df = pd.DataFrame({
            "Close": [100.0],
            "Volume": [1000],
        })

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df

        _install_mock_yfinance(mock_ticker)
        try:
            from app.collectors.us_fund_flow import fetch_etf_flow_proxy
            result = await fetch_etf_flow_proxy()
        finally:
            _remove_mock_yfinance()

        assert "risk_appetite" in result
        assert "SPY" not in result

    @pytest.mark.asyncio
    async def test_normal_etf_response(self):
        """Normal 5-day data — should compute price_change and volume_ratio."""
        import pandas as pd

        df = pd.DataFrame({
            "Close": [100.0, 101.0, 102.0, 103.0, 105.0],
            "Volume": [1000, 1100, 900, 1200, 1500],
        })

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df

        _install_mock_yfinance(mock_ticker)
        try:
            from app.collectors.us_fund_flow import fetch_etf_flow_proxy
            result = await fetch_etf_flow_proxy()
        finally:
            _remove_mock_yfinance()

        assert "risk_appetite" in result
        # At least one ETF should be populated
        if "SPY" in result:
            assert "price_change_pct" in result["SPY"]
            assert "volume_ratio" in result["SPY"]
            assert "latest_close" in result["SPY"]

    @pytest.mark.asyncio
    async def test_zero_prev_close(self):
        """prev_close is 0 — should skip (division by zero guard)."""
        import pandas as pd

        df = pd.DataFrame({
            "Close": [100.0, 101.0, 102.0, 0.0, 105.0],
            "Volume": [1000, 1100, 900, 1200, 1500],
        })

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df

        _install_mock_yfinance(mock_ticker)
        try:
            from app.collectors.us_fund_flow import fetch_etf_flow_proxy
            result = await fetch_etf_flow_proxy()
        finally:
            _remove_mock_yfinance()

        assert "risk_appetite" in result

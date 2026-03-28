"""Shared test fixtures for VIBE 2.0."""

import os
import sqlite3
from unittest.mock import MagicMock, patch

import bcrypt
import numpy as np
import pandas as pd
import pytest

# Point DB to temp file before any app imports
os.environ["DATABASE_URL"] = "sqlite:///./test_vibe2.db"

from app.auth import create_access_token
from app.db import SCHEMA_SQL


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Create a temporary SQLite DB with schema + dev user for every test."""
    db_path = str(tmp_path / "test.db")

    # Patch _DB_PATH in db module
    with patch("app.db._DB_PATH", db_path), \
         patch("app.db._sync_schema_initialized", False):
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA_SQL)

        # Seed dev user
        hashed = bcrypt.hashpw(b"dev1234", bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("dev", hashed),
        )
        conn.commit()
        conn.close()

        yield db_path


@pytest.fixture
def auth_token():
    """Generate a valid JWT token for the dev user."""
    token, _ = create_access_token("dev")
    return token


@pytest.fixture
def auth_header(auth_token):
    """Authorization header dict."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def sample_ohlcv():
    """Generate a realistic 200-day OHLCV DataFrame."""
    np.random.seed(42)
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=200)
    n = len(dates)
    base = 50.0
    returns = np.random.normal(0.001, 0.03, n)
    close = base * np.cumprod(1 + returns)
    high = close * (1 + np.abs(np.random.normal(0, 0.01, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, n)))
    opn = (high + low) / 2
    volume = np.random.randint(1_000_000, 50_000_000, n)
    return pd.DataFrame({
        "open": opn, "high": high, "low": low, "close": close, "volume": volume,
    }, index=dates)


@pytest.fixture
def oversold_df():
    """DataFrame designed to produce RSI ~25 (strong downtrend)."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=200)
    n = len(dates)
    # Steady decline: most days negative
    close = np.zeros(n)
    close[0] = 100.0
    np.random.seed(10)
    for i in range(1, n):
        close[i] = close[i - 1] * (1 + np.random.choice([-0.02, -0.015, -0.01, 0.005], p=[0.4, 0.3, 0.2, 0.1]))
    close = np.maximum(close, 1.0)  # Floor at 1
    return pd.DataFrame({
        "open": close * 1.005,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.full(n, 10_000_000),
    }, index=dates)


@pytest.fixture
def overbought_df():
    """DataFrame designed to produce RSI ~75+ (strong uptrend)."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=200)
    n = len(dates)
    close = np.zeros(n)
    close[0] = 20.0
    np.random.seed(20)
    for i in range(1, n):
        close[i] = close[i - 1] * (1 + np.random.choice([0.02, 0.015, 0.01, -0.005], p=[0.4, 0.3, 0.2, 0.1]))
    return pd.DataFrame({
        "open": close * 0.995,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.full(n, 10_000_000),
    }, index=dates)


@pytest.fixture
def mock_collectors():
    """Mock all external collector calls (yfinance, httpx)."""
    np.random.seed(42)
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=200)
    n = len(dates)
    close = 50.0 * np.cumprod(1 + np.random.normal(0.001, 0.02, n))
    df = pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.005,
        "low": close * 0.995,
        "close": close,
        "volume": np.full(n, 5_000_000),
    }, index=dates)

    macro_row = {
        "indicator_date": "2026-03-26",
        "vix": 20.0,
        "dxy": 102.0,
        "us_10y_yield": 4.2,
        "us_2y_yield": 3.8,
        "yield_spread": 0.4,
        "wti_crude": 70.0,
        "gold_price": 3000.0,
    }

    with patch("app.engine.signal.fetch_prices", return_value=df) as mock_fp, \
         patch("app.engine.signal.collect_all_prices", return_value={"SOXL": 200, "SOXX": 200}) as mock_cap, \
         patch("app.engine.signal.collect_all_macro", return_value=22) as mock_cam, \
         patch("app.engine.signal.get_latest_macro", return_value=macro_row) as mock_glm, \
         patch("app.engine.signal.collect_sentiment", return_value=True) as mock_cs, \
         patch("app.engine.signal.fetch_fear_greed", return_value={"fear_greed_index": 45}) as mock_fg, \
         patch("app.engine.signal._get_rate_change_5d", return_value=4.1) as mock_rc, \
         patch("app.engine.signal._save_signal") as mock_ss, \
         patch("app.collector.price.fetch_prices", return_value=df), \
         patch("app.collector.macro.get_latest_macro", return_value=macro_row):
        yield {
            "fetch_prices": mock_fp,
            "collect_all_prices": mock_cap,
            "collect_all_macro": mock_cam,
            "get_latest_macro": mock_glm,
            "collect_sentiment": mock_cs,
            "fetch_fear_greed": mock_fg,
            "rate_change_5d": mock_rc,
            "save_signal": mock_ss,
        }

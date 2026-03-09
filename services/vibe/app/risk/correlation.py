"""Return correlation analysis for concurrent BUY signals."""

import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger("vibe.risk.correlation")


def compute_return_correlation(
    price_data: dict[str, pd.DataFrame],
    window: int = 60,
) -> dict[str, dict[str, float]]:
    """Compute pairwise correlation matrix of daily returns.

    Args:
        price_data: {symbol: DataFrame with 'close' column}
        window: Number of days for correlation calculation

    Returns:
        Nested dict: {symbol_a: {symbol_b: correlation}}
    """
    returns = {}
    for symbol, df in price_data.items():
        if df is not None and not df.empty and "close" in df.columns:
            closes = pd.to_numeric(df["close"], errors="coerce").dropna()
            if len(closes) > window:
                daily_ret = closes.pct_change().replace([np.inf, -np.inf], np.nan).dropna().tail(window)
                returns[symbol] = daily_ret.values

    if len(returns) < 2:
        return {}

    symbols = list(returns.keys())
    n = len(symbols)
    corr_matrix: dict[str, dict[str, float]] = {}

    for i in range(n):
        corr_matrix[symbols[i]] = {}
        for j in range(n):
            if i == j:
                corr_matrix[symbols[i]][symbols[j]] = 1.0
            else:
                r1 = returns[symbols[i]]
                r2 = returns[symbols[j]]
                min_len = min(len(r1), len(r2))
                if min_len > 5:
                    corr = float(np.corrcoef(r1[-min_len:], r2[-min_len:])[0, 1])
                    if not math.isfinite(corr):
                        corr = 0.0
                    corr_matrix[symbols[i]][symbols[j]] = round(corr, 4)
                else:
                    corr_matrix[symbols[i]][symbols[j]] = 0.0

    return corr_matrix


def check_concurrent_signals(
    buy_symbols: list[str],
    correlation_matrix: dict[str, dict[str, float]],
    threshold: float = 0.8,
) -> list[str]:
    """Check if concurrent BUY signals have high correlation.

    Returns list of warning strings.
    """
    warnings = []
    checked = set()

    for i, sym_a in enumerate(buy_symbols):
        for j, sym_b in enumerate(buy_symbols):
            if i >= j:
                continue
            pair = tuple(sorted([sym_a, sym_b]))
            if pair in checked:
                continue
            checked.add(pair)

            corr = correlation_matrix.get(sym_a, {}).get(sym_b, 0)
            if abs(corr) >= threshold:
                warnings.append(
                    f"{sym_a}-{sym_b} correlation {corr:.2f} (>{threshold}): concentrated risk"
                )

    return warnings

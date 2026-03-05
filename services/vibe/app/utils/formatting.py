"""Shared formatting utilities used across notifier and pipeline modules."""


def fmt_float(val: float | None, decimals: int = 1) -> str:
    """Format a float value for display, returning 'N/A' for None."""
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"

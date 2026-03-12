"""Profile Engine — build, update, and version-manage personality profiles."""

from __future__ import annotations

import logging
from typing import Any

from app.polaris import repository as polaris_repo

logger = logging.getLogger("vibe.polaris.profile.engine")


async def get_current_profile(figure_id: str) -> dict | None:
    """Get the latest profile for a figure."""
    return await polaris_repo.get_latest_profile(figure_id)


async def save_new_profile(figure_id: str, profile_data: dict,
                           changelog: str = "초기 프로파일 생성") -> dict:
    """Save a new profile version."""
    return await polaris_repo.insert_profile(figure_id, profile_data, changelog)


async def update_profile_from_event(figure_id: str, event_summary: str,
                                    updated_fields: dict[str, Any],
                                    changelog: str = "") -> dict | None:
    """Create a new profile version by merging updates into the current profile.

    Returns:
        New profile dict, or None if no current profile exists.
    """
    current = await polaris_repo.get_latest_profile(figure_id)
    if not current:
        logger.warning("No existing profile for figure %s — cannot update", figure_id)
        return None

    current_data = current.get("profile_data", {})
    merged = _deep_merge(current_data, updated_fields)

    if not changelog:
        changelog = f"이벤트 기반 업데이트: {event_summary[:100]}"

    return await polaris_repo.insert_profile(figure_id, merged, changelog)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = _merge_lists(result[key], value)
        else:
            result[key] = value
    return result


def _merge_lists(base: list, new: list) -> list:
    """Merge two lists, avoiding duplicates for dicts (by first string field)."""
    if not new:
        return base
    if not base:
        return new

    if isinstance(base[0], dict) and isinstance(new[0], dict):
        key_field = None
        for candidate in ("name", "pattern", "event"):
            if candidate in base[0]:
                key_field = candidate
                break

        if key_field:
            existing_keys = {item.get(key_field) for item in base}
            merged = list(base)
            for item in new:
                if item.get(key_field) not in existing_keys:
                    merged.append(item)
                    existing_keys.add(item.get(key_field))
            return merged

    if isinstance(base[0], str):
        seen = set(base)
        merged = list(base)
        for item in new:
            if item not in seen:
                merged.append(item)
                seen.add(item)
        return merged

    return base + new

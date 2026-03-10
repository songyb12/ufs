"""Dynamic schedule optimizer — allocates routines into time blocks."""


# Time slot preferences (hour ranges)
SLOT_RANGES = {
    "MORNING": (6, 12),
    "AFTERNOON": (12, 18),
    "EVENING": (18, 23),
    "FLEXIBLE": (6, 23),
}


def _time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _minutes_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def generate_schedule(
    routines: list[dict],
    locked_blocks: list[dict],
    day_start: int = 6,
    day_end: int = 23,
    slot_interval: int = 30,
    break_min: int = 0,
) -> list[dict]:
    """Generate optimized schedule blocks from routines, avoiding locked blocks.

    Args:
        routines: Active routines for the day, each with time_slot, duration_min, priority.
        locked_blocks: Existing locked schedule blocks with start_time, end_time.
        day_start: Hour the day starts.
        day_end: Hour the day ends.
        slot_interval: Minimum time block granularity in minutes.
        break_min: Minutes of break to insert between generated blocks.

    Returns:
        List of generated schedule block dicts.
    """
    if slot_interval <= 0:
        slot_interval = 30
    start_min = day_start * 60
    end_min = day_end * 60
    # Round break to slot interval
    break_slots = ((break_min + slot_interval - 1) // slot_interval) * slot_interval if break_min > 0 else 0

    # Build occupied set (in slot_interval chunks)
    occupied = set()
    for block in locked_blocks:
        bs = _time_to_minutes(block["start_time"])
        be = _time_to_minutes(block["end_time"])
        t = bs
        while t < be:
            occupied.add(t)
            t += slot_interval

    # Sort routines: higher priority first, then shorter duration
    sorted_routines = sorted(
        routines,
        key=lambda r: (-r.get("priority", 3), r.get("duration_min", 30)),
    )

    generated = []

    for routine in sorted_routines:
        duration = routine.get("duration_min", 30)
        # Round up to slot_interval
        duration = ((duration + slot_interval - 1) // slot_interval) * slot_interval
        time_slot = routine.get("time_slot", "FLEXIBLE")
        pref_start, pref_end = SLOT_RANGES.get(time_slot, SLOT_RANGES["FLEXIBLE"])
        # Clamp slot ranges to configured day bounds
        pref_start_min = max(pref_start * 60, start_min)
        pref_end_min = min(pref_end * 60, end_min)

        placed = False

        # Try preferred time range first
        for search_start, search_end in [
            (pref_start_min, pref_end_min),
            (start_min, end_min),
        ]:
            if placed:
                break
            t = search_start
            while t + duration <= search_end:
                # Check if all slots are free
                conflict = False
                check = t
                while check < t + duration:
                    if check in occupied:
                        conflict = True
                        break
                    check += slot_interval
                if not conflict:
                    # Place it
                    block = {
                        "start_time": _minutes_to_time(t),
                        "end_time": _minutes_to_time(t + duration),
                        "title": routine["name"],
                        "source": "GENERATED",
                        "routine_id": routine["id"],
                        "priority": routine.get("priority", 3),
                        "is_locked": 0,
                    }
                    generated.append(block)
                    # Mark occupied (including break after)
                    mark = t
                    while mark < t + duration + break_slots:
                        occupied.add(mark)
                        mark += slot_interval
                    placed = True
                    break
                t += slot_interval

    return generated

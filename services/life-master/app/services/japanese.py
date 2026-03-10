"""SM-2 Spaced Repetition + Gamification engine for Japanese learning."""

import math
from datetime import date, timedelta


# ── SM-2 Algorithm ──────────────────────────────────────

def sm2_update(
    quality: int,  # 0-5 (0=complete fail, 5=perfect)
    repetitions: int,
    ease_factor: float,
    interval_days: int,
) -> dict:
    """
    SM-2 spaced repetition algorithm.
    Returns updated card state.
    """
    if quality < 0 or quality > 5:
        raise ValueError("quality must be 0-5")

    if quality >= 3:  # correct
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval_days * ease_factor)
        new_repetitions = repetitions + 1
    else:  # incorrect — reset
        new_interval = 1
        new_repetitions = 0

    new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(1.3, new_ef)

    next_review = (date.today() + timedelta(days=new_interval)).isoformat()

    return {
        "ease_factor": round(new_ef, 2),
        "interval_days": new_interval,
        "repetitions": new_repetitions,
        "next_review": next_review,
    }


# ── Gamification ────────────────────────────────────────

# XP table: quality → base XP
XP_TABLE = {0: 0, 1: 2, 2: 5, 3: 10, 4: 15, 5: 20}

# Level thresholds (XP needed per level)
def xp_for_level(level: int) -> int:
    """XP needed to reach a given level. Exponential growth."""
    return int(100 * (1.5 ** (level - 1)))


def total_xp_for_level(level: int) -> int:
    """Total cumulative XP needed to reach a given level."""
    return sum(xp_for_level(i) for i in range(1, level + 1))


def level_from_xp(total_xp: int) -> int:
    """Calculate level from total XP."""
    level = 1
    accumulated = 0
    while True:
        needed = xp_for_level(level)
        if accumulated + needed > total_xp:
            break
        accumulated += needed
        level += 1
    return level


def calculate_xp(quality: int, combo: int, is_streak_bonus: bool = False) -> dict:
    """
    Calculate XP earned from a single review.
    combo: consecutive correct answers
    """
    base = XP_TABLE.get(quality, 0)

    # Combo multiplier: 5연속 = 1.5x, 10연속 = 2x, 20연속 = 3x
    if combo >= 20:
        combo_mult = 3.0
    elif combo >= 10:
        combo_mult = 2.0
    elif combo >= 5:
        combo_mult = 1.5
    else:
        combo_mult = 1.0

    # Streak bonus (연속 학습일)
    streak_mult = 1.2 if is_streak_bonus else 1.0

    total = int(base * combo_mult * streak_mult)

    return {
        "base_xp": base,
        "combo_multiplier": combo_mult,
        "streak_multiplier": streak_mult,
        "total_xp": total,
        "combo": combo,
    }


# ── Achievements ────────────────────────────────────────

ACHIEVEMENTS = {
    "first_review": {"name": "첫 발걸음", "desc": "첫 번째 복습 완료", "xp_bonus": 50},
    "streak_3": {"name": "3일 연속", "desc": "3일 연속 학습", "xp_bonus": 100},
    "streak_7": {"name": "일주일 달성", "desc": "7일 연속 학습", "xp_bonus": 200},
    "streak_30": {"name": "한 달의 기적", "desc": "30일 연속 학습", "xp_bonus": 500},
    "combo_10": {"name": "콤보 마스터", "desc": "10 콤보 달성", "xp_bonus": 100},
    "combo_20": {"name": "연쇄 격파", "desc": "20 콤보 달성", "xp_bonus": 200},
    "vocab_50": {"name": "단어 수집가", "desc": "50개 단어 학습", "xp_bonus": 150},
    "vocab_100": {"name": "어휘력 100", "desc": "100개 단어 학습", "xp_bonus": 300},
    "vocab_500": {"name": "단어 장인", "desc": "500개 단어 학습", "xp_bonus": 500},
    "n5_clear": {"name": "N5 클리어", "desc": "N5 단어 전부 마스터", "xp_bonus": 1000},
    "n4_clear": {"name": "N4 클리어", "desc": "N4 단어 전부 마스터", "xp_bonus": 1500},
    "n3_clear": {"name": "N3 클리어", "desc": "N3 단어 전부 마스터", "xp_bonus": 2000},
    "n2_clear": {"name": "N2 클리어", "desc": "N2 단어 전부 마스터", "xp_bonus": 3000},
    "n1_clear": {"name": "N1 클리어", "desc": "N1 단어 전부 마스터", "xp_bonus": 5000},
    "quiz_perfect": {"name": "퍼펙트 게임", "desc": "퀴즈 만점 달성", "xp_bonus": 200},
    "time_attack_30": {"name": "스피드러너", "desc": "타임어택 30초 이내 클리어", "xp_bonus": 300},
    "level_10": {"name": "견습생", "desc": "레벨 10 달성", "xp_bonus": 500},
    "level_25": {"name": "중급자", "desc": "레벨 25 달성", "xp_bonus": 1000},
    "level_50": {"name": "달인", "desc": "레벨 50 달성", "xp_bonus": 2000},
    "song_master_5": {"name": "멜로디 학습자", "desc": "5곡으로 학습 완료", "xp_bonus": 300},
    "anime_fan": {"name": "오타쿠 학습법", "desc": "애니/게임 소스 10개 학습", "xp_bonus": 300},
}


def check_achievements(
    current: list[str],
    total_reviews: int,
    total_correct: int,
    streak: int,
    combo_best: int,
    total_xp: int,
    vocab_mastered: int = 0,
    level: int = 1,
    n_levels_cleared: dict | None = None,
) -> list[str]:
    """Check for newly unlocked achievements. Returns list of new achievement IDs."""
    new = []
    n_levels_cleared = n_levels_cleared or {}

    checks = {
        "first_review": total_reviews >= 1,
        "streak_3": streak >= 3,
        "streak_7": streak >= 7,
        "streak_30": streak >= 30,
        "combo_10": combo_best >= 10,
        "combo_20": combo_best >= 20,
        "vocab_50": vocab_mastered >= 50,
        "vocab_100": vocab_mastered >= 100,
        "vocab_500": vocab_mastered >= 500,
        "level_10": level >= 10,
        "level_25": level >= 25,
        "level_50": level >= 50,
    }

    for level_key in ["n5", "n4", "n3", "n2", "n1"]:
        checks[f"{level_key}_clear"] = n_levels_cleared.get(level_key, False)

    for aid, condition in checks.items():
        if condition and aid not in current:
            new.append(aid)

    return new

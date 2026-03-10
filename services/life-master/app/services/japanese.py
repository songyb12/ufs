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


# ── Mastery Tiers ───────────────────────────────────────

MASTERY_TIERS = {
    "unlearned": {"label": "미학습", "icon": "⬜", "min_reps": 0, "min_interval": 0},
    "bronze": {"label": "브론즈", "icon": "🥉", "min_reps": 3, "min_interval": 7},
    "silver": {"label": "실버", "icon": "🥈", "min_reps": 5, "min_interval": 14},
    "gold": {"label": "골드", "icon": "🥇", "min_reps": 8, "min_interval": 30},
    "diamond": {"label": "다이아", "icon": "💎", "min_reps": 12, "min_interval": 60},
    "master": {"label": "마스터", "icon": "👑", "min_reps": 15, "min_interval": 90},
}


def get_mastery_tier(repetitions: int, interval_days: int) -> str:
    """Determine mastery tier based on SRS card state."""
    tier = "unlearned"
    for key in ["bronze", "silver", "gold", "diamond", "master"]:
        t = MASTERY_TIERS[key]
        if repetitions >= t["min_reps"] and interval_days >= t["min_interval"]:
            tier = key
    return tier


def mastery_xp_bonus(tier: str) -> int:
    """XP bonus when reaching a new mastery tier."""
    bonuses = {
        "bronze": 5,
        "silver": 15,
        "gold": 30,
        "diamond": 50,
        "master": 100,
    }
    return bonuses.get(tier, 0)


# ── Gamification ────────────────────────────────────────

# XP table: quality → base XP
XP_TABLE = {0: 0, 1: 2, 2: 5, 3: 10, 4: 15, 5: 20}

# JLPT difficulty multiplier (harder levels = more XP)
JLPT_XP_MULT = {"N5": 1.0, "N4": 1.2, "N3": 1.5, "N2": 2.0, "N1": 2.5}


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


def calculate_xp(
    quality: int,
    combo: int,
    is_streak_bonus: bool = False,
    jlpt_level: str = "N5",
) -> dict:
    """
    Calculate XP earned from a single review.
    combo: consecutive correct answers
    """
    base = XP_TABLE.get(quality, 0)

    # JLPT difficulty multiplier
    jlpt_mult = JLPT_XP_MULT.get(jlpt_level, 1.0)

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

    total = int(base * jlpt_mult * combo_mult * streak_mult)

    return {
        "base_xp": base,
        "jlpt_multiplier": jlpt_mult,
        "combo_multiplier": combo_mult,
        "streak_multiplier": streak_mult,
        "total_xp": total,
        "combo": combo,
    }


# ── Daily Quests ────────────────────────────────────────

DAILY_QUEST_TEMPLATES = [
    {
        "quest_type": "review_count",
        "title": "오늘의 복습",
        "desc": "카드 {target}장 복습하기",
        "target": 10,
        "xp_reward": 50,
        "tier": "basic",
    },
    {
        "quest_type": "review_count",
        "title": "열공 모드",
        "desc": "카드 {target}장 복습하기",
        "target": 30,
        "xp_reward": 120,
        "tier": "challenge",
    },
    {
        "quest_type": "perfect_reviews",
        "title": "완벽한 기억",
        "desc": "quality 5로 {target}장 복습하기",
        "target": 5,
        "xp_reward": 80,
        "tier": "basic",
    },
    {
        "quest_type": "combo_reach",
        "title": "콤보 달성",
        "desc": "{target} 콤보 달성하기",
        "target": 10,
        "xp_reward": 60,
        "tier": "basic",
    },
    {
        "quest_type": "quiz_complete",
        "title": "퀴즈 도전",
        "desc": "퀴즈 {target}회 완료하기",
        "target": 1,
        "xp_reward": 40,
        "tier": "basic",
    },
    {
        "quest_type": "quiz_perfect",
        "title": "퀴즈 퍼펙트",
        "desc": "퀴즈에서 만점 받기",
        "target": 1,
        "xp_reward": 100,
        "tier": "challenge",
    },
    {
        "quest_type": "time_attack_clear",
        "title": "타임어택 클리어",
        "desc": "타임어택 모드 클리어",
        "target": 1,
        "xp_reward": 80,
        "tier": "challenge",
    },
    {
        "quest_type": "boss_clear",
        "title": "보스전 승리",
        "desc": "보스 모드 만점 클리어",
        "target": 1,
        "xp_reward": 150,
        "tier": "hard",
    },
    {
        "quest_type": "accuracy_above",
        "title": "정확도 유지",
        "desc": "오늘 정확도 {target}% 이상",
        "target": 80,
        "xp_reward": 60,
        "tier": "basic",
    },
    {
        "quest_type": "new_vocab_learn",
        "title": "새 단어 도전",
        "desc": "처음 보는 단어 {target}개 학습",
        "target": 5,
        "xp_reward": 70,
        "tier": "basic",
    },
    {
        "quest_type": "review_count",
        "title": "학습 마라톤",
        "desc": "카드 {target}장 복습하기",
        "target": 50,
        "xp_reward": 200,
        "tier": "hard",
    },
    {
        "quest_type": "source_study",
        "title": "콘텐츠 학습",
        "desc": "소스(노래/애니) 기반 학습 {target}회",
        "target": 1,
        "xp_reward": 50,
        "tier": "basic",
    },
]


def generate_daily_quests(player_level: int, current_streak: int) -> list[dict]:
    """Generate 3 daily quests appropriate for player level and streak."""
    import random as _rng

    # Weight harder quests for higher level players
    pool_basic = [q for q in DAILY_QUEST_TEMPLATES if q["tier"] == "basic"]
    pool_challenge = [q for q in DAILY_QUEST_TEMPLATES if q["tier"] == "challenge"]
    pool_hard = [q for q in DAILY_QUEST_TEMPLATES if q["tier"] == "hard"]

    quests = []

    # Always 1 basic quest
    if pool_basic:
        quests.append(_rng.choice(pool_basic))

    # 1 challenge quest (or basic if low level)
    if player_level >= 5 and pool_challenge:
        quests.append(_rng.choice(pool_challenge))
    elif pool_basic:
        pick = _rng.choice([q for q in pool_basic if q not in quests] or pool_basic)
        quests.append(pick)

    # 1 hard quest for high level, or challenge/basic
    if player_level >= 15 and pool_hard:
        quests.append(_rng.choice(pool_hard))
    elif player_level >= 5 and pool_challenge:
        pick = _rng.choice([q for q in pool_challenge if q not in quests] or pool_challenge)
        quests.append(pick)
    elif pool_basic:
        pick = _rng.choice([q for q in pool_basic if q not in quests] or pool_basic)
        quests.append(pick)

    # Streak bonus: extra XP for long streaks
    streak_bonus = 1.0
    if current_streak >= 30:
        streak_bonus = 1.5
    elif current_streak >= 14:
        streak_bonus = 1.3
    elif current_streak >= 7:
        streak_bonus = 1.2

    result = []
    for i, q in enumerate(quests):
        result.append({
            "slot": i,
            "quest_type": q["quest_type"],
            "title": q["title"],
            "desc": q["desc"].format(target=q["target"]),
            "target": q["target"],
            "xp_reward": int(q["xp_reward"] * streak_bonus),
            "tier": q["tier"],
        })
    return result


# ── Weekly Challenge ────────────────────────────────────

WEEKLY_CHALLENGES = [
    {
        "title": "주간 복습왕",
        "desc": "이번 주 총 {target}장 복습",
        "challenge_type": "weekly_review_count",
        "target": 100,
        "xp_reward": 500,
    },
    {
        "title": "7일 연속 학습",
        "desc": "이번 주 매일 학습하기",
        "challenge_type": "weekly_streak",
        "target": 7,
        "xp_reward": 400,
    },
    {
        "title": "퀴즈 마스터",
        "desc": "이번 주 퀴즈 {target}회 완료",
        "challenge_type": "weekly_quiz_count",
        "target": 5,
        "xp_reward": 300,
    },
    {
        "title": "정확도 장인",
        "desc": "이번 주 평균 정확도 {target}% 이상",
        "challenge_type": "weekly_accuracy",
        "target": 85,
        "xp_reward": 350,
    },
    {
        "title": "XP 헌터",
        "desc": "이번 주 총 {target} XP 획득",
        "challenge_type": "weekly_xp",
        "target": 1000,
        "xp_reward": 400,
    },
    {
        "title": "콤보 파이터",
        "desc": "이번 주 최대 콤보 {target} 달성",
        "challenge_type": "weekly_combo",
        "target": 15,
        "xp_reward": 300,
    },
]


def get_weekly_challenge(week_number: int) -> dict:
    """Get the weekly challenge based on week number (rotating)."""
    idx = week_number % len(WEEKLY_CHALLENGES)
    ch = WEEKLY_CHALLENGES[idx]
    return {
        "title": ch["title"],
        "desc": ch["desc"].format(target=ch["target"]),
        "challenge_type": ch["challenge_type"],
        "target": ch["target"],
        "xp_reward": ch["xp_reward"],
    }


# ── Achievements (40+) ─────────────────────────────────

ACHIEVEMENTS = {
    # ── 첫 경험 ──
    "first_review": {"name": "첫 발걸음", "desc": "첫 번째 복습 완료", "xp_bonus": 50, "category": "milestone"},
    "first_quiz": {"name": "첫 퀴즈", "desc": "첫 퀴즈 도전", "xp_bonus": 50, "category": "milestone"},
    "first_perfect": {"name": "첫 만점", "desc": "처음으로 quality 5 달성", "xp_bonus": 30, "category": "milestone"},
    # ── 스트릭 ──
    "streak_3": {"name": "3일 연속", "desc": "3일 연속 학습", "xp_bonus": 100, "category": "streak"},
    "streak_7": {"name": "일주일 달성", "desc": "7일 연속 학습", "xp_bonus": 200, "category": "streak"},
    "streak_14": {"name": "2주의 끈기", "desc": "14일 연속 학습", "xp_bonus": 350, "category": "streak"},
    "streak_30": {"name": "한 달의 기적", "desc": "30일 연속 학습", "xp_bonus": 500, "category": "streak"},
    "streak_60": {"name": "두 달의 집념", "desc": "60일 연속 학습", "xp_bonus": 800, "category": "streak"},
    "streak_100": {"name": "100일의 전설", "desc": "100일 연속 학습", "xp_bonus": 1500, "category": "streak"},
    "streak_365": {"name": "1년의 기적", "desc": "365일 연속 학습", "xp_bonus": 5000, "category": "streak"},
    # ── 콤보 ──
    "combo_10": {"name": "콤보 마스터", "desc": "10 콤보 달성", "xp_bonus": 100, "category": "combo"},
    "combo_20": {"name": "연쇄 격파", "desc": "20 콤보 달성", "xp_bonus": 200, "category": "combo"},
    "combo_50": {"name": "끝없는 연쇄", "desc": "50 콤보 달성", "xp_bonus": 500, "category": "combo"},
    "combo_100": {"name": "전설의 콤보", "desc": "100 콤보 달성", "xp_bonus": 1000, "category": "combo"},
    # ── 단어 학습량 ──
    "vocab_50": {"name": "단어 수집가", "desc": "50개 단어 학습", "xp_bonus": 150, "category": "vocab"},
    "vocab_100": {"name": "어휘력 100", "desc": "100개 단어 학습", "xp_bonus": 300, "category": "vocab"},
    "vocab_300": {"name": "단어 헌터", "desc": "300개 단어 학습", "xp_bonus": 400, "category": "vocab"},
    "vocab_500": {"name": "단어 장인", "desc": "500개 단어 학습", "xp_bonus": 500, "category": "vocab"},
    "vocab_1000": {"name": "사전급 어휘", "desc": "1000개 단어 학습", "xp_bonus": 1000, "category": "vocab"},
    # ── 마스터리 (다이아/마스터 등급 도달) ──
    "mastery_first_gold": {"name": "첫 골드", "desc": "처음으로 골드 등급 달성", "xp_bonus": 100, "category": "mastery"},
    "mastery_first_diamond": {"name": "다이아몬드 탄생", "desc": "처음으로 다이아 등급 달성", "xp_bonus": 300, "category": "mastery"},
    "mastery_first_master": {"name": "마스터 등극", "desc": "처음으로 마스터 등급 달성", "xp_bonus": 500, "category": "mastery"},
    "mastery_10_gold": {"name": "황금의 열 개", "desc": "골드 등급 10개 달성", "xp_bonus": 300, "category": "mastery"},
    "mastery_10_diamond": {"name": "다이아 수집가", "desc": "다이아 등급 10개 달성", "xp_bonus": 500, "category": "mastery"},
    # ── JLPT 레벨 클리어 ──
    "n5_clear": {"name": "N5 클리어", "desc": "N5 단어 전부 마스터", "xp_bonus": 1000, "category": "jlpt"},
    "n4_clear": {"name": "N4 클리어", "desc": "N4 단어 전부 마스터", "xp_bonus": 1500, "category": "jlpt"},
    "n3_clear": {"name": "N3 클리어", "desc": "N3 단어 전부 마스터", "xp_bonus": 2000, "category": "jlpt"},
    "n2_clear": {"name": "N2 클리어", "desc": "N2 단어 전부 마스터", "xp_bonus": 3000, "category": "jlpt"},
    "n1_clear": {"name": "N1 클리어", "desc": "N1 단어 전부 마스터", "xp_bonus": 5000, "category": "jlpt"},
    # ── 퀴즈 ──
    "quiz_perfect": {"name": "퍼펙트 게임", "desc": "퀴즈 만점 달성", "xp_bonus": 200, "category": "quiz"},
    "quiz_10": {"name": "퀴즈 단골", "desc": "퀴즈 10회 완료", "xp_bonus": 150, "category": "quiz"},
    "quiz_50": {"name": "퀴즈 매니아", "desc": "퀴즈 50회 완료", "xp_bonus": 300, "category": "quiz"},
    "quiz_100": {"name": "퀴즈 마스터", "desc": "퀴즈 100회 완료", "xp_bonus": 500, "category": "quiz"},
    "time_attack_30": {"name": "스피드러너", "desc": "타임어택 30초 이내 클리어", "xp_bonus": 300, "category": "quiz"},
    "boss_clear": {"name": "보스 슬레이어", "desc": "보스 모드 만점 클리어", "xp_bonus": 400, "category": "quiz"},
    # ── 레벨 ──
    "level_5": {"name": "초심자", "desc": "레벨 5 달성", "xp_bonus": 200, "category": "level"},
    "level_10": {"name": "견습생", "desc": "레벨 10 달성", "xp_bonus": 500, "category": "level"},
    "level_25": {"name": "중급자", "desc": "레벨 25 달성", "xp_bonus": 1000, "category": "level"},
    "level_50": {"name": "달인", "desc": "레벨 50 달성", "xp_bonus": 2000, "category": "level"},
    "level_100": {"name": "전설", "desc": "레벨 100 달성", "xp_bonus": 5000, "category": "level"},
    # ── 콘텐츠 학습 ──
    "song_master_5": {"name": "멜로디 학습자", "desc": "5곡으로 학습 완료", "xp_bonus": 300, "category": "content"},
    "song_master_15": {"name": "노래방 고수", "desc": "15곡으로 학습 완료", "xp_bonus": 500, "category": "content"},
    "anime_fan": {"name": "오타쿠 학습법", "desc": "애니 소스 10개 학습", "xp_bonus": 300, "category": "content"},
    "anime_master": {"name": "애니 마스터", "desc": "애니 소스 25개 학습", "xp_bonus": 500, "category": "content"},
    "manga_reader": {"name": "만화 독서가", "desc": "만화 소스 10개 학습", "xp_bonus": 300, "category": "content"},
    # ── 데일리 퀘스트 ──
    "daily_quest_first": {"name": "퀘스트 시작", "desc": "첫 데일리 퀘스트 클리어", "xp_bonus": 50, "category": "quest"},
    "daily_quest_7": {"name": "퀘스트 주간왕", "desc": "7일 연속 데일리 퀘스트 클리어", "xp_bonus": 200, "category": "quest"},
    "daily_quest_30": {"name": "퀘스트 월간왕", "desc": "30일 누적 데일리 퀘스트 클리어", "xp_bonus": 500, "category": "quest"},
    # ── 위클리 챌린지 ──
    "weekly_first": {"name": "주간 도전자", "desc": "첫 위클리 챌린지 클리어", "xp_bonus": 100, "category": "quest"},
    "weekly_5": {"name": "위클리 단골", "desc": "위클리 챌린지 5회 클리어", "xp_bonus": 300, "category": "quest"},
    # ── 총 복습 횟수 ──
    "reviews_100": {"name": "100번의 노력", "desc": "총 100회 복습", "xp_bonus": 100, "category": "milestone"},
    "reviews_500": {"name": "500번의 성실", "desc": "총 500회 복습", "xp_bonus": 300, "category": "milestone"},
    "reviews_1000": {"name": "천 번의 반복", "desc": "총 1000회 복습", "xp_bonus": 500, "category": "milestone"},
    "reviews_5000": {"name": "만렙 복습러", "desc": "총 5000회 복습", "xp_bonus": 1000, "category": "milestone"},
    # ── 정확도 ──
    "accuracy_90": {"name": "정밀 사격", "desc": "누적 정확도 90% 이상 (100회+)", "xp_bonus": 300, "category": "performance"},
    "accuracy_95": {"name": "신의 기억력", "desc": "누적 정확도 95% 이상 (200회+)", "xp_bonus": 500, "category": "performance"},
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
    quiz_count: int = 0,
    daily_quests_completed: int = 0,
    weekly_challenges_completed: int = 0,
    mastery_counts: dict | None = None,
) -> list[str]:
    """Check for newly unlocked achievements. Returns list of new achievement IDs."""
    new = []
    n_levels_cleared = n_levels_cleared or {}
    mastery_counts = mastery_counts or {}

    accuracy = (total_correct / total_reviews * 100) if total_reviews > 0 else 0

    checks = {
        # Milestones
        "first_review": total_reviews >= 1,
        "first_perfect": total_correct >= 1,
        "reviews_100": total_reviews >= 100,
        "reviews_500": total_reviews >= 500,
        "reviews_1000": total_reviews >= 1000,
        "reviews_5000": total_reviews >= 5000,
        # Streaks
        "streak_3": streak >= 3,
        "streak_7": streak >= 7,
        "streak_14": streak >= 14,
        "streak_30": streak >= 30,
        "streak_60": streak >= 60,
        "streak_100": streak >= 100,
        "streak_365": streak >= 365,
        # Combos
        "combo_10": combo_best >= 10,
        "combo_20": combo_best >= 20,
        "combo_50": combo_best >= 50,
        "combo_100": combo_best >= 100,
        # Vocab mastery
        "vocab_50": vocab_mastered >= 50,
        "vocab_100": vocab_mastered >= 100,
        "vocab_300": vocab_mastered >= 300,
        "vocab_500": vocab_mastered >= 500,
        "vocab_1000": vocab_mastered >= 1000,
        # Mastery tiers
        "mastery_first_gold": mastery_counts.get("gold", 0) >= 1,
        "mastery_first_diamond": mastery_counts.get("diamond", 0) >= 1,
        "mastery_first_master": mastery_counts.get("master", 0) >= 1,
        "mastery_10_gold": mastery_counts.get("gold", 0) >= 10,
        "mastery_10_diamond": mastery_counts.get("diamond", 0) >= 10,
        # Levels
        "level_5": level >= 5,
        "level_10": level >= 10,
        "level_25": level >= 25,
        "level_50": level >= 50,
        "level_100": level >= 100,
        # Quizzes
        "quiz_10": quiz_count >= 10,
        "quiz_50": quiz_count >= 50,
        "quiz_100": quiz_count >= 100,
        # Daily quests
        "daily_quest_first": daily_quests_completed >= 1,
        "daily_quest_30": daily_quests_completed >= 30,
        # Weekly challenges
        "weekly_first": weekly_challenges_completed >= 1,
        "weekly_5": weekly_challenges_completed >= 5,
        # Accuracy
        "accuracy_90": accuracy >= 90 and total_reviews >= 100,
        "accuracy_95": accuracy >= 95 and total_reviews >= 200,
    }

    for level_key in ["n5", "n4", "n3", "n2", "n1"]:
        checks[f"{level_key}_clear"] = n_levels_cleared.get(level_key, False)

    for aid, condition in checks.items():
        if condition and aid not in current:
            new.append(aid)

    return new

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


# ── Title System (애니 RPG 스타일) ─────────────────────

TITLES = [
    # (min_level, title_ja, title_ko, flavor_text)
    (1, "入門者", "입문자", "모험이 시작됐다!"),
    (3, "初心者", "초심자", "첫 걸음을 떼었다"),
    (5, "見習い冒険者", "견습 모험가", "던전의 문이 열린다"),
    (8, "言葉の旅人", "언어의 여행자", "새로운 세계가 보이기 시작한다"),
    (10, "語学の戦士", "어학의 전사", "기초를 다진 전사, 중급 던전으로"),
    (13, "漢字ハンター", "한자 헌터", "한자가 두렵지 않다"),
    (15, "中級冒険者", "중급 모험가", "중급의 벽을 돌파하기 시작"),
    (18, "文法マスター", "문법 마스터", "문법이라는 적을 제압"),
    (20, "読解の騎士", "독해의 기사", "문장을 베어내는 검술"),
    (23, "単語の魔術師", "단어의 마법사", "단어를 자유자재로 다루는 힘"),
    (25, "上級学習者", "상급 학습자", "상급 던전의 문턱에 섰다"),
    (28, "言霊の使い手", "코토다마의 사용자", "말에 영혼이 깃든다"),
    (30, "語学の勇者", "어학의 용사", "마왕에게 도전할 자격"),
    (33, "漢字の達人", "한자의 달인", "한자 미궁도 두렵지 않다"),
    (35, "敬語の賢者", "경어의 현자", "존경어와 겸양어를 마스터"),
    (38, "多読の覇者", "다독의 패자", "텍스트를 지배하는 자"),
    (40, "言語マスター", "언어 마스터", "일본어의 심연에 도달"),
    (43, "翻訳の鬼", "번역의 귀신", "원문과 번역을 넘나든다"),
    (45, "文豪", "문호", "말과 글의 장인"),
    (48, "伝説の学習者", "전설의 학습자", "전설로 남을 학습 기록"),
    (50, "日本語の達人", "일본어의 달인", "달인의 경지에 올라섰다"),
    (55, "言葉の鬼神", "언어의 귀신", "인간의 한계를 초월"),
    (60, "万巻の書を読む者", "만권독파자", "만 권을 읽은 자의 경지"),
    (70, "語学の神", "어학의 신", "신의 영역에 발을 딛다"),
    (80, "異世界の住人", "이세계의 주민", "일본어가 모국어처럼"),
    (90, "全知全能", "전지전능", "모든 단어를 꿰뚫는 자"),
    (100, "日本語の王", "일본어의 왕", "이 세상 일본어의 정점"),
]


def get_player_title(level: int) -> dict:
    """Get the player's title based on level. Returns the highest matching title."""
    result = TITLES[0]
    for min_lv, title_ja, title_ko, flavor in TITLES:
        if level >= min_lv:
            result = (min_lv, title_ja, title_ko, flavor)
    return {
        "title_ja": result[1],
        "title_ko": result[2],
        "flavor_text": result[3],
        "min_level": result[0],
    }


# ── Daily Quests (재미있는 퀘스트) ─────────────────────

DAILY_QUEST_TEMPLATES = [
    # ── basic ──
    {
        "quest_type": "review_count",
        "title": "오늘의 복습",
        "desc": "카드 {target}장 복습하기",
        "target": 10,
        "xp_reward": 50,
        "tier": "basic",
    },
    {
        "quest_type": "perfect_reviews",
        "title": "완벽한 기억",
        "desc": "quality 5로 {target}장 복습",
        "target": 5,
        "xp_reward": 80,
        "tier": "basic",
    },
    {
        "quest_type": "combo_reach",
        "title": "콤보 스타터",
        "desc": "{target} 콤보 달성",
        "target": 5,
        "xp_reward": 40,
        "tier": "basic",
    },
    {
        "quest_type": "quiz_complete",
        "title": "퀴즈 한 판!",
        "desc": "퀴즈 {target}회 도전",
        "target": 1,
        "xp_reward": 40,
        "tier": "basic",
    },
    {
        "quest_type": "new_vocab_learn",
        "title": "미지의 단어",
        "desc": "새 단어 {target}개 학습",
        "target": 5,
        "xp_reward": 70,
        "tier": "basic",
    },
    {
        "quest_type": "source_study",
        "title": "노래/애니로 배우기",
        "desc": "소스 기반 학습 {target}회",
        "target": 1,
        "xp_reward": 50,
        "tier": "basic",
    },
    {
        "quest_type": "review_count",
        "title": "아침 복습",
        "desc": "카드 {target}장 복습으로 시작",
        "target": 5,
        "xp_reward": 30,
        "tier": "basic",
    },
    {
        "quest_type": "accuracy_above",
        "title": "실수 금지",
        "desc": "오늘 정확도 {target}% 이상 유지",
        "target": 80,
        "xp_reward": 60,
        "tier": "basic",
    },
    # ── challenge ──
    {
        "quest_type": "review_count",
        "title": "열공 모드",
        "desc": "카드 {target}장 복습!",
        "target": 30,
        "xp_reward": 120,
        "tier": "challenge",
    },
    {
        "quest_type": "combo_reach",
        "title": "콤보의 폭풍",
        "desc": "{target} 콤보 돌파!",
        "target": 15,
        "xp_reward": 100,
        "tier": "challenge",
    },
    {
        "quest_type": "quiz_perfect",
        "title": "퀴즈 퍼펙트",
        "desc": "퀴즈에서 만점!",
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
        "quest_type": "perfect_reviews",
        "title": "연속 만점",
        "desc": "quality 5를 {target}번 연속!",
        "target": 10,
        "xp_reward": 150,
        "tier": "challenge",
    },
    {
        "quest_type": "accuracy_above",
        "title": "정밀 사격",
        "desc": "정확도 {target}% 이상",
        "target": 90,
        "xp_reward": 100,
        "tier": "challenge",
    },
    {
        "quest_type": "new_vocab_learn",
        "title": "단어 탐험대",
        "desc": "새 단어 {target}개 정복",
        "target": 10,
        "xp_reward": 120,
        "tier": "challenge",
    },
    # ── hard ──
    {
        "quest_type": "review_count",
        "title": "학습 마라톤",
        "desc": "카드 {target}장 총력전!",
        "target": 50,
        "xp_reward": 200,
        "tier": "hard",
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
        "quest_type": "combo_reach",
        "title": "전설의 콤보",
        "desc": "{target} 콤보 달성!",
        "target": 25,
        "xp_reward": 180,
        "tier": "hard",
    },
    {
        "quest_type": "review_count",
        "title": "극한 수행",
        "desc": "카드 {target}장... 가능한가?",
        "target": 100,
        "xp_reward": 400,
        "tier": "hard",
    },
    {
        "quest_type": "perfect_reviews",
        "title": "완벽주의자",
        "desc": "quality 5를 {target}번!",
        "target": 20,
        "xp_reward": 250,
        "tier": "hard",
    },
]


def generate_daily_quests(player_level: int, current_streak: int) -> list[dict]:
    """Generate 3 daily quests appropriate for player level and streak."""
    import random as _rng

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


# ── Weekly Challenge (더 다양하게) ──────────────────────

WEEKLY_CHALLENGES = [
    {
        "title": "주간 복습왕",
        "desc": "이번 주 총 {target}장 복습 — 양이 질을 만든다",
        "challenge_type": "weekly_review_count",
        "target": 100,
        "xp_reward": 500,
    },
    {
        "title": "7일 연속 출석",
        "desc": "매일 학습 — 하루도 빼먹지 마!",
        "challenge_type": "weekly_streak",
        "target": 7,
        "xp_reward": 400,
    },
    {
        "title": "퀴즈 마스터",
        "desc": "이번 주 퀴즈 {target}회 — 실전 감각 키우기",
        "challenge_type": "weekly_quiz_count",
        "target": 5,
        "xp_reward": 300,
    },
    {
        "title": "정확도 장인",
        "desc": "주간 평균 정확도 {target}% — 한 글자도 틀리지 마",
        "challenge_type": "weekly_accuracy",
        "target": 85,
        "xp_reward": 350,
    },
    {
        "title": "XP 헌터",
        "desc": "이번 주 총 {target} XP — 경험치 수확기",
        "challenge_type": "weekly_xp",
        "target": 1000,
        "xp_reward": 400,
    },
    {
        "title": "콤보 파이터",
        "desc": "주간 최대 콤보 {target} — 끊기지 않는 집중력",
        "challenge_type": "weekly_combo",
        "target": 15,
        "xp_reward": 300,
    },
    {
        "title": "다독 챌린지",
        "desc": "이번 주 {target}장 이상 복습 — 양으로 밀어붙여!",
        "challenge_type": "weekly_review_count",
        "target": 200,
        "xp_reward": 800,
    },
    {
        "title": "퀴즈 폭격기",
        "desc": "이번 주 퀴즈 {target}회 완료",
        "challenge_type": "weekly_quiz_count",
        "target": 10,
        "xp_reward": 500,
    },
    {
        "title": "정밀 타격",
        "desc": "주간 정확도 {target}% 이상 유지 — 실수는 사치",
        "challenge_type": "weekly_accuracy",
        "target": 92,
        "xp_reward": 500,
    },
    {
        "title": "XP 폭주",
        "desc": "이번 주 {target} XP — 경험치를 태워라",
        "challenge_type": "weekly_xp",
        "target": 2000,
        "xp_reward": 700,
    },
    {
        "title": "콤보 킹",
        "desc": "주간 최대 콤보 {target} — 전설의 콤보에 도전",
        "challenge_type": "weekly_combo",
        "target": 30,
        "xp_reward": 600,
    },
    {
        "title": "매일 학습 + 퀴즈",
        "desc": "이번 주 매일 학습 + 퀴즈 {target}회",
        "challenge_type": "weekly_quiz_count",
        "target": 7,
        "xp_reward": 450,
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


# ── Achievements (80+ 재미있는 이름들) ─────────────────

ACHIEVEMENTS = {
    # ═══════════════════════════════════════════
    # 첫 경험 — 튜토리얼 업적
    # ═══════════════════════════════════════════
    "first_review": {
        "name": "첫 발걸음",
        "desc": "첫 번째 복습 완료 — 천 리 길도 한 걸음부터",
        "xp_bonus": 50, "category": "milestone", "rarity": "common",
    },
    "first_quiz": {
        "name": "퀴즈 입문",
        "desc": "첫 퀴즈 도전 — 도전하는 자만이 성장한다",
        "xp_bonus": 50, "category": "milestone", "rarity": "common",
    },
    "first_perfect": {
        "name": "첫 만점",
        "desc": "처음으로 quality 5 — 완벽한 순간",
        "xp_bonus": 30, "category": "milestone", "rarity": "common",
    },
    "first_source": {
        "name": "콘텐츠 학습자",
        "desc": "소스(노래/애니)로 처음 학습 — 재미있는 방법이지?",
        "xp_bonus": 50, "category": "milestone", "rarity": "common",
    },

    # ═══════════════════════════════════════════
    # 스트릭 — 매일매일의 근성
    # ═══════════════════════════════════════════
    "streak_3": {
        "name": "3일 연속!",
        "desc": "3일 연속 학습 — 습관의 시작",
        "xp_bonus": 100, "category": "streak", "rarity": "common",
    },
    "streak_7": {
        "name": "일주일 달성",
        "desc": "7일 연속 — 루피: '계속 가자!!'",
        "xp_bonus": 200, "category": "streak", "rarity": "uncommon",
    },
    "streak_14": {
        "name": "2주의 끈기",
        "desc": "14일 연속 — 카카시: '대단한 근성이군'",
        "xp_bonus": 350, "category": "streak", "rarity": "uncommon",
    },
    "streak_21": {
        "name": "3주 연속!",
        "desc": "21일이면 습관이 된다 — 과학적으로 입증!",
        "xp_bonus": 400, "category": "streak", "rarity": "uncommon",
    },
    "streak_30": {
        "name": "한 달의 기적",
        "desc": "30일 연속 — 안자이 선생: '포기하면 거기서 끝이에요'",
        "xp_bonus": 500, "category": "streak", "rarity": "rare",
    },
    "streak_60": {
        "name": "두 달의 집념",
        "desc": "60일 연속 — 에렌: '전진하라!'",
        "xp_bonus": 800, "category": "streak", "rarity": "rare",
    },
    "streak_100": {
        "name": "100일의 전설",
        "desc": "100일 연속 — 리바이: '완벽한 선택이었다'",
        "xp_bonus": 1500, "category": "streak", "rarity": "epic",
    },
    "streak_200": {
        "name": "200일 — 불굴의 의지",
        "desc": "200일 연속 — 이 정도면 달인 아닌가?",
        "xp_bonus": 3000, "category": "streak", "rarity": "epic",
    },
    "streak_365": {
        "name": "1년의 전설",
        "desc": "365일 연속 — 고죠: '최강이야'",
        "xp_bonus": 5000, "category": "streak", "rarity": "legendary",
    },

    # ═══════════════════════════════════════════
    # 콤보 — 끊기지 않는 집중력
    # ═══════════════════════════════════════════
    "combo_5": {
        "name": "콤보 개시!",
        "desc": "5 콤보 — 워밍업 완료",
        "xp_bonus": 30, "category": "combo", "rarity": "common",
    },
    "combo_10": {
        "name": "콤보 마스터",
        "desc": "10 콤보 — 집중력 ON",
        "xp_bonus": 100, "category": "combo", "rarity": "common",
    },
    "combo_20": {
        "name": "연쇄 격파",
        "desc": "20 콤보 — 사쿠라기: '천재니까!'",
        "xp_bonus": 200, "category": "combo", "rarity": "uncommon",
    },
    "combo_30": {
        "name": "무쌍 모드",
        "desc": "30 콤보 — 멈출 수가 없다!",
        "xp_bonus": 300, "category": "combo", "rarity": "uncommon",
    },
    "combo_50": {
        "name": "끝없는 연쇄",
        "desc": "50 콤보 — 히나타: '난 날 수 있어!'",
        "xp_bonus": 500, "category": "combo", "rarity": "rare",
    },
    "combo_100": {
        "name": "전설의 콤보",
        "desc": "100 콤보 — 올마이트: '내가 왔다!'",
        "xp_bonus": 1000, "category": "combo", "rarity": "epic",
    },

    # ═══════════════════════════════════════════
    # 단어 학습량 — 어휘력의 성장
    # ═══════════════════════════════════════════
    "vocab_10": {
        "name": "단어 입문",
        "desc": "10개 단어 학습 — 시작이 좋아",
        "xp_bonus": 50, "category": "vocab", "rarity": "common",
    },
    "vocab_50": {
        "name": "단어 수집가",
        "desc": "50개 — 기초 어휘 확보",
        "xp_bonus": 150, "category": "vocab", "rarity": "common",
    },
    "vocab_100": {
        "name": "어휘력 100",
        "desc": "100개 — 대화가 가능해지기 시작",
        "xp_bonus": 300, "category": "vocab", "rarity": "uncommon",
    },
    "vocab_200": {
        "name": "단어 사냥꾼",
        "desc": "200개 — 읽기가 자연스러워진다",
        "xp_bonus": 350, "category": "vocab", "rarity": "uncommon",
    },
    "vocab_300": {
        "name": "단어 헌터",
        "desc": "300개 — 뉴스도 슬슬 읽힌다",
        "xp_bonus": 400, "category": "vocab", "rarity": "uncommon",
    },
    "vocab_500": {
        "name": "단어 장인",
        "desc": "500개 — 소설을 읽을 수 있다",
        "xp_bonus": 500, "category": "vocab", "rarity": "rare",
    },
    "vocab_1000": {
        "name": "사전급 어휘",
        "desc": "1000개 — 걸어다니는 사전",
        "xp_bonus": 1000, "category": "vocab", "rarity": "epic",
    },
    "vocab_2000": {
        "name": "어휘 제왕",
        "desc": "2000개 — 원어민에 가까운 어휘력",
        "xp_bonus": 2000, "category": "vocab", "rarity": "legendary",
    },

    # ═══════════════════════════════════════════
    # 마스터리 티어 — 단어를 완전히 정복
    # ═══════════════════════════════════════════
    "mastery_first_bronze": {
        "name": "첫 브론즈",
        "desc": "첫 브론즈 등급 — 기억의 싹이 트다",
        "xp_bonus": 30, "category": "mastery", "rarity": "common",
    },
    "mastery_first_silver": {
        "name": "첫 실버",
        "desc": "첫 실버 등급 — 기억이 단단해지고 있다",
        "xp_bonus": 50, "category": "mastery", "rarity": "common",
    },
    "mastery_first_gold": {
        "name": "첫 골드!",
        "desc": "첫 골드 등급 — 이 단어는 완전히 내 것",
        "xp_bonus": 100, "category": "mastery", "rarity": "uncommon",
    },
    "mastery_first_diamond": {
        "name": "다이아몬드 탄생",
        "desc": "첫 다이아 — 영구적으로 기억에 새긴 단어",
        "xp_bonus": 300, "category": "mastery", "rarity": "rare",
    },
    "mastery_first_master": {
        "name": "마스터 등극",
        "desc": "첫 마스터 — 이 단어는 네 몸의 일부다",
        "xp_bonus": 500, "category": "mastery", "rarity": "epic",
    },
    "mastery_10_gold": {
        "name": "황금의 열 개",
        "desc": "골드 10개 — 금메달 컬렉터",
        "xp_bonus": 300, "category": "mastery", "rarity": "uncommon",
    },
    "mastery_10_diamond": {
        "name": "다이아 수집가",
        "desc": "다이아 10개 — 보석함이 빛난다",
        "xp_bonus": 500, "category": "mastery", "rarity": "rare",
    },
    "mastery_50_gold": {
        "name": "골드 러시",
        "desc": "골드 50개 — 금광을 발견했다!",
        "xp_bonus": 800, "category": "mastery", "rarity": "rare",
    },
    "mastery_10_master": {
        "name": "마스터 컬렉터",
        "desc": "마스터 10개 — 전문가의 증표",
        "xp_bonus": 1000, "category": "mastery", "rarity": "epic",
    },

    # ═══════════════════════════════════════════
    # JLPT 레벨 클리어 — 최종 보스전
    # ═══════════════════════════════════════════
    "n5_clear": {
        "name": "N5 클리어!",
        "desc": "N5 완전 마스터 — 첫 번째 보스 격파!",
        "xp_bonus": 1000, "category": "jlpt", "rarity": "rare",
    },
    "n4_clear": {
        "name": "N4 클리어!",
        "desc": "N4 완전 마스터 — 기초를 넘어선다",
        "xp_bonus": 1500, "category": "jlpt", "rarity": "rare",
    },
    "n3_clear": {
        "name": "N3 클리어!",
        "desc": "N3 완전 마스터 — 중급의 벽을 돌파",
        "xp_bonus": 2000, "category": "jlpt", "rarity": "epic",
    },
    "n2_clear": {
        "name": "N2 클리어!",
        "desc": "N2 완전 마스터 — 상급자의 영역",
        "xp_bonus": 3000, "category": "jlpt", "rarity": "epic",
    },
    "n1_clear": {
        "name": "N1 클리어!!",
        "desc": "N1 완전 마스터 — 최종 보스 격파! 전설이 되었다",
        "xp_bonus": 5000, "category": "jlpt", "rarity": "legendary",
    },

    # ═══════════════════════════════════════════
    # 퀴즈 — 실전의 감각
    # ═══════════════════════════════════════════
    "quiz_perfect": {
        "name": "퍼펙트 게임",
        "desc": "퀴즈 만점 — 실수는 없었다",
        "xp_bonus": 200, "category": "quiz", "rarity": "uncommon",
    },
    "quiz_3_perfect": {
        "name": "연속 만점",
        "desc": "만점 3회 연속 — 흔들림 없는 실력",
        "xp_bonus": 400, "category": "quiz", "rarity": "rare",
    },
    "quiz_10": {
        "name": "퀴즈 단골",
        "desc": "퀴즈 10회 — 퀴즈가 일상이 되다",
        "xp_bonus": 150, "category": "quiz", "rarity": "common",
    },
    "quiz_50": {
        "name": "퀴즈 매니아",
        "desc": "퀴즈 50회 — 문제를 보면 반사적으로 답이",
        "xp_bonus": 300, "category": "quiz", "rarity": "uncommon",
    },
    "quiz_100": {
        "name": "퀴즈 마스터",
        "desc": "퀴즈 100회 — 이제 퀴즈가 널 시험하는 게 아니라 네가 퀴즈를 시험한다",
        "xp_bonus": 500, "category": "quiz", "rarity": "rare",
    },
    "time_attack_30": {
        "name": "스피드러너",
        "desc": "타임어택 30초 이내 — 반사신경의 극한",
        "xp_bonus": 300, "category": "quiz", "rarity": "rare",
    },
    "time_attack_15": {
        "name": "섬광의 응답",
        "desc": "타임어택 15초 이내 — 빛보다 빠른 반응",
        "xp_bonus": 500, "category": "quiz", "rarity": "epic",
    },
    "boss_clear": {
        "name": "보스 슬레이어",
        "desc": "보스 모드 만점 — 보스를 쓰러뜨렸다!",
        "xp_bonus": 400, "category": "quiz", "rarity": "rare",
    },
    "boss_clear_5": {
        "name": "보스 헌터",
        "desc": "보스 모드 5회 만점 클리어 — 보스가 널 무서워한다",
        "xp_bonus": 800, "category": "quiz", "rarity": "epic",
    },

    # ═══════════════════════════════════════════
    # 레벨 — 성장의 이정표
    # ═══════════════════════════════════════════
    "level_5": {
        "name": "견습 모험가",
        "desc": "레벨 5 — 모험이 시작됐다",
        "xp_bonus": 200, "category": "level", "rarity": "common",
    },
    "level_10": {
        "name": "어학의 전사",
        "desc": "레벨 10 — '진정한 전사는 매일 검을 간다'",
        "xp_bonus": 500, "category": "level", "rarity": "uncommon",
    },
    "level_15": {
        "name": "중급 돌파",
        "desc": "레벨 15 — 중급의 벽을 넘기 시작",
        "xp_bonus": 700, "category": "level", "rarity": "uncommon",
    },
    "level_20": {
        "name": "독해의 기사",
        "desc": "레벨 20 — 원문이 읽히기 시작한다!",
        "xp_bonus": 800, "category": "level", "rarity": "uncommon",
    },
    "level_25": {
        "name": "상급 학습자",
        "desc": "레벨 25 — 나루토: '이게 내 닌자도다!'",
        "xp_bonus": 1000, "category": "level", "rarity": "rare",
    },
    "level_30": {
        "name": "어학의 용사",
        "desc": "레벨 30 — 마왕(N1)에게 도전할 자격",
        "xp_bonus": 1200, "category": "level", "rarity": "rare",
    },
    "level_40": {
        "name": "언어 마스터",
        "desc": "레벨 40 — 일본어의 심연에 도달",
        "xp_bonus": 1500, "category": "level", "rarity": "epic",
    },
    "level_50": {
        "name": "달인",
        "desc": "레벨 50 — '일본어의 달인' 칭호 획득!",
        "xp_bonus": 2000, "category": "level", "rarity": "epic",
    },
    "level_75": {
        "name": "언어의 귀신",
        "desc": "레벨 75 — 인간의 한계를 초월하는 중",
        "xp_bonus": 3000, "category": "level", "rarity": "legendary",
    },
    "level_100": {
        "name": "일본어의 왕",
        "desc": "레벨 100 — 이 세상 일본어의 정점에 서다",
        "xp_bonus": 5000, "category": "level", "rarity": "legendary",
    },

    # ═══════════════════════════════════════════
    # 콘텐츠 학습 — 노래/애니/만화로 배우기
    # ═══════════════════════════════════════════
    "song_master_3": {
        "name": "음악 학습자",
        "desc": "3곡으로 학습 — 노래로 외우면 잊히지 않는다",
        "xp_bonus": 150, "category": "content", "rarity": "common",
    },
    "song_master_5": {
        "name": "멜로디 학습자",
        "desc": "5곡으로 학습 — 흥얼거리면서 복습",
        "xp_bonus": 300, "category": "content", "rarity": "uncommon",
    },
    "song_master_15": {
        "name": "노래방 고수",
        "desc": "15곡으로 학습 — 일본 노래방에서 부를 수 있다",
        "xp_bonus": 500, "category": "content", "rarity": "rare",
    },
    "song_master_25": {
        "name": "JPOP 마스터",
        "desc": "25곡으로 학습 — 오리콘 차트를 섭렵",
        "xp_bonus": 800, "category": "content", "rarity": "epic",
    },
    "anime_fan_5": {
        "name": "애니 입문자",
        "desc": "애니 소스 5개 학습 — 자막 없이 도전 시작!",
        "xp_bonus": 150, "category": "content", "rarity": "common",
    },
    "anime_fan": {
        "name": "오타쿠 학습법",
        "desc": "애니 소스 10개 학습 — 덕후력으로 일본어 습득",
        "xp_bonus": 300, "category": "content", "rarity": "uncommon",
    },
    "anime_master": {
        "name": "애니 마스터",
        "desc": "애니 소스 25개 — 자막 없이 애니를 본다",
        "xp_bonus": 500, "category": "content", "rarity": "rare",
    },
    "manga_reader_5": {
        "name": "만화 독서 시작",
        "desc": "만화 소스 5개 학습 — 원작으로 읽는 맛",
        "xp_bonus": 150, "category": "content", "rarity": "common",
    },
    "manga_reader": {
        "name": "만화 독서가",
        "desc": "만화 소스 10개 — 원서 만화를 즐긴다",
        "xp_bonus": 300, "category": "content", "rarity": "uncommon",
    },
    "manga_master": {
        "name": "만화 마스터",
        "desc": "만화 소스 20개 — 일본 서점이 놀이터",
        "xp_bonus": 500, "category": "content", "rarity": "rare",
    },
    "game_player": {
        "name": "게임 학습자",
        "desc": "게임 소스 5개 학습 — 게임하면서 일본어를",
        "xp_bonus": 200, "category": "content", "rarity": "uncommon",
    },
    "all_rounder": {
        "name": "올라운더",
        "desc": "노래+애니+만화+게임 모두 학습 — 진정한 일본 문화 마스터",
        "xp_bonus": 500, "category": "content", "rarity": "rare",
    },

    # ═══════════════════════════════════════════
    # 데일리 퀘스트 & 위클리
    # ═══════════════════════════════════════════
    "daily_quest_first": {
        "name": "퀘스트 시작",
        "desc": "첫 데일리 퀘스트 클리어 — 오늘의 미션 완료!",
        "xp_bonus": 50, "category": "quest", "rarity": "common",
    },
    "daily_quest_7": {
        "name": "퀘스트 주간왕",
        "desc": "7일 연속 데일리 클리어 — 일주일 개근!",
        "xp_bonus": 200, "category": "quest", "rarity": "uncommon",
    },
    "daily_quest_30": {
        "name": "퀘스트 월간왕",
        "desc": "30일 누적 클리어 — 꾸준함이 최고의 무기",
        "xp_bonus": 500, "category": "quest", "rarity": "rare",
    },
    "daily_quest_100": {
        "name": "퀘스트 헌터",
        "desc": "100일 누적 클리어 — 퀘스트가 생활이 되었다",
        "xp_bonus": 1000, "category": "quest", "rarity": "epic",
    },
    "weekly_first": {
        "name": "주간 도전자",
        "desc": "첫 위클리 챌린지 클리어",
        "xp_bonus": 100, "category": "quest", "rarity": "common",
    },
    "weekly_5": {
        "name": "위클리 단골",
        "desc": "위클리 5회 클리어 — 매주 도전하는 습관",
        "xp_bonus": 300, "category": "quest", "rarity": "uncommon",
    },
    "weekly_10": {
        "name": "위클리 마스터",
        "desc": "위클리 10회 클리어 — 10주의 기록",
        "xp_bonus": 500, "category": "quest", "rarity": "rare",
    },

    # ═══════════════════════════════════════════
    # 총 복습 횟수 — 순수한 노력의 증거
    # ═══════════════════════════════════════════
    "reviews_50": {
        "name": "반복의 시작",
        "desc": "50회 복습 — 반복은 배신하지 않는다",
        "xp_bonus": 50, "category": "milestone", "rarity": "common",
    },
    "reviews_100": {
        "name": "100번의 노력",
        "desc": "100회 — 3자릿수 돌파!",
        "xp_bonus": 100, "category": "milestone", "rarity": "common",
    },
    "reviews_500": {
        "name": "500번의 성실",
        "desc": "500회 — 진짜 실력이 붙기 시작",
        "xp_bonus": 300, "category": "milestone", "rarity": "uncommon",
    },
    "reviews_1000": {
        "name": "천 번의 반복",
        "desc": "1000회 — 千里の道も一歩から",
        "xp_bonus": 500, "category": "milestone", "rarity": "rare",
    },
    "reviews_2500": {
        "name": "불굴의 학습자",
        "desc": "2500회 — 에이스: '살아있어서 다행이야'",
        "xp_bonus": 700, "category": "milestone", "rarity": "rare",
    },
    "reviews_5000": {
        "name": "만렙 복습러",
        "desc": "5000회 — 수행의 극치",
        "xp_bonus": 1000, "category": "milestone", "rarity": "epic",
    },
    "reviews_10000": {
        "name": "일만 번의 수련",
        "desc": "10000회 — 一万回の練習が本物を作る",
        "xp_bonus": 2000, "category": "milestone", "rarity": "legendary",
    },

    # ═══════════════════════════════════════════
    # 정확도 — 질의 증명
    # ═══════════════════════════════════════════
    "accuracy_80": {
        "name": "안정적 학습",
        "desc": "누적 정확도 80%+ (50회+) — 실수가 줄어든다",
        "xp_bonus": 150, "category": "performance", "rarity": "common",
    },
    "accuracy_90": {
        "name": "정밀 사격",
        "desc": "누적 정확도 90%+ (100회+) — 거의 틀리지 않는다",
        "xp_bonus": 300, "category": "performance", "rarity": "uncommon",
    },
    "accuracy_95": {
        "name": "신의 기억력",
        "desc": "누적 정확도 95%+ (200회+) — L: '확률은 95% 이상'",
        "xp_bonus": 500, "category": "performance", "rarity": "rare",
    },
    "accuracy_99": {
        "name": "무결점",
        "desc": "누적 정확도 99%+ (500회+) — 완벽에 가까운 기억",
        "xp_bonus": 1000, "category": "performance", "rarity": "epic",
    },

    # ═══════════════════════════════════════════
    # 히든 업적 — 특정 조건에서만 달성
    # ═══════════════════════════════════════════
    "night_owl": {
        "name": "올빼미 학습자",
        "desc": "자정 이후 학습 — 밤은 집중의 시간",
        "xp_bonus": 100, "category": "hidden", "rarity": "uncommon",
    },
    "early_bird": {
        "name": "아침형 인간",
        "desc": "오전 6시 이전 학습 — 새벽의 전사",
        "xp_bonus": 100, "category": "hidden", "rarity": "uncommon",
    },
    "weekend_warrior": {
        "name": "주말 전사",
        "desc": "주말에 50장 이상 복습 — 쉬는 날에도 학습!",
        "xp_bonus": 200, "category": "hidden", "rarity": "uncommon",
    },
    "comeback_kid": {
        "name": "컴백 키드",
        "desc": "스트릭이 끊긴 후 다시 3일 연속 학습 — 넘어져도 일어난다",
        "xp_bonus": 150, "category": "hidden", "rarity": "uncommon",
    },
    "speed_demon": {
        "name": "스피드 데몬",
        "desc": "평균 응답시간 2초 이내로 10장 복습 — 번개같은 반응",
        "xp_bonus": 300, "category": "hidden", "rarity": "rare",
    },
    "xp_millionaire": {
        "name": "백만장자",
        "desc": "총 XP 1,000,000 돌파 — 부자가 되었다!",
        "xp_bonus": 5000, "category": "hidden", "rarity": "legendary",
    },
    "all_n_clear": {
        "name": "JLPT 올 클리어",
        "desc": "N5~N1 전 레벨 클리어 — 일본어 완전 정복!",
        "xp_bonus": 10000, "category": "hidden", "rarity": "legendary",
    },
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
        "reviews_50": total_reviews >= 50,
        "reviews_100": total_reviews >= 100,
        "reviews_500": total_reviews >= 500,
        "reviews_1000": total_reviews >= 1000,
        "reviews_2500": total_reviews >= 2500,
        "reviews_5000": total_reviews >= 5000,
        "reviews_10000": total_reviews >= 10000,
        # Streaks
        "streak_3": streak >= 3,
        "streak_7": streak >= 7,
        "streak_14": streak >= 14,
        "streak_21": streak >= 21,
        "streak_30": streak >= 30,
        "streak_60": streak >= 60,
        "streak_100": streak >= 100,
        "streak_200": streak >= 200,
        "streak_365": streak >= 365,
        # Combos
        "combo_5": combo_best >= 5,
        "combo_10": combo_best >= 10,
        "combo_20": combo_best >= 20,
        "combo_30": combo_best >= 30,
        "combo_50": combo_best >= 50,
        "combo_100": combo_best >= 100,
        # Vocab mastery
        "vocab_10": vocab_mastered >= 10,
        "vocab_50": vocab_mastered >= 50,
        "vocab_100": vocab_mastered >= 100,
        "vocab_200": vocab_mastered >= 200,
        "vocab_300": vocab_mastered >= 300,
        "vocab_500": vocab_mastered >= 500,
        "vocab_1000": vocab_mastered >= 1000,
        "vocab_2000": vocab_mastered >= 2000,
        # Mastery tiers
        "mastery_first_bronze": mastery_counts.get("bronze", 0) >= 1,
        "mastery_first_silver": mastery_counts.get("silver", 0) >= 1,
        "mastery_first_gold": mastery_counts.get("gold", 0) >= 1,
        "mastery_first_diamond": mastery_counts.get("diamond", 0) >= 1,
        "mastery_first_master": mastery_counts.get("master", 0) >= 1,
        "mastery_10_gold": mastery_counts.get("gold", 0) >= 10,
        "mastery_10_diamond": mastery_counts.get("diamond", 0) >= 10,
        "mastery_50_gold": mastery_counts.get("gold", 0) >= 50,
        "mastery_10_master": mastery_counts.get("master", 0) >= 10,
        # Levels
        "level_5": level >= 5,
        "level_10": level >= 10,
        "level_15": level >= 15,
        "level_20": level >= 20,
        "level_25": level >= 25,
        "level_30": level >= 30,
        "level_40": level >= 40,
        "level_50": level >= 50,
        "level_75": level >= 75,
        "level_100": level >= 100,
        # Quizzes
        "quiz_10": quiz_count >= 10,
        "quiz_50": quiz_count >= 50,
        "quiz_100": quiz_count >= 100,
        # Daily quests
        "daily_quest_first": daily_quests_completed >= 1,
        "daily_quest_30": daily_quests_completed >= 30,
        "daily_quest_100": daily_quests_completed >= 100,
        # Weekly challenges
        "weekly_first": weekly_challenges_completed >= 1,
        "weekly_5": weekly_challenges_completed >= 5,
        "weekly_10": weekly_challenges_completed >= 10,
        # Accuracy
        "accuracy_80": accuracy >= 80 and total_reviews >= 50,
        "accuracy_90": accuracy >= 90 and total_reviews >= 100,
        "accuracy_95": accuracy >= 95 and total_reviews >= 200,
        "accuracy_99": accuracy >= 99 and total_reviews >= 500,
        # Hidden (XP-based)
        "xp_millionaire": total_xp >= 1000000,
        # All JLPT clear
        "all_n_clear": all(n_levels_cleared.get(k, False) for k in ["n5", "n4", "n3", "n2", "n1"]),
    }

    for level_key in ["n5", "n4", "n3", "n2", "n1"]:
        checks[f"{level_key}_clear"] = n_levels_cleared.get(level_key, False)

    for aid, condition in checks.items():
        if condition and aid not in current:
            new.append(aid)

    return new

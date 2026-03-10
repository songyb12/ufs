"""JLPT vocabulary seed data + J-POP/anime/game source content."""

import json
import logging

from app.database.connection import get_db

logger = logging.getLogger("life-master.jp-seed")

# ── JLPT N5 Core Vocabulary (샘플 50개 — API로 추가 가능) ──

SEED_VOCAB = [
    # N5 — 기초
    ("食べる", "たべる", "먹다", "N5", "verb", "毎日ご飯を食べる。", "매일 밥을 먹는다."),
    ("飲む", "のむ", "마시다", "N5", "verb", "水を飲む。", "물을 마신다."),
    ("行く", "いく", "가다", "N5", "verb", "学校に行く。", "학교에 간다."),
    ("来る", "くる", "오다", "N5", "verb", "友達が来る。", "친구가 온다."),
    ("見る", "みる", "보다", "N5", "verb", "映画を見る。", "영화를 본다."),
    ("聞く", "きく", "듣다", "N5", "verb", "音楽を聞く。", "음악을 듣는다."),
    ("読む", "よむ", "읽다", "N5", "verb", "本を読む。", "책을 읽는다."),
    ("書く", "かく", "쓰다", "N5", "verb", "手紙を書く。", "편지를 쓴다."),
    ("話す", "はなす", "말하다", "N5", "verb", "日本語を話す。", "일본어를 말한다."),
    ("買う", "かう", "사다", "N5", "verb", "本を買う。", "책을 산다."),
    ("大きい", "おおきい", "크다", "N5", "adjective", "大きい家。", "큰 집."),
    ("小さい", "ちいさい", "작다", "N5", "adjective", "小さい猫。", "작은 고양이."),
    ("新しい", "あたらしい", "새롭다", "N5", "adjective", "新しい靴を買った。", "새 신발을 샀다."),
    ("古い", "ふるい", "오래되다", "N5", "adjective", "古い建物。", "오래된 건물."),
    ("高い", "たかい", "높다/비싸다", "N5", "adjective", "高い山。", "높은 산."),
    ("安い", "やすい", "싸다", "N5", "adjective", "安いレストラン。", "저렴한 레스토랑."),
    ("人", "ひと", "사람", "N5", "noun", "あの人は先生です。", "저 사람은 선생님입니다."),
    ("時間", "じかん", "시간", "N5", "noun", "時間がない。", "시간이 없다."),
    ("今日", "きょう", "오늘", "N5", "noun", "今日は暑い。", "오늘은 덥다."),
    ("明日", "あした", "내일", "N5", "noun", "明日学校に行く。", "내일 학교에 간다."),
    # N4
    ("届ける", "とどける", "전달하다", "N4", "verb", "荷物を届ける。", "짐을 전달한다."),
    ("決める", "きめる", "정하다", "N4", "verb", "予定を決める。", "예정을 정한다."),
    ("集める", "あつめる", "모으다", "N4", "verb", "切手を集める。", "우표를 모은다."),
    ("経験", "けいけん", "경험", "N4", "noun", "いい経験になった。", "좋은 경험이 됐다."),
    ("習慣", "しゅうかん", "습관", "N4", "noun", "良い習慣を作る。", "좋은 습관을 만든다."),
    ("特別", "とくべつ", "특별", "N4", "na-adjective", "特別な日。", "특별한 날."),
    ("簡単", "かんたん", "간단", "N4", "na-adjective", "簡単な問題。", "간단한 문제."),
    ("複雑", "ふくざつ", "복잡", "N4", "na-adjective", "複雑な気持ち。", "복잡한 기분."),
    # N3
    ("影響", "えいきょう", "영향", "N3", "noun", "環境に影響を与える。", "환경에 영향을 준다."),
    ("努力", "どりょく", "노력", "N3", "noun", "努力が必要だ。", "노력이 필요하다."),
    ("挑戦", "ちょうせん", "도전", "N3", "noun", "新しいことに挑戦する。", "새로운 것에 도전한다."),
    ("成長", "せいちょう", "성장", "N3", "noun", "子供の成長。", "아이의 성장."),
    ("関係", "かんけい", "관계", "N3", "noun", "人間関係。", "인간관계."),
    ("比較", "ひかく", "비교", "N3", "noun", "二つを比較する。", "둘을 비교한다."),
    ("判断", "はんだん", "판단", "N3", "noun", "正しい判断。", "올바른 판단."),
    ("確認", "かくにん", "확인", "N3", "noun", "予約を確認する。", "예약을 확인한다."),
    # N2
    ("貢献", "こうけん", "공헌", "N2", "noun", "社会に貢献する。", "사회에 공헌한다."),
    ("維持", "いじ", "유지", "N2", "noun", "健康を維持する。", "건강을 유지한다."),
    ("対応", "たいおう", "대응", "N2", "noun", "問題に対応する。", "문제에 대응한다."),
    ("効率", "こうりつ", "효율", "N2", "noun", "効率を上げる。", "효율을 올린다."),
    ("環境", "かんきょう", "환경", "N2", "noun", "自然環境を守る。", "자연환경을 지킨다."),
    ("展開", "てんかい", "전개", "N2", "noun", "物語が展開する。", "이야기가 전개된다."),
    # N1
    ("概念", "がいねん", "개념", "N1", "noun", "基本的な概念。", "기본적인 개념."),
    ("把握", "はあく", "파악", "N1", "noun", "状況を把握する。", "상황을 파악한다."),
    ("妥協", "だきょう", "타협", "N1", "noun", "妥協しない。", "타협하지 않는다."),
    ("矛盾", "むじゅん", "모순", "N1", "noun", "矛盾した意見。", "모순된 의견."),
    ("洞察", "どうさつ", "통찰", "N1", "noun", "深い洞察力。", "깊은 통찰력."),
    ("齟齬", "そご", "어긋남", "N1", "noun", "意見に齟齬が生じる。", "의견에 어긋남이 생긴다."),
]

# ── J-POP / Anime / Game Sources ──

SEED_SOURCES = [
    # J-POP
    {
        "title": "Lemon",
        "artist": "米津玄師",
        "source_type": "song",
        "content_ja": "夢ならばどれほどよかったでしょう\n未だにあなたのことを夢にみる\n忘れた物を取りに帰るように\n古びた思い出の埃を払う",
        "content_ko": "꿈이라면 얼마나 좋았을까\n아직도 당신을 꿈에서 봐\n잊어버린 것을 가지러 돌아가듯\n빛바랜 추억의 먼지를 털어낸다",
        "difficulty": "N3",
        "tags": '["jpop", "ballad"]',
    },
    {
        "title": "打上花火",
        "artist": "DAOKO × 米津玄師",
        "source_type": "song",
        "content_ja": "あの日見渡した渚を\n今も思い出すんだ\n砂の上に刻んだ言葉\n君の後ろ姿",
        "content_ko": "그날 바라봤던 해변을\n지금도 떠올린다\n모래 위에 새긴 말\n너의 뒷모습",
        "difficulty": "N4",
        "tags": '["jpop", "anime"]',
    },
    {
        "title": "夜に駆ける",
        "artist": "YOASOBI",
        "source_type": "song",
        "content_ja": "沈むように溶けてゆくように\n二人だけの空が広がる夜に\n「さよなら」だけだった\nその一言で全てが分かった",
        "content_ko": "가라앉듯이 녹아가듯이\n둘만의 하늘이 펼쳐지는 밤에\n「안녕」뿐이었어\n그 한마디로 전부 알았어",
        "difficulty": "N3",
        "tags": '["jpop", "yoasobi"]',
    },
    # Anime
    {
        "title": "진격의 거인 — 리바이 대사",
        "artist": "進撃の巨人",
        "source_type": "anime",
        "content_ja": "悔いが残らない方を自分で選べ。\nお前の判断を信じろ。\n結果がどうであれ、自分で選んだ道なら後悔はない。",
        "content_ko": "후회가 남지 않는 쪽을 스스로 선택해라.\n네 판단을 믿어라.\n결과가 어떻든, 스스로 선택한 길이라면 후회는 없다.",
        "difficulty": "N3",
        "tags": '["anime", "shingeki"]',
    },
    {
        "title": "나루토 — 나루토 대사",
        "artist": "NARUTO",
        "source_type": "anime",
        "content_ja": "まっすぐ自分の言葉は曲げねえ。\nそれが俺の忍道だ！\n諦めないのが俺の忍道だってばよ！",
        "content_ko": "곧은 자신의 말은 꺾지 않아.\n그게 나의 닌자도다!\n포기하지 않는 게 나의 닌자도라고!",
        "difficulty": "N4",
        "tags": '["anime", "naruto"]',
    },
    {
        "title": "원피스 — 루피 대사",
        "artist": "ONE PIECE",
        "source_type": "anime",
        "content_ja": "海賊王に俺はなる！\n仲間がいるよ！！\nうるせえ！！行こう！！！",
        "content_ko": "해적왕에 내가 된다!\n동료가 있잖아!!\n시끄러!! 가자!!!",
        "difficulty": "N5",
        "tags": '["anime", "onepiece"]',
    },
    {
        "title": "귀멸의 칼날 — 탄지로 대사",
        "artist": "鬼滅の刃",
        "source_type": "anime",
        "content_ja": "俺は長男だから我慢できたけど、次男だったら我慢できなかった。\n頑張れ！人は心が原動力だから。",
        "content_ko": "나는 장남이니까 참을 수 있었지만, 차남이었으면 참지 못했을 거야.\n힘내! 사람은 마음이 원동력이니까.",
        "difficulty": "N3",
        "tags": '["anime", "kimetsu"]',
    },
    # Games
    {
        "title": "파이널 판타지 — 클라우드",
        "artist": "Final Fantasy VII",
        "source_type": "game",
        "content_ja": "興味ないね。\nこの星の未来は俺が守る。\n約束したんだ、必ず助けに来るって。",
        "content_ko": "흥미 없어.\n이 별의 미래는 내가 지킨다.\n약속했잖아, 반드시 도와주러 온다고.",
        "difficulty": "N4",
        "tags": '["game", "ff7"]',
    },
    {
        "title": "페르소나 5 — 명대사",
        "artist": "Persona 5",
        "source_type": "game",
        "content_ja": "お前の罪を告白しろ！\n我は汝、汝は我。\nもう一人の自分と向き合え。",
        "content_ko": "네 죄를 고백해라!\n나는 너, 너는 나.\n또 다른 자신과 마주해라.",
        "difficulty": "N3",
        "tags": '["game", "persona"]',
    },
    {
        "title": "젤다의 전설 — 명언",
        "artist": "ゼルダの伝説",
        "source_type": "game",
        "content_ja": "時の勇者よ、目覚めなさい。\n勇気のトライフォースが光り輝く時、\n闇は退く。",
        "content_ko": "시간의 용사여, 눈을 떠라.\n용기의 트라이포스가 빛나는 때,\n어둠은 물러간다.",
        "difficulty": "N3",
        "tags": '["game", "zelda"]',
    },
]

# ── Source ↔ Vocab Mappings (source_title → vocab words) ──

SOURCE_VOCAB_MAP = {
    "Lemon": ["夢ならば", "忘れた", "古びた", "思い出"],
    "原피스 — 루피 대사": ["海賊", "仲間"],
    "진격의 거인 — 리바이 대사": ["判断", "結果"],
}


async def seed_japanese_data() -> dict:
    """Insert seed vocabulary and sources. Skips if already seeded."""
    db = await get_db()

    # Check if already seeded
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM jp_vocabulary")
    row = await cursor.fetchone()
    if row and row["cnt"] > 0:
        logger.info("Japanese data already seeded (%d vocab)", row["cnt"])
        return {"status": "already_seeded", "vocab_count": row["cnt"]}

    # Insert vocabulary
    vocab_count = 0
    for word, reading, meaning, level, pos, ex_ja, ex_ko in SEED_VOCAB:
        await db.execute(
            """INSERT INTO jp_vocabulary (word, reading, meaning, jlpt_level, part_of_speech, example_ja, example_ko)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (word, reading, meaning, level, pos, ex_ja, ex_ko),
        )
        vocab_count += 1

    # Create SRS cards for all vocab
    await db.execute(
        """INSERT INTO jp_srs_cards (vocab_id, next_review)
           SELECT id, date('now') FROM jp_vocabulary
           WHERE id NOT IN (SELECT vocab_id FROM jp_srs_cards)"""
    )

    # Insert sources
    source_count = 0
    for src in SEED_SOURCES:
        await db.execute(
            """INSERT INTO jp_sources (title, artist, source_type, content_ja, content_ko, difficulty, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (src["title"], src.get("artist"), src["source_type"],
             src["content_ja"], src.get("content_ko"), src["difficulty"], src["tags"]),
        )
        source_count += 1

    # Init player stats
    await db.execute(
        """INSERT OR IGNORE INTO jp_player_stats (id, total_xp, level)
           VALUES (1, 0, 1)"""
    )

    await db.commit()
    logger.info("Japanese seed data inserted: %d vocab, %d sources", vocab_count, source_count)
    return {"status": "seeded", "vocab_count": vocab_count, "source_count": source_count}

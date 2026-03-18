"""Seed data for N5 writing exercises — 30 exercises (15 translation, 10 sentence_order, 5 grammar_usage)."""

import json
import logging

from app.database.connection import get_db

logger = logging.getLogger("life-master.writing-seed")

# (exercise_type, jlpt_level, prompt_ko, prompt_jp, answer_jp, alt_answers, grammar_point, hint, difficulty)

EXERCISES = [
    # ── Translation (15) ──────────────────────────────────
    (
        "translation", "N5",
        "저는 학생입니다.",
        None,
        "わたしはがくせいです。",
        json.dumps(["わたしはがくせいです", "私は学生です。"]),
        "~です", "명사 + です", 1,
    ),
    (
        "translation", "N5",
        "이것은 책입니다.",
        None,
        "これはほんです。",
        json.dumps(["これは本です。"]),
        "~です", "これ/それ/あれ + は + 명사 + です", 1,
    ),
    (
        "translation", "N5",
        "매일 아침 7시에 일어납니다.",
        None,
        "まいにちあさしちじにおきます。",
        json.dumps(["毎日朝七時に起きます。", "まいにちあさ7じにおきます。"]),
        "~に（시간）", "시간 + に + 동사", 1,
    ),
    (
        "translation", "N5",
        "어제 영화를 봤습니다.",
        None,
        "きのうえいがをみました。",
        json.dumps(["昨日映画を見ました。"]),
        "~ました（과거）", "동사 ます형 → ました", 1,
    ),
    (
        "translation", "N5",
        "일본어를 공부하고 있습니다.",
        None,
        "にほんごをべんきょうしています。",
        json.dumps(["日本語を勉強しています。"]),
        "~ています", "동사 て형 + います（진행）", 2,
    ),
    (
        "translation", "N5",
        "커피를 마시고 싶습니다.",
        None,
        "コーヒーをのみたいです。",
        json.dumps(["コーヒーを飲みたいです。"]),
        "~たい", "동사 ます형 어간 + たい", 1,
    ),
    (
        "translation", "N5",
        "도서관에서 책을 읽었습니다.",
        None,
        "としょかんでほんをよみました。",
        json.dumps(["図書館で本を読みました。"]),
        "~で（장소）", "장소 + で + 동사", 2,
    ),
    (
        "translation", "N5",
        "내일 친구와 만납니다.",
        None,
        "あしたともだちとあいます。",
        json.dumps(["明日友達と会います。"]),
        "~と（동반）", "사람 + と + 동사", 1,
    ),
    (
        "translation", "N5",
        "이 가방은 크고 무겁습니다.",
        None,
        "このかばんはおおきくておもいです。",
        json.dumps(["この鞄は大きくて重いです。", "このかばんはおおきくておもいです"]),
        "い형용사 て형", "い → くて", 2,
    ),
    (
        "translation", "N5",
        "저는 고기를 먹지 않습니다.",
        None,
        "わたしはにくをたべません。",
        json.dumps(["私は肉を食べません。"]),
        "~ません", "동사 ます형 부정", 1,
    ),
    (
        "translation", "N5",
        "학교까지 버스로 갑니다.",
        None,
        "がっこうまでバスでいきます。",
        json.dumps(["学校までバスで行きます。"]),
        "~まで/~で（수단）", "장소 + まで + 수단 + で + 동사", 2,
    ),
    (
        "translation", "N5",
        "일본 음식은 맛있습니다.",
        None,
        "にほんのたべものはおいしいです。",
        json.dumps(["日本の食べ物はおいしいです。", "日本の食べ物は美味しいです。"]),
        "い형용사", "명사 + は + い형용사 + です", 1,
    ),
    (
        "translation", "N5",
        "방 안에 고양이가 있습니다.",
        None,
        "へやのなかにねこがいます。",
        json.dumps(["部屋の中に猫がいます。"]),
        "~にいます", "장소 + に + 생물 + がいます", 2,
    ),
    (
        "translation", "N5",
        "어머니는 요리가 잘합니다.",
        None,
        "はははりょうりがじょうずです。",
        json.dumps(["母は料理が上手です。"]),
        "~がじょうず", "명사 + が + じょうず/へた + です", 2,
    ),
    (
        "translation", "N5",
        "주말에 무엇을 합니까?",
        None,
        "しゅうまつになにをしますか。",
        json.dumps(["週末に何をしますか。"]),
        "의문사 + か", "なに/だれ/どこ + を/が/に + 동사 + か", 1,
    ),
    # ── Sentence Order (10) ───────────────────────────────
    (
        "sentence_order", "N5",
        "저는 매일 학교에 갑니다.",
        None,
        "わたしはまいにちがっこうにいきます",
        json.dumps(["わたしはまいにちがっこうへいきます"]),
        "~に/へ いきます", None, 1,
    ),
    (
        "sentence_order", "N5",
        "친구와 공원에서 놀았습니다.",
        None,
        "ともだちとこうえんであそびました",
        None,
        "~と ~で ~ました", None, 1,
    ),
    (
        "sentence_order", "N5",
        "아침에 빵과 우유를 먹었습니다.",
        None,
        "あさにパンとぎゅうにゅうをたべました",
        json.dumps(["あさパンとぎゅうにゅうをたべました"]),
        "~と（나열）", None, 1,
    ),
    (
        "sentence_order", "N5",
        "도쿄에서 전철을 탔습니다.",
        None,
        "とうきょうででんしゃにのりました",
        None,
        "~で ~に のります", None, 2,
    ),
    (
        "sentence_order", "N5",
        "이 꽃은 아주 예쁩니다.",
        None,
        "このはなはとてもきれいです",
        None,
        "な형용사", None, 1,
    ),
    (
        "sentence_order", "N5",
        "형은 회사에서 일합니다.",
        None,
        "あにはかいしゃではたらいています",
        json.dumps(["あにはかいしゃではたらきます"]),
        "~ています", None, 2,
    ),
    (
        "sentence_order", "N5",
        "역에서 택시를 탑시다.",
        None,
        "えきからタクシーにのりましょう",
        None,
        "~ましょう", None, 2,
    ),
    (
        "sentence_order", "N5",
        "테이블 위에 컵이 있습니다.",
        None,
        "テーブルのうえにコップがあります",
        None,
        "~にあります", None, 1,
    ),
    (
        "sentence_order", "N5",
        "저는 일본에 가고 싶습니다.",
        None,
        "わたしはにほんにいきたいです",
        json.dumps(["わたしはにほんへいきたいです"]),
        "~たい", None, 1,
    ),
    (
        "sentence_order", "N5",
        "여름은 덥고 겨울은 춥습니다.",
        None,
        "なつはあつくてふゆはさむいです",
        None,
        "い형용사 て형", None, 2,
    ),
    # ── Grammar Usage (5) ─────────────────────────────────
    (
        "grammar_usage", "N5",
        "「～てください」를 사용하여 창문을 열어달라고 부탁하는 문장을 쓰세요.",
        "まどをあけてください。",
        "まどをあけてください。",
        json.dumps(["窓を開けてください。", "まどをあけてください"]),
        "～てください", "동사 て형 + ください（요청）", 2,
    ),
    (
        "grammar_usage", "N5",
        "「～てはいけません」를 사용하여 여기서 사진을 찍으면 안 된다는 문장을 쓰세요.",
        "ここでしゃしんをとってはいけません。",
        "ここでしゃしんをとってはいけません。",
        json.dumps(["ここで写真を撮ってはいけません。"]),
        "～てはいけません", "동사 て형 + はいけません（금지）", 2,
    ),
    (
        "grammar_usage", "N5",
        "「～ことができます」를 사용하여 일본어를 말할 수 있다는 문장을 쓰세요.",
        "にほんごをはなすことができます。",
        "にほんごをはなすことができます。",
        json.dumps(["日本語を話すことができます。"]),
        "～ことができます", "동사 사전형 + ことができます（가능）", 3,
    ),
    (
        "grammar_usage", "N5",
        "「～たことがあります」를 사용하여 일본에 간 적이 있다는 문장을 쓰세요.",
        "にほんにいったことがあります。",
        "にほんにいったことがあります。",
        json.dumps(["日本に行ったことがあります。"]),
        "～たことがあります", "동사 た형 + ことがあります（경험）", 3,
    ),
    (
        "grammar_usage", "N5",
        "「～なければなりません」를 사용하여 숙제를 해야 한다는 문장을 쓰세요.",
        "しゅくだいをしなければなりません。",
        "しゅくだいをしなければなりません。",
        json.dumps(["宿題をしなければなりません。", "しゅくだいをしなければいけません。"]),
        "～なければなりません", "동사 ない형 어간 + なければなりません（의무）", 3,
    ),
]


async def seed_writing_data() -> int:
    """Insert N5 writing exercises. Returns exercise count."""
    db = await get_db()

    # Check if data already exists
    cursor = await db.execute("SELECT COUNT(*) FROM jp_writing_exercise")
    count = (await cursor.fetchone())[0]
    if count > 0:
        logger.info("Writing exercises already seeded (%d rows), skipping", count)
        return count

    for ex in EXERCISES:
        await db.execute(
            """INSERT INTO jp_writing_exercise
               (exercise_type, jlpt_level, prompt_ko, prompt_jp, answer_jp, alt_answers, grammar_point, hint, difficulty)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ex,
        )

    await db.commit()
    logger.info("Seeded %d writing exercises", len(EXERCISES))
    return len(EXERCISES)

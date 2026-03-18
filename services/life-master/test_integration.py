"""Integration test — DB init → seed → service function calls.

Uses a temp SQLite file with the real async service layer (get_db singleton).
"""

import asyncio
import os
import sys
import tempfile
import traceback

# Ensure app is importable
sys.path.insert(0, os.path.dirname(__file__))


passed = 0
failed = 0
errors: list[str] = []


def ok(name: str):
    global passed
    passed += 1
    print(f"  PASS {name}")


def fail(name: str, err: str):
    global failed
    failed += 1
    errors.append(f"{name}: {err}")
    print(f"  FAIL {name} -- {err}")


async def run_tests():
    # ── Setup: temp DB ──────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        from app.database.connection import set_db_path, close_db
        set_db_path(tmp_path)

        # ── 1. Schema init ──────────────────────────────────
        print("\n[1] Schema init")
        try:
            from app.database.schema import init_db
            await init_db()
            ok("init_db")
        except Exception as e:
            fail("init_db", str(e))
            traceback.print_exc()
            return  # Can't continue without schema

        # ── 2. Seed data ────────────────────────────────────
        print("\n[2] Seed data")

        # 2a. Vocab seed (jp_seed.py)
        try:
            from app.database.jp_seed import seed_japanese_data
            result = await seed_japanese_data()
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            ok(f"seed_japanese_data → {result}")
        except Exception as e:
            fail("seed_japanese_data", str(e))
            traceback.print_exc()

        # 2b. Grammar seed (may return existing count since jp_seed already seeded)
        try:
            from app.database.jp_grammar_seed import seed_grammar_data
            count = await seed_grammar_data()
            assert count >= 0, f"Expected >=0 grammar, got {count}"
            ok(f"seed_grammar_data → {count} (idempotent)")
        except Exception as e:
            fail("seed_grammar_data", str(e))
            traceback.print_exc()

        # 2c. Kanji seed (may return 0 since jp_seed already seeded)
        try:
            from app.database.jp_kanji_seed import seed_kanji_data
            count = await seed_kanji_data()
            assert count >= 0, f"Expected >=0 kanji, got {count}"
            ok(f"seed_kanji_data → {count} (idempotent)")
        except Exception as e:
            fail("seed_kanji_data", str(e))
            traceback.print_exc()

        # 2d. Reading seed
        try:
            from app.database.jp_reading_seed import seed_reading_data
            count = await seed_reading_data()
            assert count > 0, f"Expected >0 passages, got {count}"
            ok(f"seed_reading_data → {count}")
        except Exception as e:
            fail("seed_reading_data", str(e))
            traceback.print_exc()

        # 2e. Writing seed
        try:
            from app.database.jp_writing_seed import seed_writing_data
            count = await seed_writing_data()
            assert count > 0, f"Expected >0 exercises, got {count}"
            ok(f"seed_writing_data → {count}")
        except Exception as e:
            fail("seed_writing_data", str(e))
            traceback.print_exc()

        # ── 3. Grammar service ──────────────────────────────
        print("\n[3] Grammar service")
        try:
            from app.services.grammar_service import get_grammar_list
            result = await get_grammar_list()
            assert result["total"] > 0, f"No grammar items"
            ok(f"get_grammar_list → {result['total']} items")
        except Exception as e:
            fail("get_grammar_list", str(e))
            traceback.print_exc()

        try:
            from app.services.grammar_service import get_grammar_detail
            detail = await get_grammar_detail(1)
            assert detail is not None, "Grammar id=1 not found"
            assert "grammar_point" in detail
            ok(f"get_grammar_detail(1) → {detail['grammar_point']}")
        except Exception as e:
            fail("get_grammar_detail", str(e))
            traceback.print_exc()

        try:
            from app.services.grammar_service import grammar_quiz_fill_blank
            quiz = await grammar_quiz_fill_blank()
            assert isinstance(quiz, list)
            ok(f"grammar_quiz_fill_blank → {len(quiz)} questions")
        except Exception as e:
            fail("grammar_quiz_fill_blank", str(e))
            traceback.print_exc()

        # ── 4. Kanji service ────────────────────────────────
        print("\n[4] Kanji service")
        try:
            from app.services.kanji_service import get_kanji_list
            result = await get_kanji_list()
            assert result["total"] > 0, "No kanji items"
            ok(f"get_kanji_list → {result['total']} items")
        except Exception as e:
            fail("get_kanji_list", str(e))
            traceback.print_exc()

        try:
            from app.services.kanji_service import get_kanji_detail
            detail = await get_kanji_detail(1)
            assert detail is not None, "Kanji id=1 not found"
            assert "character" in detail
            ok(f"get_kanji_detail(1) → {detail['character']}")
        except Exception as e:
            fail("get_kanji_detail", str(e))
            traceback.print_exc()

        try:
            from app.services.kanji_service import search_kanji
            results = await search_kanji("日")
            assert isinstance(results, list)
            ok(f"search_kanji('日') → {len(results)} results")
        except Exception as e:
            fail("search_kanji", str(e))
            traceback.print_exc()

        try:
            from app.services.kanji_service import kanji_quiz_reading
            quiz = await kanji_quiz_reading()
            assert isinstance(quiz, list)
            ok(f"kanji_quiz_reading → {len(quiz)} questions")
        except Exception as e:
            fail("kanji_quiz_reading", str(e))
            traceback.print_exc()

        try:
            from app.services.kanji_service import kanji_quiz_meaning
            quiz = await kanji_quiz_meaning()
            assert isinstance(quiz, list)
            ok(f"kanji_quiz_meaning → {len(quiz)} questions")
        except Exception as e:
            fail("kanji_quiz_meaning", str(e))
            traceback.print_exc()

        # ── 5. Reading service ──────────────────────────────
        print("\n[5] Reading service")
        try:
            from app.services.reading_service import get_passages
            result = await get_passages()
            assert result["total"] > 0, "No passages"
            ok(f"get_passages → {result['total']} items")
        except Exception as e:
            fail("get_passages", str(e))
            traceback.print_exc()

        try:
            from app.services.reading_service import get_passage_detail
            detail = await get_passage_detail(1)
            assert detail is not None, "Passage id=1 not found"
            assert "questions" in detail
            ok(f"get_passage_detail(1) → {detail['title']}, {len(detail['questions'])} questions")
        except Exception as e:
            fail("get_passage_detail", str(e))
            traceback.print_exc()

        try:
            from app.services.reading_service import submit_reading_answers
            # Submit correct answers for passage 1 questions
            detail = await get_passage_detail(1)
            if detail and detail["questions"]:
                # Need to get correct answers from DB
                from app.database.connection import get_db
                db = await get_db()
                cursor = await db.execute(
                    "SELECT id, correct_answer FROM jp_reading_question WHERE passage_id = 1"
                )
                qa = await cursor.fetchall()
                answers = {str(r[0]): r[1] for r in qa}
                result = await submit_reading_answers(1, answers)
                assert result["score_percent"] == 100
                ok(f"submit_reading_answers(1) → {result['score_percent']}%")
            else:
                fail("submit_reading_answers", "No questions for passage 1")
        except Exception as e:
            fail("submit_reading_answers", str(e))
            traceback.print_exc()

        # ── 6. Writing service ──────────────────────────────
        print("\n[6] Writing service")
        try:
            from app.services.writing_service import get_translation_exercise
            ex = await get_translation_exercise()
            assert ex is not None, "No translation exercise"
            assert "exercise_id" in ex
            ok(f"get_translation_exercise → id={ex['exercise_id']}")
        except Exception as e:
            fail("get_translation_exercise", str(e))
            traceback.print_exc()

        try:
            from app.services.writing_service import get_sentence_order_exercise
            ex = await get_sentence_order_exercise()
            assert ex is not None, "No sentence_order exercise"
            assert "scrambled_words" in ex
            ok(f"get_sentence_order_exercise → {len(ex['scrambled_words'])} words")
        except Exception as e:
            fail("get_sentence_order_exercise", str(e))
            traceback.print_exc()

        try:
            from app.services.writing_service import get_grammar_usage_exercise
            ex = await get_grammar_usage_exercise()
            assert ex is not None, "No grammar_usage exercise"
            ok(f"get_grammar_usage_exercise → id={ex['exercise_id']}")
        except Exception as e:
            fail("get_grammar_usage_exercise", str(e))
            traceback.print_exc()

        try:
            from app.services.writing_service import check_writing_answer
            # Get a translation exercise and check with the correct answer
            from app.database.connection import get_db
            db = await get_db()
            cursor = await db.execute(
                "SELECT id, answer_jp FROM jp_writing_exercise WHERE exercise_type='translation' LIMIT 1"
            )
            row = await cursor.fetchone()
            if row:
                result = await check_writing_answer(row[0], row[1])
                assert result["is_correct"], f"Should be correct for exact answer"
                ok(f"check_writing_answer → correct={result['is_correct']}")
            else:
                fail("check_writing_answer", "No translation exercise in DB")
        except Exception as e:
            fail("check_writing_answer", str(e))
            traceback.print_exc()

        # ── 7. Analytics service ────────────────────────────
        print("\n[7] Analytics service")
        try:
            from app.services.analytics_service import get_weakness_analysis
            result = await get_weakness_analysis()
            assert "areas" in result
            ok(f"get_weakness_analysis → areas={list(result['areas'].keys())}")
        except Exception as e:
            fail("get_weakness_analysis", str(e))
            traceback.print_exc()

        try:
            from app.services.analytics_service import get_learning_curve
            result = await get_learning_curve(7)
            assert "daily" in result
            assert len(result["daily"]) == 7
            ok(f"get_learning_curve(7) → {len(result['daily'])} days")
        except Exception as e:
            fail("get_learning_curve", str(e))
            traceback.print_exc()

        try:
            from app.services.analytics_service import get_srs_forecast
            result = await get_srs_forecast(7)
            assert "daily" in result
            ok(f"get_srs_forecast(7) → {len(result['daily'])} days")
        except Exception as e:
            fail("get_srs_forecast", str(e))
            traceback.print_exc()

        try:
            from app.services.analytics_service import get_mastery_breakdown
            result = await get_mastery_breakdown()
            assert "levels" in result
            ok(f"get_mastery_breakdown → levels={list(result['levels'].keys())}")
        except Exception as e:
            fail("get_mastery_breakdown", str(e))
            traceback.print_exc()

        try:
            from app.services.analytics_service import get_streak_info
            result = await get_streak_info()
            assert "current_streak" in result
            ok(f"get_streak_info → streak={result['current_streak']}")
        except Exception as e:
            fail("get_streak_info", str(e))
            traceback.print_exc()

    finally:
        await close_db()
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # ── Summary ─────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(f"  FAIL {e}")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)

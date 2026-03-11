"""SQL-RAG: Natural language query engine over VIBE database.

Converts Korean/English questions into SQL queries against the VIBE schema,
executes them read-only, and synthesizes a natural language answer.

Flow:
  1. User question → Schema-aware prompt → LLM generates SQL
  2. SQL validation (SELECT only, allowlisted tables, row limit)
  3. Execute against vibe.db (read-only)
  4. Results + original question → LLM synthesizes Korean answer
"""

import json
import logging
import re
from typing import Any

from app.config import settings
from app.database.connection import get_db

logger = logging.getLogger("vibe.briefing.rag")

# ---------------------------------------------------------------------------
# Security: table allowlist (exclude users, runtime_config, etc.)
# ---------------------------------------------------------------------------

ALLOWED_TABLES = frozenset({
    "watchlist",
    "price_history",
    "technical_indicators",
    "macro_indicators",
    "fund_flow_kr",
    "pipeline_runs",
    "signals",
    "dashboard_snapshots",
    "backtest_runs",
    "backtest_trades",
    "signal_performance",
    "symbol_metadata",
    "event_calendar",
    "portfolio_groups",
    "portfolio_state",
    "fundamental_data",
    "weekly_indicators",
    "screening_candidates",
    "sentiment_data",
    "us_fund_flow",
    "short_interest",
    "portfolio_scenarios",
    "news_data",
    "llm_reviews",
    "alert_history",
    "market_briefings",
    "monthly_reports",
    "position_exits",
    "forex_history",
    "interest_rates",
})

MAX_ROWS = 100

# ---------------------------------------------------------------------------
# Schema description for the LLM prompt
# ---------------------------------------------------------------------------

SCHEMA_DESCRIPTION = """
[VIBE Database Schema — SQLite]

watchlist: 종목 관심목록
  - symbol (TEXT), name (TEXT), market (TEXT: KR/US), asset_type, is_active (0/1)

price_history: 일별 OHLCV 가격
  - symbol, market, trade_date (TEXT: YYYY-MM-DD), open, high, low, close, volume

technical_indicators: 기술적 지표
  - symbol, market, trade_date, rsi_14, ma_5, ma_20, ma_60, ma_120,
    macd, macd_signal, macd_histogram, bollinger_upper/middle/lower,
    disparity_20, volume_ratio

macro_indicators: 매크로 경제 지표 (일별)
  - indicator_date, us_10y_yield, us_2y_yield, us_yield_spread, fed_funds_rate,
    dxy_index, vix, fear_greed_index, kr_base_rate, usd_krw, wti_crude, gold_price, copper_price

fund_flow_kr: 한국 수급 (외국인/기관/개인)
  - symbol, trade_date, foreign_net_buy, institution_net_buy, individual_net_buy,
    pension_net_buy, foreign_holding_ratio

signals: 매매 시그널
  - run_id, symbol, market, signal_date, raw_signal, raw_score, final_signal (BUY/SELL/HOLD),
    confidence, red_team_warning, rsi_value, disparity_value, macro_score,
    technical_score, fund_flow_score, rationale, explanation_rule

fundamental_data: 펀더멘털 지표
  - symbol, market, trade_date, per, pbr, eps, roe, operating_margin,
    div_yield, market_cap, fundamental_score, value_score, quality_score

weekly_indicators: 주간 지표
  - symbol, market, week_ending, rsi_14_weekly, ma_5_weekly, ma_20_weekly,
    macd_weekly, trend_direction

portfolio_state: 현재 포트폴리오 보유
  - portfolio_id, symbol, market, position_size, entry_date, entry_price, sector, is_hidden

position_exits: 매도 기록
  - portfolio_id, symbol, market, entry_price, exit_price, position_size,
    entry_date, exit_date, exit_reason, pnl_pct

signal_performance: 시그널 성과 추적
  - signal_id, symbol, market, signal_date, signal_type, signal_score,
    entry_price, price_t1, price_t5, price_t20, return_t1, return_t5, return_t20,
    is_correct_t5, is_correct_t20

sentiment_data: 시장 심리
  - indicator_date, fear_greed_index, put_call_ratio, vix_term_structure

event_calendar: 이벤트 일정
  - event_date, event_type, market, symbol, description, impact_level

news_data: 뉴스 데이터
  - run_id, symbol, market, trade_date, news_score, article_count,
    bullish_count, bearish_count, headlines_json

symbol_metadata: 종목 메타데이터
  - symbol, market, sector, industry, market_cap, next_earnings_date

short_interest: 공매도 지표
  - symbol, market, report_date, short_interest_shares, short_ratio, short_pct_float

forex_history: 환율 이력
  - pair, trade_date, close_price

interest_rates: 중앙은행 금리
  - currency, rate, central_bank

[중요 참고]
- 날짜는 모두 TEXT (YYYY-MM-DD 형식)
- market은 'KR' 또는 'US'
- final_signal은 'BUY', 'SELL', 'HOLD'
- watchlist.name으로 종목명 조인 가능
- 최신 날짜: SELECT MAX(signal_date) FROM signals
"""

SQL_GENERATION_SYSTEM_PROMPT = """당신은 VIBE 투자 데이터베이스의 SQL 쿼리 생성기입니다.
사용자의 자연어 질문을 SQLite SELECT 쿼리로 변환하세요.

규칙:
1. SELECT 문만 생성 (INSERT/UPDATE/DELETE/DROP 등 절대 불가)
2. LIMIT은 최대 100
3. 종목명으로 질문하면 watchlist 테이블과 JOIN하여 symbol 매핑
4. 날짜 필터가 없으면 최신 데이터 기준으로 쿼리
5. 한 번에 하나의 쿼리만 생성
6. 최신 시그널: signal_date = (SELECT MAX(signal_date) FROM signals) 서브쿼리 사용
7. 종목명 검색: watchlist.name LIKE '%키워드%' 사용 (한국어 종목명)

예시:
Q: "삼성전자 최근 RSI는?"
SQL: SELECT w.name, t.rsi_14, t.trade_date FROM technical_indicators t JOIN watchlist w ON t.symbol = w.symbol AND t.market = w.market WHERE w.name LIKE '%삼성전자%' ORDER BY t.trade_date DESC LIMIT 10

Q: "BUY 시그널 종목 목록"
SQL: SELECT w.name, s.symbol, s.market, s.raw_score, s.rsi_value, s.confidence FROM signals s JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals) AND s.final_signal = 'BUY' ORDER BY s.raw_score DESC

Q: "VIX 추이"
SQL: SELECT indicator_date, vix FROM macro_indicators ORDER BY indicator_date DESC LIMIT 30

Q: "포트폴리오 현황"
SQL: SELECT ps.symbol, w.name, ps.market, ps.entry_price, ps.position_size, ps.sector FROM portfolio_state ps JOIN watchlist w ON ps.symbol = w.symbol AND ps.market = w.market WHERE ps.position_size > 0 AND ps.is_hidden = 0

Q: "최근 매도 기록"
SQL: SELECT pe.symbol, w.name, pe.entry_price, pe.exit_price, pe.pnl_pct, pe.exit_date, pe.exit_reason FROM position_exits pe JOIN watchlist w ON pe.symbol = w.symbol AND pe.market = w.market ORDER BY pe.exit_date DESC LIMIT 10"""

SYNTHESIS_SYSTEM_PROMPT = """당신은 VIBE 투자 분석 어시스턴트입니다.
SQL 쿼리 결과를 바탕으로 사용자의 질문에 한국어로 답변하세요.
- 핵심 수치를 포함하여 구체적으로 답변
- 투자 조언이 아닌 객관적 데이터 해설
- 결과가 비어있으면 해당 데이터가 없음을 안내"""


# ---------------------------------------------------------------------------
# SQL validation
# ---------------------------------------------------------------------------

def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate that SQL is safe to execute."""
    sql_stripped = sql.strip().rstrip(";")

    # Must be SELECT
    if not sql_stripped.upper().startswith("SELECT"):
        return False, "SELECT 문만 허용됩니다."

    # Forbidden keywords
    forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "REPLACE", "ATTACH", "DETACH"}
    sql_upper = sql_stripped.upper()
    for kw in forbidden:
        if re.search(rf'\b{kw}\b', sql_upper):
            return False, f"'{kw}' 문은 허용되지 않습니다."

    # Check table names against allowlist
    # Extract table names from FROM and JOIN clauses
    table_pattern = re.findall(r'(?:FROM|JOIN)\s+(\w+)', sql_upper)
    for table in table_pattern:
        if table.lower() not in ALLOWED_TABLES:
            return False, f"테이블 '{table}'에 대한 접근이 허용되지 않습니다."

    # Enforce LIMIT
    if "LIMIT" not in sql_upper:
        sql_stripped += f" LIMIT {MAX_ROWS}"

    return True, sql_stripped


# ---------------------------------------------------------------------------
# Core RAG pipeline
# ---------------------------------------------------------------------------

async def generate_sql(question: str) -> dict[str, Any]:
    """Step 1: Generate SQL from natural language question using LLM."""
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
        model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

        prompt = f"{SCHEMA_DESCRIPTION}\n\n[사용자 질문]\n{question}"

        response = await client.messages.create(
            model=model,
            max_tokens=500,
            system=SQL_GENERATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "execute_sql",
                "description": "Execute a SQL SELECT query against the VIBE database",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQLite SELECT query",
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Brief explanation of what this query does",
                        },
                    },
                    "required": ["sql", "explanation"],
                },
            }],
            tool_choice={"type": "tool", "name": "execute_sql"},
        )

        for block in response.content:
            if block.type == "tool_use":
                return {
                    "sql": block.input["sql"],
                    "explanation": block.input.get("explanation", ""),
                }

        return {"error": "LLM did not generate a SQL query"}

    except Exception as e:
        logger.error("SQL generation failed: %s", e, exc_info=True)
        return {"error": f"SQL 생성 실패: {e}"}


async def execute_safe_sql(sql: str) -> dict[str, Any]:
    """Step 2: Validate and execute SQL query."""
    is_valid, result_or_error = validate_sql(sql)
    if not is_valid:
        return {"error": result_or_error, "rows": []}

    safe_sql = result_or_error

    try:
        db = await get_db()
        cursor = await db.execute(safe_sql)
        rows = await cursor.fetchall()

        # Convert to list of dicts
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in rows]

        return {
            "columns": columns,
            "rows": results,
            "row_count": len(results),
            "sql_executed": safe_sql,
        }
    except Exception as e:
        logger.error("SQL execution failed: %s | SQL: %s", e, safe_sql)
        return {"error": f"SQL 실행 실패: {e}", "rows": [], "sql_executed": safe_sql}


async def synthesize_answer(question: str, sql_result: dict) -> str:
    """Step 3: Generate natural language answer from SQL results."""
    if sql_result.get("error"):
        return f"쿼리 오류: {sql_result['error']}"

    rows = sql_result.get("rows", [])
    if not rows:
        return "해당 조건에 맞는 데이터가 없습니다."

    # Truncate result for LLM context
    result_text = json.dumps(rows[:50], ensure_ascii=False, default=str)
    if len(result_text) > 4000:
        result_text = result_text[:4000] + "... (truncated)"

    prompt = (
        f"[원본 질문] {question}\n\n"
        f"[실행된 SQL] {sql_result.get('sql_executed', 'N/A')}\n\n"
        f"[결과 ({sql_result.get('row_count', 0)}건)]\n{result_text}"
    )

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
        model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

        response = await client.messages.create(
            model=model,
            max_tokens=1000,
            system=SYNTHESIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error("Answer synthesis failed: %s", e, exc_info=True)
        # Fallback: return raw data summary
        return f"데이터 {sql_result.get('row_count', 0)}건 조회됨.\n{result_text[:500]}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def rag_query(question: str) -> dict[str, Any]:
    """Run the full SQL-RAG pipeline: question → SQL → execute → answer.

    Returns:
        dict with keys: status, question, answer, sql, sql_explanation, row_count, metadata
    """
    if not settings.LLM_API_KEY:
        return {
            "status": "error",
            "message": "LLM API 키가 설정되지 않았습니다. .env에 LLM_API_KEY를 설정하세요.",
        }

    # Step 1: Generate SQL
    sql_gen = await generate_sql(question)
    if "error" in sql_gen:
        return {"status": "error", "message": sql_gen["error"]}

    sql = sql_gen["sql"]
    sql_explanation = sql_gen.get("explanation", "")

    # Step 2: Execute SQL
    sql_result = await execute_safe_sql(sql)

    # Step 3: Synthesize answer
    answer = await synthesize_answer(question, sql_result)

    return {
        "status": "ok",
        "question": question,
        "answer": answer,
        "sql": sql_result.get("sql_executed", sql),
        "sql_explanation": sql_explanation,
        "row_count": sql_result.get("row_count", 0),
        "error": sql_result.get("error"),
    }

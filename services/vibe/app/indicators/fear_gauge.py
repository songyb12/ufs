"""Fear Gauge — quantitative peak fear phase detection.

Classifies market fear phases from VIX velocity, Fear&Greed momentum,
Put/Call ratio spikes, and VIX term structure.

Phases:
  Calm          — VIX stable <20, F&G >40
  Initial Panic — VIX accelerating upward, F&G dropping rapidly
  Peak Fear     — VIX elevated but velocity decelerating, F&G at extreme low
  Post-Peak     — VIX declining from high, F&G starting to recover

All functions are pure (no DB access).
"""

from __future__ import annotations

PHASE_LABELS = {
    "calm": {
        "en": "Calm",
        "kr": "안정",
        "action_kr": "시장 안정 구간. 기존 전략 유지, 과도한 레버리지 주의.",
    },
    "initial_panic": {
        "en": "Initial Panic",
        "kr": "초기 패닉",
        "action_kr": "공포 확산 초기. 추격 매도 금지, 추가 하락 가능성 높음. 관망 권장.",
    },
    "peak_fear": {
        "en": "Peak Fear",
        "kr": "공포 극점",
        "action_kr": "공포 극대화 구간. 역발상 분할 매수 시작 검토. 급반등 가능성.",
    },
    "post_peak": {
        "en": "Post-Peak",
        "kr": "공포 완화",
        "action_kr": "공포 완화 진행 중. 분할 매수 지속, 단 2차 패닉 가능성 주시.",
    },
}


def compute_fear_gauge(
    macro_history: list[dict],
    sentiment_history: list[dict],
) -> dict:
    """Classify current fear phase from historical data.

    Args:
        macro_history: 20-30+ days of macro_indicators rows (oldest→newest).
                       Must have "vix" and "indicator_date" fields.
        sentiment_history: 20-30+ days of sentiment_data rows (oldest→newest).
                          Must have "fear_greed_index", "put_call_ratio",
                          "vix_term_structure" fields.

    Returns:
        {
            "phase": str,
            "phase_kr": str,
            "confidence": float (0.0-1.0),
            "metrics": {...},
            "action_kr": str,
            "date": str | None,
        }
    """
    metrics = _compute_metrics(macro_history, sentiment_history)

    # Classify phase
    phase_key, confidence = _classify_phase(metrics)
    info = PHASE_LABELS[phase_key]

    date = None
    if macro_history:
        date = macro_history[-1].get("indicator_date")

    return {
        "phase": info["en"],
        "phase_kr": info["kr"],
        "confidence": round(confidence, 2),
        "metrics": metrics,
        "action_kr": info["action_kr"],
        "date": date,
    }


def _compute_metrics(
    macro_history: list[dict],
    sentiment_history: list[dict],
) -> dict:
    """Extract all quantitative fear metrics from histories."""
    metrics: dict = {
        "vix_current": None,
        "vix_velocity_5d": None,
        "vix_acceleration": None,
        "fg_current": None,
        "fg_momentum_5d": None,
        "fg_momentum_10d": None,
        "put_call_current": None,
        "put_call_spike": False,
        "vix_term_current": None,
        "backwardation_streak": 0,
    }

    # ── VIX metrics ──
    vix_values = [
        h.get("vix") for h in macro_history
        if h.get("vix") is not None
    ]

    if vix_values:
        metrics["vix_current"] = vix_values[-1]

    if len(vix_values) >= 6:
        current = vix_values[-1]
        past_5d = vix_values[-6]
        if past_5d > 0:
            metrics["vix_velocity_5d"] = round(
                (current - past_5d) / past_5d, 4
            )

    if len(vix_values) >= 11:
        # Velocity now vs velocity 5 days ago
        v_now = (vix_values[-1] - vix_values[-6]) / max(vix_values[-6], 1.0)
        v_5d_ago = (vix_values[-6] - vix_values[-11]) / max(vix_values[-11], 1.0)
        metrics["vix_acceleration"] = round(v_now - v_5d_ago, 4)

    # ── Fear & Greed metrics ──
    fg_values = [
        h.get("fear_greed_index") for h in sentiment_history
        if h.get("fear_greed_index") is not None
    ]

    if fg_values:
        metrics["fg_current"] = fg_values[-1]

    if len(fg_values) >= 6:
        metrics["fg_momentum_5d"] = fg_values[-1] - fg_values[-6]

    if len(fg_values) >= 11:
        metrics["fg_momentum_10d"] = fg_values[-1] - fg_values[-11]

    # ── Put/Call metrics ──
    pc_values = [
        h.get("put_call_ratio") for h in sentiment_history
        if h.get("put_call_ratio") is not None
    ]
    if pc_values:
        metrics["put_call_current"] = pc_values[-1]
        metrics["put_call_spike"] = pc_values[-1] > 1.2

    # ── VIX Term Structure ──
    vts_values = [
        h.get("vix_term_structure") for h in sentiment_history
        if h.get("vix_term_structure") is not None
    ]
    if vts_values:
        metrics["vix_term_current"] = vts_values[-1]
        # Count consecutive backwardation days from the end
        streak = 0
        for v in reversed(vts_values):
            if v == "backwardation":
                streak += 1
            else:
                break
        metrics["backwardation_streak"] = streak

    return metrics


def _classify_phase(metrics: dict) -> tuple[str, float]:
    """Classify fear phase from metrics. Returns (phase_key, confidence)."""
    vix = metrics.get("vix_current")
    vix_vel = metrics.get("vix_velocity_5d")
    vix_acc = metrics.get("vix_acceleration")
    fg = metrics.get("fg_current")
    fg_mom_5d = metrics.get("fg_momentum_5d")
    pc_spike = metrics.get("put_call_spike", False)
    backwardation = metrics.get("backwardation_streak", 0)

    # Default: Calm
    if vix is None or fg is None:
        return "calm", 0.3

    # Scoring for each phase
    scores: dict[str, float] = {
        "calm": 0.0,
        "initial_panic": 0.0,
        "peak_fear": 0.0,
        "post_peak": 0.0,
    }

    # ── Calm signals ──
    if vix < 20:
        scores["calm"] += 2.0
    if fg is not None and fg > 40:
        scores["calm"] += 1.5
    if vix_vel is not None and abs(vix_vel) < 0.05:
        scores["calm"] += 1.0

    # ── Initial Panic signals ──
    if vix_vel is not None and vix_vel > 0.15:
        scores["initial_panic"] += 2.5
    if vix_vel is not None and vix_vel > 0.30:
        scores["initial_panic"] += 1.0  # Extra for extreme velocity
    if fg_mom_5d is not None and fg_mom_5d < -10:
        scores["initial_panic"] += 2.0
    if vix_acc is not None and vix_acc > 0.05:
        scores["initial_panic"] += 1.5  # Accelerating = getting worse
    if pc_spike:
        scores["initial_panic"] += 1.0

    # ── Peak Fear signals ──
    if vix is not None and vix > 25:
        scores["peak_fear"] += 1.0
    if vix is not None and vix > 30:
        scores["peak_fear"] += 1.0
    if vix_vel is not None and 0 < vix_vel < 0.15 and vix > 25:
        scores["peak_fear"] += 1.5  # Velocity slowing but still elevated
    if vix_acc is not None and vix_acc < -0.05 and vix > 25:
        scores["peak_fear"] += 2.0  # Decelerating = peaking
    if fg is not None and fg < 25:
        scores["peak_fear"] += 2.0
    if fg is not None and fg < 15:
        scores["peak_fear"] += 1.0
    if backwardation >= 3:
        scores["peak_fear"] += 1.0

    # ── Post-Peak signals ──
    if vix is not None and vix > 22:
        scores["post_peak"] += 0.5  # Still elevated
    if vix_vel is not None and vix_vel < -0.05:
        scores["post_peak"] += 2.5  # VIX declining
    if fg_mom_5d is not None and fg_mom_5d > 3:
        scores["post_peak"] += 2.0  # F&G recovering
    if fg is not None and 20 < fg < 40:
        scores["post_peak"] += 1.0  # Still fearful but not extreme

    # Select highest-scoring phase
    best_phase = max(scores, key=lambda k: scores[k])
    best_score = scores[best_phase]
    total = sum(scores.values())

    # Confidence = how dominant the winning phase is
    if total > 0:
        confidence = min(1.0, best_score / total * 1.5)
    else:
        confidence = 0.3

    # Minimum threshold: need at least 2.0 score to override calm
    if best_phase != "calm" and best_score < 2.0:
        best_phase = "calm"
        confidence = 0.4

    return best_phase, max(0.3, min(1.0, confidence))

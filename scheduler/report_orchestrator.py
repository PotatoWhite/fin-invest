"""Report cycle orchestration: prepare data → trigger Claude Code → deliver."""

import json
import logging
from datetime import datetime

from db import Database
from engine.regime_detector import detect_regime
from engine.signal_detector import detect_signals
from engine.signal_filter import run_filter_pipeline
from engine.prediction_evaluator import evaluate_expired_predictions
from scheduler.event_calendar import check_upcoming_events, determine_active_experts
from bot.claude_bridge import call_claude_async
from config import SIGNAL_QUALITY_TIER2_THRESHOLD

logger = logging.getLogger(__name__)


async def prepare_report_cycle(db: Database) -> dict:
    """Prepare all data for a Tier 3 report cycle."""
    logger.info("Preparing report cycle...")

    # 1. Evaluate expired predictions
    evaluated = evaluate_expired_predictions(db)

    # 2. Detect current regime
    regime = detect_regime(db)

    # 3. Run signal detection
    raw_signals = detect_signals(db)
    filtered = run_filter_pipeline(db, raw_signals) if raw_signals else []

    # 4. Check upcoming events
    events = check_upcoming_events(db)

    # 5. Determine active experts
    high_quality_signals = [
        s for s in filtered if s.final_quality >= SIGNAL_QUALITY_TIER2_THRESHOLD
    ]
    experts = determine_active_experts(
        db, regime.regime,
        [{"ticker": s.signal.ticker} for s in high_quality_signals],
        events)

    # 6. Create cycle record
    cycle_id = datetime.now().strftime("%Y-%m-%dT%H:%M")
    db.insert("reports",
              cycle_id=cycle_id,
              report_type="tier3_full",
              triggered_by="schedule",
              agents_activated=json.dumps(experts))

    result = {
        "cycle_id": cycle_id,
        "regime": regime.regime,
        "regime_score": regime.score,
        "experts": experts,
        "signals_count": len(filtered),
        "high_quality_signals": len(high_quality_signals),
        "events_count": len(events),
        "predictions_evaluated": evaluated,
    }

    logger.info("Report cycle prepared: %s", result)
    return result


async def run_tier3_report(db: Database) -> str | None:
    """Run a full Tier 3 report cycle using Claude Code."""
    prep = await prepare_report_cycle(db)

    # Build leader prompt
    prompt = (
        f"보고 사이클 {prep['cycle_id']}을 실행합니다.\n"
        f"현재 레짐: {prep['regime']} (score: {prep['regime_score']})\n"
        f"활성화할 전문가: {', '.join(prep['experts']) if prep['experts'] else '없음 (리더만)'}\n"
        f"감지된 신호: {prep['signals_count']}개 (품질 0.7+: {prep['high_quality_signals']}개)\n"
        f"이벤트: {prep['events_count']}개\n"
        f"검증된 예측: {prep['predictions_evaluated']}개\n\n"
        "MCP 도구를 사용하여 데이터를 조회하고, "
        "전문가를 서브에이전트로 실행하여 분석한 후, "
        "종합 보고서를 작성하세요. CLAUDE.md의 보고서 형식을 따르세요.\n"
        "보고서 완료 후 save_report()로 DB에 저장하세요."
    )

    logger.info("Triggering leader agent for cycle %s", prep["cycle_id"])
    leader_result = await call_claude_async(prompt, agent="leader")

    # Run goguma independently (parallel would be ideal, but sequential is safer)
    goguma_prompt = (
        f"보고 사이클 {prep['cycle_id']}.\n"
        "독립적으로 시장을 분석하고, 포트폴리오를 점검하고, "
        "매매 추천을 작성하세요."
    )
    logger.info("Triggering goguma agent for cycle %s", prep["cycle_id"])
    goguma_result = await call_claude_async(goguma_prompt, agent="goguma")

    # Combine results
    full_report = f"{leader_result}\n\n━━━━━━━━━━━━━━━━━━\n🍠 고구마의 코너\n━━━━━━━━━━━━━━━━━━\n\n{goguma_result}"

    # Update report in DB
    db.execute(
        "UPDATE reports SET content_telegram=?, notification_sent=0 "
        "WHERE cycle_id=?",
        (full_report[:4000], prep["cycle_id"]))

    logger.info("Report cycle %s complete (%d chars)",
                prep["cycle_id"], len(full_report))
    return full_report


async def run_tier2_alert(db: Database, signal_description: str,
                          ticker: str) -> str | None:
    """Run a quick Tier 2 alert analysis."""
    prompt = (
        f"긴급 신호 분석:\n{signal_description}\n\n"
        f"종목: {ticker}\n"
        "MCP 도구로 데이터를 조회하여 간략한 분석을 제공하세요.\n"
        "인과 사슬이 있으면 추적하세요."
    )
    return await call_claude_async(prompt)

"""Market regime detection: Risk-On / Transition / Risk-Off / Crisis."""

from dataclasses import dataclass
from db import Database


@dataclass
class RegimeResult:
    regime: str          # 'risk_on', 'transition', 'risk_off', 'crisis'
    score: float         # 0.0 (crisis) ~ 1.0 (risk-on)
    vix: float | None
    vix_score: float
    spread_score: float
    breadth_score: float
    flow_score: float


def _get_param(db: Database, name: str, default: float) -> float:
    row = db.query_one(
        "SELECT value * calibration_factor as v FROM model_params "
        "WHERE category='regime' AND param_name=?", (name,))
    return row["v"] if row else default


def vix_to_score(vix: float | None) -> float:
    """VIX → 0~1 score. Low VIX = high score (risk-on)."""
    if vix is None:
        return 0.5  # neutral if unknown
    if vix < 12:
        return 1.0
    if vix < 18:
        return 0.8
    if vix < 25:
        return 0.5
    if vix < 35:
        return 0.2
    return 0.0


def spread_to_score(db: Database) -> float:
    """HY spread → 0~1 score. Narrow spread = risk-on."""
    # For now, use VIX as proxy since we don't have direct HY spread data
    # TODO: Add HY spread data source
    return 0.5  # neutral placeholder


def breadth_to_score(db: Database) -> float:
    """Market breadth → 0~1 score."""
    # TODO: Compute from advance/decline data
    return 0.5  # neutral placeholder


def flow_to_score(db: Database) -> float:
    """Safe haven flow → 0~1 score. Low safe-haven flow = risk-on."""
    # Check gold movement as proxy
    gold = db.get_latest_indicator("commodity", "GC")
    if gold and gold["change_pct"]:
        change = gold["change_pct"]
        if change > 2.0:  # Gold surging = risk-off
            return 0.2
        if change > 0.5:
            return 0.4
        if change < -0.5:
            return 0.8
        return 0.5
    return 0.5


def detect_regime(db: Database) -> RegimeResult:
    """Detect current market regime from multiple indicators."""
    # Get VIX
    vix_row = db.get_latest_indicator("index", ".VIX")
    vix = vix_row["value"] if vix_row else None

    # Get weights from model_params
    vix_w = _get_param(db, "vix_weight", 0.35)
    spread_w = _get_param(db, "spread_weight", 0.25)
    breadth_w = _get_param(db, "breadth_weight", 0.20)
    flow_w = _get_param(db, "flow_weight", 0.20)

    # Compute component scores
    v_score = vix_to_score(vix)
    s_score = spread_to_score(db)
    b_score = breadth_to_score(db)
    f_score = flow_to_score(db)

    # Weighted regime score
    score = (v_score * vix_w + s_score * spread_w +
             b_score * breadth_w + f_score * flow_w)

    # Get thresholds from model_params
    risk_on_threshold = _get_param(db, "score_risk_on", 0.7)
    transition_threshold = _get_param(db, "score_transition", 0.4)
    risk_off_threshold = _get_param(db, "score_risk_off", 0.15)

    if score > risk_on_threshold:
        regime = "risk_on"
    elif score > transition_threshold:
        regime = "transition"
    elif score > risk_off_threshold:
        regime = "risk_off"
    else:
        regime = "crisis"

    return RegimeResult(
        regime=regime, score=round(score, 3),
        vix=vix, vix_score=round(v_score, 3),
        spread_score=round(s_score, 3),
        breadth_score=round(b_score, 3),
        flow_score=round(f_score, 3),
    )

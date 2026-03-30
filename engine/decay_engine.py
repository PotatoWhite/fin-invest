"""Half-life decay functions for news impact calculation."""

import math
from datetime import datetime


def exponential_decay(magnitude: float, elapsed_hours: float,
                      half_life_hours: float, confidence: float) -> float:
    """Standard exponential decay: magnitude * e^(-λt) * confidence."""
    if half_life_hours <= 0 or elapsed_hours < 0:
        return 0.0
    # 3x half-life = residual < 12.5%, ignore
    if elapsed_hours > half_life_hours * 3:
        return 0.0
    decay = math.exp(-0.693 * elapsed_hours / half_life_hours)
    return magnitude * decay * confidence


def step_decay(magnitude: float, elapsed_hours: float,
               trigger_hours: float, confidence: float) -> float:
    """Full value until trigger, then rapid decay."""
    if elapsed_hours < trigger_hours:
        return magnitude * confidence
    # After trigger: decay with 2-hour half-life
    post_trigger = elapsed_hours - trigger_hours
    return exponential_decay(magnitude, post_trigger, 2.0, confidence)


def dual_decay(magnitude: float, elapsed_hours: float,
               half_life_hours: float, confidence: float) -> float:
    """30% decays fast (half_life/3), 70% decays at full half_life."""
    fast_part = exponential_decay(
        magnitude * 0.3, elapsed_hours, half_life_hours / 3, confidence)
    slow_part = exponential_decay(
        magnitude * 0.7, elapsed_hours, half_life_hours, confidence)
    return fast_part + slow_part


def residual_decay(magnitude: float, elapsed_hours: float,
                   half_life_hours: float, confidence: float,
                   residual_pct: float = 0.1) -> float:
    """Exponential decay with a fixed residual that doesn't decay."""
    residual = magnitude * residual_pct * confidence
    decaying = exponential_decay(
        magnitude * (1 - residual_pct), elapsed_hours,
        half_life_hours, confidence)
    return decaying + residual


# Decay type dispatcher
DECAY_FUNCTIONS = {
    "exponential": exponential_decay,
    "step": step_decay,
    "dual": dual_decay,
    "residual": residual_decay,
}


def calculate_residual(magnitude: float, elapsed_hours: float,
                       half_life_hours: float, confidence: float,
                       decay_type: str = "exponential",
                       **kwargs) -> float:
    """Calculate residual impact using the specified decay type."""
    func = DECAY_FUNCTIONS.get(decay_type, exponential_decay)
    return func(magnitude, elapsed_hours, half_life_hours, confidence, **kwargs)


def hours_since(timestamp_str: str) -> float:
    """Calculate hours elapsed since a timestamp string."""
    try:
        ts = datetime.fromisoformat(timestamp_str)
        delta = datetime.now() - ts
        return delta.total_seconds() / 3600
    except (ValueError, TypeError):
        return float("inf")

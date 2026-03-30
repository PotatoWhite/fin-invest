"""Tests for engine/decay_engine.py."""

import pytest
from engine.decay_engine import (
    exponential_decay, step_decay, dual_decay, residual_decay,
    calculate_residual,
)


class TestExponentialDecay:
    def test_no_decay_at_zero(self):
        result = exponential_decay(10.0, 0, 24, 1.0)
        assert result == pytest.approx(10.0, rel=0.01)

    def test_half_at_halflife(self):
        result = exponential_decay(10.0, 24, 24, 1.0)
        assert result == pytest.approx(5.0, rel=0.01)

    def test_quarter_at_double_halflife(self):
        result = exponential_decay(10.0, 48, 24, 1.0)
        assert result == pytest.approx(2.5, rel=0.01)

    def test_expired_after_3x_halflife(self):
        result = exponential_decay(10.0, 73, 24, 1.0)
        assert result == 0.0

    def test_confidence_scaling(self):
        result = exponential_decay(10.0, 0, 24, 0.5)
        assert result == pytest.approx(5.0, rel=0.01)

    def test_zero_halflife(self):
        assert exponential_decay(10.0, 5, 0, 1.0) == 0.0

    def test_negative_elapsed(self):
        assert exponential_decay(10.0, -1, 24, 1.0) == 0.0


class TestStepDecay:
    def test_before_trigger(self):
        result = step_decay(10.0, 5, 24, 0.9)
        assert result == pytest.approx(9.0)

    def test_after_trigger(self):
        result = step_decay(10.0, 30, 24, 0.9)
        assert result < 9.0  # Should decay rapidly


class TestDualDecay:
    def test_at_zero(self):
        result = dual_decay(10.0, 0, 24, 1.0)
        assert result == pytest.approx(10.0, rel=0.01)

    def test_fast_component_decays_faster(self):
        early = dual_decay(10.0, 8, 24, 1.0)  # 8h = fast component's halflife
        simple = exponential_decay(10.0, 8, 24, 1.0)
        # Dual should be less than simple because fast part decayed more
        assert early < simple


class TestResidualDecay:
    def test_never_reaches_zero(self):
        result = residual_decay(10.0, 100, 24, 1.0, residual_pct=0.1)
        assert result >= 1.0  # 10% residual = 1.0


class TestCalculateResidual:
    def test_dispatch_exponential(self):
        result = calculate_residual(10, 12, 24, 0.9, "exponential")
        assert result > 0

    def test_dispatch_step(self):
        result = calculate_residual(10, 5, 24, 0.9, "step")
        assert result == pytest.approx(9.0)

    def test_dispatch_unknown(self):
        # Falls back to exponential
        result = calculate_residual(10, 12, 24, 0.9, "unknown_type")
        assert result > 0

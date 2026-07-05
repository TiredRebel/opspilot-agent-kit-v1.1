import pytest
from app.retrieval import blend_confidence
from app.settings import settings


def test_blend_formula():
    assert blend_confidence(1.0, 0.40) == 0.70
    assert blend_confidence(0.8, 0.6) == 0.7
    assert blend_confidence(0.0, 0.0) == 0.0
    assert blend_confidence(1.0, 1.0) == 1.0


def test_gate_boundary_exactly_070_passes_0699_escalates():
    passing = blend_confidence(1.0, 0.40)  # exactly 0.70
    escalating = blend_confidence(1.0, 0.398)  # exactly 0.699

    assert passing == 0.70
    assert passing >= settings.confidence_threshold

    assert escalating == pytest.approx(0.699)
    assert escalating < settings.confidence_threshold

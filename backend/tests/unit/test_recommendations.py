"""Sprint 8 / D38: tests for architecture-aware recommendation patterns."""

from app.modules.cv_pipeline.recommendations import generate_recommendation
from app.schemas.models import ArchViolation


def _violation(violation_type, **overrides):
    defaults = dict(
        id="v1", verdict="VIOLATION", source_component="a", target_component="b",
        expected="a -> c -> b", actual="a -> b (direct)", severity="medium", description="",
    )
    defaults.update(overrides)
    return ArchViolation(violation_type=violation_type, **defaults)


def test_layer_violation_mentions_source_target_and_expected():
    rec = generate_recommendation(_violation("layer_violation"))
    assert "a" in rec and "b" in rec and "a -> c -> b" in rec


def test_forbidden_dependency_mentions_removal():
    rec = generate_recommendation(_violation("forbidden_dependency"))
    assert "Remove" in rec


def test_missing_dependency_mentions_adding_the_integration():
    rec = generate_recommendation(_violation("missing_dependency"))
    assert "Add" in rec


def test_unexpected_dependency_mentions_updating_the_diagram():
    rec = generate_recommendation(_violation("unexpected_dependency"))
    assert "diagram" in rec.lower()


def test_cycle_violation_mentions_breaking_the_cycle():
    rec = generate_recommendation(_violation("cycle_violation"))
    assert "cycle" in rec.lower()


def test_unknown_violation_type_falls_back_to_default_pattern():
    rec = generate_recommendation(_violation(None))
    assert "a" in rec and "b" in rec

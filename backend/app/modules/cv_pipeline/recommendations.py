"""
Sprint 8 / D38: architecture-aware recommendation patterns for common
violation classes.

Each pattern is a template keyed by the real `ViolationType` enum from
`backend/app/schemas/models.py` - no separate violation taxonomy invented.
"""

from __future__ import annotations

from app.schemas.models import ArchViolation

_PATTERNS: dict[str, str] = {
    "layer_violation": (
        "Route the call through the intended intermediate component instead of "
        "calling {target} directly from {source}. Expected path: {expected}."
    ),
    "forbidden_dependency": (
        "Remove the dependency from {source} to {target}; it is explicitly "
        "forbidden by the architecture rules. Actual: {actual}."
    ),
    "missing_dependency": (
        "Add the missing integration from {source} to {target} described in the "
        "intended architecture (expected: {expected}), or update the diagram if "
        "this dependency is no longer required."
    ),
    "unexpected_dependency": (
        "{source} -> {target} exists in the code but isn't documented in the "
        "intended architecture (actual: {actual}). Either update the diagram to "
        "reflect this real dependency, or remove it from the code if unintended."
    ),
    "cycle_violation": (
        "{source} and {target} participate in a dependency cycle. Break it by "
        "introducing an interface/inversion point, or by removing one direction "
        "of the dependency."
    ),
    "interface_violation": (
        "{source}'s usage of {target} doesn't match {target}'s intended interface "
        "contract (expected: {expected}; actual: {actual}). Align the call to the "
        "documented interface."
    ),
}

_DEFAULT_PATTERN = "Review the dependency from {source} to {target} against the intended architecture."


def generate_recommendation(violation: ArchViolation) -> str:
    """Fill in the pattern for this violation's type with its real field values."""
    violation_type = violation.violation_type.value if violation.violation_type else None
    pattern = _PATTERNS.get(violation_type, _DEFAULT_PATTERN)
    return pattern.format(
        source=violation.source_component,
        target=violation.target_component,
        expected=violation.expected or "(not specified)",
        actual=violation.actual or "(not specified)",
    )

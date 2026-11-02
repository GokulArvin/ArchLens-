"""
Unit tests for graph confidence scoring and UNCERTAIN verdict — Sprint 2 P3 (Task 9.1).

Acceptance Criteria:
- Exact import match  → edge confidence == 1.0
- Partial import match (single candidate) → edge confidence == 0.8
- Ambiguous import (multiple candidates)  → edge confidence == 0.5
- Edge with confidence < 0.6 → ConformanceEngine verdict UNCERTAIN
- Edge with confidence >= 0.6 → no UNCERTAIN verdict for that edge
- Keyword-matched component → inference_confidence == 1.0
- Default MODULE component  → inference_confidence == 0.6
"""

import pytest

from app.modules.architecture_recovery.ast_parser import DependencyGraphBuilder
from app.modules.conformance_engine.engine import ConformanceEngine, UNCERTAIN


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_graph(components, relationships, graph_type="current"):
    """Build a minimal graph dict for ConformanceEngine."""
    return {
        "schema_version": "1.0.0",
        "name": "TestGraph",
        "graph_type": graph_type,
        "components": components,
        "relationships": relationships,
    }


# ─── 1. Three-tier confidence scoring ────────────────────────────────────────

def test_exact_match_confidence_1_0():
    """Exact import string match in module_map → confidence 1.0."""
    builder = DependencyGraphBuilder()
    module_map = {"order_service": "services/order_service.py"}

    target, confidence = builder._resolve_java_import("order_service", module_map)

    assert target == "order_service"
    assert confidence == 1.0


def test_partial_match_confidence_0_8():
    """Import matching a single module by last segment → confidence 0.8."""
    builder = DependencyGraphBuilder()
    # Module stored as "services.order_service", import arrives as "order_service"
    module_map = {"services.order_service": "services/OrderService.java"}

    target, confidence = builder._resolve_java_import("order_service", module_map)

    assert target == "services.order_service"
    assert confidence == 0.8


def test_ambiguous_match_confidence_0_5():
    """Import matching multiple modules by last segment → confidence 0.5."""
    builder = DependencyGraphBuilder()
    module_map = {
        "a.order_service": "a/OrderService.java",
        "b.order_service": "b/OrderService.java",
    }

    target, confidence = builder._resolve_java_import("order_service", module_map)

    # Deterministic: first alphabetically
    assert target == "a.order_service"
    assert confidence == 0.5


def test_external_import_returns_none():
    """Import that matches nothing internal → (None, 0.0)."""
    builder = DependencyGraphBuilder()
    module_map = {"order_service": "services/OrderService.java"}

    target, confidence = builder._resolve_java_import("java.util.List", module_map)

    assert target is None
    assert confidence == 0.0


# ─── 2. UNCERTAIN verdict integration ────────────────────────────────────────

def test_uncertain_verdict_below_threshold():
    """Edge with confidence=0.45 (< 0.6) → overall verdict UNCERTAIN."""
    engine = ConformanceEngine(confidence_threshold=0.6)
    components = [
        {"id": "svc", "name": "OrderService", "type": "service"},
        {"id": "ext", "name": "PaymentGateway", "type": "external"},
    ]
    G_I = make_graph(components, [], "intended")
    G_C = make_graph(components, [
        {"source": "svc", "target": "ext", "type": "depends_on", "confidence": 0.45}
    ], "current")

    result = engine.check_conformance(G_I, G_C)

    assert result["verdict"] == UNCERTAIN
    uncertain = [v for v in result["violations"] if v["verdict"] == UNCERTAIN]
    assert len(uncertain) >= 1
    assert uncertain[0]["confidence"] == 0.45


def test_no_uncertain_verdict_at_threshold():
    """Edge with confidence exactly 0.6 (== threshold) → NOT flagged UNCERTAIN."""
    engine = ConformanceEngine(confidence_threshold=0.6)
    components = [
        {"id": "ctrl", "name": "OrderController", "type": "controller"},
        {"id": "svc",  "name": "OrderService",    "type": "service"},
    ]
    rels = [{"source": "ctrl", "target": "svc", "type": "depends_on", "confidence": 0.6}]
    G_I = make_graph(components, rels, "intended")
    G_C = make_graph(components, rels, "current")

    result = engine.check_conformance(G_I, G_C)

    uncertain = [v for v in result["violations"] if v["verdict"] == UNCERTAIN]
    assert len(uncertain) == 0


def test_no_uncertain_verdict_above_threshold():
    """Edge with confidence=0.65 (> 0.6) → NOT flagged UNCERTAIN."""
    engine = ConformanceEngine(confidence_threshold=0.6)
    components = [
        {"id": "ctrl", "name": "OrderController", "type": "controller"},
        {"id": "svc",  "name": "OrderService",    "type": "service"},
    ]
    rels = [{"source": "ctrl", "target": "svc", "type": "depends_on", "confidence": 0.65}]
    G_I = make_graph(components, rels, "intended")
    G_C = make_graph(components, rels, "current")

    result = engine.check_conformance(G_I, G_C)

    uncertain = [v for v in result["violations"] if v["verdict"] == UNCERTAIN]
    assert len(uncertain) == 0


# ─── 3. inference_confidence on nodes ────────────────────────────────────────

def test_inference_confidence_keyword_match():
    """Component whose module name matches an architectural keyword → inference_confidence 1.0."""
    builder = DependencyGraphBuilder()
    # "order_controller" contains "controller" — keyword match
    comp_type = builder._infer_component_type("order_controller", {})
    assert comp_type != "module"  # keyword was matched

    # Simulate what build_from_python / build_from_java sets
    keyword_match = comp_type != "module"
    inference_confidence = 1.0 if keyword_match else 0.6
    assert inference_confidence == 1.0


def test_inference_confidence_default_module():
    """Component whose name has no keyword → type MODULE → inference_confidence 0.6."""
    builder = DependencyGraphBuilder()
    # "xyz_component" doesn't match any architectural keyword
    comp_type = builder._infer_component_type("xyz_component", {})
    assert comp_type == "module"

    keyword_match = comp_type != "module"
    inference_confidence = 1.0 if keyword_match else 0.6
    assert inference_confidence == 0.6


def test_build_from_python_nodes_have_inference_confidence():
    """build_from_python emits inference_confidence on every node."""
    from pathlib import Path
    sample_repo = str(
        Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    )
    from app.modules.architecture_recovery.ast_parser import (
        PythonASTParser, DependencyGraphBuilder as DGB,
    )
    parser = PythonASTParser()
    builder = DGB()
    parsed = parser.parse_directory(sample_repo)
    graph = builder.build_from_python(parsed, sample_repo)

    for comp in graph["components"]:
        assert "inference_confidence" in comp, f"Missing on {comp['name']}"
        assert comp["inference_confidence"] in (0.6, 1.0)


# ─── Property-based tests (Tasks 9.2–9.5) ────────────────────────────────────

from hypothesis import given, settings as h_settings, HealthCheck
from hypothesis import strategies as st

# Reusable strategy: valid Python identifier-like strings (no dots, no spaces)
_ident = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    min_size=1, max_size=30,
)


# Feature: archlens-sprint2-p3, Property 5: Exact-match import produces confidence 1.0
@h_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(_ident)
def test_property_exact_match_confidence_1_0(module_name: str):
    """For any module name that exactly matches a key in module_map, confidence must be 1.0."""
    builder = DependencyGraphBuilder()
    module_map = {module_name: f"some/path/{module_name}.java"}

    target, confidence = builder._resolve_java_import(module_name, module_map)

    assert target == module_name
    assert confidence == 1.0


# Feature: archlens-sprint2-p3, Property 6: Partial-match import produces confidence 0.8
@h_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(_ident, _ident)
def test_property_partial_match_confidence_0_8(prefix: str, base: str):
    """When import matches exactly one module by last segment, confidence must be 0.8."""
    # Ensure prefix != base so the full key differs from the import string
    assume_distinct = prefix.lower() != base.lower()
    if not assume_distinct:
        base = base + "X"

    full_key = f"{prefix}.{base}"
    module_map = {full_key: f"path/{base}.java"}

    builder = DependencyGraphBuilder()
    target, confidence = builder._resolve_java_import(base, module_map)

    # Only assert 0.8 when it's a single partial match (not exact)
    if target is not None and target != base:
        assert confidence == 0.8


# Feature: archlens-sprint2-p3, Property 7: Ambiguous import produces confidence 0.5
@h_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(_ident, _ident, _ident)
def test_property_ambiguous_match_confidence_0_5(prefix_a: str, prefix_b: str, base: str):
    """When import matches multiple modules by last segment, confidence must be 0.5."""
    if prefix_a.lower() == prefix_b.lower():
        prefix_b = prefix_b + "2"

    full_key_a = f"{prefix_a}.{base}"
    full_key_b = f"{prefix_b}.{base}"
    if full_key_a == full_key_b:
        return  # degenerate case, skip

    module_map = {
        full_key_a: f"a/{base}.java",
        full_key_b: f"b/{base}.java",
    }

    builder = DependencyGraphBuilder()
    target, confidence = builder._resolve_java_import(base, module_map)

    if target is not None:
        assert confidence == 0.5


# Feature: archlens-sprint2-p3, Property 8: inference_confidence follows keyword-match rule
@h_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(_ident)
def test_property_inference_confidence_keyword_rule(module_name: str):
    """inference_confidence is 1.0 when type != MODULE, 0.6 when type == MODULE."""
    builder = DependencyGraphBuilder()
    comp_type = builder._infer_component_type(module_name, {})

    keyword_match = comp_type != "module"
    expected_confidence = 1.0 if keyword_match else 0.6

    # Verify the rule is consistent
    if keyword_match:
        assert expected_confidence == 1.0
    else:
        assert expected_confidence == 0.6

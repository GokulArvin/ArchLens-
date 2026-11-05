"""
Unit tests for the Conformance Engine (Module E).
"""

import pytest
from app.modules.conformance_engine.engine import ConformanceEngine, VIOLATION, CONFORMANT, MISSING


@pytest.fixture
def engine():
    return ConformanceEngine()


def make_graph(components, relationships):
    return {"components": components, "relationships": relationships}


def test_conformant_graph(engine):
    """No violations when G_I and G_C match perfectly."""
    components = [
        {"id": "controller", "name": "OrderController", "type": "controller"},
        {"id": "service", "name": "OrderService", "type": "service"},
    ]
    relationships = [{"source": "controller", "target": "service", "type": "depends_on"}]
    G_I = make_graph(components, relationships)
    G_C = make_graph(components, relationships)

    result = engine.check_conformance(G_I, G_C)
    assert result["verdict"] == CONFORMANT
    assert len(result["violations"]) == 0


def test_forbidden_dependency_detected(engine):
    """Controller → Repository should be flagged as VIOLATION."""
    components = [
        {"id": "ctrl", "name": "OrderController", "type": "controller"},
        {"id": "repo", "name": "OrderRepository", "type": "repository"},
    ]
    G_I = make_graph(components, [])
    G_C = make_graph(components, [
        {"source": "ctrl", "target": "repo", "type": "depends_on"}
    ])

    result = engine.check_conformance(G_I, G_C)
    assert result["verdict"] == VIOLATION
    violations = result["violations"]
    assert any(v["violation_type"] == "forbidden_dependency" for v in violations)


def test_missing_dependency_detected(engine):
    """Dependencies in G_I not present in G_C → MISSING."""
    components = [
        {"id": "svc", "name": "OrderService", "type": "service"},
        {"id": "repo", "name": "OrderRepository", "type": "repository"},
    ]
    G_I = make_graph(components, [{"source": "svc", "target": "repo"}])
    G_C = make_graph(components, [])

    result = engine.check_conformance(G_I, G_C)
    missing = [v for v in result["violations"] if v["verdict"] == MISSING]
    assert len(missing) >= 1


def test_cycle_detection(engine):
    """Cycles in G_C should be flagged."""
    components = [
        {"id": "a", "name": "A", "type": "service"},
        {"id": "b", "name": "B", "type": "service"},
        {"id": "c", "name": "C", "type": "service"},
    ]
    G_I = make_graph(components, [])
    G_C = make_graph(components, [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
        {"source": "c", "target": "a"},
    ])

    result = engine.check_conformance(G_I, G_C)
    cycles = [v for v in result["violations"] if v.get("violation_type") == "cycle_violation"]
    assert len(cycles) >= 1


def test_summary_counts(engine):
    """Verify summary counts are correct."""
    components = [
        {"id": "ctrl", "name": "FrontController", "type": "controller"},
        {"id": "db", "name": "Database", "type": "database"},
    ]
    G_I = make_graph(components, [])
    G_C = make_graph(components, [
        {"source": "ctrl", "target": "db", "type": "depends_on"}
    ])

    result = engine.check_conformance(G_I, G_C)
    assert result["summary"]["total_violations"] == len(result["violations"])

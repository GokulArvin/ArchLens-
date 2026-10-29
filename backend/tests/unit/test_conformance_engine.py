"""
Unit tests for the Conformance Engine (Module E) - Sprint 1 P3 Deliverables.

Acceptance Criteria:
- Versioned graph schema
- Rule schema (ALLOW / FORBID / REQUIRE)
- Example graphs
- Initial unit tests for CONFORMANT, VIOLATION, MISSING, UNEXPECTED and UNCERTAIN
"""

import json
from pathlib import Path
import pytest

from app.modules.conformance_engine.engine import (
    ConformanceEngine,
    CONFORMANT,
    VIOLATION,
    MISSING,
    UNEXPECTED,
    UNCERTAIN,
)
from app.schemas.models import (
    ArchGraph,
    IntendedGraph,
    CurrentGraph,
    ArchitectureRule,
    RuleSet,
    RuleAction,
    RuleCategory,
    ComponentType,
    RelationshipType,
)


@pytest.fixture
def engine():
    return ConformanceEngine()


def make_graph(components, relationships, graph_type="intended"):
    return {
        "schema_version": "1.0.0",
        "name": "TestGraph",
        "graph_type": graph_type,
        "components": components,
        "relationships": relationships,
    }


# ─── 1. CONFORMANT Unit Test ──────────────────────────────────────────────────

def test_conformant_graph(engine):
    """Verdict CONFORMANT when G_I and G_C match and adhere to allowed patterns."""
    components = [
        {"id": "controller", "name": "OrderController", "type": "controller"},
        {"id": "service", "name": "OrderService", "type": "service"},
    ]
    relationships = [{"source": "controller", "target": "service", "type": "depends_on"}]
    G_I = make_graph(components, relationships, "intended")
    G_C = make_graph(components, relationships, "current")

    result = engine.check_conformance(G_I, G_C)
    assert result["verdict"] == CONFORMANT
    assert len(result["violations"]) == 0
    assert result["summary"]["verdicts"][CONFORMANT] >= 1


# ─── 2. VIOLATION Unit Tests (Forbidden & Cycle) ──────────────────────────────

def test_forbidden_dependency_detected(engine):
    """Verdict VIOLATION: Controller → Repository violates layered constraints."""
    components = [
        {"id": "ctrl", "name": "OrderController", "type": "controller"},
        {"id": "repo", "name": "OrderRepository", "type": "repository"},
    ]
    G_I = make_graph(components, [], "intended")
    G_C = make_graph(components, [
        {"source": "ctrl", "target": "repo", "type": "depends_on", "confidence": 1.0}
    ], "current")

    result = engine.check_conformance(G_I, G_C)
    assert result["verdict"] == VIOLATION
    violations = result["violations"]
    assert any(
        v["verdict"] == VIOLATION and v["violation_type"] == "forbidden_dependency"
        for v in violations
    )
    assert result["summary"]["verdicts"][VIOLATION] >= 1


def test_cycle_detection(engine):
    """Verdict VIOLATION: Cycles in G_C must be flagged as cycle_violation."""
    components = [
        {"id": "a", "name": "A", "type": "service"},
        {"id": "b", "name": "B", "type": "service"},
        {"id": "c", "name": "C", "type": "service"},
    ]
    G_I = make_graph(components, [], "intended")
    G_C = make_graph(components, [
        {"source": "a", "target": "b", "confidence": 1.0},
        {"source": "b", "target": "c", "confidence": 1.0},
        {"source": "c", "target": "a", "confidence": 1.0},
    ], "current")

    result = engine.check_conformance(G_I, G_C)
    assert result["verdict"] == VIOLATION
    cycles = [v for v in result["violations"] if v.get("violation_type") == "cycle_violation"]
    assert len(cycles) >= 1
    assert cycles[0]["verdict"] == VIOLATION


# ─── 3. MISSING Unit Test ─────────────────────────────────────────────────────

def test_missing_dependency_detected(engine):
    """Verdict MISSING: Dependencies present in G_I but absent in G_C."""
    components = [
        {"id": "svc", "name": "OrderService", "type": "service"},
        {"id": "repo", "name": "OrderRepository", "type": "repository"},
    ]
    G_I = make_graph(components, [{"source": "svc", "target": "repo", "confidence": 1.0}], "intended")
    G_C = make_graph(components, [], "current")

    result = engine.check_conformance(G_I, G_C)
    assert result["verdict"] == MISSING
    missing = [v for v in result["violations"] if v["verdict"] == MISSING]
    assert len(missing) >= 1
    assert missing[0]["violation_type"] == "missing_dependency"
    assert result["summary"]["verdicts"][MISSING] >= 1


# ─── 4. UNEXPECTED Unit Test ──────────────────────────────────────────────────

def test_unexpected_dependency_detected(engine):
    """Verdict UNEXPECTED: Implementation contains an edge not in G_I nor allowed."""
    components = [
        {"id": "ctrl", "name": "OrderController", "type": "controller"},
        {"id": "cache", "name": "RedisCache", "type": "cache"},
    ]
    G_I = make_graph(components, [], "intended")
    G_C = make_graph(components, [
        {"source": "ctrl", "target": "cache", "type": "depends_on", "confidence": 1.0}
    ], "current")

    result = engine.check_conformance(G_I, G_C)
    assert result["verdict"] == UNEXPECTED
    unexpected = [v for v in result["violations"] if v["verdict"] == UNEXPECTED]
    assert len(unexpected) >= 1
    assert unexpected[0]["violation_type"] == "unexpected_dependency"
    assert result["summary"]["verdicts"][UNEXPECTED] >= 1


# ─── 5. UNCERTAIN Unit Test ───────────────────────────────────────────────────

def test_uncertain_verdict_low_confidence():
    """Verdict UNCERTAIN: Relationship confidence below the defined threshold."""
    engine_with_thresh = ConformanceEngine(confidence_threshold=0.6)
    components = [
        {"id": "svc", "name": "OrderService", "type": "service"},
        {"id": "ext", "name": "ThirdPartyPayment", "type": "external"},
    ]
    G_I = make_graph(components, [], "intended")
    # Edge with confidence 0.45 (< 0.6 threshold)
    G_C = make_graph(components, [
        {"source": "svc", "target": "ext", "type": "depends_on", "confidence": 0.45}
    ], "current")

    result = engine_with_thresh.check_conformance(G_I, G_C)
    assert result["verdict"] == UNCERTAIN
    uncertain_violations = [v for v in result["violations"] if v["verdict"] == UNCERTAIN]
    assert len(uncertain_violations) >= 1
    assert uncertain_violations[0]["violation_type"] == "uncertain_dependency"
    assert result["summary"]["verdicts"][UNCERTAIN] >= 1


# ─── 6. ALLOW / FORBID / REQUIRE Ruleset Unit Test ────────────────────────────

def test_allow_forbid_require_ruleset():
    """Verify custom RuleSet with ALLOW, FORBID, and REQUIRE actions."""
    rules = [
        ArchitectureRule(
            name="Allow Svc->Repo",
            action=RuleAction.ALLOW,
            category=RuleCategory.LAYER_RULE,
            source="service",
            target="repository",
        ),
        ArchitectureRule(
            name="Forbid Ctrl->Repo",
            action=RuleAction.FORBID,
            category=RuleCategory.LAYER_RULE,
            source="controller",
            target="repository",
            severity="high",
        ),
        ArchitectureRule(
            name="Require Svc->Audit",
            action=RuleAction.REQUIRE,
            category=RuleCategory.DEPENDENCY_RULE,
            source="service",
            target="audit",
            severity="medium",
        ),
    ]
    custom_ruleset = RuleSet(name="CustomSprint1Rules", rules=rules, confidence_threshold=0.6)
    custom_engine = ConformanceEngine(ruleset=custom_ruleset)

    components = [
        {"id": "c1", "name": "OrderController", "type": "controller"},
        {"id": "s1", "name": "OrderService", "type": "service"},
        {"id": "r1", "name": "OrderRepository", "type": "repository"},
        {"id": "a1", "name": "AuditLogger", "type": "audit"},
    ]

    # G_C has:
    # 1. Controller -> Repository (forbidden -> VIOLATION)
    # 2. Service -> Repository (allowed -> CONFORMANT)
    # Missing: Service -> Audit (required -> MISSING)
    G_I = make_graph(components, [], "intended")
    G_C = make_graph(components, [
        {"source": "c1", "target": "r1", "confidence": 1.0},
        {"source": "s1", "target": "r1", "confidence": 1.0},
    ], "current")

    result = custom_engine.check_conformance(G_I, G_C)
    verdicts = [v["verdict"] for v in result["violations"]]
    assert VIOLATION in verdicts
    assert MISSING in verdicts
    assert result["summary"]["verdicts"][VIOLATION] >= 1
    assert result["summary"]["verdicts"][MISSING] >= 1


# ─── 7. Summary Counts Unit Test ──────────────────────────────────────────────

def test_summary_counts(engine):
    """Verify summary counts correctly reflect all violation categories."""
    components = [
        {"id": "ctrl", "name": "FrontController", "type": "controller"},
        {"id": "db", "name": "Database", "type": "database"},
    ]
    G_I = make_graph(components, [], "intended")
    G_C = make_graph(components, [
        {"source": "ctrl", "target": "db", "type": "depends_on", "confidence": 1.0}
    ], "current")

    result = engine.check_conformance(G_I, G_C)
    assert result["summary"]["total_violations"] == len(result["violations"])
    assert "verdicts" in result["summary"]
    assert all(k in result["summary"]["verdicts"] for k in [CONFORMANT, VIOLATION, MISSING, UNEXPECTED, UNCERTAIN])


# ─── 8. Versioned Graph Schemas Serialization Unit Test ───────────────────────

def test_versioned_schemas_serialization():
    """Verify Pydantic models for versioned graph and rules schemas."""
    graph = ArchGraph(
        schema_version="1.0.0",
        name="OrderServiceGraph",
        graph_type="intended",
        components=[
            {"id": "c1", "name": "OrderService", "type": ComponentType.SERVICE, "confidence": 0.95}
        ],
        relationships=[
            {"source": "c1", "target": "c2", "type": RelationshipType.DEPENDS_ON, "confidence": 0.90}
        ],
    )
    dumped = graph.model_dump()
    assert dumped["schema_version"] == "1.0.0"
    assert dumped["graph_type"] == "intended"

    # IntendedGraph subclass
    intended = IntendedGraph(name="GI", schema_version="1.0.0")
    assert intended.graph_type == "intended"

    # CurrentGraph subclass
    current = CurrentGraph(name="GC", schema_version="1.0.0")
    assert current.graph_type == "current"


# ─── 9. Example JSON Fixtures Integration Test ────────────────────────────────

def test_example_json_fixtures(engine):
    """Verify example JSON files load cleanly and produce expected verdicts."""
    examples_dir = Path(__file__).resolve().parent.parent.parent / "app" / "schemas" / "examples"
    assert examples_dir.exists(), f"Examples directory not found at {examples_dir}"

    gi_path = examples_dir / "example_GI.json"
    gc_conformant_path = examples_dir / "example_GC_conformant.json"
    gc_violations_path = examples_dir / "example_GC_violations.json"
    ruleset_path = examples_dir / "example_ruleset.json"

    with open(gi_path, "r", encoding="utf-8") as f:
        gi_data = json.load(f)
    with open(gc_conformant_path, "r", encoding="utf-8") as f:
        gc_conf_data = json.load(f)
    with open(gc_violations_path, "r", encoding="utf-8") as f:
        gc_viol_data = json.load(f)
    with open(ruleset_path, "r", encoding="utf-8") as f:
        ruleset_data = json.load(f)

    # 1. Verify schema loading
    gi_model = IntendedGraph(**gi_data)
    gc_conf_model = CurrentGraph(**gc_conf_data)
    gc_viol_model = CurrentGraph(**gc_viol_data)
    ruleset_model = RuleSet(**ruleset_data)

    assert gi_model.schema_version == "1.0.0"
    assert gc_conf_model.schema_version == "1.0.0"
    assert ruleset_model.schema_version == "1.0.0"

    # 2. Conformant comparison
    conf_result = engine.check_conformance(gi_model, gc_conf_model, ruleset_model)
    assert conf_result["verdict"] == CONFORMANT
    assert len(conf_result["violations"]) == 0

    # 3. Violations comparison (contains VIOLATION, MISSING, UNEXPECTED, UNCERTAIN)
    engine_custom = ConformanceEngine(ruleset=ruleset_model)
    viol_result = engine_custom.check_conformance(gi_model, gc_viol_model)

    v_types = {v["verdict"] for v in viol_result["violations"]}
    assert VIOLATION in v_types
    assert MISSING in v_types
    assert UNCERTAIN in v_types

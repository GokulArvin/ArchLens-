"""
Sprint 10 (D46, D50) — ArchLens P3 Conformance & Evidence End-to-End Demo.

Demonstrates the complete P3 static analysis, graph conformance, impact, and
evidence pipeline:
  1. Ingestion / Construction of G_I (Intended) and G_C (Current)
  2. Pre-conformance Graph Integrity Verification (D19, D24)
  3. Deterministic Conformance Engine Evaluation (All 5 verdicts: D3, D26-D30)
  4. Impact Analysis & Blast-Radius Calculation (D36-D40)
  5. Architecture-Aware Correction Safety Validation (D38)
  6. Git Evidence & Introducing Commit Mining (D31-D35)
  7. Quantitative Conformance & Evaluation Metrics (D41-D45)

Usage:
  cd backend
  python3 scripts/demo_p3_conformance_pipeline.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add backend/ to python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.conformance_engine.engine import ConformanceEngine  # noqa: E402
from app.modules.cv_pipeline.git_evidence_p3 import rank_candidate_commits  # noqa: E402
from app.modules.cv_pipeline.impact_analysis import (  # noqa: E402
    compute_impact_summary,
    validate_correction_edges,
)
from app.modules.evaluation.conformance_metrics import ConformanceEvaluator  # noqa: E402
from app.modules.graph.builder import ArchGraphBuilder  # noqa: E402
from app.modules.graph.integrity import GraphIntegrityChecker  # noqa: E402
from app.schemas.models import (  # noqa: E402
    ArchitectureRule,
    RuleAction,
    RuleCategory,
    RuleSet,
)

logging.basicConfig(level=logging.WARNING)


def run_demo():
    print("=" * 76)
    print("  ArchLens: Module E (Conformance & Graph Analysis) End-to-End Demo")
    print("  Person 3 (Static Analysis & Conformance Lead) — Final Sprint 10 Release")
    print("=" * 76)

    # -------------------------------------------------------------------------
    # 1. Define Intended Architecture Graph (G_I)
    # -------------------------------------------------------------------------
    print("\n[Step 1] Constructing Intended Architecture Graph (G_I)...")
    intended_spec = {
        "schema_version": "1.0.0",
        "name": "E-Commerce Intended Architecture",
        "graph_type": "intended",
        "components": [
            {"id": "frontend", "name": "WebUI", "type": "frontend", "confidence": 1.0},
            {"id": "gateway", "name": "ApiGateway", "type": "gateway", "confidence": 1.0},
            {"id": "orders.controller", "name": "OrderController", "type": "controller", "confidence": 1.0},
            {"id": "orders.service", "name": "OrderService", "type": "service", "confidence": 1.0},
            {"id": "orders.repo", "name": "OrderRepository", "type": "repository", "confidence": 1.0},
            {"id": "orders.db", "name": "OrderDB", "type": "database", "confidence": 1.0},
            {"id": "audit.service", "name": "AuditService", "type": "service", "confidence": 1.0},
            {"id": "ext.payment", "name": "StripeGateway", "type": "external", "confidence": 1.0},
        ],
        "relationships": [
            {"source": "frontend", "target": "gateway", "type": "depends_on", "confidence": 1.0},
            {"source": "gateway", "target": "orders.controller", "type": "calls", "confidence": 1.0},
            {"source": "orders.controller", "target": "orders.service", "type": "calls", "confidence": 1.0},
            {"source": "orders.service", "target": "orders.repo", "type": "calls", "confidence": 1.0},
            {"source": "orders.repo", "target": "orders.db", "type": "writes_to", "confidence": 1.0},
            {"source": "orders.service", "target": "audit.service", "type": "publishes_to", "confidence": 1.0},
        ],
    }
    G_I = ArchGraphBuilder.build(intended_spec)
    print(f"  G_I loaded: {G_I.number_of_nodes()} components, {G_I.number_of_edges()} relationships")

    # -------------------------------------------------------------------------
    # 2. Define Current Architecture Graph (G_C) with Controlled Violations
    # -------------------------------------------------------------------------
    print("\n[Step 2] Constructing Current Architecture Graph (G_C) with Controlled Faults...")
    current_spec = {
        "schema_version": "1.0.0",
        "name": "E-Commerce Implementation Graph",
        "graph_type": "current",
        "components": intended_spec["components"],
        "relationships": [
            # 1. Conformant edges
            {"source": "frontend", "target": "gateway", "type": "depends_on", "confidence": 1.0},
            {"source": "gateway", "target": "orders.controller", "type": "calls", "confidence": 1.0},
            {"source": "orders.controller", "target": "orders.service", "type": "calls", "confidence": 1.0},
            {"source": "orders.service", "target": "orders.repo", "type": "calls", "confidence": 1.0},
            {"source": "orders.repo", "target": "orders.db", "type": "writes_to", "confidence": 1.0},

            # 2. Controlled Fault: Direct layer bypass (controller -> repository forbidden)
            {"source": "orders.controller", "target": "orders.repo", "type": "calls", "confidence": 1.0},

            # 3. Controlled Fault: Reverse upward layer dependency (database -> service)
            {"source": "orders.db", "target": "orders.service", "type": "calls", "confidence": 0.95},

            # 4. Controlled Fault: Unexpected third-party coupling (service -> external Stripe unmodeled)
            {"source": "orders.service", "target": "ext.payment", "type": "calls", "confidence": 0.90},

            # 5. Controlled Fault: Low-confidence extraction (<0.6 threshold -> UNCERTAIN)
            {"source": "orders.controller", "target": "audit.service", "type": "calls", "confidence": 0.45},

            # Note: orders.service -> audit.service is missing in G_C (Required edge -> MISSING)
        ],
    }
    G_C = ArchGraphBuilder.build(current_spec)
    print(f"  G_C loaded: {G_C.number_of_nodes()} components, {G_C.number_of_edges()} relationships")

    # -------------------------------------------------------------------------
    # 3. Pre-conformance Integrity Audit (Sprint 5 / D19)
    # -------------------------------------------------------------------------
    print("\n[Step 3] Running Pre-conformance Graph Integrity Checker...")
    checker = GraphIntegrityChecker()
    integrity_report = checker.check(G_C)
    print(f"  Integrity Valid: {integrity_report.is_valid}")
    print(f"  Issues Detected: {len(integrity_report.issues)} (Errors: {len(integrity_report.errors())}, Warnings: {len(integrity_report.warnings())})")
    for issue in integrity_report.issues:
        print(f"    - [{issue.severity.value.upper()}] {issue.code}: {issue.description}")

    # -------------------------------------------------------------------------
    # 4. Deterministic Conformance Evaluation (Sprint 1, 6, 7)
    # -------------------------------------------------------------------------
    print("\n[Step 4] Executing Deterministic Conformance Engine...")
    ruleset = RuleSet(
        name="ProductionArchitecturePolicy",
        rules=[
            ArchitectureRule(
                name="Controllers must not bypass services to access repositories",
                action=RuleAction.FORBID,
                category=RuleCategory.LAYER_RULE,
                source="controller",
                target="repository",
                severity="critical",
            ),
            ArchitectureRule(
                name="Orders service must publish telemetry to Audit service",
                action=RuleAction.REQUIRE,
                category=RuleCategory.DEPENDENCY_RULE,
                source="orders.service",
                target="audit.service",
                severity="high",
            ),
        ],
        confidence_threshold=0.6,
    )

    engine = ConformanceEngine(ruleset=ruleset)
    conformance_result = engine.check_conformance(G_I, G_C)

    print(f"  Overall Verdict: {conformance_result['verdict']}")
    print("  Verdict Taxonomy Breakdown:")
    for v_name, count in conformance_result["summary"]["verdicts"].items():
        print(f"    - {v_name:<12}: {count}")

    print("\n  Localized Violations:")
    for v in conformance_result["violations"]:
        print(f"    * [{v.get('verdict')}] {v.get('source')} -> {v.get('target')}")
        print(f"      Type: {v.get('violation_type')}, Severity: {v.get('severity')}, Conf: {v.get('confidence')}")
        print(f"      Note: {v.get('description')}")

    # -------------------------------------------------------------------------
    # 5. Impact Analysis & Blast Radius (Sprint 8 / D36-D40)
    # -------------------------------------------------------------------------
    print("\n[Step 5] Analyzing Blast Radius for Major Violations...")
    bypass_impact = compute_impact_summary(
        G_C,
        source="orders.controller",
        target="orders.repo",
        violation_type="forbidden_dependency",
    )
    print("  Impact for 'orders.controller -> orders.repo' (Layer Bypass):")
    print(f"    - Upstream coupled nodes  : {bypass_impact['upstream_affected']}")
    print(f"    - Downstream affected nodes: {bypass_impact['downstream_affected']}")
    print(f"    - Blast radius fraction   : {bypass_impact['blast_radius_fraction'] * 100:.1f}%")
    print(f"    - Computed Impact Severity : {bypass_impact['impact_severity'].upper()}")

    # -------------------------------------------------------------------------
    # 6. Recommendation & Correction Safety Validation (Sprint 8 / D38)
    # -------------------------------------------------------------------------
    print("\n[Step 6] Validating Proposed Architectural Corrections (D38)...")
    # Bad proposed fix: connect controller directly to database instead
    unsafe_proposal = [("orders.controller", "orders.db")]
    unsafe_val = validate_correction_edges(G_I, G_C, "orders.controller", "orders.repo", unsafe_proposal)
    print(f"  Proposal 1 (controller -> db): Valid = {unsafe_val.valid}")
    for err in unsafe_val.violations:
        print(f"    [Blocked] {err}")

    # Good proposed fix: delegate to orders.service
    safe_proposal = [("orders.controller", "orders.service")]
    safe_val = validate_correction_edges(G_I, G_C, "orders.controller", "orders.repo", safe_proposal)
    print(f"  Proposal 2 (controller -> service): Valid = {safe_val.valid}")
    for edge in safe_val.safe_edges:
        print(f"    [Approved] Allowed edge: {edge[0]} -> {edge[1]}")

    # -------------------------------------------------------------------------
    # 7. Git Evidence & Introducing Commit Mining (Sprint 7 / D31-D35)
    # -------------------------------------------------------------------------
    print("\n[Step 7] Packaging Git History Evidence (Sprint 7)...")
    sample_candidate_commits = [
        {"hash": "e5d6303", "message": "Add OrderRepository direct query in OrderController", "author": "Dev A", "date": "2026-10-12", "diff": "from orders.repo import OrderRepository\norder_repo.find()", "is_merge_commit": False},
        {"hash": "baedeb7", "message": "Merge branch 'staging' into main", "author": "Dev B", "date": "2026-10-15", "diff": "Merge conflict resolution", "is_merge_commit": True},
    ]
    ranked = rank_candidate_commits(sample_candidate_commits, pattern="OrderRepository", violation_id="viol-001")
    print(f"  Candidate Commits Evaluated: {len(ranked)}")
    for c in ranked:
        print(f"    Rank #{c.rank}: commit {c.hash[:7]} (score={c.score:.2f}) — {c.message}")
        print(f"      Merge: {c.is_merge_commit}, Renames: {c.renames_detected}")

    # -------------------------------------------------------------------------
    # 8. Ground-Truth Conformance Metric Evaluation (Sprint 9 / D41-D45)
    # -------------------------------------------------------------------------
    print("\n[Step 8] Evaluating Baseline Performance Against Ground Truth...")
    gt = [
        {"fixture_id": "demo", "source": "orders.controller", "target": "orders.repo", "verdict": "VIOLATION", "violation_type": "forbidden_dependency"},
        {"fixture_id": "demo", "source": "orders.service", "target": "audit.service", "verdict": "MISSING", "violation_type": "missing_dependency"},
    ]
    evaluator = ConformanceEvaluator(gt)
    eval_metrics = evaluator.evaluate(conformance_result["violations"])
    print(f"  Precision : {eval_metrics.precision:.4f}")
    print(f"  Recall    : {eval_metrics.recall:.4f}")
    print(f"  F1 Score  : {eval_metrics.f1:.4f}")
    print(f"  Breakdown : TP={eval_metrics.tp}, FP={eval_metrics.fp}, FN={eval_metrics.fn}")

    print("\n" + "=" * 76)
    print("  [SUCCESS] ArchLens P3 Sprint 10 End-to-End Walkthrough Complete!")
    print("=" * 76)


if __name__ == "__main__":
    run_demo()

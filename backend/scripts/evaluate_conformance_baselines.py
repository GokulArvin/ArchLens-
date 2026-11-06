#!/usr/bin/env python3
"""
Sprint 9 P3 — D42/D43: Evaluate conformance baselines on the sample_repo fixture.

Baselines:
  1. static_only         — ArchitectureRecoveryPipeline (G_C) vs hand-crafted G_I,
                           ConformanceEngine with DEFAULT forbidden pairs only.
  2. static_conformance  — Same G_C but with explicit FORBID/REQUIRE rules.
  3. full_pipeline       — LLM component stubbed; identical to static_conformance.

Writes results to:
  experiments/baselines/sprint9_p3_conformance_evaluation.json
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend/ is on the path when run as `python3 scripts/evaluate_conformance_baselines.py`
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.modules.architecture_recovery.ast_parser import ArchitectureRecoveryPipeline  # noqa: E402
from app.modules.conformance_engine.engine import ConformanceEngine  # noqa: E402
from app.modules.graph.builder import ArchGraphBuilder  # noqa: E402
from app.modules.evaluation.conformance_metrics import ConformanceEvaluator, EvaluationResult  # noqa: E402
from app.schemas.models import RuleSet, ArchitectureRule, RuleAction, RuleCategory  # noqa: E402

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SAMPLE_REPO = str(
    _BACKEND_DIR / "tests" / "fixtures" / "sample_repo"
)
OUTPUT_PATH = (
    _BACKEND_DIR.parent / "experiments" / "baselines" / "sprint9_p3_conformance_evaluation.json"
)

# ---------------------------------------------------------------------------
# Ground-truth violations (D41)
# Reflects the OrderController → OrderRepository forbidden direct import
# that is literally present in tests/fixtures/sample_repo/controllers/order_controller.py
# ---------------------------------------------------------------------------
GROUND_TRUTH_VIOLATIONS: List[Dict[str, str]] = [
    {
        "fixture_id": "sample_repo",
        "source": "controllers",
        "target": "repositories",
        "verdict": "VIOLATION",
        "violation_type": "forbidden_dependency",
    },
]

# ---------------------------------------------------------------------------
# Hand-crafted G_I (intended architecture) for the sample_repo
# Controllers → Services → Repositories → (nothing further in this small repo)
# The forbidden edge controllers → repositories is intentionally absent.
# ---------------------------------------------------------------------------
GI_DICT: Dict[str, Any] = {
    "schema_version": "1.0.0",
    "id": "gi-sample_repo",
    "name": "sample_repo IntendedArchitecture",
    "graph_type": "intended",
    "components": [
        {"id": "controllers", "name": "controllers", "type": "controller"},
        {"id": "services",    "name": "services",    "type": "service"},
        {"id": "repositories","name": "repositories","type": "repository"},
        {"id": "models",      "name": "models",      "type": "model"},
    ],
    "relationships": [
        {"source": "controllers",  "target": "services",     "type": "depends_on"},
        {"source": "services",     "target": "repositories", "type": "depends_on"},
        {"source": "services",     "target": "models",       "type": "depends_on"},
        {"source": "repositories", "target": "models",       "type": "depends_on"},
    ],
}

# ---------------------------------------------------------------------------
# Explicit ruleset for static_conformance / full_pipeline baselines
# ---------------------------------------------------------------------------
EXPLICIT_RULESET = RuleSet(
    id="sprint9-ruleset",
    name="Sprint 9 P3 Explicit Rules",
    rules=[
        ArchitectureRule(
            id="r1",
            name="Controllers must not access repositories directly",
            source_type="controller",
            target_type="repository",
            action=RuleAction.FORBID,
            category=RuleCategory.DEPENDENCY_RULE,
            description="Layer violation: controller → repository bypasses service layer.",
        ),
        ArchitectureRule(
            id="r2",
            name="Controllers may call services",
            source_type="controller",
            target_type="service",
            action=RuleAction.ALLOW,
            category=RuleCategory.DEPENDENCY_RULE,
        ),
        ArchitectureRule(
            id="r3",
            name="Services may call repositories",
            source_type="service",
            target_type="repository",
            action=RuleAction.ALLOW,
            category=RuleCategory.DEPENDENCY_RULE,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Helper: convert engine output → list of violation dicts for evaluator
# ---------------------------------------------------------------------------
def _extract_violation_predictions(
    engine_output: Dict[str, Any],
    source_module_map: Dict[str, str],
    target_module_map: Dict[str, str],
) -> List[Dict[str, str]]:
    """
    Map ConformanceEngine raw output to the same schema as GROUND_TRUTH_VIOLATIONS.
    We normalise node IDs to their directory/module names (lowercase) so they
    align with the GT labels ("controllers", "repositories", …).
    """
    predictions: List[Dict[str, str]] = []
    for v in engine_output.get("violations", []):
        verdict = v.get("verdict", "")
        if verdict != "VIOLATION":
            # For this evaluation we care only about VIOLATION verdicts
            continue
        raw_src = str(v.get("source", "")).lower()
        raw_tgt = str(v.get("target", "")).lower()
        # Resolve to canonical module name using provided maps (identity if unknown)
        src = source_module_map.get(raw_src, raw_src)
        tgt = target_module_map.get(raw_tgt, raw_tgt)
        predictions.append(
            {
                "fixture_id": "sample_repo",
                "source": src,
                "target": tgt,
                "verdict": verdict,
                "violation_type": v.get("violation_type", "unknown"),
            }
        )
    return predictions


# ---------------------------------------------------------------------------
# Run pipeline → build G_C → check conformance
# ---------------------------------------------------------------------------
def _run_baseline(
    ruleset: RuleSet | None,
    gi_dict: Dict[str, Any],
    gc_dict: Dict[str, Any],
    source_module_map: Dict[str, str],
    target_module_map: Dict[str, str],
) -> Dict[str, Any]:
    G_I = ArchGraphBuilder.build(gi_dict)
    G_C = ArchGraphBuilder.build(gc_dict)

    engine = ConformanceEngine(ruleset=ruleset)
    result = engine.check_conformance(G_I, G_C)

    predictions = _extract_violation_predictions(result, source_module_map, target_module_map)
    evaluator = ConformanceEvaluator(GROUND_TRUTH_VIOLATIONS)
    eval_result: EvaluationResult = evaluator.evaluate(predictions)

    return {
        "metrics": eval_result.summary(),
        "raw_violations_detected": len(result.get("violations", [])),
        "predictions": predictions,
        "false_positives": eval_result.false_positives,
        "false_negatives": eval_result.false_negatives,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("ArchLens Sprint 9 P3 — Conformance Baseline Evaluation")
    print("=" * 70)

    # 1. Recover G_C from sample_repo via static analysis
    pipeline = ArchitectureRecoveryPipeline()
    gc_raw = pipeline.analyze_repository(SAMPLE_REPO, language="python")

    # Build a module-name normalisation map so that node IDs (which may be
    # full paths or partial module names) are mapped to short canonical names.
    source_module_map: Dict[str, str] = {}
    target_module_map: Dict[str, str] = {}
    for comp in gc_raw.get("components", []):
        cid = str(comp.get("id", "")).lower()
        name = str(comp.get("name", "")).lower()
        for canon in ("controllers", "services", "repositories", "models"):
            if canon in cid or canon in name:
                source_module_map[cid] = canon
                target_module_map[cid] = canon
                source_module_map[name] = canon
                target_module_map[name] = canon
                break

    print(f"\nG_C recovered: {len(gc_raw['components'])} components, "
          f"{len(gc_raw['relationships'])} relationships\n")

    # 2. Baseline A — static-only (default forbidden pairs, no explicit ruleset)
    print("Running baseline: static_only …")
    static_only = _run_baseline(None, GI_DICT, gc_raw, source_module_map, target_module_map)

    # 3. Baseline B — static + explicit conformance rules
    print("Running baseline: static_conformance …")
    static_conformance = _run_baseline(
        EXPLICIT_RULESET, GI_DICT, gc_raw, source_module_map, target_module_map
    )

    # 4. Baseline C — full_pipeline (LLM stubbed → same as static_conformance)
    print("Running baseline: full_pipeline (LLM stubbed) …")
    full_pipeline = dict(static_conformance)  # shallow copy — identical results
    full_pipeline["note"] = "LLM component stubbed; results identical to static_conformance."

    # 5. Write JSON output
    output: Dict[str, Any] = {
        "experiment": "sprint9_p3_conformance_evaluation",
        "sprint": 9,
        "person": "P3",
        "note": "Generated by scripts/evaluate_conformance_baselines.py.",
        "ground_truth_violations": GROUND_TRUTH_VIOLATIONS,
        "baselines": {
            "static_only": static_only,
            "static_conformance": static_conformance,
            "full_pipeline": full_pipeline,
        },
        "limitations": [
            "Sample repo fixture is small (4 modules); metrics may not generalize.",
            "LLM component stubbed — full_pipeline uses same results as static_conformance.",
            "No held-out test set used at this stage.",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\nResults written to: {OUTPUT_PATH}")

    # 6. Print comparison table
    _print_table(output["baselines"])


def _print_table(baselines: Dict[str, Any]) -> None:
    header = f"\n{'Baseline':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>5} {'FP':>5} {'FN':>5}"
    print(header)
    print("-" * len(header))
    for name, data in baselines.items():
        m = data.get("metrics", {})
        print(
            f"{name:<25} "
            f"{m.get('precision', 0.0):>10.4f} "
            f"{m.get('recall', 0.0):>10.4f} "
            f"{m.get('f1', 0.0):>10.4f} "
            f"{m.get('tp', 0):>5} "
            f"{m.get('fp', 0):>5} "
            f"{m.get('fn', 0):>5}"
        )
    print()


if __name__ == "__main__":
    main()

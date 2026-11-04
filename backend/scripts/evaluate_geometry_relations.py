"""
Sprint 5 / D24: compare geometry-based relation candidates (D23) against the
real hand-annotated relationships in the manifest.

Matching is undirected (component-pair match, ignoring source/target order):
Hough-line-endpoint-to-box matching has no reliable way to tell which end of
a detected line segment is the arrow's source vs target, so direction is
explicitly out of scope for this baseline - documented honestly rather than
inflating results with an arbitrary direction guess.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/evaluate_geometry_relations.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402
from app.modules.cv_pipeline.geometry_relations import detect_lines, propose_relations  # noqa: E402
from app.modules.cv_pipeline.pipeline import CVPreprocessor  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
OUT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint5_geometry_relations.json"


def main():
    preprocessor = CVPreprocessor()
    per_diagram = []
    totals = {"tp": 0, "fp": 0, "fn": 0}

    for g in load_manifest():
        img = preprocessor.load(str(DIAGRAMS_DIR / Path(g.source).name))
        lines = detect_lines(img)
        candidates = propose_relations(lines, g.components)

        gt_pairs = {frozenset((r.source, r.target)) for r in g.relationships}
        candidate_pairs = {frozenset((c.source, c.target)) for c in candidates}

        tp = len(gt_pairs & candidate_pairs)
        fp = len(candidate_pairs - gt_pairs)
        fn = len(gt_pairs - candidate_pairs)
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        per_diagram.append({
            "diagram_id": g.id,
            "num_ground_truth_edges": len(gt_pairs),
            "num_lines_detected": len(lines),
            "num_candidate_edges": len(candidate_pairs),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        })
        print(f"{g.id}: GT={len(gt_pairs)} candidates={len(candidate_pairs)} TP={tp} FP={fp} FN={fn} "
              f"P={precision:.3f} R={recall:.3f}")

    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if (totals["tp"] + totals["fp"]) else 0.0
    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if (totals["tp"] + totals["fn"]) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "matching": "undirected component-pair (direction out of scope - see docstring)",
        "aggregate": {**totals, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)},
        "per_diagram": per_diagram,
    }, indent=2), encoding="utf-8")
    print(f"\nAggregate: P={precision:.4f} R={recall:.4f} F1={f1:.4f}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

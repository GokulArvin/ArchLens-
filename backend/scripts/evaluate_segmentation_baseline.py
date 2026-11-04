"""
Sprint 4 / D18: compare the region-cropping segmentation baseline's proposed
boxes against real hand-annotated ground truth, on a small subset.

Subset chosen for diversity: istio_bookinfo_derived (simplest, 4 components),
spring_cloud_brewery_dependency_graph (simple, small image), and
gcp_microservices_demo (densest, 12 components) - covers the easy and hard
ends of the dataset.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/evaluate_segmentation_baseline.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402
from app.modules.cv_pipeline.detection_eval import evaluate_detections  # noqa: E402
from app.modules.cv_pipeline.pipeline import CVPreprocessor  # noqa: E402
from app.modules.cv_pipeline.segmentation import RegionProposalSegmenter  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
OUT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint4_segmentation_baseline.json"
SUBSET = ["istio_bookinfo_derived", "spring_cloud_brewery_dependency_graph", "gcp_microservices_demo"]


def main():
    graphs = {g.id: g for g in load_manifest()}
    preprocessor = CVPreprocessor()
    segmenter = RegionProposalSegmenter()

    per_diagram = []
    totals = {"tp": 0, "fp": 0, "fn": 0}
    for diagram_id in SUBSET:
        g = graphs[diagram_id]
        img = preprocessor.preprocess(str(DIAGRAMS_DIR / Path(g.source).name))
        regions = segmenter.propose_regions(img)
        predicted_boxes = [r.bbox for r in regions]

        result = evaluate_detections(diagram_id, g.components, predicted_boxes, iou_threshold=0.5)
        per_diagram.append(result.to_dict())
        totals["tp"] += result.true_positives
        totals["fp"] += result.false_positives
        totals["fn"] += result.false_negatives
        print(f"{diagram_id}: {len(g.components)} GT, {len(regions)} proposals -> "
              f"TP={result.true_positives} FP={result.false_positives} FN={result.false_negatives} "
              f"P={result.precision:.3f} R={result.recall:.3f}")

    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if (totals["tp"] + totals["fp"]) else 0.0
    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if (totals["tp"] + totals["fn"]) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "subset": SUBSET,
        "iou_threshold": 0.5,
        "aggregate": {**totals, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)},
        "per_diagram": per_diagram,
    }, indent=2), encoding="utf-8")
    print(f"\nAggregate over subset: P={precision:.4f} R={recall:.4f} F1={f1:.4f}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

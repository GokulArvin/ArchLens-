"""
Sprint 9 / D42 + D43: evaluate the detector (Sprint 3), segmentation
(Sprint 4), and geometry-relation (Sprint 5) baselines specifically against
the frozen test split (data/annotations/splits.json), not the full 10
diagrams - this is the first evaluation in the project scoped to the
held-out test set rather than the whole dataset, per the plan's "freeze the
held-out test split before final experiments" rule.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/evaluate_on_frozen_test_split.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402
from app.modules.cv_pipeline.detection_eval import evaluate_detections  # noqa: E402
from app.modules.cv_pipeline.detection_mapping import map_detections  # noqa: E402
from app.modules.cv_pipeline.geometry_relations import detect_lines, propose_relations  # noqa: E402
from app.modules.cv_pipeline.pipeline import ComponentDetector, CVPreprocessor  # noqa: E402
from app.modules.cv_pipeline.segmentation import RegionProposalSegmenter  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
SPLITS_PATH = REPO_ROOT / "data" / "annotations" / "splits.json"
MODEL_PATH = BACKEND_DIR / "models" / "yolov8n.pt"
OUT_PATH = REPO_ROOT / "experiments" / "results" / "sprint9_test_split_evaluation.json"


def _aggregate(results: list[dict]) -> dict:
    tp = sum(r["true_positives"] for r in results)
    fp = sum(r["false_positives"] for r in results)
    fn = sum(r["false_negatives"] for r in results)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def main():
    if not SPLITS_PATH.exists():
        raise FileNotFoundError(f"{SPLITS_PATH} not found - run freeze_splits.py (D41) first.")
    splits = json.loads(SPLITS_PATH.read_text(encoding="utf-8"))
    test_ids = set(splits["test"])
    graphs = [g for g in load_manifest() if g.id in test_ids]
    print(f"Evaluating on frozen test split: {sorted(test_ids)}")

    preprocessor = CVPreprocessor()
    detector = ComponentDetector(model_path=str(MODEL_PATH), confidence=0.25) if MODEL_PATH.exists() else None
    segmenter = RegionProposalSegmenter()

    detection_results, segmentation_results, geometry_results = [], [], []

    for g in graphs:
        img_path = DIAGRAMS_DIR / Path(g.source).name

        # Detector (Sprint 3)
        if detector is not None:
            img = preprocessor.preprocess(str(img_path))
            mapped = map_detections(detector.detect(img), confidence_threshold=0.25)
            det_result = evaluate_detections(g.id, g.components, [m.bbox for m in mapped], iou_threshold=0.5)
            detection_results.append(det_result.to_dict())

        # Segmentation (Sprint 4)
        img_raw = preprocessor.preprocess(str(img_path))
        regions = segmenter.propose_regions(img_raw)
        seg_result = evaluate_detections(g.id, g.components, [r.bbox for r in regions], iou_threshold=0.5)
        segmentation_results.append(seg_result.to_dict())

        # Geometry relations (Sprint 5)
        raw_img = preprocessor.load(str(img_path))
        lines = detect_lines(raw_img)
        candidates = propose_relations(lines, g.components)
        gt_pairs = {frozenset((r.source, r.target)) for r in g.relationships}
        candidate_pairs = {frozenset((c.source, c.target)) for c in candidates}
        tp = len(gt_pairs & candidate_pairs)
        fp = len(candidate_pairs - gt_pairs)
        fn = len(gt_pairs - candidate_pairs)
        geometry_results.append({"diagram_id": g.id, "true_positives": tp, "false_positives": fp, "false_negatives": fn})

        print(f"{g.id}: detector={detection_results[-1] if detector is not None else 'skipped'}, "
              f"segmentation TP/FP/FN={seg_result.true_positives}/{seg_result.false_positives}/{seg_result.false_negatives}, "
              f"geometry TP/FP/FN={tp}/{fp}/{fn}")

    summary = {
        "test_split": sorted(test_ids),
        "detector_yolo_coco": _aggregate(detection_results) if detection_results else None,
        "segmentation_region_cropping": _aggregate(segmentation_results),
        "geometry_relations": _aggregate(geometry_results),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "summary": summary,
        "detection_results": detection_results,
        "segmentation_results": segmentation_results,
        "geometry_results": geometry_results,
    }, indent=2), encoding="utf-8")

    print("\n=== Test-split summary ===")
    for name, agg in summary.items():
        if name == "test_split" or agg is None:
            continue
        print(f"{name}: P={agg['precision']:.4f} R={agg['recall']:.4f} F1={agg['f1']:.4f}")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

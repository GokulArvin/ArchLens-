"""
Sprint 3 / D15: evaluate the Sprint 3 YOLO-COCO baseline (D13's output)
against real ground truth, inspect false positives/negatives, and record
the baseline honestly.

Consumes experiments/baselines/sprint3_yolo_coco_baseline.json (D13).
Writes experiments/baselines/sprint3_yolo_coco_baseline_eval.json and
docs/sprint3_detection_baseline.md.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/evaluate_detection_baseline.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import load_manifest  # noqa: E402
from app.modules.cv_pipeline.detection_eval import evaluate_detections  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
BASELINE_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint3_yolo_coco_baseline.json"
EVAL_OUT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint3_yolo_coco_baseline_eval.json"
DOC_PATH = REPO_ROOT / "docs" / "sprint3_detection_baseline.md"


def main():
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(f"{BASELINE_PATH} not found - run run_detection_baseline.py (D13) first.")

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    graphs = {g.id: g for g in load_manifest()}

    per_diagram = []
    totals = {"tp": 0, "fp": 0, "fn": 0}
    fp_examples, fn_examples = [], []

    for entry in baseline["results"]:
        g = graphs[entry["diagram_id"]]
        predicted_boxes = [m["bbox"] for m in entry["mapped_detections"]]
        result = evaluate_detections(g.id, g.components, predicted_boxes, iou_threshold=0.5)
        per_diagram.append(result.to_dict())
        totals["tp"] += result.true_positives
        totals["fp"] += result.false_positives
        totals["fn"] += result.false_negatives

        for pi in result.unmatched_predicted_indices:
            det = entry["mapped_detections"][pi]
            fp_examples.append({
                "diagram_id": g.id,
                "bbox": det["bbox"],
                "confidence": det["confidence"],
                "raw_coco_class": det["raw_coco_class"],
            })
        for gt_id in result.unmatched_ground_truth_ids:
            comp = next(c for c in g.components if c.id == gt_id)
            fn_examples.append({"diagram_id": g.id, "component_id": gt_id, "name": comp.name, "type": comp.type.value})

    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if (totals["tp"] + totals["fp"]) else 0.0
    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if (totals["tp"] + totals["fn"]) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    EVAL_OUT_PATH.write_text(json.dumps({
        "iou_threshold": 0.5,
        "aggregate": {**totals, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)},
        "per_diagram": per_diagram,
        "false_positive_examples": fp_examples,
        "false_negative_examples": fn_examples,
    }, indent=2), encoding="utf-8")

    doc_lines = [
        "# Sprint 3 Detection Baseline (D15)",
        "",
        f"Model: {baseline['model']}, confidence threshold {baseline['confidence_threshold']}, IoU threshold 0.5.",
        "",
        "## Aggregate result (real, measured - not assumed)",
        "",
        f"- True positives: {totals['tp']}",
        f"- False positives: {totals['fp']}",
        f"- False negatives: {totals['fn']}",
        f"- Precision: {precision:.4f}",
        f"- Recall: {recall:.4f}",
        f"- F1: {f1:.4f}",
        "",
        "## Per-diagram results",
        "",
        "| diagram | GT components | predicted | TP | FP | FN |",
        "|---|---|---|---|---|---|",
    ]
    for r in per_diagram:
        doc_lines.append(
            f"| {r['diagram_id']} | {r['num_ground_truth']} | {r['num_predicted']} | "
            f"{r['true_positives']} | {r['false_positives']} | {r['false_negatives']} |"
        )

    doc_lines += [
        "",
        "## False positive inspection",
        "",
    ]
    if fp_examples:
        for fp in fp_examples:
            doc_lines.append(f"- `{fp['diagram_id']}`: COCO class \"{fp['raw_coco_class']}\" at confidence {fp['confidence']:.2f} - no matching real component at this location.")
    else:
        doc_lines.append("None - the detector produced zero false positives (it mostly produced zero detections at all).")

    doc_lines += [
        "",
        "## True positive inspection (important caveat)",
        "",
    ]
    any_tp = False
    for r in per_diagram:
        for mp in r["matched_pairs"]:
            any_tp = True
            pred = baseline["results"][[e["diagram_id"] for e in baseline["results"]].index(r["diagram_id"])]["mapped_detections"][mp["predicted_index"]]
            doc_lines.append(
                f"- `{r['diagram_id']}`: COCO class \"{pred['raw_coco_class']}\" (conf {pred['confidence']:.2f}) spatially overlaps "
                f"ground-truth component `{mp['ground_truth_component_id']}` at IoU>=0.5 - this is a coincidental spatial match, "
                f"not a semantically meaningful detection (\"{pred['raw_coco_class']}\" has nothing to do with the real component)."
            )
    if not any_tp:
        doc_lines.append("None.")

    doc_lines += [
        "",
        "## False negative inspection (summary - every undetected component had a ground-truth box the detector never found)",
        "",
        f"{len(fn_examples)} of {sum(r['num_ground_truth'] for r in per_diagram)} real ground-truth components were missed entirely.",
        "",
        "## Interpretation",
        "",
        "This confirms the D11/D12 hypothesis: a COCO-pretrained detector finds",
        "almost nothing in architecture diagrams, because diagram components",
        "(labeled boxes, arrows) share no visual vocabulary with COCO's",
        "photograph-object classes. The one diagram with real detections",
        "(`spring_cloud_brewery_overview`) has illustrated 3D icons - a barrel,",
        "bottles, boxes - that coincidentally resemble COCO objects, producing",
        "false positives rather than useful detections. Even the single",
        "true positive is a coincidental spatial overlap (see above), so the",
        "effective, semantically-meaningful recall of this baseline is 0/89.",
        "",
        "This is the honest Sprint 3 baseline, not a target to beat by tuning",
        "thresholds on this same set (that would violate the plan's \"do not",
        "tune on the final test set\" rule). It motivates Sprint 4/5's planned",
        "work: segmentation/region-cropping and CLIP zero-shot classification,",
        "which don't depend on COCO's label vocabulary matching diagram content.",
    ]
    DOC_PATH.write_text("\n".join(doc_lines), encoding="utf-8")

    print(f"Aggregate: TP={totals['tp']} FP={totals['fp']} FN={totals['fn']} "
          f"P={precision:.4f} R={recall:.4f} F1={f1:.4f}")
    print(f"Wrote {EVAL_OUT_PATH}")
    print(f"Wrote {DOC_PATH}")


if __name__ == "__main__":
    main()

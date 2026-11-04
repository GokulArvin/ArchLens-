"""
Sprint 4 / D16: determine whether pretrained segmentation is viable for
diagram components.

Tests torchvision's Mask R-CNN (ResNet50-FPN, COCO-pretrained) - the
standard off-the-shelf pretrained instance segmentation model - against all
10 real diagrams, and records the real result. Mask R-CNN shares COCO's
80-class vocabulary with the YOLOv8n detector tested in Sprint 3
(docs/yolo_classes.md), so the same semantic-mismatch problem is expected -
this script confirms (or refutes) that empirically rather than by analogy
alone, and feeds the keep/drop decision in D20.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/test_segmentation_feasibility.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import torch  # noqa: E402
from torchvision.models.detection import MaskRCNN_ResNet50_FPN_Weights, maskrcnn_resnet50_fpn  # noqa: E402
from torchvision.transforms.functional import to_tensor  # noqa: E402

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402
from app.modules.cv_pipeline.pipeline import CVPreprocessor  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
OUT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint4_maskrcnn_feasibility.json"
CONFIDENCE_THRESHOLD = 0.25


def main():
    weights = MaskRCNN_ResNet50_FPN_Weights.DEFAULT
    model = maskrcnn_resnet50_fpn(weights=weights)
    model.eval()
    class_names = weights.meta["categories"]

    preprocessor = CVPreprocessor()
    graphs = load_manifest()

    results = []
    with torch.no_grad():
        for g in graphs:
            img_path = DIAGRAMS_DIR / Path(g.source).name
            img_rgb = preprocessor.preprocess(str(img_path), color_mode="rgb")
            tensor = to_tensor(img_rgb)
            prediction = model([tensor])[0]

            masks_above_threshold = int((prediction["scores"] >= CONFIDENCE_THRESHOLD).sum())
            detections = []
            for score, label, box in zip(prediction["scores"], prediction["labels"], prediction["boxes"]):
                if score < CONFIDENCE_THRESHOLD:
                    continue
                detections.append({
                    "class_name": class_names[int(label)],
                    "confidence": float(score),
                    "bbox": [float(v) for v in box],
                })

            results.append({
                "diagram_id": g.id,
                "ground_truth_component_count": len(g.components),
                "maskrcnn_detection_count": masks_above_threshold,
                "detections": detections,
            })
            print(f"{g.id}: {len(g.components)} ground-truth components, {masks_above_threshold} Mask R-CNN detections")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "model": "maskrcnn_resnet50_fpn (COCO-pretrained, torchvision)",
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "results": results,
    }, indent=2), encoding="utf-8")
    total_detections = sum(r["maskrcnn_detection_count"] for r in results)
    print(f"\nTotal Mask R-CNN detections across all 10 diagrams: {total_detections}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

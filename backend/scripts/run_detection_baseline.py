"""
Sprint 3 / D13: run the pretrained YOLOv8n detector on all 10 annotated
diagrams and save raw + mapped boxes/confidences.

Writes experiments/baselines/sprint3_yolo_coco_baseline.json - real inference
output, not fabricated. No performance claim is written anywhere until this
has actually run (per the plan's non-negotiable evaluation rule); D14/D15
consume this file to compute real metrics.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/run_detection_baseline.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402
from app.modules.cv_pipeline.detection_mapping import map_detections  # noqa: E402
from app.modules.cv_pipeline.pipeline import ComponentDetector, CVPreprocessor  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
MODEL_PATH = BACKEND_DIR / "models" / "yolov8n.pt"
OUT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint3_yolo_coco_baseline.json"
CONFIDENCE_THRESHOLD = 0.25


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"{MODEL_PATH} not found - run backend/scripts/inspect_yolo_classes.py first to download it."
        )

    preprocessor = CVPreprocessor()
    detector = ComponentDetector(model_path=str(MODEL_PATH), confidence=CONFIDENCE_THRESHOLD)

    graphs = load_manifest()
    results = []
    for g in graphs:
        img_path = DIAGRAMS_DIR / Path(g.source).name
        img = preprocessor.preprocess(str(img_path))  # BGR, resized, normalized
        raw_detections = detector.detect(img)
        mapped = map_detections(raw_detections, confidence_threshold=CONFIDENCE_THRESHOLD)

        results.append({
            "diagram_id": g.id,
            "image_shape": list(img.shape),
            "ground_truth_component_count": len(g.components),
            "raw_detection_count": len(raw_detections),
            "mapped_detection_count": len(mapped),
            "raw_detections": raw_detections,
            "mapped_detections": [m.to_dict() for m in mapped],
        })
        print(f"{g.id}: {len(g.components)} ground-truth components, "
              f"{len(raw_detections)} raw YOLO detections, {len(mapped)} mapped")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "model": "yolov8n.pt (COCO-pretrained)",
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()

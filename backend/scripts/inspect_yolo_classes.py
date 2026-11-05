"""
Sprint 3 / D11: choose a pretrained YOLO detector and inspect its supported
classes.

Uses YOLOv8n (nano, COCO-pretrained, via ultralytics) - the smallest/fastest
variant, appropriate as a Sprint 3 baseline per the plan's "start with
pretrained models and small, reproducible baselines" rule. Weights
auto-download to backend/models/yolov8n.pt on first run (gitignored).

Writes docs/yolo_classes.md with the real class list and an honest
assessment of applicability to architecture diagrams (feeds D12).
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
REPO_ROOT = BACKEND_DIR.parent
MODEL_PATH = BACKEND_DIR / "models" / "yolov8n.pt"
DOC_PATH = REPO_ROOT / "docs" / "yolo_classes.md"


def main():
    from ultralytics import YOLO

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(MODEL_PATH) if MODEL_PATH.exists() else "yolov8n.pt")
    if not MODEL_PATH.exists():
        # ultralytics downloads to CWD by name; relocate into backend/models/
        downloaded = Path("yolov8n.pt")
        if downloaded.exists():
            downloaded.replace(MODEL_PATH)

    names = model.names  # dict[int, str], real COCO class names from the loaded model
    print(f"Loaded YOLOv8n, {len(names)} classes:")
    for idx, name in names.items():
        print(f"  {idx}: {name}")

    lines = [
        "# YOLOv8n (COCO-pretrained) Class Inventory (Sprint 3 / D11)",
        "",
        f"Model: `yolov8n.pt` (ultralytics, COCO-pretrained, {len(names)} classes).",
        "",
        "## Full class list",
        "",
        "| id | class |",
        "|---|---|",
    ]
    lines += [f"| {idx} | {name} |" for idx, name in names.items()]
    lines += [
        "",
        "## Assessment (feeds D12)",
        "",
        "None of these 80 COCO classes describe architecture-diagram components",
        "(services, databases, queues, gateways, etc.) - COCO is a photograph",
        "object-detection dataset (people, vehicles, animals, furniture,",
        "household items). A diagram box labeled \"Database\" will not match any",
        "COCO class by label; the detector may still fire on diagram content",
        "that incidentally resembles a COCO object (e.g. a person icon), but",
        "that's coincidental, not semantically meaningful for our task.",
        "",
        "Per the plan's non-negotiable rule (\"start with pretrained models...",
        "do not spend the 50 days training a large detector from scratch\"),",
        "Sprint 3's approach is therefore: run the pretrained detector as-is,",
        "and - per D12 - treat *any* detection above the confidence threshold",
        "as a generic `architecture_component` candidate, ignoring its COCO",
        "label entirely rather than trying to map COCO semantics onto diagram",
        "semantics. The real precision/recall this yields against our hand-",
        "annotated ground truth is measured honestly in D13-D15, not assumed.",
    ]
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {DOC_PATH}")


if __name__ == "__main__":
    main()

"""
Sprint 2 / D9: batch-preprocess every diagram in the manifest and save the
processed images under stable IDs (the manifest's diagram_id), alongside
real before/after quality metadata for D7/D8.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/batch_preprocess.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import cv2  # noqa: E402

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402
from app.modules.cv_pipeline.image_metadata import compute_metadata  # noqa: E402
from app.modules.cv_pipeline.pipeline import CVPreprocessor  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
PROCESSED_DIR = REPO_ROOT / "data" / "diagrams" / "processed"
METADATA_PATH = PROCESSED_DIR / "metadata.json"


def main():
    graphs = load_manifest()
    preprocessor = CVPreprocessor()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    for g in graphs:
        raw_path = DIAGRAMS_DIR / Path(g.source).name

        original = preprocessor.load(str(raw_path))
        original_meta = compute_metadata(original, str(raw_path), channel_order="bgr")

        processed = preprocessor.preprocess(str(raw_path), color_mode="rgb")
        processed_meta = compute_metadata(processed, channel_order="rgb")

        out_path = PROCESSED_DIR / f"{g.id}.png"
        # cv2.imwrite expects BGR; processed is RGB, so convert back for saving.
        cv2.imwrite(str(out_path), cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))

        records.append({
            "diagram_id": g.id,
            "raw_path": str(raw_path.relative_to(REPO_ROOT)),
            "processed_path": str(out_path.relative_to(REPO_ROOT)),
            "original": original_meta.to_dict(),
            "processed": processed_meta.to_dict(),
        })
        print(f"{g.id}: {original_meta.width}x{original_meta.height} -> {processed_meta.width}x{processed_meta.height}"
              f"  blur {original_meta.blur_score:.1f} -> {processed_meta.blur_score:.1f}")

    METADATA_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"\nProcessed {len(records)} diagrams. Metadata written to {METADATA_PATH}")


if __name__ == "__main__":
    main()

"""
Sprint 5 / D21 + D22: crop every real ground-truth component region, compute
a CLIP embedding baseline for each, and run OCR to recover its text label.

Crops are taken from the raw (unresized) diagram images, since the manifest's
bbox coordinates were annotated against the originals.

Writes experiments/baselines/sprint5_embeddings_ocr.json and prints a real
validation check for D21 (same-type components should be more visually
similar to each other than to different-type components, on average).

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/compute_component_embeddings.py
"""

import json
import sys
from itertools import combinations
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest  # noqa: E402
from app.modules.cv_pipeline.embeddings import ComponentEmbedder, cosine_similarity  # noqa: E402
from app.modules.cv_pipeline.ocr import RegionOCR  # noqa: E402
from app.modules.cv_pipeline.pipeline import CVPreprocessor  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
OUT_PATH = REPO_ROOT / "experiments" / "baselines" / "sprint5_embeddings_ocr.json"


def main():
    preprocessor = CVPreprocessor()
    embedder = ComponentEmbedder()
    ocr = RegionOCR()

    records = []
    for g in load_manifest():
        raw_path = DIAGRAMS_DIR / Path(g.source).name
        img = preprocessor.load(str(raw_path))  # raw, unresized BGR - matches annotation coordinate space
        for c in g.components:
            if c.bbox is None:
                continue
            x1, y1, x2, y2 = int(c.bbox.x1), int(c.bbox.y1), int(c.bbox.x2), int(c.bbox.y2)
            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            embedding = embedder.embed_region(crop)
            best_ocr = ocr.read_best_text(crop)
            ocr_text = best_ocr.text if best_ocr else None
            ocr_confidence = best_ocr.confidence if best_ocr else 0.0
            matches_label = bool(ocr_text and ocr_text.strip().lower() in c.name.lower())

            records.append({
                "diagram_id": g.id,
                "component_id": c.id,
                "component_name": c.name,
                "component_type": c.type.value,
                "bbox": [x1, y1, x2, y2],
                "embedding": embedding,
                "ocr_text": ocr_text,
                "ocr_confidence": ocr_confidence,
                "ocr_matches_label": matches_label,
            })
        print(f"{g.id}: embedded + OCR'd {len(g.components)} components")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"\nWrote {len(records)} component records to {OUT_PATH}")

    # D21 baseline validation: same-type pairs should be more similar on
    # average than different-type pairs, if the embedding carries real signal.
    same_type_sims, diff_type_sims = [], []
    for a, b in combinations(records, 2):
        sim = cosine_similarity(a["embedding"], b["embedding"])
        if a["component_type"] == b["component_type"]:
            same_type_sims.append(sim)
        else:
            diff_type_sims.append(sim)

    avg_same = sum(same_type_sims) / len(same_type_sims) if same_type_sims else 0.0
    avg_diff = sum(diff_type_sims) / len(diff_type_sims) if diff_type_sims else 0.0
    matches = sum(1 for r in records if r["ocr_matches_label"])

    print(f"\nAvg cosine similarity, same-type pairs ({len(same_type_sims)}): {avg_same:.4f}")
    print(f"Avg cosine similarity, different-type pairs ({len(diff_type_sims)}): {avg_diff:.4f}")
    print(f"OCR recovered text matching the real label: {matches}/{len(records)}")


if __name__ == "__main__":
    main()

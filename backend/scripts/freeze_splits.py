"""
Sprint 9 / D41: freeze the diagram train/validation/test split.

With only 10 real diagrams, a deterministic seeded shuffle assigns 6/2/2.
Written once to data/annotations/splits.json; this script refuses to
overwrite an existing split file (that's the point of "freezing" it - see
the plan's non-negotiable rule: "do not tune prompts or thresholds on the
final test set"). All Sprint 9 evaluation scripts read this same file
rather than re-splitting.

Run from the backend/ directory: ../venv/Scripts/python.exe scripts/freeze_splits.py
"""

import json
import random
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.cv_pipeline.dataset_manifest import load_manifest  # noqa: E402

REPO_ROOT = BACKEND_DIR.parent
SPLITS_PATH = REPO_ROOT / "data" / "annotations" / "splits.json"
SEED = 42
VAL_SIZE = 2
TEST_SIZE = 2


def main():
    if SPLITS_PATH.exists():
        print(f"{SPLITS_PATH} already exists - split is frozen, not regenerating.")
        return

    diagram_ids = sorted(g.id for g in load_manifest())
    rng = random.Random(SEED)
    shuffled = diagram_ids.copy()
    rng.shuffle(shuffled)

    test = sorted(shuffled[:TEST_SIZE])
    val = sorted(shuffled[TEST_SIZE:TEST_SIZE + VAL_SIZE])
    train = sorted(shuffled[TEST_SIZE + VAL_SIZE:])

    splits = {"seed": SEED, "train": train, "val": val, "test": test}
    SPLITS_PATH.write_text(json.dumps(splits, indent=2), encoding="utf-8")
    print(f"Wrote {SPLITS_PATH}")
    print(f"train ({len(train)}): {train}")
    print(f"val ({len(val)}): {val}")
    print(f"test ({len(test)}): {test}")


if __name__ == "__main__":
    main()

"""Sprint 9 / D41: tests that the frozen train/val/test split is well-formed."""

import json
from pathlib import Path

from app.modules.cv_pipeline.dataset_manifest import load_manifest

SPLITS_PATH = Path(__file__).resolve().parents[3] / "data" / "annotations" / "splits.json"


def _splits():
    return json.loads(SPLITS_PATH.read_text(encoding="utf-8"))


def test_splits_file_exists():
    assert SPLITS_PATH.exists()


def test_splits_cover_every_real_diagram_with_no_overlap():
    splits = _splits()
    train, val, test = set(splits["train"]), set(splits["val"]), set(splits["test"])

    assert train & val == set()
    assert train & test == set()
    assert val & test == set()

    all_manifest_ids = {g.id for g in load_manifest()}
    assert train | val | test == all_manifest_ids


def test_test_split_is_small_and_held_out():
    splits = _splits()
    assert 1 <= len(splits["test"]) <= 3  # a genuine held-out set, not most of the dataset

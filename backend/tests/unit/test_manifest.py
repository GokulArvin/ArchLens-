"""Sprint 1 / D4: tests for the diagram manifest (data/annotations/manifest.json)."""

from pathlib import Path

import pytest

from app.modules.cv_pipeline.dataset_manifest import (
    DIAGRAMS_DIR,
    MANIFEST_PATH,
    load_manifest,
    validate_manifest,
)


@pytest.fixture(scope="module")
def graphs():
    return load_manifest()


def test_manifest_file_exists():
    assert MANIFEST_PATH.exists(), f"manifest not found at {MANIFEST_PATH}"


def test_manifest_has_at_least_ten_entries(graphs):
    assert len(graphs) >= 10


def test_validate_manifest_reports_no_problems(graphs):
    problems = validate_manifest(graphs)
    assert problems == []


def test_every_diagram_image_can_be_opened(graphs):
    from PIL import Image

    for g in graphs:
        img_path = DIAGRAMS_DIR / Path(g.source).name
        with Image.open(img_path) as im:
            width, height = im.size
        assert width > 0 and height > 0


def test_every_component_bbox_within_image_bounds(graphs):
    from PIL import Image

    for g in graphs:
        img_path = DIAGRAMS_DIR / Path(g.source).name
        with Image.open(img_path) as im:
            width, height = im.size
        for c in g.components:
            if c.bbox is None:
                continue
            assert 0 <= c.bbox.x1 < c.bbox.x2 <= width, f"{g.id}/{c.id} x out of bounds"
            assert 0 <= c.bbox.y1 < c.bbox.y2 <= height, f"{g.id}/{c.id} y out of bounds"


def test_every_graph_has_a_real_paired_repository(graphs):
    for g in graphs:
        repo = g.metadata.get("source_repository")
        assert repo is not None, f"{g.id} missing source_repository"
        assert repo["repo_url"].startswith("https://github.com/")
        assert repo["diagram_provenance"] in ("official", "derived")


def test_derived_diagrams_cite_real_evidence(graphs):
    for g in graphs:
        repo = g.metadata["source_repository"]
        if repo["diagram_provenance"] == "derived":
            assert len(repo.get("evidence", [])) > 0, f"{g.id} is derived but has no evidence citations"


def test_relationship_endpoints_reference_real_components(graphs):
    for g in graphs:
        ids = {c.id for c in g.components}
        for rel in g.relationships:
            assert rel.source in ids, f"{g.id}: unknown relationship source {rel.source}"
            assert rel.target in ids, f"{g.id}: unknown relationship target {rel.target}"

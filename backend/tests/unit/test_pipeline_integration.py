"""
Audit-pass fixes for backend/app/modules/cv_pipeline/pipeline.py:

1. select_component_type: CLIPClassifier.classify() with no model loaded
   returns all-zero scores; a bare max(scores, key=scores.get) tie-broke to
   the first dict entry ("database"), silently mistyping every component.
2. CVPipeline._extract_relationships was a stale placeholder that always
   returned [] despite Sprint 5 building real geometry-based extraction
   (geometry_relations.py) - now wired in for real.

These don't need YOLO/CLIP model weights loaded, so they stay in the fast
unit-test suite (CVPipeline.__new__ bypasses __init__'s model loading).
"""

from pathlib import Path

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest
from app.modules.cv_pipeline.pipeline import CVPipeline, select_component_type


def test_select_component_type_returns_unknown_for_all_zero_scores():
    scores = {"database": 0.0, "service": 0.0, "queue": 0.0, "gateway": 0.0, "frontend": 0.0, "cache": 0.0, "external": 0.0}
    assert select_component_type(scores) == "unknown"


def test_select_component_type_returns_unknown_for_empty_dict():
    assert select_component_type({}) == "unknown"


def test_select_component_type_picks_the_real_winner():
    scores = {"database": 0.1, "service": 0.9, "queue": 0.0}
    assert select_component_type(scores) == "service"


def test_select_component_type_does_not_default_to_database_on_tie():
    """Regression test for the specific bug found: a naive max() tie-break
    on all-zero scores always landed on "database" (first dict key)."""
    scores = {"database": 0.0, "service": 0.0}
    assert select_component_type(scores) != "database"


def test_extract_relationships_returns_empty_for_no_components():
    pipeline = CVPipeline.__new__(CVPipeline)  # bypass __init__, no model loading needed
    assert pipeline._extract_relationships([], img=None) == []


def test_extract_relationships_uses_real_geometry_extraction():
    """Regression test for the stale placeholder: feed it real ground-truth
    components (as the dict shape analyze() produces) for a real diagram and
    confirm it returns real geometry-based candidates, not []."""
    g = next(x for x in load_manifest() if x.id == "gcp_microservices_demo")
    img_path = DIAGRAMS_DIR / Path(g.source).name

    import cv2
    img = cv2.imread(str(img_path))

    components = [
        {"id": c.id, "name": c.name, "type": c.type.value, "bbox": {"x1": c.bbox.x1, "y1": c.bbox.y1, "x2": c.bbox.x2, "y2": c.bbox.y2}, "confidence": 1.0}
        for c in g.components
        if c.bbox is not None
    ]

    pipeline = CVPipeline.__new__(CVPipeline)  # bypass __init__, no model loading needed
    relationships = pipeline._extract_relationships(components, img)

    assert len(relationships) > 0  # this diagram has real connectors Hough should find
    for r in relationships:
        assert "source" in r and "target" in r and "confidence" in r

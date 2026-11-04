"""Sprint 4 / D17-D18: tests for the region-cropping segmentation fallback."""

from pathlib import Path

import pytest

from app.modules.cv_pipeline.dataset_manifest import DIAGRAMS_DIR, load_manifest
from app.modules.cv_pipeline.pipeline import CVPreprocessor
from app.modules.cv_pipeline.segmentation import RegionProposalSegmenter


@pytest.fixture(scope="module")
def sample_image():
    g = load_manifest()[0]
    return CVPreprocessor().preprocess(str(DIAGRAMS_DIR / Path(g.source).name))


def test_propose_regions_returns_at_least_one_region(sample_image):
    regions = RegionProposalSegmenter().propose_regions(sample_image)
    assert len(regions) > 0


def test_region_bboxes_within_image_bounds(sample_image):
    h, w = sample_image.shape[:2]
    regions = RegionProposalSegmenter().propose_regions(sample_image)
    for r in regions:
        x1, y1, x2, y2 = r.bbox
        assert 0 <= x1 < x2 <= w
        assert 0 <= y1 < y2 <= h


def test_region_area_matches_bbox_roughly(sample_image):
    regions = RegionProposalSegmenter().propose_regions(sample_image)
    for r in regions:
        x1, y1, x2, y2 = r.bbox
        bbox_area = (x2 - x1) * (y2 - y1)
        # contour area can't exceed its own bounding box area
        assert r.area <= bbox_area + 1e-6


def test_contour_points_form_a_real_polygon(sample_image):
    regions = RegionProposalSegmenter().propose_regions(sample_image)
    assert any(len(r.contour_points) >= 3 for r in regions)


def test_area_fraction_filtering_excludes_near_whole_image_and_tiny_noise(sample_image):
    h, w = sample_image.shape[:2]
    image_area = h * w
    regions = RegionProposalSegmenter(min_area_fraction=0.0005, max_area_fraction=0.5).propose_regions(sample_image)
    for r in regions:
        fraction = r.area / image_area
        assert 0.0 <= fraction <= 0.5 + 1e-6


def test_stricter_min_area_yields_fewer_or_equal_regions(sample_image):
    loose = RegionProposalSegmenter(min_area_fraction=0.0001).propose_regions(sample_image)
    strict = RegionProposalSegmenter(min_area_fraction=0.01).propose_regions(sample_image)
    assert len(strict) <= len(loose)

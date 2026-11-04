"""Sprint 5 / D23-D24: tests for geometry-based relation extraction."""

import cv2
import numpy as np
import pytest

from app.modules.cv_pipeline.geometry_relations import _nearest_component, detect_lines, propose_relations
from app.schemas.models import ArchComponent, BoundingBox


def _component(id_, bbox):
    return ArchComponent(id=id_, name=id_, type="service", bbox=BoundingBox(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3]))


def test_detect_lines_finds_a_drawn_straight_line():
    img = np.full((200, 200, 3), 255, dtype=np.uint8)
    cv2.line(img, (20, 100), (180, 100), (0, 0, 0), 3)
    lines = detect_lines(img, min_line_length=50)
    assert len(lines) > 0


def test_detect_lines_returns_empty_list_for_blank_image():
    img = np.full((200, 200, 3), 255, dtype=np.uint8)
    assert detect_lines(img) == []


def test_nearest_component_point_inside_box_has_zero_distance():
    comps = [_component("a", [0, 0, 100, 100])]
    comp_id, dist = _nearest_component((50, 50), comps, max_distance=1000)
    assert comp_id == "a"
    assert dist == pytest.approx(0.0)


def test_nearest_component_respects_max_distance():
    comps = [_component("a", [0, 0, 10, 10])]
    comp_id, _ = _nearest_component((1000, 1000), comps, max_distance=50)
    assert comp_id is None


def test_nearest_component_picks_the_closer_of_two():
    comps = [_component("near", [0, 0, 10, 10]), _component("far", [500, 500, 510, 510])]
    comp_id, _ = _nearest_component((20, 20), comps, max_distance=1000)
    assert comp_id == "near"


def test_propose_relations_connects_two_different_components():
    comps = [_component("a", [0, 0, 20, 20]), _component("b", [180, 180, 200, 200])]
    lines = [(10.0, 10.0, 190.0, 190.0)]  # connects the center of a to the center of b
    candidates = propose_relations(lines, comps, max_endpoint_distance=50)
    assert len(candidates) == 1
    assert {candidates[0].source, candidates[0].target} == {"a", "b"}


def test_propose_relations_excludes_self_loops():
    comps = [_component("a", [0, 0, 100, 100])]
    lines = [(10.0, 10.0, 90.0, 90.0)]  # both endpoints nearest to the same component
    candidates = propose_relations(lines, comps, max_endpoint_distance=50)
    assert candidates == []


def test_propose_relations_deduplicates_and_keeps_best_distance():
    comps = [_component("a", [0, 0, 20, 20]), _component("b", [180, 180, 200, 200])]
    lines = [
        (10.0, 10.0, 190.0, 190.0),  # tight fit
        (-50.0, -50.0, 250.0, 250.0),  # same pair, much looser fit
    ]
    candidates = propose_relations(lines, comps, max_endpoint_distance=1000)
    assert len(candidates) == 1  # deduplicated to one candidate for the (a, b) pair

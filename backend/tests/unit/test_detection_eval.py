"""Sprint 3 / D14: tests for IoU and greedy box matching, using known-value cases."""

import pytest

from app.modules.cv_pipeline.detection_eval import evaluate_detections, iou
from app.schemas.models import ArchComponent, BoundingBox


def test_iou_identical_boxes_is_one():
    box = [0, 0, 10, 10]
    assert iou(box, box) == pytest.approx(1.0)


def test_iou_disjoint_boxes_is_zero():
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == pytest.approx(0.0)


def test_iou_known_partial_overlap():
    # two 10x10 boxes overlapping in a 5x10 region: intersection=50, union=150
    a = [0, 0, 10, 10]
    b = [5, 0, 15, 10]
    assert iou(a, b) == pytest.approx(50 / 150)


def test_iou_is_symmetric():
    a = [0, 0, 10, 10]
    b = [5, 5, 15, 15]
    assert iou(a, b) == pytest.approx(iou(b, a))


def _component(id_, bbox):
    return ArchComponent(id=id_, name=id_, type="service", bbox=BoundingBox(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3]))


def test_evaluate_detections_perfect_match():
    gt = [_component("a", [0, 0, 10, 10]), _component("b", [20, 20, 30, 30])]
    preds = [[0, 0, 10, 10], [20, 20, 30, 30]]
    result = evaluate_detections("d", gt, preds, iou_threshold=0.5)
    assert result.true_positives == 2
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.precision == pytest.approx(1.0)
    assert result.recall == pytest.approx(1.0)


def test_evaluate_detections_no_predictions_is_all_false_negatives():
    gt = [_component("a", [0, 0, 10, 10])]
    result = evaluate_detections("d", gt, [], iou_threshold=0.5)
    assert result.true_positives == 0
    assert result.false_negatives == 1
    assert result.recall == 0.0
    assert result.precision == 0.0  # no predictions at all -> defined as 0, not divide-by-zero


def test_evaluate_detections_spurious_prediction_is_false_positive():
    gt = [_component("a", [0, 0, 10, 10])]
    preds = [[100, 100, 110, 110]]  # nowhere near the ground truth
    result = evaluate_detections("d", gt, preds, iou_threshold=0.5)
    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 1


def test_evaluate_detections_greedy_matching_prefers_best_iou():
    gt = [_component("a", [0, 0, 10, 10])]
    # one weak overlap, one near-perfect overlap - matcher must pick the better one
    preds = [[2, 2, 14, 14], [0, 0, 10, 10]]
    result = evaluate_detections("d", gt, preds, iou_threshold=0.1)
    assert result.true_positives == 1
    assert result.matched_pairs[0][1] == 1  # matched the second (better) prediction

"""
Unit tests for BaseComponentDetector, ComponentDetector (YOLO), and FasterRCNNDetector.
Sprint 3 P3 (Task 14.1) — all torch-dependent tests use MagicMock; no GPU or real model needed.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from app.modules.cv_pipeline.pipeline import (
    BaseComponentDetector,
    ComponentDetector,
    FasterRCNNDetector,
)


# ─── BaseComponentDetector ABC ───────────────────────────────────────────────

def test_base_detector_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseComponentDetector()


def test_abstract_subclass_missing_detect_raises():
    class IncompleteDetector(BaseComponentDetector):
        pass
    with pytest.raises(TypeError):
        IncompleteDetector()


def test_component_detector_is_subclass():
    assert issubclass(ComponentDetector, BaseComponentDetector)


def test_faster_rcnn_detector_is_subclass():
    assert issubclass(FasterRCNNDetector, BaseComponentDetector)


# ─── ComponentDetector (YOLO) ─────────────────────────────────────────────────

def test_yolo_detect_no_model_returns_empty_list():
    detector = ComponentDetector()
    result = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
    assert result == []


# ─── FasterRCNNDetector — helpers ────────────────────────────────────────────

def _make_torch_mock(boxes_list, labels_list, scores_list):
    """Build a (fake_model, torch_mock) pair without importing real torch."""
    boxes_mock  = MagicMock()
    labels_mock = MagicMock()
    scores_mock = MagicMock()
    boxes_mock.cpu().numpy.return_value  = boxes_list
    labels_mock.cpu().numpy.return_value = labels_list
    scores_mock.cpu().numpy.return_value = scores_list

    fake_pred  = {"boxes": boxes_mock, "labels": labels_mock, "scores": scores_mock}
    fake_model = MagicMock(return_value=[fake_pred])

    no_grad_ctx = MagicMock()
    no_grad_ctx.__enter__ = MagicMock(return_value=None)
    no_grad_ctx.__exit__  = MagicMock(return_value=False)

    torch_mock = MagicMock()
    torch_mock.no_grad.return_value = no_grad_ctx
    torch_mock.from_numpy = MagicMock(return_value=MagicMock())

    return fake_model, torch_mock


# ─── FasterRCNNDetector ───────────────────────────────────────────────────────

def test_faster_rcnn_unavailable_torch_returns_empty():
    detector = FasterRCNNDetector()
    with patch.object(detector, "_get_model", return_value=None):
        result = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
    assert result == []


def test_faster_rcnn_no_model_returns_empty():
    detector = FasterRCNNDetector()
    detector._model = None
    detector._init_attempted = True
    result = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
    assert result == []


def test_faster_rcnn_detect_returns_detection_result_format():
    fake_model, torch_mock = _make_torch_mock(
        [[10.0, 20.0, 50.0, 60.0]], [1], [0.9]
    )
    detector = FasterRCNNDetector(confidence=0.5)
    detector._model = fake_model
    detector._init_attempted = True

    with patch.dict("sys.modules", {"torch": torch_mock}):
        results = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == {"bbox", "confidence", "class_id", "class_name"}
    assert isinstance(r["bbox"], list) and len(r["bbox"]) == 4
    assert isinstance(r["confidence"], float)
    assert isinstance(r["class_id"], int)
    assert isinstance(r["class_name"], str)


def test_faster_rcnn_confidence_threshold_filters_low_scores():
    fake_model, torch_mock = _make_torch_mock(
        [[0.,0.,1.,1.], [0.,0.,1.,1.], [0.,0.,1.,1.]],
        [1, 2, 3],
        [0.9, 0.5, 0.3],
    )
    detector = FasterRCNNDetector(confidence=0.8)
    detector._model = fake_model
    detector._init_attempted = True

    with patch.dict("sys.modules", {"torch": torch_mock}):
        results = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

    assert len(results) == 1
    assert results[0]["confidence"] == pytest.approx(0.9, abs=1e-4)


def test_faster_rcnn_detect_result_keys_match_yolo_format():
    fake_model, torch_mock = _make_torch_mock([[5.,5.,50.,50.]], [2], [0.8])
    frcnn = FasterRCNNDetector(confidence=0.5)
    frcnn._model = fake_model
    frcnn._init_attempted = True

    with patch.dict("sys.modules", {"torch": torch_mock}):
        results = frcnn.detect(np.zeros((100, 100, 3), dtype=np.uint8))

    assert len(results) == 1
    assert set(results[0].keys()) == {"bbox", "confidence", "class_id", "class_name"}

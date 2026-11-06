"""
Sprint 9 / D41–D45 (P3): Unit tests for ConformanceEvaluator and RCAEvaluator.
"""

from __future__ import annotations

import json
import pytest

from app.modules.evaluation.conformance_metrics import (
    ConformanceEvaluator,
    EvaluationResult,
    RCAEvaluator,
)


# ---------------------------------------------------------------------------
# ConformanceEvaluator Tests
# ---------------------------------------------------------------------------

class TestConformanceEvaluator:

    def test_evaluation_result_perfect_prediction(self):
        """When predictions exactly match ground truth, precision, recall, and F1 are 1.0."""
        gt = [
            {"fixture_id": "f1", "source": "controller", "target": "repository", "verdict": "VIOLATION", "violation_type": "forbidden_dependency"},
            {"fixture_id": "f1", "source": "service", "target": "database", "verdict": "MISSING", "violation_type": "missing_dependency"},
        ]
        preds = [
            {"source": "controller", "target": "repository", "verdict": "VIOLATION"},
            {"source": "service", "target": "database", "verdict": "MISSING"},
        ]
        evaluator = ConformanceEvaluator(gt)
        result = evaluator.evaluate(preds)

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert result.tp == 2
        assert result.fp == 0
        assert result.fn == 0
        assert len(result.false_positives) == 0
        assert len(result.false_negatives) == 0

    def test_evaluation_result_no_predictions(self):
        """When no predictions are made, precision is 0.0, recall is 0.0, F1 is 0.0, fn == len(gt)."""
        gt = [
            {"fixture_id": "f1", "source": "controller", "target": "repository", "verdict": "VIOLATION"},
        ]
        evaluator = ConformanceEvaluator(gt)
        result = evaluator.evaluate([])

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0
        assert result.tp == 0
        assert result.fp == 0
        assert result.fn == 1
        assert len(result.false_negatives) == 1

    def test_evaluation_result_no_ground_truth(self):
        """When ground truth is empty and predictions exist, precision is 0.0, recall is 0.0, fp == len(preds)."""
        preds = [
            {"source": "ctrl", "target": "repo", "verdict": "VIOLATION"},
        ]
        evaluator = ConformanceEvaluator([])
        result = evaluator.evaluate(preds)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0
        assert result.tp == 0
        assert result.fp == 1
        assert result.fn == 0
        assert len(result.false_positives) == 1

    def test_evaluation_result_partial_match(self):
        """1 TP, 1 FP, 1 FN: precision = 0.5, recall = 0.5, F1 = 0.5."""
        gt = [
            {"source": "a", "target": "b", "verdict": "VIOLATION"},
            {"source": "c", "target": "d", "verdict": "MISSING"},
        ]
        preds = [
            {"source": "a", "target": "b", "verdict": "VIOLATION"},  # TP
            {"source": "x", "target": "y", "verdict": "VIOLATION"},  # FP
        ]
        evaluator = ConformanceEvaluator(gt)
        result = evaluator.evaluate(preds)

        assert result.tp == 1
        assert result.fp == 1
        assert result.fn == 1
        assert result.precision == pytest.approx(0.5)
        assert result.recall == pytest.approx(0.5)
        assert result.f1 == pytest.approx(0.5)

    def test_evaluate_by_verdict(self):
        """Test per-verdict breakdowns."""
        gt = [
            {"source": "a", "target": "b", "verdict": "VIOLATION"},
            {"source": "c", "target": "d", "verdict": "MISSING"},
        ]
        preds = [
            {"source": "a", "target": "b", "verdict": "VIOLATION"},
        ]
        evaluator = ConformanceEvaluator(gt)
        breakdown = evaluator.evaluate_by_verdict(preds, gt)

        assert "VIOLATION" in breakdown
        assert breakdown["VIOLATION"]["tp"] == 1
        assert breakdown["VIOLATION"]["recall"] == 1.0

        assert "MISSING" in breakdown
        assert breakdown["MISSING"]["tp"] == 0
        assert breakdown["MISSING"]["fn"] == 1
        assert breakdown["MISSING"]["recall"] == 0.0

    def test_summary_and_to_json(self):
        """Test summary dictionary and json serialization."""
        gt = [{"source": "a", "target": "b", "verdict": "VIOLATION"}]
        evaluator = ConformanceEvaluator(gt)
        result = evaluator.evaluate(gt)

        summary = result.summary()
        assert summary["tp"] == 1
        assert summary["precision"] == 1.0

        json_str = result.to_json()
        loaded = json.loads(json_str)
        assert loaded["tp"] == 1
        assert loaded["f1"] == 1.0


# ---------------------------------------------------------------------------
# RCAEvaluator Tests
# ---------------------------------------------------------------------------

class TestRCAEvaluator:

    def test_rca_top_k_accuracy_perfect(self):
        """Correct commit at rank 1 gives top-1 = top-3 = top-5 = 1.0."""
        gt = {"v1": "commit_1", "v2": "commit_2"}
        preds = {
            "v1": ["commit_1", "other_a", "other_b"],
            "v2": ["commit_2", "other_c"],
        }
        evaluator = RCAEvaluator(gt)
        top_k = evaluator.evaluate_top_k(preds)

        assert top_k["top_1"] == 1.0
        assert top_k["top_3"] == 1.0
        assert top_k["top_5"] == 1.0

    def test_rca_top_k_accuracy_at_3(self):
        """Correct commit at rank 3 gives top-1 = 0.0, top-3 = 1.0, top-5 = 1.0."""
        gt = {"v1": "target_commit"}
        preds = {
            "v1": ["first", "second", "target_commit", "fourth"],
        }
        evaluator = RCAEvaluator(gt)
        top_k = evaluator.evaluate_top_k(preds)

        assert top_k["top_1"] == 0.0
        assert top_k["top_3"] == 1.0
        assert top_k["top_5"] == 1.0

    def test_rca_top_k_not_found(self):
        """Correct commit not in predictions yields 0.0 across all k."""
        gt = {"v1": "target_commit"}
        preds = {
            "v1": ["unrelated_1", "unrelated_2", "unrelated_3"],
        }
        evaluator = RCAEvaluator(gt)
        top_k = evaluator.evaluate_top_k(preds)

        assert top_k["top_1"] == 0.0
        assert top_k["top_3"] == 0.0
        assert top_k["top_5"] == 0.0

    def test_error_analysis_structure(self):
        """error_analysis returns per-violation breakdown with expected keys."""
        gt = {"v1": "commit_a", "v2": "commit_b"}
        preds = {
            "v1": ["commit_a", "commit_x"],
            "v2": ["commit_y", "commit_z", "commit_b"],
        }
        evaluator = RCAEvaluator(gt)
        analysis = evaluator.error_analysis(preds)

        assert len(analysis) == 2
        entry1 = next(e for e in analysis if e["violation_id"] == "v1")
        assert entry1["expected"] == "commit_a"
        assert entry1["predicted_rank"] == 1
        assert entry1["found_in_top_5"] is True

        entry2 = next(e for e in analysis if e["violation_id"] == "v2")
        assert entry2["expected"] == "commit_b"
        assert entry2["predicted_rank"] == 3
        assert entry2["found_in_top_5"] is True

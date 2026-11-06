"""
Sprint 9 P3 — Conformance and RCA evaluation metrics.

Provides:
  - EvaluationResult  : dataclass holding P/R/F1 and TP/FP/FN breakdowns
  - ConformanceEvaluator : computes conformance precision/recall/F1
  - RCAEvaluator         : computes Top-k accuracy for root-cause commit retrieval
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_div(numerator: float, denominator: float) -> float:
    """Return numerator / denominator, or 0.0 on zero-division."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _violation_key(item: Dict) -> Tuple[str, str, str]:
    """Canonical match key: (source, target, verdict)."""
    return (
        str(item.get("source", "")).lower().strip(),
        str(item.get("target", "")).lower().strip(),
        str(item.get("verdict", "")).upper().strip(),
    )


# ---------------------------------------------------------------------------
# EvaluationResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    """Holds the full evaluation outcome for a single conformance baseline."""

    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int
    by_verdict: Dict[str, Dict] = field(default_factory=dict)
    false_positives: List[Dict] = field(default_factory=list)
    false_negatives: List[Dict] = field(default_factory=list)

    # ------------------------------------------------------------------
    def summary(self) -> Dict:
        """Return all top-level metrics as a plain dict."""
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "by_verdict": self.by_verdict,
            "false_positives_count": len(self.false_positives),
            "false_negatives_count": len(self.false_negatives),
        }

    def to_json(self) -> str:
        """Serialize the full result to a JSON string."""
        return json.dumps(
            {
                "precision": self.precision,
                "recall": self.recall,
                "f1": self.f1,
                "tp": self.tp,
                "fp": self.fp,
                "fn": self.fn,
                "by_verdict": self.by_verdict,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
            },
            indent=2,
        )


# ---------------------------------------------------------------------------
# ConformanceEvaluator
# ---------------------------------------------------------------------------

class ConformanceEvaluator:
    """Evaluate conformance violation detection against a ground-truth label set.

    Ground-truth format (each item):
      {
        "fixture_id"    : str,
        "source"        : str,
        "target"        : str,
        "verdict"       : str,   # e.g. "VIOLATION"
        "violation_type": str,
      }

    Prediction format is identical (fixture_id is optional in predictions).
    Matching is performed on the triple (source, target, verdict).
    """

    def __init__(self, ground_truth_labels: List[Dict]) -> None:
        self.ground_truth: List[Dict] = ground_truth_labels
        logger.info(
            "ConformanceEvaluator initialised with %d ground-truth items.",
            len(self.ground_truth),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, predictions: List[Dict]) -> EvaluationResult:
        """Compute overall precision, recall, and F1 for violation detection.

        Matching criterion: (source, target, verdict) triple.
        """
        gt_keys = {_violation_key(g) for g in self.ground_truth}
        pred_keys = {_violation_key(p) for p in predictions}

        tp = len(gt_keys & pred_keys)
        fp = len(pred_keys - gt_keys)
        fn = len(gt_keys - pred_keys)

        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)

        by_verdict = self.evaluate_by_verdict(predictions, self.ground_truth)
        false_positives = self.compute_false_positives(predictions, self.ground_truth)
        false_negatives = self.compute_false_negatives(predictions, self.ground_truth)

        return EvaluationResult(
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            tp=tp,
            fp=fp,
            fn=fn,
            by_verdict=by_verdict,
            false_positives=false_positives,
            false_negatives=false_negatives,
        )

    def evaluate_by_verdict(
        self,
        predictions: List[Dict],
        ground_truth: List[Dict],
    ) -> Dict[str, Dict]:
        """Compute per-verdict precision, recall, and F1.

        Returns a dict keyed by verdict string:
          {"VIOLATION": {"precision": ..., "recall": ..., "f1": ..., "tp": ..., "fp": ..., "fn": ...}, ...}
        """
        all_verdicts = {
            str(item.get("verdict", "")).upper()
            for item in list(ground_truth) + list(predictions)
            if item.get("verdict")
        }

        results: Dict[str, Dict] = {}
        for verdict in sorted(all_verdicts):
            gt_v = [g for g in ground_truth if str(g.get("verdict", "")).upper() == verdict]
            pred_v = [p for p in predictions if str(p.get("verdict", "")).upper() == verdict]

            gt_keys_v = {_violation_key(g) for g in gt_v}
            pred_keys_v = {_violation_key(p) for p in pred_v}

            tp_v = len(gt_keys_v & pred_keys_v)
            fp_v = len(pred_keys_v - gt_keys_v)
            fn_v = len(gt_keys_v - pred_keys_v)

            prec_v = _safe_div(tp_v, tp_v + fp_v)
            rec_v = _safe_div(tp_v, tp_v + fn_v)
            f1_v = _safe_div(2 * prec_v * rec_v, prec_v + rec_v)

            results[verdict] = {
                "precision": round(prec_v, 4),
                "recall": round(rec_v, 4),
                "f1": round(f1_v, 4),
                "tp": tp_v,
                "fp": fp_v,
                "fn": fn_v,
            }

        return results

    def compute_false_positives(
        self,
        predictions: List[Dict],
        ground_truth: List[Dict],
    ) -> List[Dict]:
        """Return predicted violations not present in ground truth."""
        gt_keys = {_violation_key(g) for g in ground_truth}
        return [p for p in predictions if _violation_key(p) not in gt_keys]

    def compute_false_negatives(
        self,
        predictions: List[Dict],
        ground_truth: List[Dict],
    ) -> List[Dict]:
        """Return ground-truth violations not captured by predictions."""
        pred_keys = {_violation_key(p) for p in predictions}
        return [g for g in ground_truth if _violation_key(g) not in pred_keys]


# ---------------------------------------------------------------------------
# RCAEvaluator
# ---------------------------------------------------------------------------

class RCAEvaluator:
    """Evaluate Root Cause Analysis (RCA) commit retrieval accuracy.

    Ground truth: mapping of violation_id -> known introducing commit hash.
    Predictions : mapping of violation_id -> ranked list of commit hashes.

    Top-k accuracy = fraction of violations where the correct commit appears
    within the top k predictions.
    """

    def __init__(self, ground_truth_commits: Dict[str, str]) -> None:
        """
        Args:
            ground_truth_commits: Maps violation_id -> correct commit hash string.
        """
        self.ground_truth: Dict[str, str] = ground_truth_commits
        logger.info(
            "RCAEvaluator initialised with %d known introducing commits.",
            len(self.ground_truth),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_top_k(
        self,
        predictions: Dict[str, List[str]],
        k_values: Optional[List[int]] = None,
    ) -> Dict[str, float]:
        """Compute Top-k accuracy for commit retrieval.

        Args:
            predictions: Maps violation_id -> ranked list of commit hashes.
            k_values   : k values to evaluate (default: [1, 3, 5]).

        Returns:
            Dict with keys "top_1", "top_3", "top_5" (or matching k_values).
        """
        if k_values is None:
            k_values = [1, 3, 5]

        # Only evaluate violations present in ground truth
        relevant_ids = [vid for vid in self.ground_truth if vid in predictions]
        total = len(relevant_ids)

        result: Dict[str, float] = {}
        for k in k_values:
            if total == 0:
                result[f"top_{k}"] = 0.0
                continue

            hits = 0
            for vid in relevant_ids:
                expected = self.ground_truth[vid]
                ranked = predictions[vid][:k]  # top-k slice
                if expected in ranked:
                    hits += 1

            result[f"top_{k}"] = round(_safe_div(hits, total), 4)

        logger.info("RCA Top-k evaluation complete: %s", result)
        return result

    def error_analysis(
        self,
        predictions: Dict[str, List[str]],
    ) -> List[Dict]:
        """Return per-violation analysis for inspection.

        Each entry:
          {
            "violation_id"   : str,
            "expected"       : str,          # ground-truth commit hash
            "predicted_rank" : int | None,   # 1-based rank, or None if not found
            "found_in_top_5" : bool,
          }
        """
        analysis: List[Dict] = []
        for vid, expected_commit in self.ground_truth.items():
            ranked = predictions.get(vid, [])
            predicted_rank: Optional[int] = None
            if expected_commit in ranked:
                predicted_rank = ranked.index(expected_commit) + 1  # 1-based

            analysis.append(
                {
                    "violation_id": vid,
                    "expected": expected_commit,
                    "predicted_rank": predicted_rank,
                    "found_in_top_5": predicted_rank is not None and predicted_rank <= 5,
                }
            )

        return analysis

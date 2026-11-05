"""
Sprint 3 / D14: a simple evaluation script for box overlap (IoU) and class
labels - compares detector output against the real hand-annotated ground
truth in data/annotations/manifest.json.

Matching strategy: greedy best-IoU matching per diagram at a fixed IoU
threshold (standard for a first-pass detection baseline; Sprint 9 can
swap in a stricter Hungarian/mAP-style matcher if needed).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.models import ArchComponent

DEFAULT_IOU_THRESHOLD = 0.5


def iou(box_a: list[float], box_b: list[float]) -> float:
    """Intersection-over-union of two [x1, y1, x2, y2] boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w, inter_h = max(0.0, inter_x2 - inter_x1), max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


@dataclass
class DetectionEvalResult:
    diagram_id: str
    num_ground_truth: int
    num_predicted: int
    true_positives: int
    false_positives: int
    false_negatives: int
    matched_pairs: list[tuple[str, int]] = field(default_factory=list)  # (gt_component_id, predicted_index)
    unmatched_ground_truth_ids: list[str] = field(default_factory=list)
    unmatched_predicted_indices: list[int] = field(default_factory=list)

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict:
        return {
            "diagram_id": self.diagram_id,
            "num_ground_truth": self.num_ground_truth,
            "num_predicted": self.num_predicted,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "matched_pairs": [{"ground_truth_component_id": gt_id, "predicted_index": pi} for gt_id, pi in self.matched_pairs],
            "unmatched_ground_truth_ids": self.unmatched_ground_truth_ids,
            "unmatched_predicted_indices": self.unmatched_predicted_indices,
        }


def evaluate_detections(
    diagram_id: str,
    ground_truth: list[ArchComponent],
    predicted_boxes: list[list[float]],
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
) -> DetectionEvalResult:
    """Greedy best-IoU matching between ground-truth components and predicted boxes.

    Box-overlap-only evaluation (class labels aren't compared) because every
    prediction is mapped to the single generic `architecture_component`
    class (D12) - there is no class taxonomy to score against yet.
    """
    gt_boxes = [(c.id, [c.bbox.x1, c.bbox.y1, c.bbox.x2, c.bbox.y2]) for c in ground_truth if c.bbox is not None]

    # all pairwise IoUs, sorted best-first, greedily assigned
    pairs = []
    for gi, (_gt_id, gt_box) in enumerate(gt_boxes):
        for pi, pred_box in enumerate(predicted_boxes):
            score = iou(gt_box, pred_box)
            if score >= iou_threshold:
                pairs.append((score, gi, pi))
    pairs.sort(reverse=True)

    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    matched_pairs: list[tuple[str, int]] = []
    for _score, gi, pi in pairs:
        if gi in matched_gt or pi in matched_pred:
            continue
        matched_gt.add(gi)
        matched_pred.add(pi)
        matched_pairs.append((gt_boxes[gi][0], pi))

    true_positives = len(matched_pairs)
    false_negatives = len(gt_boxes) - true_positives
    false_positives = len(predicted_boxes) - true_positives

    unmatched_gt_ids = [gt_boxes[gi][0] for gi in range(len(gt_boxes)) if gi not in matched_gt]
    unmatched_pred_indices = [pi for pi in range(len(predicted_boxes)) if pi not in matched_pred]

    return DetectionEvalResult(
        diagram_id=diagram_id,
        num_ground_truth=len(gt_boxes),
        num_predicted=len(predicted_boxes),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        matched_pairs=matched_pairs,
        unmatched_ground_truth_ids=unmatched_gt_ids,
        unmatched_predicted_indices=unmatched_pred_indices,
    )

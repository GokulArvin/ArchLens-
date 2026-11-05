"""
Sprint 3 / D12: map raw YOLO (COCO-pretrained) detections to a generic
"architecture_component" class.

Per docs/yolo_classes.md's assessment (D11): none of COCO's 80 classes
describe architecture-diagram components, so there is no meaningful
label-to-label mapping to perform. Instead, every detection above the
confidence threshold is treated as a generic architecture_component
candidate; the original COCO label/class_id is kept in metadata for
traceability (e.g. to later audit *what* the detector actually fired on),
but is not used as the component's semantic type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GENERIC_COMPONENT_CLASS = "architecture_component"


@dataclass
class MappedDetection:
    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float
    mapped_class: str  # always GENERIC_COMPONENT_CLASS
    raw_coco_class: str  # original YOLO/COCO label, kept for traceability
    raw_coco_class_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox,
            "confidence": self.confidence,
            "mapped_class": self.mapped_class,
            "raw_coco_class": self.raw_coco_class,
            "raw_coco_class_id": self.raw_coco_class_id,
        }


def map_detection_to_component(detection: dict[str, Any], confidence_threshold: float = 0.25) -> MappedDetection | None:
    """Map one raw ComponentDetector.detect() entry to a generic component.

    detection is expected to have the shape produced by
    pipeline.ComponentDetector.detect(): {"bbox", "confidence", "class_id", "class_name"}.
    Returns None if the detection's confidence is below the threshold.
    """
    if detection["confidence"] < confidence_threshold:
        return None
    return MappedDetection(
        bbox=list(detection["bbox"]),
        confidence=float(detection["confidence"]),
        mapped_class=GENERIC_COMPONENT_CLASS,
        raw_coco_class=detection["class_name"],
        raw_coco_class_id=int(detection["class_id"]),
    )


def map_detections(detections: list[dict[str, Any]], confidence_threshold: float = 0.25) -> list[MappedDetection]:
    mapped = [map_detection_to_component(d, confidence_threshold) for d in detections]
    return [m for m in mapped if m is not None]

"""
Sprint 4 / D17 + D19: a simple region-cropping segmentation baseline.

D16 established (empirically, see experiments/baselines/sprint4_maskrcnn_feasibility.json
and docs/sprint4_segmentation_baseline.md) that pretrained instance
segmentation (Mask R-CNN, COCO-pretrained) is not viable for architecture
diagrams - same vocabulary mismatch as Sprint 3's YOLO baseline. This module
is the retained fallback: classical contour-based region proposals.

Per D19, the Canny edge map is used as an *input feature* that feeds region
detection (closing edge fragments into closed boundaries before contouring)
- it is not returned as the final output; the final output is always a set
of candidate component boxes.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RegionProposal:
    bbox: list[float]  # [x1, y1, x2, y2]
    area: float
    contour_points: list[list[float]]  # polygon vertices, for an actual "mask" rather than just a box

    def to_dict(self) -> dict:
        return {"bbox": self.bbox, "area": self.area, "contour_points": self.contour_points}


class RegionProposalSegmenter:
    """Stage 4 fallback: edge-assisted contour-based region proposals."""

    def __init__(
        self,
        canny_low: int = 50,
        canny_high: int = 150,
        close_kernel_size: int = 5,
        min_area_fraction: float = 0.0005,
        max_area_fraction: float = 0.5,
    ):
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.close_kernel_size = close_kernel_size
        self.min_area_fraction = min_area_fraction
        self.max_area_fraction = max_area_fraction

    def propose_regions(self, img_bgr: np.ndarray) -> list[RegionProposal]:
        h, w = img_bgr.shape[:2]
        image_area = h * w

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        # Edge map as an input feature (D19) - not the final output.
        edges = cv2.Canny(gray, self.canny_low, self.canny_high)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.close_kernel_size, self.close_kernel_size))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        proposals = []
        for contour in contours:
            area = cv2.contourArea(contour)
            area_fraction = area / image_area if image_area else 0.0
            if area_fraction < self.min_area_fraction or area_fraction > self.max_area_fraction:
                continue
            x, y, cw, ch = cv2.boundingRect(contour)
            proposals.append(RegionProposal(
                bbox=[float(x), float(y), float(x + cw), float(y + ch)],
                area=float(area),
                contour_points=[[float(p[0][0]), float(p[0][1])] for p in contour],
            ))
        return proposals

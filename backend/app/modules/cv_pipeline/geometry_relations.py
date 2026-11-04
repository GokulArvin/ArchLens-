"""
Sprint 5 / D23: geometry-based relation candidates using component boxes and
detected line/edge endpoints (Hough transform on the Canny edge map).

Approach: detect straight line segments in the diagram, then for each line,
find which component box each endpoint is nearest to (within a tolerance,
since connector lines rarely touch a box's exact border pixel). If the two
endpoints resolve to two *different* components, propose a relation
candidate between them.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.schemas.models import ArchComponent


@dataclass
class RelationCandidate:
    source: str
    target: str
    confidence: float  # 1 / (1 + total endpoint-to-box distance), higher = tighter geometric fit

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "confidence": round(self.confidence, 4)}


def detect_lines(
    img_bgr: np.ndarray,
    canny_low: int = 50,
    canny_high: int = 150,
    hough_threshold: int = 30,
    min_line_length: int = 20,
    max_line_gap: int = 10,
) -> list[tuple[float, float, float, float]]:
    """Detect straight line segments (likely connectors/arrows) via Hough transform."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, canny_low, canny_high)
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=hough_threshold,
        minLineLength=min_line_length, maxLineGap=max_line_gap,
    )
    if lines is None:
        return []
    # OpenCV returns shape (N, 1, 4) on some versions, (N, 4) on others (e.g. 5.x) - normalize.
    return [(float(x1), float(y1), float(x2), float(y2)) for x1, y1, x2, y2 in lines.reshape(-1, 4)]


def _nearest_component(point: tuple[float, float], components: list[ArchComponent], max_distance: float):
    px, py = point
    best_id, best_dist = None, max_distance
    for c in components:
        if c.bbox is None:
            continue
        cx = min(max(px, c.bbox.x1), c.bbox.x2)
        cy = min(max(py, c.bbox.y1), c.bbox.y2)
        dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
        if dist < best_dist:
            best_id, best_dist = c.id, dist
    return best_id, best_dist


def propose_relations(
    lines: list[tuple[float, float, float, float]],
    components: list[ArchComponent],
    max_endpoint_distance: float = 40.0,
) -> list[RelationCandidate]:
    """Propose relation candidates by matching line endpoints to nearby component boxes."""
    candidates: dict[tuple[str, str], float] = {}  # (source, target) -> best total distance seen
    for x1, y1, x2, y2 in lines:
        source_id, d1 = _nearest_component((x1, y1), components, max_endpoint_distance)
        target_id, d2 = _nearest_component((x2, y2), components, max_endpoint_distance)
        if source_id is None or target_id is None or source_id == target_id:
            continue
        key = tuple(sorted((source_id, target_id)))
        total_dist = d1 + d2
        if key not in candidates or total_dist < candidates[key]:
            candidates[key] = total_dist

    return [
        RelationCandidate(source=a, target=b, confidence=1.0 / (1.0 + dist))
        for (a, b), dist in candidates.items()
    ]

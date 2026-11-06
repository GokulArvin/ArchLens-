"""
Sprint 5 / D23: geometry-based relation candidates using component boxes and
detected line/edge endpoints (Hough transform on the Canny edge map).

Sprint 6 / D23 (P3): Extended with directed relation candidates using
arrowhead detection heuristics — the endpoint that is farther from the
line's centroid and lies closest to a component box is treated as the
*target* (arrowhead tip), making the other end the *source*.

Approach: detect straight line segments in the diagram, then for each line,
find which component box each endpoint is nearest to (within a tolerance,
since connector lines rarely touch a box's exact border pixel). If the two
endpoints resolve to two *different* components, propose a directed relation
candidate between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.schemas.models import ArchComponent


@dataclass
class RelationCandidate:
    source: str
    target: str
    confidence: float  # 1 / (1 + total endpoint-to-box distance), higher = tighter geometric fit
    directed: bool = False  # True when direction was inferred from arrowhead geometry
    evidence: dict = field(default_factory=dict)  # Sprint 6 D23: provenance dict

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "confidence": round(self.confidence, 4),
            "directed": self.directed,
            "evidence": self.evidence,
        }


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


# ---------------------------------------------------------------------------
# Sprint 6 / D23 (P3) — Directed relation candidates
# ---------------------------------------------------------------------------

def _arrowhead_density(
    img_bgr: np.ndarray,
    tip: tuple[float, float],
    radius: int = 12,
) -> float:
    """
    Estimate the local edge density around a point (potential arrowhead tip).
    A dense cluster of edge pixels near a line endpoint hints that there is
    an arrowhead there, making that end the *target* of the directed relation.

    Returns a float in [0, 1] — higher means more arrowhead-like.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    h, w = edges.shape
    x, y = int(round(tip[0])), int(round(tip[1]))
    x1 = max(0, x - radius)
    y1 = max(0, y - radius)
    x2 = min(w, x + radius)
    y2 = min(h, y + radius)
    region = edges[y1:y2, x1:x2]
    if region.size == 0:
        return 0.0
    return float((region > 0).sum()) / region.size


def propose_directed_relations(
    lines: list[tuple[float, float, float, float]],
    components: list[ArchComponent],
    img_bgr: np.ndarray,
    max_endpoint_distance: float = 40.0,
    arrowhead_radius: int = 12,
) -> list[RelationCandidate]:
    """
    Propose *directed* relation candidates.

    Direction heuristic (Sprint 6 D23)
    ------------------------------------
    For each detected line, both endpoints are matched to component boxes.
    The endpoint with *higher local edge density* (more arrowhead-like pixel
    cluster) is treated as the arrow tip → that component is the **target**.
    The other endpoint is the **source**.

    When both endpoints have similar density (|Δdensity| < 0.05) the
    direction is ambiguous — the candidate is returned with ``directed=False``
    to signal UNCERTAIN direction.

    Parameters
    ----------
    lines : output of detect_lines()
    components : list of ArchComponent with bbox
    img_bgr : original BGR image (used for arrowhead density sampling)
    max_endpoint_distance : max pixel distance for endpoint→box matching
    arrowhead_radius : pixel radius of the density sampling window

    Returns
    -------
    list[RelationCandidate] with directed=True/False and evidence dict.
    """
    # Accumulate best (lowest total dist) directed candidate per (src, tgt) pair
    directed_map: dict[tuple[str, str], tuple[float, bool]] = {}

    for x1, y1, x2, y2 in lines:
        id1, d1 = _nearest_component((x1, y1), components, max_endpoint_distance)
        id2, d2 = _nearest_component((x2, y2), components, max_endpoint_distance)
        if id1 is None or id2 is None or id1 == id2:
            continue

        density1 = _arrowhead_density(img_bgr, (x1, y1), arrowhead_radius)
        density2 = _arrowhead_density(img_bgr, (x2, y2), arrowhead_radius)
        ambiguous = abs(density1 - density2) < 0.05

        # Higher density at endpoint2 → target is id2 (arrow tip is at p2)
        if not ambiguous and density2 >= density1:
            src, tgt, directed = id1, id2, True
        elif not ambiguous:
            src, tgt, directed = id2, id1, True
        else:
            # Ambiguous: keep lexicographic ordering, mark undirected
            src, tgt, directed = (min(id1, id2), max(id1, id2), False)

        total_dist = d1 + d2
        key = (src, tgt)
        existing = directed_map.get(key)
        if existing is None or total_dist < existing[0]:
            directed_map[key] = (total_dist, directed)

    return [
        RelationCandidate(
            source=src,
            target=tgt,
            confidence=round(1.0 / (1.0 + dist), 4),
            directed=directed,
            evidence={
                "method": "hough_arrowhead_density",
                "arrowhead_radius_px": arrowhead_radius,
                "max_endpoint_distance_px": max_endpoint_distance,
            },
        )
        for (src, tgt), (dist, directed) in directed_map.items()
    ]

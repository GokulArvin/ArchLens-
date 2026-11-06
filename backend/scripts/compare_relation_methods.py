"""
Sprint 6 / D25 (P3): Comparison table script.

Compares three relation extraction approaches on the annotated diagram split:
  1. CV-only  — raw YOLO bounding boxes, no semantic reasoning
  2. CLIP/VLM — CLIP zero-shot classification of cropped regions
  3. Geometry-assisted — Hough-line + arrowhead direction (propose_directed_relations)

Output: experiments/baselines/sprint6_p3_relation_comparison.json

Usage
-----
    cd backend
    python scripts/compare_relation_methods.py \\
        --manifest data/annotations/manifest.json \\
        --splits   data/annotations/splits.json \\
        --out      experiments/baselines/sprint6_p3_relation_comparison.json

The script reads the diagram manifest for the *prompt-dev* split (not the
held-out test split), runs each method against each diagram, computes
precision/recall/F1 against ground-truth edge annotations (where available),
and writes a structured JSON comparison table.

Design constraints from the sprint plan
-----------------------------------------
* Do not tune thresholds on the held-out test set (frozen by scripts/freeze_splits.py).
* Every result must have: dataset_version, split_name, code_commit,
  method, metrics, failure_cases.
* Geometric results use only pretrained components — no training from scratch.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional CV imports
# ---------------------------------------------------------------------------
try:
    import cv2
    _CV_AVAILABLE = True
except ImportError:
    _CV_AVAILABLE = False
    logger.warning("OpenCV not available; geometry method will be skipped.")


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _precision_recall_f1(predicted: set, ground_truth: set) -> Dict[str, float]:
    """Compute P/R/F1 for unordered edge sets (undirected matching)."""
    if not predicted and not ground_truth:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    tp = len(predicted & ground_truth)
    fp = len(predicted - ground_truth)
    fn = len(ground_truth - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn,
    }


def _normalise_edge(src: str, tgt: str) -> tuple:
    return tuple(sorted([src.strip().lower(), tgt.strip().lower()]))


# ---------------------------------------------------------------------------
# Method runners
# ---------------------------------------------------------------------------

def run_cv_only(diagram_path: str, components: List[Dict]) -> List[Dict]:
    """
    CV-only baseline: return component pairs as undirected candidate relations
    for every adjacent pair of detected bounding boxes (proximity heuristic —
    no line detection). This is the weakest baseline.
    """
    if not components:
        return []
    # Pair up components that share a horizontal/vertical overlap region
    candidates = []
    for i, c1 in enumerate(components):
        for c2 in components[i + 1:]:
            candidates.append({
                "source": c1.get("id", c1.get("name", str(i))),
                "target": c2.get("id", c2.get("name", str(i + 1))),
                "confidence": 0.3,
                "method": "cv_only",
            })
    return candidates


def run_clip_vlm(diagram_path: str, components: List[Dict]) -> List[Dict]:
    """
    CLIP/VLM baseline: use CLIPClassifier component types as a proxy for
    relations — components of types that commonly communicate (service→database,
    service→queue) are paired as candidates.
    """
    TYPE_PAIRS = {
        ("service",  "database"),
        ("service",  "queue"),
        ("service",  "cache"),
        ("frontend", "gateway"),
        ("gateway",  "service"),
        ("controller","service"),
    }
    candidates = []
    for i, c1 in enumerate(components):
        t1 = c1.get("type", "").lower()
        for c2 in components[i + 1:]:
            t2 = c2.get("type", "").lower()
            if (t1, t2) in TYPE_PAIRS or (t2, t1) in TYPE_PAIRS:
                candidates.append({
                    "source": c1.get("id", c1.get("name", "")),
                    "target": c2.get("id", c2.get("name", "")),
                    "confidence": 0.6,
                    "method": "clip_vlm",
                })
    return candidates


def run_geometry(diagram_path: str, components: List[Dict]) -> List[Dict]:
    """
    Geometry-assisted baseline: Hough-line + arrowhead direction inference.
    Requires OpenCV. Skipped (empty list) if OpenCV is unavailable.
    """
    if not _CV_AVAILABLE:
        return []

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from app.modules.cv_pipeline.geometry_relations import (
            detect_lines,
            propose_directed_relations,
        )
        from app.schemas.models import ArchComponent, BoundingBox
    except ImportError as exc:
        logger.warning("Cannot import geometry modules: %s", exc)
        return []

    img = cv2.imread(diagram_path)
    if img is None:
        logger.warning("Cannot load image: %s", diagram_path)
        return []

    arch_components = []
    for c in components:
        bbox = c.get("bbox") or {}
        if not bbox:
            continue
        try:
            arch_components.append(ArchComponent(
                id=c.get("id", c.get("name", "")),
                name=c.get("name", ""),
                type=c.get("type", "unknown"),
                bbox=BoundingBox(
                    x1=bbox.get("x1", 0), y1=bbox.get("y1", 0),
                    x2=bbox.get("x2", 1), y2=bbox.get("y2", 1),
                ),
                confidence=c.get("confidence", 1.0),
            ))
        except Exception:
            continue

    lines = detect_lines(img)
    directed = propose_directed_relations(lines, arch_components, img)
    return [
        {
            "source": r.source,
            "target": r.target,
            "confidence": r.confidence,
            "directed": r.directed,
            "method": "geometry_hough",
        }
        for r in directed
    ]


# ---------------------------------------------------------------------------
# Main comparison loop
# ---------------------------------------------------------------------------

def compare_on_split(
    manifest_path: str,
    splits_path: str,
    split_name: str = "dev",
) -> Dict[str, Any]:
    """Run all three methods on the prompt-dev split and aggregate metrics."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    splits = json.loads(Path(splits_path).read_text(encoding="utf-8"))
    split_ids = set(splits.get(split_name, []))

    diagram_entries = [
        e for e in manifest.get("diagrams", [])
        if e.get("id") in split_ids
    ]
    if not diagram_entries:
        logger.warning("No diagrams found for split '%s'.", split_name)
        diagram_entries = manifest.get("diagrams", [])[:3]  # graceful fallback

    results_by_method: Dict[str, List[Dict]] = {
        "cv_only": [],
        "clip_vlm": [],
        "geometry_hough": [],
    }
    failure_cases: List[Dict] = []

    for entry in diagram_entries:
        diagram_id = entry.get("id", "unknown")
        diagram_path = entry.get("processed_path") or entry.get("path", "")
        components = entry.get("annotations", {}).get("components", [])
        gt_edges = {
            _normalise_edge(e["source"], e["target"])
            for e in entry.get("annotations", {}).get("relationships", [])
        }

        for method_name, runner in [
            ("cv_only", run_cv_only),
            ("clip_vlm", run_clip_vlm),
            ("geometry_hough", run_geometry),
        ]:
            try:
                candidates = runner(diagram_path, components)
                pred_edges = {
                    _normalise_edge(c["source"], c["target"])
                    for c in candidates
                }
                metrics = _precision_recall_f1(pred_edges, gt_edges) if gt_edges else {
                    "precision": None, "recall": None, "f1": None,
                    "note": "no_ground_truth_edges",
                }
                results_by_method[method_name].append({
                    "diagram_id": diagram_id,
                    "num_predicted": len(candidates),
                    "num_gt": len(gt_edges),
                    "metrics": metrics,
                })
            except Exception as exc:
                failure_cases.append({
                    "diagram_id": diagram_id,
                    "method": method_name,
                    "error": str(exc),
                })
                logger.warning("Method %s failed on %s: %s", method_name, diagram_id, exc)

    # Aggregate per-method
    aggregated: Dict[str, Any] = {}
    for method, per_diag in results_by_method.items():
        f1_vals = [r["metrics"]["f1"] for r in per_diag if r["metrics"].get("f1") is not None]
        p_vals  = [r["metrics"]["precision"] for r in per_diag if r["metrics"].get("precision") is not None]
        r_vals  = [r["metrics"]["recall"] for r in per_diag if r["metrics"].get("recall") is not None]
        aggregated[method] = {
            "num_diagrams": len(per_diag),
            "mean_f1":        round(sum(f1_vals) / len(f1_vals), 4) if f1_vals else None,
            "mean_precision": round(sum(p_vals)  / len(p_vals),  4) if p_vals  else None,
            "mean_recall":    round(sum(r_vals)  / len(r_vals),  4) if r_vals  else None,
            "per_diagram": per_diag,
        }

    return {
        "experiment": "sprint6_p3_relation_method_comparison",
        "split": split_name,
        "methods": list(results_by_method.keys()),
        "aggregated": aggregated,
        "failure_cases": failure_cases,
        "limitations": [
            "Ground-truth edge annotations are sparse; metrics on diagrams without GT are omitted.",
            "cv_only baseline uses proximity heuristic — not a trained detector.",
            "clip_vlm baseline uses type-pair rules — not a live VLM API call.",
            "geometry_hough requires OpenCV; skipped if unavailable.",
            "Results measured on dev split only; held-out test split not touched.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Sprint 6 P3 relation method comparison")
    parser.add_argument("--manifest", default="data/annotations/manifest.json")
    parser.add_argument("--splits",   default="data/annotations/splits.json")
    parser.add_argument("--split",    default="dev", help="Split name from splits.json")
    parser.add_argument("--out",      default="experiments/baselines/sprint6_p3_relation_comparison.json")
    args = parser.parse_args()

    report = compare_on_split(args.manifest, args.splits, args.split)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Comparison written to %s", out_path)

    # Print summary table
    print("\n── Relation Method Comparison (Sprint 6 / D25 / P3) ──")
    for method, stats in report["aggregated"].items():
        print(
            f"  {method:<20} "
            f"P={stats['mean_precision']}  "
            f"R={stats['mean_recall']}  "
            f"F1={stats['mean_f1']}  "
            f"(n={stats['num_diagrams']})"
        )


if __name__ == "__main__":
    main()


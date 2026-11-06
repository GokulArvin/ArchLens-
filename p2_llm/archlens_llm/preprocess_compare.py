"""Sprint 2 D7: denoising / contrast-enhancement alternatives, compared qualitatively (grid image)
and with a cheap quantitative proxy: how well per-component OCR reads the gold names after each variant.

P1 owns the production preprocessing module; this is P2's comparison of what helps the
*semantic* step (reading labels). Run:  python -m archlens_llm.preprocess_compare fixtures/synthetic
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np


def variants(gray: np.ndarray) -> dict[str, np.ndarray]:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return {
        "original": gray,
        "gaussian_3": cv2.GaussianBlur(gray, (3, 3), 0),
        "median_3": cv2.medianBlur(gray, 3),
        "bilateral": cv2.bilateralFilter(gray, 7, 50, 50),
        "hist_eq": cv2.equalizeHist(gray),
        "clahe": clahe.apply(gray),
        "median+clahe": clahe.apply(cv2.medianBlur(gray, 3)),
        "adaptive_thresh": cv2.adaptiveThreshold(cv2.medianBlur(gray, 3), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                 cv2.THRESH_BINARY, 31, 10),
        "median+close": cv2.morphologyEx(cv2.medianBlur(gray, 3), cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8)),
    }


def grid(imgs: dict[str, np.ndarray], cols: int = 3, width: int = 420) -> np.ndarray:
    tiles = []
    for name, im in imgs.items():
        h = int(im.shape[0] * width / im.shape[1])
        t = cv2.cvtColor(cv2.resize(im, (width, h)), cv2.COLOR_GRAY2BGR)
        cv2.rectangle(t, (0, 0), (width, 22), (255, 255, 255), -1)
        cv2.putText(t, name, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 200), 1)
        tiles.append(t)
    h = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 255))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    return np.vstack(rows)


def compare(fixture_root: str | Path, out_dir: str | Path = "runs/preprocess_compare") -> dict:
    from .ocr import evaluate_text_association, ocr_components
    root, out = Path(fixture_root), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    table: dict[str, dict[str, float]] = {}
    for sysdir in sorted(p for p in root.iterdir() if (p / "diagram.png").exists()):
        gray = cv2.imread(str(sysdir / "diagram.png"), cv2.IMREAD_GRAYSCALE)
        dets = json.loads((sysdir / "detections.json").read_text())
        gold = json.loads((sysdir / "annotation.json").read_text())
        vs = variants(gray)
        cv2.imwrite(str(out / f"{sysdir.name}_grid.png"), grid(vs))
        for name, im in vs.items():
            r = evaluate_text_association(ocr_components(im, dets), gold)
            table.setdefault(name, {})[sysdir.name] = round(r["exact_rate"], 3)
    summary = {k: {"mean_exact_name_rate": round(sum(v.values()) / len(v), 3), **v} for k, v in table.items()}
    (out / "comparison.json").write_text(json.dumps(summary, indent=1))
    lines = ["| variant | mean exact-name OCR rate | " + " | ".join(next(iter(table.values())).keys()) + " |",
             "|---|---|" + "---|" * len(next(iter(table.values())))]
    for k, v in sorted(summary.items(), key=lambda x: -x[1]["mean_exact_name_rate"]):
        lines.append(f"| {k} | {v['mean_exact_name_rate']} | " + " | ".join(str(v[s]) for s in table[k]) + " |")
    (out / "comparison.md").write_text("\n".join(lines) + "\n")
    return summary


if __name__ == "__main__":
    s = compare(sys.argv[1] if len(sys.argv) > 1 else "fixtures/synthetic")
    for k, v in sorted(s.items(), key=lambda x: -x[1]["mean_exact_name_rate"]):
        print(f"{k:18s} {v['mean_exact_name_rate']}")

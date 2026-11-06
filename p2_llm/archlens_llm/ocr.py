"""Sprint 3 D13 + Sprint 4 D16–D17: OCR text as a supplement to detector boxes, and the
component <-> text association rules.

Association rules (docs/cv_semantic_handoff.md):
  A1 a word belongs to the SMALLEST detector box that contains the word's centre
  A2 a word with no containing box is attached to the nearest box only if within `margin` px
     (labels written just under/next to icons) and flagged 'outside_box'
  A3 a box with no words -> ocr_text = "" and issue 'no_text' (VLM must read it or abstain)
  A4 a word whose centre lies in >1 box at equal smallest area -> 'ambiguous_text', not attached
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None


@dataclass
class Word:
    text: str
    box: tuple[int, int, int, int]  # x1,y1,x2,y2
    conf: float

    @property
    def centre(self):
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)


def run_ocr(image: np.ndarray | str, min_conf: float = 30, psm: int = 11) -> list[Word]:
    if pytesseract is None:
        raise RuntimeError("pytesseract not installed")
    img = cv2.imread(image) if isinstance(image, str) else image
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    d = pytesseract.image_to_data(big, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    words = []
    for i, t in enumerate(d["text"]):
        t = t.strip()
        c = float(d["conf"][i])
        if t and c >= min_conf and any(ch.isalnum() for ch in t):
            x, y, w, h = (d[k][i] // 2 for k in ("left", "top", "width", "height"))
            words.append(Word(t, (x, y, x + w, y + h), c))
    return words


def _inside(pt, b):
    return b[0] <= pt[0] <= b[2] and b[1] <= pt[1] <= b[3]


def _dist(pt, b):
    dx = max(b[0] - pt[0], 0, pt[0] - b[2])
    dy = max(b[1] - pt[1], 0, pt[1] - b[3])
    return (dx * dx + dy * dy) ** 0.5


def associate_text(components: list[dict], words: list[Word], margin: float = 25) -> list[dict]:
    """Return copies of detector components with ocr_text, ocr_conf and association issues."""
    out = {c["id"]: {**c, "ocr_words": [], "issues": []} for c in components}
    area = {c["id"]: (c["bbox"][2] - c["bbox"][0]) * (c["bbox"][3] - c["bbox"][1]) for c in components}
    for w in words:
        containing = [c for c in components if _inside(w.centre, c["bbox"])]
        if containing:
            smallest = min(area[c["id"]] for c in containing)
            tied = [c for c in containing if area[c["id"]] == smallest]
            if len(tied) > 1:
                for c in tied:
                    out[c["id"]]["issues"].append(f"ambiguous_text:{w.text}")
                continue
            out[tied[0]["id"]]["ocr_words"].append(w)
        else:
            near = sorted(components, key=lambda c: _dist(w.centre, c["bbox"]))
            if near and _dist(w.centre, near[0]["bbox"]) <= margin:
                out[near[0]["id"]]["ocr_words"].append(w)
                out[near[0]["id"]]["issues"].append(f"outside_box:{w.text}")
    result = []
    for cid, c in out.items():
        ws = sorted(c.pop("ocr_words"), key=lambda w: (round(w.box[1] / 12), w.box[0]))
        c["ocr_text"] = " ".join(w.text for w in ws)
        c["ocr_conf"] = round(sum(w.conf for w in ws) / len(ws) / 100, 3) if ws else 0.0
        if not ws:
            c["issues"].append("no_text")
        result.append(c)
    return result


def evaluate_text_association(associated: list[dict], gold: dict) -> dict:
    """S4 D17: do labels stay attached to the right regions? Compare ocr_text with gold names."""
    from .labels import normalize_name
    from .annotation import iou
    exact = partial = missing = 0
    rows = []
    for c in associated:
        g = max(gold["components"], key=lambda gc: iou(gc["bbox"], c["bbox"]))
        gn, on = normalize_name(g["name"]), normalize_name(c["ocr_text"])
        if not on:
            missing += 1
            status = "missing"
        elif gn == on:
            exact += 1
            status = "exact"
        elif set(gn.split()) & set(on.split()):
            partial += 1
            status = "partial"
        else:
            status = "wrong"
        rows.append({"id": c["id"], "gold": g["name"], "ocr": c["ocr_text"], "status": status, "issues": c["issues"]})
    n = len(associated) or 1
    return {"exact_rate": exact / n, "partial_rate": partial / n, "missing_rate": missing / n, "rows": rows}


# ---------------------------------------------------------------------------
# Per-component crop OCR (S3 D13 finding: page-level OCR misses text near boxes/arrows;
# cropping each detected box and OCR-ing the interior is far more reliable).
# ---------------------------------------------------------------------------
import re as _re

_EDGE_PUNCT = _re.compile(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$")


def _clean_tokens(tokens: list[tuple[str, float]], min_conf: float) -> tuple[str, float]:
    keep = []
    for t, c in tokens:
        t = _EDGE_PUNCT.sub("", t)
        if not t or c < min_conf:
            continue
        if len(t) <= 2 and not t.isupper():   # border fragments like 'ee', 'om'
            continue
        keep.append((t, c))
    if not keep:
        return "", 0.0
    return " ".join(t for t, _ in keep), sum(c for _, c in keep) / len(keep) / 100


def ocr_components(image: np.ndarray | str, components: list[dict], min_conf: float = 40,
                   pad_x: int = 5, pad_y_frac: float = 0.15) -> list[dict]:
    """OCR the interior of each detector box. Returns component copies with ocr_text/ocr_conf/issues."""
    if pytesseract is None:
        raise RuntimeError("pytesseract not installed")
    img = cv2.imread(image, cv2.IMREAD_GRAYSCALE) if isinstance(image, str) else image
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = img.shape[:2]
    out = []
    for c in components:
        x1, y1, x2, y2 = (int(v) for v in c["bbox"])
        py = int((y2 - y1) * pad_y_frac) + 4
        crop = img[max(0, y1 + py):min(H, y2 - py), max(0, x1 + pad_x):min(W, x2 - pad_x)]
        issues = []
        if crop.size == 0:
            out.append({**c, "ocr_text": "", "ocr_conf": 0.0, "issues": ["empty_crop"]})
            continue
        best_text, best_conf, best_score = "", 0.0, -1.0
        big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        variants = [big, cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                    cv2.threshold(cv2.medianBlur(big, 5), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]]
        for v in variants:
            for psm in (7, 6):
                d = pytesseract.image_to_data(v, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
                t, cf = _clean_tokens([(t, float(x)) for t, x in zip(d["text"], d["conf"]) if t.strip()], min_conf)
                score = cf * len(t.replace(" ", "")) ** 0.5   # prefer confident AND complete reads
                if score > best_score:
                    best_text, best_conf, best_score = t, cf, score
        text, conf = best_text, best_conf
        if not text:
            issues.append("no_text")
        elif conf < 0.7:
            issues.append("low_ocr_conf")
        out.append({**c, "ocr_text": text, "ocr_conf": round(conf, 3), "issues": issues})
    return out

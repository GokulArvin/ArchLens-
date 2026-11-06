"""Sprint 2–3: pilot annotation format, validation, audit, inter-annotator agreement, frozen splits.

Annotation file (one per diagram), see docs/annotation_guide_v1.md:
{"diagram_id": "...", "image": "diagram.png", "annotator": "P2",
 "components": [{"id": "c1", "name": "Order Service", "type": "service", "bbox": [x1,y1,x2,y2]}],
 "relationships": [{"source": "c1", "target": "c2", "type": "depends_on"}]}
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from .labels import normalize_name, normalize_type_label
from .schemas import COMPONENT_TYPES, RELATION_TYPES


def iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def validate_annotation(ann: dict) -> list[str]:
    """S2 D8: structural rules every annotation must satisfy."""
    errs = []
    ids = [c.get("id") for c in ann.get("components", [])]
    if len(ids) != len(set(ids)):
        errs.append("duplicate component ids")
    for c in ann.get("components", []):
        if c.get("type") not in COMPONENT_TYPES:
            errs.append(f"{c.get('id')}: type '{c.get('type')}' not in vocabulary")
        if not c.get("name"):
            errs.append(f"{c.get('id')}: empty name (use type 'unknown' + name '?' if unreadable)")
        b = c.get("bbox")
        if not b or len(b) != 4 or b[2] <= b[0] or b[3] <= b[1]:
            errs.append(f"{c.get('id')}: invalid bbox {b}")
    for r in ann.get("relationships", []):
        if r.get("source") not in ids or r.get("target") not in ids:
            errs.append(f"relation {r.get('source')}->{r.get('target')}: unknown endpoint")
        if r.get("source") == r.get("target"):
            errs.append(f"relation {r.get('source')}: self-loop")
        if r.get("type", "depends_on") not in RELATION_TYPES:
            errs.append(f"relation {r.get('source')}->{r.get('target')}: type '{r.get('type')}' not in vocabulary")
    return errs


def audit_annotations(anns: list[dict]) -> dict:
    """S3 D11: find inconsistent labels across the pilot set.

    * same normalized name labelled with different types in different diagrams
    * type labels that are non-canonical but normalizable (auto-fix suggestions)
    * structural errors per diagram
    """
    by_name: dict[str, Counter] = defaultdict(Counter)
    fixes, structural = [], {}
    for a in anns:
        e = validate_annotation(a)
        if e:
            structural[a["diagram_id"]] = e
        for c in a["components"]:
            by_name[normalize_name(c["name"])][c["type"]] += 1
            if c["type"] not in COMPONENT_TYPES:
                canon = normalize_type_label(str(c["type"]))
                fixes.append({"diagram_id": a["diagram_id"], "id": c["id"], "from": c["type"], "to": canon})
    inconsistent = {n: dict(cnt) for n, cnt in by_name.items() if len(cnt) > 1}
    return {"structural_errors": structural, "type_fix_suggestions": fixes, "inconsistent_names": inconsistent}


def _kappa(pairs: list[tuple[str, str]]) -> float:
    if not pairs:
        return float("nan")
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agreement(a: dict, b: dict, iou_thr: float = 0.5) -> dict:
    """S2 D9: compare two annotators on the same diagram; returns kappa, F1s and disagreement cases."""
    match: dict[str, str] = {}
    used = set()
    for ca in a["components"]:
        best, bi = None, iou_thr
        for cb in b["components"]:
            if cb["id"] in used:
                continue
            v = iou(ca["bbox"], cb["bbox"])
            if v >= bi:
                best, bi = cb, v
        if best:
            match[ca["id"]] = best["id"]
            used.add(best["id"])
    bmap = {c["id"]: c for c in b["components"]}
    amap = {c["id"]: c for c in a["components"]}
    type_pairs, cases = [], []
    for ia, ib in match.items():
        ta, tb = amap[ia]["type"], bmap[ib]["type"]
        type_pairs.append((ta, tb))
        if ta != tb:
            cases.append({"kind": "type", "a": amap[ia], "b": bmap[ib]})
        if normalize_name(amap[ia]["name"]) != normalize_name(bmap[ib]["name"]):
            cases.append({"kind": "name", "a": amap[ia]["name"], "b": bmap[ib]["name"]})
    unmatched_a = [c for c in a["components"] if c["id"] not in match]
    unmatched_b = [c for c in b["components"] if c["id"] not in used]
    cases += [{"kind": "box_only_in_a", "a": c} for c in unmatched_a] + [{"kind": "box_only_in_b", "b": c} for c in unmatched_b]
    ra = {(match.get(r["source"]), match.get(r["target"])) for r in a["relationships"]}
    rb = {(r["source"], r["target"]) for r in b["relationships"]}
    tp = len(ra & rb)
    p = tp / len(rb) if rb else 1.0
    r = tp / len(ra) if ra else 1.0
    for e in ra ^ rb:
        cases.append({"kind": "relation", "edge_b_ids": e, "in": "a" if e in ra else "b"})
    nb = len(a["components"]) + len(b["components"])
    return {"component_match_rate": 2 * len(match) / nb if nb else 1.0, "type_kappa": round(_kappa(type_pairs), 3),
            "relation_f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "disagreements": cases}


def make_split(diagram_ids: list[str], out_path: str | Path, dev_fraction: float = 0.5, seed: int = 13,
               overwrite: bool = False) -> dict:
    """S2 D10: prompt-development split kept separate from the held-out test split.

    Written once; refuses to overwrite so nobody tunes prompts on the test set by accident.
    """
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        return json.loads(out_path.read_text())
    ids = sorted(diagram_ids)
    random.Random(seed).shuffle(ids)
    k = max(1, round(len(ids) * dev_fraction))
    split = {"seed": seed, "prompt_dev": sorted(ids[:k]), "held_out_test": sorted(ids[k:])}
    split["sha256"] = hashlib.sha256(json.dumps(split, sort_keys=True).encode()).hexdigest()[:16]
    out_path.write_text(json.dumps(split, indent=1))
    return split

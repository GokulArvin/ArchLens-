"""Metrics for the P2 experiments (Sprint 9). All scoring rules are fixed here, before any run."""
from __future__ import annotations

from collections import Counter

from ..annotation import iou
from ..labels import normalize_name


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return round(p, 3), round(r, 3), round(2 * p * r / (p + r), 3) if p + r else 0.0


def extraction_metrics(result, gold: dict, iou_thr: float = 0.5) -> dict:
    ex = result.extraction
    gmap = {}
    used = set()
    for c in ex.components:
        if c.bbox is None:
            continue
        best, bv = None, iou_thr
        for g in gold["components"]:
            if g["id"] in used:
                continue
            v = iou(c.bbox, g["bbox"])
            if v >= bv:
                best, bv = g, v
        if best:
            gmap[c.id] = best
            used.add(best["id"])
    names = types = 0
    per_type = Counter()
    for c in ex.components:
        g = gmap.get(c.id)
        if g is None:
            continue
        names += normalize_name(c.name) == normalize_name(g["name"])
        ok = c.type == g["type"]
        types += ok
        per_type[(g["type"], ok)] += 1
    n_gold = len(gold["components"])
    gold_edges = {(r["source"], r["target"]) for r in gold["relationships"]}
    pred_edges = {(gmap[r.source]["id"], gmap[r.target]["id"]) for r in ex.relationships
                  if r.status == "candidate" and r.source in gmap and r.target in gmap}
    unc = sum(r.status == "uncertain" for r in ex.relationships)
    tp = len(pred_edges & gold_edges)
    p, r, f = _prf(tp, len(pred_edges - gold_edges), len(gold_edges - pred_edges))
    return {"component_recall": round(len(gmap) / n_gold, 3) if n_gold else 0.0,
            "name_accuracy": round(names / n_gold, 3) if n_gold else 0.0,
            "type_accuracy": round(types / n_gold, 3) if n_gold else 0.0,
            "relation_precision": p, "relation_recall": r, "relation_f1": f,
            "uncertain_relations": unc,
            "abstained_components": sum(c.abstain for c in ex.components),
            "valid_structured_output": not result.fallback}


def rca_metrics(result, gt: dict) -> dict:
    o = result.output
    rank = o.candidate_commit_ranking if o else []
    gtc = gt.get("introducing_commit")
    topk = {}
    if gtc:
        pos = rank.index(gtc) + 1 if gtc in rank else None
        topk = {f"top{k}": int(pos is not None and pos <= k) for k in (1, 3, 5)}
        topk["introducing_commit_correct"] = int(bool(o) and o.introducing_commit == gtc)
    expected = gt.get("expected_status", "SUPPORTED")
    kws = gt.get("root_cause_keywords", [])
    rc = (o.root_cause.lower() if o else "")
    kw_recall = round(sum(k.lower() in rc for k in kws) / len(kws), 3) if kws else None
    aff_pred = {a.lower() for a in (o.affected_components if o else [])}
    aff_gold = {a.lower() for a in gt.get("affected", [])}
    ap, ar, af = _prf(len(aff_pred & aff_gold), len(aff_pred - aff_gold), len(aff_gold - aff_pred))
    return {"valid_structured_output": o is not None and "failed validation" not in " ".join(result.reasons),
            "status": result.status, "status_correct": int(result.status == expected),
            "overclaim": int(expected == "UNCERTAIN" and result.status == "SUPPORTED"),
            "root_cause_keyword_recall": kw_recall, "grounding_score": result.grounding_score,
            "unsupported_claims": len(result.unsupported), "n_citations": len(o.evidence) if o else 0,
            "affected_precision": ap, "affected_recall": ar, **topk}


def impact_metrics(result, gt: dict) -> dict:
    o = result.output
    fix = gt.get("expected_fix", {})
    if o is None:
        return {"valid_structured_output": False, "status": result.status, "fix_correct": 0, "forbidden_edges_proposed": 0}
    rem = [list(e) for e in o.recommendation.remove_edges]
    add = [list(e) for e in o.recommendation.add_edges]
    ok = all(e in rem for e in fix.get("remove", [])) and all(e in add for e in fix.get("add", []))
    return {"valid_structured_output": True, "status": result.status, "fix_correct": int(ok),
            "forbidden_edges_proposed": sum(r["verdict"] == "FORBIDDEN" for r in result.rule_check),
            "n_impacts": len(o.impacts), "abstained": int(o.abstain)}


def mean_table(rows: list[dict], keys: list[str] | None = None) -> dict:
    keys = keys or sorted({k for r in rows for k, v in r.items() if isinstance(v, (int, float, bool)) and v is not None})
    out = {}
    for k in keys:
        vals = [float(r[k]) for r in rows if isinstance(r.get(k), (int, float, bool)) and r.get(k) is not None]
        out[k] = round(sum(vals) / len(vals), 3) if vals else None
    out["n"] = len(rows)
    return out

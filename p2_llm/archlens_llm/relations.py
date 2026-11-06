"""Sprint 4 D18–D20: relation-candidate validation and UNCERTAIN handling.

Rules applied to every relation from the VLM, geometry, or both (docs/uncertainty_policy.md):
  R1 endpoint ids must exist in the component list           -> rejected
  R2 self-loops                                               -> rejected
  R3 relation type outside vocabulary                         -> mapped to depends_on + flagged
  R4 duplicates (same source, target)                         -> merged (max confidence, union evidence)
  R5 both directions present with |conf diff| < 0.15          -> both 'uncertain' (direction ambiguous)
  R6 confidence below threshold                               -> 'uncertain'
  R7 no evidence string                                       -> 'uncertain'
  R8 an endpoint component abstained / is 'unknown'           -> 'uncertain'
Rejected relations are kept in the issues log, never silently dropped.
"""
from __future__ import annotations

from .schemas import RELATION_TYPES, ComponentLabel, RelationCandidate


def validate_relations(relations: list[dict | RelationCandidate], components: list[dict | ComponentLabel],
                       uncertain_below: float = 0.5) -> tuple[list[RelationCandidate], list[dict]]:
    comps = {(c.id if isinstance(c, ComponentLabel) else c["id"]):
             (c if isinstance(c, ComponentLabel) else None) for c in components}
    shaky = {cid for cid, c in comps.items() if c is not None and (c.abstain or c.type == "unknown")}
    issues: list[dict] = []
    merged: dict[tuple[str, str], RelationCandidate] = {}
    for r in relations:
        d = r.model_dump() if isinstance(r, RelationCandidate) else dict(r)
        s, t = d.get("source"), d.get("target")
        if s not in comps or t not in comps:
            issues.append({"rule": "R1", "edge": [s, t], "action": "rejected", "why": "unknown endpoint id"})
            continue
        if s == t:
            issues.append({"rule": "R2", "edge": [s, t], "action": "rejected", "why": "self-loop"})
            continue
        if d.get("type") not in RELATION_TYPES:
            issues.append({"rule": "R3", "edge": [s, t], "action": "mapped", "why": f"type {d.get('type')} -> depends_on"})
            d["type"] = "depends_on"
        d["confidence"] = min(1.0, max(0.0, float(d.get("confidence", 0.0))))
        d.setdefault("evidence", [])
        d.setdefault("status", "candidate")
        if d["status"] == "rejected":
            issues.append({"rule": "model", "edge": [s, t], "action": "rejected", "why": "rejected by model"})
            continue
        rc = RelationCandidate(**{k: d[k] for k in ("source", "target", "type", "confidence", "evidence", "status")})
        key = (s, t)
        if key in merged:
            old = merged[key]
            issues.append({"rule": "R4", "edge": [s, t], "action": "merged"})
            merged[key] = old.model_copy(update={
                "confidence": max(old.confidence, rc.confidence),
                "evidence": sorted(set(old.evidence) | set(rc.evidence)),
                "status": "candidate" if "candidate" in (old.status, rc.status) else "uncertain"})
        else:
            merged[key] = rc
    out = dict(merged)
    for (s, t), r in merged.items():
        rev = merged.get((t, s))
        if rev is not None and abs(rev.confidence - r.confidence) < 0.15 and s < t:
            for k in ((s, t), (t, s)):
                out[k] = out[k].model_copy(update={"status": "uncertain"})
            issues.append({"rule": "R5", "edge": [s, t], "action": "uncertain", "why": "direction ambiguous"})
    final = []
    for (s, t), r in out.items():
        why = []
        if r.confidence < uncertain_below:
            why.append("R6 low confidence")
        if not r.evidence:
            why.append("R7 no evidence")
        if s in shaky or t in shaky:
            why.append("R8 endpoint uncertain")
        if why and r.status != "uncertain":
            r = r.model_copy(update={"status": "uncertain"})
            issues.append({"rule": ",".join(w.split()[0] for w in why), "edge": [s, t], "action": "uncertain", "why": "; ".join(why)})
        final.append(r)
    return final, issues

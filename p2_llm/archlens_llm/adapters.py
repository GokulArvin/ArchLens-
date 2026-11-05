"""Adapters: teammates' current output formats -> the shapes P2 consumes.

Pure functions, no I/O. Each docstring names the source format it accepts (as found on the
teammates' branches) and the P2 contract it produces (see README "Contracts with teammates").

    P1 (CV)          detections, ArchComponent dicts, geometric relation candidates
    P3 (static)      G_C components, ruleset rules, conformance verdicts, G_C relationships
    P4 (backend)     GitEvidenceExtractor.build_evidence_package() output

Nothing here calls a model or changes P2 logic: it only renames fields, fills ids and
converts layouts, so `service.*`, `RCAAnalyzer` and `ImpactRecommender` can take the result.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

# P3's ComponentType values (backend/app/schemas/models.py on the P3 branch). Used to tell a
# type-based rule ("controller") from a name-based one ("order_controller") in from_p3_rules.
P3_COMPONENT_TYPES = frozenset({
    "component", "service", "database", "queue", "gateway", "frontend", "cache", "external",
    "external_system", "module", "interface", "controller", "repository", "model", "utility", "unknown",
})

# P2's relation_uncertain_below threshold is 0.5 (config/llm_config.json). See from_p1_relations.
UNDIRECTED_CONFIDENCE_CAP = 0.49

_COMMIT_FIELDS = ("hash", "message", "author", "date", "files", "diff")


# ----------------------------------------------------------------------------- helpers
def _bbox_list(bbox: Any) -> Optional[list[float]]:
    """[x1,y1,x2,y2] list/tuple, or {x1,y1,x2,y2} dict (P1/P3 BoundingBox) -> [x1,y1,x2,y2]."""
    if bbox is None:
        return None
    if isinstance(bbox, dict):
        return [float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"])]
    x1, y1, x2, y2 = bbox
    return [float(x1), float(y1), float(x2), float(y2)]


def _layer(type_value: str) -> str:
    """P3 type value -> P2 layer label: 'controller' -> 'Controller' (same rule as layer_of_from_p3)."""
    return type_value.capitalize()


def _rule_side(name: Optional[str], type_value: Optional[str]) -> str:
    """One side of a P3 rule -> a P2 pattern side.

    Explicit source_type/target_type wins; a value that is a P3 type becomes a layer label;
    anything else is treated as a component name and kept as is; nothing at all -> '*'.
    """
    if type_value:
        return _layer(str(type_value))
    if not name:
        return "*"
    return _layer(name) if name in P3_COMPONENT_TYPES else name


def _commit(c: dict) -> dict:
    """P4 commit dict (hash, short_hash, message, author, date, diff?) -> P2 Commit fields."""
    out = {k: c[k] for k in _COMMIT_FIELDS if c.get(k) is not None}
    out.setdefault("files", [])
    return out


# ------------------------------------------------------------------------------- P1 / P4 (CV)
def from_p1_detections(dets: Iterable[dict]) -> list[dict]:
    """Detections -> P2 detections.json: [{id, bbox:[x1,y1,x2,y2], class, confidence}].

    Accepts:
      * P1 MappedDetection.to_dict(): {bbox:[...], confidence, mapped_class, raw_coco_class, raw_coco_class_id}
      * P4 ComponentDetector.detect():  {bbox:[...], confidence, class_name}
      * bbox as a list or as a {x1,y1,x2,y2} dict.
    Ids are kept if present, otherwise generated in input order: d1, d2, ...
    """
    out = []
    for i, d in enumerate(dets, 1):
        out.append({
            "id": str(d.get("id") or f"d{i}"),
            "bbox": _bbox_list(d["bbox"]),
            "class": d.get("class") or d.get("mapped_class") or d.get("class_name") or "architecture_component",
            "confidence": float(d.get("confidence", 1.0)),
        })
    return out


def from_p1_components(comps: Iterable[dict]) -> list[dict]:
    """P1/P3 ArchComponent dicts -> P2 detections.json format.

    Source: {id, name, type, bbox:{x1,y1,x2,y2} | None, confidence, metadata}.
    The component id is kept (relations refer to it). `type` becomes `class`.
    Components without a bbox cannot be placed on the image and are skipped.
    """
    out = []
    for c in comps:
        box = _bbox_list(c.get("bbox"))
        if box is None:
            continue
        out.append({"id": str(c["id"]), "bbox": box, "class": c.get("type") or "architecture_component",
                    "confidence": float(c.get("confidence", 1.0))})
    return out


def from_p1_relations(rels: Iterable[dict], directed: bool = False) -> list[dict]:
    """Relation candidates -> P2 geometry_candidates.json: [{id, source, target, confidence}].

    Accepts:
      * P1 RelationCandidate.to_dict(): {source, target, confidence}  (pair is SORTED -> undirected)
      * P4 CVPipeline relationships:    {id, source, target, type, confidence, metadata}
    Ids are kept if present, otherwise generated: g1, g2, ...
    """
    out = []
    for i, r in enumerate(rels, 1):
        conf = float(r.get("confidence", 0.0))
        if not directed:
            # P1 stores each pair sorted (source < target), so the arrow's direction is unknown:
            # "a -> b" may really be "b -> a". Capping below P2's relation_uncertain_below (0.5)
            # makes P2 mark the relation "uncertain" unless the VLM confirms the direction from
            # the image, instead of trusting a direction that geometry never measured.
            conf = min(conf, UNDIRECTED_CONFIDENCE_CAP)
        out.append({"id": str(r.get("id") or f"g{i}"), "source": str(r["source"]),
                    "target": str(r["target"]), "confidence": conf})
    return out


# ---------------------------------------------------------------------------- P3 (static)
def from_p3_entities(components: Iterable[dict]) -> list[dict]:
    """P3 G_C components -> P2 code_entities.json: [{id, name, kind, path}].

    Source (DependencyGraphBuilder nodes): {id: dotted module, name: file stem, type, file,
    classes, inference_confidence, metadata}. `kind` = type; `path` = file, or the id if the
    component has no file (the example_GC_*.json files omit it).
    """
    return [{"id": str(c["id"]), "name": c.get("name") or str(c["id"]),
             "kind": c.get("type") or "unknown", "path": c.get("file") or str(c["id"])}
            for c in components]


def layer_of_from_p3(components: Iterable[dict]) -> dict[str, str]:
    """P3 G_C components -> P2 layer_of: {component name: Type.capitalize()}.

    Source: {id, name, type, ...}; e.g. {name: 'OrderController', type: 'controller'} ->
    {'OrderController': 'Controller'}. Components without a type are left out.
    """
    return {c.get("name") or str(c["id"]): _layer(c["type"]) for c in components if c.get("type")}


def from_p3_rules(rules: Iterable[dict] | dict) -> dict[str, list[str]]:
    """P3 rules -> P2 architecture_rule: {"allowed": ["S->T"], "forbidden": [...], "required": [...]}.

    Source: ArchitectureRule dicts {id, name, action: ALLOW|FORBID|REQUIRE, category, source,
    target, source_type?, target_type?, severity, description}, or a whole RuleSet dict
    ({..., rules: [...]}). Type-based sides become layer labels ('controller' -> 'Controller',
    matching layer_of_from_p3); name-based sides stay as names; a missing side becomes '*'.
    """
    if isinstance(rules, dict):
        rules = rules.get("rules", [])
    key = {"ALLOW": "allowed", "FORBID": "forbidden", "REQUIRE": "required"}
    out: dict[str, list[str]] = {"allowed": [], "forbidden": [], "required": []}
    for r in rules:
        bucket = key.get(str(r.get("action", "ALLOW")).upper())
        if bucket is None:
            continue
        pattern = f"{_rule_side(r.get('source'), r.get('source_type'))}->{_rule_side(r.get('target'), r.get('target_type'))}"
        if pattern not in out[bucket]:
            out[bucket].append(pattern)
    return out


def from_p3_verdict(verdict: dict, id_to_name: dict[str, str]) -> dict:
    """P3 ConformanceEngine verdict -> P2 violation: {type, source, target, verdict}.

    Source: {verdict, violation_type, source, target, severity, confidence, description, rule_id?}
    where source/target are component ids. id_to_name maps them to the display names P2 uses
    in edges and layer_of (ids missing from the map are kept as is).
    """
    return {"type": verdict.get("violation_type") or "unknown",
            "source": id_to_name.get(verdict["source"], verdict["source"]),
            "target": id_to_name.get(verdict["target"], verdict["target"]),
            "verdict": verdict.get("verdict", "VIOLATION")}


def edges_from_p3(relationships: Iterable[dict], id_to_name: dict[str, str]) -> list[list[str]]:
    """P3 G_C/G_I relationships {id, source, target, type, confidence} -> P2 edges [[source, target]] by name."""
    out: list[list[str]] = []
    for r in relationships:
        e = [id_to_name.get(r["source"], r["source"]), id_to_name.get(r["target"], r["target"])]
        if e not in out:
            out.append(e)
    return out


# --------------------------------------------------------------------------- P4 (backend)
def from_p4_evidence(pkg: dict, current_edges: Optional[Iterable[Iterable[str]]] = None,
                     intended_edges: Optional[Iterable[Iterable[str]]] = None,
                     layer_of: Optional[dict[str, str]] = None) -> dict:
    """P4 GitEvidenceExtractor.build_evidence_package() -> dict for EvidencePackage.model_validate.

    Source: {violation, architecture_rule, code: {file, target_symbol}, dependency_path,
    commit: {hash, short_hash, message, author, date, diff} | None, diff, recent_commits: [...]}.

      * candidate_commits = [commit] + recent_commits, de-duplicated by hash (order kept)
      * code.file kept; lines/snippet added when the package has them
      * architecture_rule: a P3 rule list / RuleSet is converted with from_p3_rules
      * violation: a P3-shaped verdict (violation_type) gets the `type` key P2 reads
      * current_edges / intended_edges / layer_of: P4 does not produce these yet, so the caller
        passes them (e.g. edges_from_p3 / layer_of_from_p3); P2 computes affected components
        from current_edges.
    """
    violation = dict(pkg.get("violation") or {})
    if "type" not in violation and violation.get("violation_type"):
        violation["type"] = violation["violation_type"]

    rule = pkg.get("architecture_rule") or {}
    if isinstance(rule, list) or "rules" in rule:
        rule = from_p3_rules(rule)

    code_in = pkg.get("code") or {}
    code = {"file": code_in.get("file", "")}
    for k in ("lines", "snippet", "target_symbol"):
        if code_in.get(k):
            code[k] = code_in[k]

    commit = _commit(pkg["commit"]) if pkg.get("commit") else None
    candidates, seen = [], set()
    for c in ([pkg["commit"]] if pkg.get("commit") else []) + list(pkg.get("recent_commits") or []):
        if c and c.get("hash") and c["hash"] not in seen:
            seen.add(c["hash"])
            candidates.append(_commit(c))

    src, tgt = violation.get("source", ""), violation.get("target", "")
    out = {
        "violation_id": pkg.get("violation_id") or violation.get("id") or f"{src}->{tgt}",
        "violation": violation,
        "architecture_rule": rule,
        "code": code,
        "dependency_path": list(pkg.get("dependency_path") or [src, tgt]),
        "commit": commit,
        "candidate_commits": candidates,
        "diff": pkg.get("diff") or "",
        "current_edges": [list(e) for e in (current_edges or pkg.get("current_edges") or [])],
        "intended_edges": [list(e) for e in (intended_edges or pkg.get("intended_edges") or [])],
        "layer_of": dict(layer_of or pkg.get("layer_of") or {}),
    }
    if pkg.get("affected_components"):
        out["affected_components"] = list(pkg["affected_components"])
    return out

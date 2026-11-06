"""The only functions P4's FastAPI layer needs to call.

  POST /analyze-diagram     -> analyze_diagram_semantics(...)
  (graph alignment step)    -> align_components(...)
  POST /analyze-violation   -> analyze_violation(...)   (RCA + impact + recommendation)
  dependency role (§6.3)    -> classify_dependency_role(...)

Every function returns plain JSON-serialisable dicts that include provenance.
"""
from __future__ import annotations

from .alignment import Aligner
from .config import load_config, make_gateway
from .impact import ImpactRecommender
from .rca import RCAAnalyzer
from .schemas import SCHEMA_VERSION, DependencyRole
from .vlm_extraction import VLMExtractor


def _gw(cfg, run_dir):
    return make_gateway(cfg, run_dir=run_dir)


def analyze_diagram_semantics(diagram_id: str, image_path: str, detections: list[dict],
                              geometry_candidates: list[dict] | None = None, run_ocr: bool = True,
                              cfg: dict | None = None, run_dir: str = "runs/service") -> dict:
    cfg = cfg or load_config()
    comps = detections
    if run_ocr and detections and "ocr_text" not in detections[0]:
        from .ocr import ocr_components
        comps = ocr_components(image_path, detections)
    th, ex = cfg["thresholds"], cfg["extraction"]
    r = VLMExtractor(_gw(cfg, run_dir), mode=ex["mode"], fewshot=ex["fewshot"],
                     relation_uncertain_below=th["relation_uncertain_below"],
                     component_abstain_below=th["component_abstain_below"]).extract(
        diagram_id, image_path, comps, geometry_candidates)
    return {"schema_version": SCHEMA_VERSION, "intended_graph": r.to_graph(), "relation_issues": r.relation_issues,
            "fallback": r.fallback, "model_errors": r.model_errors}


def align_components(diagram_nodes: list[dict], code_entities: list[dict], aliases: dict | None = None,
                     cfg: dict | None = None, run_dir: str = "runs/service") -> list[dict]:
    cfg = cfg or load_config()
    th = cfg["thresholds"]
    al = Aligner(_gw(cfg, run_dir), aliases=aliases, accept_at=th["alignment_accept_at"],
                 token_accept=th["alignment_token_accept"], token_margin=th["alignment_token_margin"])
    return [a.model_dump() for a in al.align(diagram_nodes, code_entities)]


def analyze_violation(evidence_package: dict, cfg: dict | None = None, run_dir: str = "runs/service") -> dict:
    cfg = cfg or load_config()
    gw = _gw(cfg, run_dir)
    th = cfg["thresholds"]
    rca = RCAAnalyzer(gw, variant=cfg["rca"]["variant"], uncertain_below=th["rca_uncertain_below"]).analyze(evidence_package)
    imp = ImpactRecommender(gw, abstain_below=th["impact_abstain_below"]).recommend(evidence_package)
    o = rca.output
    return {
        "schema_version": SCHEMA_VERSION,
        "violation_id": rca.violation_id,
        "violation": evidence_package["violation"],
        "root_cause": {"status": rca.status, "text": o.root_cause if o else None,
                       "introducing_commit": o.introducing_commit if o else None,
                       "candidate_commit_ranking": o.candidate_commit_ranking if o else [],
                       "explanation": o.violation_explanation if o else None,
                       "evidence": [c.model_dump() for c in o.evidence] if o else [],
                       "confidence": o.confidence if o else 0.0, "uncertain_reasons": rca.reasons,
                       "unsupported_claims": rca.unsupported, "grounding_score": rca.grounding_score},
        "impact": {"status": imp.status, "affected_components": imp.affected,
                   "impacts": [i.model_dump() for i in imp.output.impacts] if imp.output else []},
        "recommendation": {**(imp.output.recommendation.model_dump() if imp.output else {}),
                           "status": imp.status, "rule_check": imp.rule_check, "uncertain_reasons": imp.reasons,
                           "note": "Suggested correction, validated against the architecture rules; not guaranteed correct."},
        "provenance": {"rca": rca.provenance, "impact": imp.provenance},
    }


def classify_dependency_role(source: str, target: str, relation: str = "depends_on", context: dict | None = None,
                             cfg: dict | None = None, run_dir: str = "runs/service") -> dict:
    cfg = cfg or load_config()
    res = _gw(cfg, run_dir).structured("dependency_role", {"input_json": {"source": source, "target": target,
                                       "relation": relation, **(context or {})}}, DependencyRole, task="dependency_role")
    return {"ok": res.ok, "role": res.parsed.model_dump() if res.ok else None, "errors": res.errors,
            "prompt_version": res.prompt_version, "model": res.model}

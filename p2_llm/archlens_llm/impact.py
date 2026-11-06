"""Sprint 8: structured impact analysis + recommendation, validated against the architecture rules.

The affected set is COMPUTED (graph traversal, owned by P3; fallback here) — the LLM only explains
impact for those components and proposes a fix. The fix is then checked deterministically:
  * every impacted component is in the computed affected set
  * every evidence id exists
  * add_edges never create an edge E-RULE forbids, nor a new cycle
  * the offending edge is removed (or, for missing_dependency, added)
Failure -> repair prompt -> abstain (UNCERTAIN). No recommendation is presented as guaranteed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from .gateway import LLMGateway
from .grounding import EVIDENCE_GROUPS, check_ids, index_evidence
from .schemas import EvidencePackage, ImpactRecommendation


def compute_affected(current_edges: list[list[str]], source: str, target: str) -> list[dict]:
    """Fallback for P3's impact function: dependants of the source (upstream) + what the target reaches (downstream)."""
    g = nx.DiGraph([tuple(e) for e in current_edges])
    g.add_nodes_from([source, target])
    aff = {source: (0, "source")}
    for n in nx.ancestors(g, source):
        aff[n] = (nx.shortest_path_length(g, n, source), "upstream")
    for n in nx.descendants(g, target) | {target}:
        d = 1 if n == target else 1 + nx.shortest_path_length(g, target, n)
        if n not in aff or d < aff[n][0]:
            aff[n] = (d, "downstream")
    return [{"component": n, "distance": d, "direction": k} for n, (d, k) in sorted(aff.items(), key=lambda x: x[1][0])]


def _match(pattern_side: str, comp: str, layer_of: dict) -> bool:
    return pattern_side == comp or layer_of.get(comp) == pattern_side or pattern_side == "*"


def edge_verdict(s: str, t: str, rules: dict, layer_of: dict, intended: list[list[str]]) -> str:
    for p in rules.get("forbidden", []):
        a, b = [x.strip() for x in p.split("->")]
        if _match(a, s, layer_of) and _match(b, t, layer_of):
            return "FORBIDDEN"
    if [s, t] in intended:
        return "ALLOWED"
    for p in rules.get("allowed", []):
        a, b = [x.strip() for x in p.split("->")]
        if _match(a, s, layer_of) and _match(b, t, layer_of):
            return "ALLOWED"
    return "NOT_IN_INTENDED"


@dataclass
class ImpactResult:
    violation_id: str
    output: ImpactRecommendation | None
    status: str                        # VALIDATED | UNCERTAIN
    rule_check: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    affected: list[dict] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self):
        return {"violation_id": self.violation_id, "status": self.status,
                "output": self.output.model_dump() if self.output else None, "rule_check": self.rule_check,
                "reasons": self.reasons, "affected": self.affected, "provenance": self.provenance}


class ImpactRecommender:
    def __init__(self, gateway: LLMGateway, abstain_below: float = 0.4, max_repairs: int = 2):
        self.gw, self.thr, self.max_repairs = gateway, abstain_below, max_repairs

    def _checks(self, o: ImpactRecommendation, pkg: EvidencePackage, affected: list[dict], idx) -> tuple[list[str], list[dict]]:
        errs, report = [], []
        v = pkg.violation
        aff = {a["component"] for a in affected}
        for it in o.impacts:
            if it.component not in aff:
                errs.append(f"impact on '{it.component}' but it is not in AFFECTED")
            bad = check_ids(it.evidence_ids, idx)
            if bad:
                errs.append(f"unknown evidence ids {bad} for {it.component}")
        bad = check_ids(o.recommendation.evidence_ids, idx)
        if bad:
            errs.append(f"recommendation cites unknown evidence ids {bad}")
        if o.abstain:
            return errs, report
        known = idx.components
        g = nx.DiGraph([tuple(e) for e in pkg.current_edges])
        for e in o.recommendation.remove_edges:
            if g.has_edge(*e):
                g.remove_edge(*e)
        for s, t in o.recommendation.add_edges:
            if s not in known or t not in known:
                errs.append(f"add_edge {s}->{t} uses a component not in the evidence")
                continue
            verdict = edge_verdict(s, t, pkg.architecture_rule, pkg.layer_of, pkg.intended_edges)
            report.append({"edge": [s, t], "verdict": verdict})
            if verdict == "FORBIDDEN":
                errs.append(f"add_edge {s}->{t} is FORBIDDEN by E-RULE")
            g.add_edge(s, t)
        offending = [v["source"], v["target"]]
        if v["type"] == "missing_dependency":
            if offending not in o.recommendation.add_edges:
                errs.append(f"missing dependency: recommendation must add {offending}")
        elif offending not in o.recommendation.remove_edges:
            errs.append(f"recommendation must remove the offending edge {offending}")
        try:
            cyc = nx.find_cycle(g)
            if v["type"] == "circular_dependency" or any(tuple(e) in [tuple(x) for x in o.recommendation.add_edges] for e in cyc):
                errs.append(f"resulting graph still has a cycle: {cyc}")
        except nx.NetworkXNoCycle:
            pass
        return errs, report

    def recommend(self, pkg: EvidencePackage | dict) -> ImpactResult:
        pkg = pkg if isinstance(pkg, EvidencePackage) else EvidencePackage.model_validate(pkg)
        v = pkg.violation
        affected = pkg.affected_components or compute_affected(pkg.current_edges, v["source"], v["target"])
        idx = index_evidence(pkg, EVIDENCE_GROUPS["grounded_full"])
        idx.components |= {a["component"] for a in affected}
        data = {"violation": {k: v.get(k) for k in ("type", "source", "target")},
                "rules": pkg.architecture_rule, "layer_of": pkg.layer_of, "affected_components": affected,
                "allowed_intermediary": getattr(pkg, "allowed_intermediary", None),
                "evidence_items": [i for i in idx.items if i["kind"] != "diff"]}
        report_box: dict = {}

        def validator(o):
            errs, rep = self._checks(o, pkg, affected, idx)
            report_box["r"] = rep
            return errs

        res = self.gw.structured("impact_recommendation", {"input_json": data}, ImpactRecommendation,
                                 validator=validator, max_repairs=self.max_repairs, task="impact_recommendation",
                                 meta={"violation_id": pkg.violation_id})
        prov = {"prompt_version": res.prompt_version, "model": res.model, "attempts": res.attempts}
        if not res.ok:
            return ImpactResult(pkg.violation_id, None, "UNCERTAIN", report_box.get("r", []),
                                ["failed validation after repairs"] + res.errors[:5], affected, prov)
        o: ImpactRecommendation = res.parsed
        reasons = []
        if o.abstain:
            reasons.append(f"model abstained: {o.abstain_reason}")
        if o.confidence < self.thr:
            reasons.append(f"confidence {o.confidence} < {self.thr}")
        warn = [r for r in report_box.get("r", []) if r["verdict"] == "NOT_IN_INTENDED"]
        if warn:
            reasons.append(f"proposed edges not in intended architecture: {[w['edge'] for w in warn]}")
        return ImpactResult(pkg.violation_id, o, "UNCERTAIN" if reasons else "VALIDATED", report_box.get("r", []),
                            reasons, affected, prov)

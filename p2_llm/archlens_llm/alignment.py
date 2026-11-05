"""Sprint 6: semantic alignment helper — map diagram components to code entities.

Cascade (cheap and deterministic first; the LLM only sees what is left — D26):
  1 exact        case-insensitive name equality
  2 normalized   normalize_name equality (camelCase, -, _, abbreviations: 'Order Svc' == 'OrderService')
  3 alias        user/team alias table {"Kafka": "messaging/kafka/EventBusProducer"}
  4 token        Jaccard of alignment keys >= token_accept and margin to runner-up >= token_margin
  5 llm          shortlist (top-k by similarity) -> LLM must pick from shortlist or null, with evidence (D27)
  6 none

Abstention policy (D30, docs/uncertainty_policy.md):
  * LLM confidence < accept_at            -> UNCERTAIN (suggestion kept, not used as a match)
  * LLM picks an id outside the shortlist  -> repair, then UNCERTAIN
  * two diagram nodes claim one code entity and neither is exact/normalized -> both UNCERTAIN
  * user / external_system nodes with no candidate are NO_MATCH, not UNCERTAIN (they have no code)
"""
from __future__ import annotations

from collections import defaultdict

from .gateway import LLMGateway
from .labels import alignment_key, normalize_name
from .schemas import AlignmentLLMAnswer, AlignmentSuggestion

NO_CODE_TYPES = {"user", "external_system"}


def _sim(a: str, b: str) -> float:
    A, B = set(alignment_key(a).split()), set(alignment_key(b).split())
    return len(A & B) / len(A | B) if A | B else 0.0


def _entity_text(e: dict) -> str:
    return f"{e['name']} {e.get('path', '')}"


class Aligner:
    def __init__(self, gateway: LLMGateway | None = None, use_llm: bool = True, aliases: dict[str, str] | None = None,
                 accept_at: float = 0.6, token_accept: float = 0.8, token_margin: float = 0.15, shortlist_k: int = 5):
        self.gw, self.use_llm = gateway, use_llm and gateway is not None
        self.aliases = {normalize_name(k): v for k, v in (aliases or {}).items()}
        self.accept_at, self.token_accept, self.token_margin, self.k = accept_at, token_accept, token_margin, shortlist_k

    def _deterministic(self, node: dict, entities: list[dict]) -> AlignmentSuggestion | None:
        nid, name = node["id"], node["name"]
        for e in entities:
            if e["name"].lower() == name.lower():
                return AlignmentSuggestion(diagram_node_id=nid, code_entity_id=e["id"], method="exact", confidence=1.0,
                                           evidence=[f"name '{name}' == '{e['name']}'"], verdict="MATCHED")
        nn = normalize_name(name)
        hits = [e for e in entities if normalize_name(e["name"]) == nn]
        if len(hits) == 1:
            return AlignmentSuggestion(diagram_node_id=nid, code_entity_id=hits[0]["id"], method="normalized",
                                       confidence=0.95, evidence=[f"normalized '{nn}'"], verdict="MATCHED")
        if nn in self.aliases:
            return AlignmentSuggestion(diagram_node_id=nid, code_entity_id=self.aliases[nn], method="alias",
                                       confidence=0.95, evidence=[f"alias table: {name}"], verdict="MATCHED")
        scored = sorted(((max(_sim(name, e["name"]), _sim(name, _entity_text(e))), e) for e in entities),
                        key=lambda x: -x[0])
        if scored and scored[0][0] >= self.token_accept and \
                (len(scored) == 1 or scored[0][0] - scored[1][0] >= self.token_margin):
            s, e = scored[0]
            return AlignmentSuggestion(diagram_node_id=nid, code_entity_id=e["id"], method="token", confidence=round(min(0.9, s), 2),
                                       evidence=[f"token overlap {s:.2f} with '{e['name']}'"], verdict="MATCHED")
        return None

    def _llm(self, node: dict, entities: list[dict]) -> AlignmentSuggestion:
        scored = sorted(entities, key=lambda e: -max(_sim(node["name"], e["name"]), _sim(node["name"], _entity_text(e))))
        shortlist = scored[: self.k]
        ids = {e["id"] for e in shortlist}

        def check(a: AlignmentLLMAnswer) -> list[str]:
            errs = []
            if a.diagram_node_id != node["id"]:
                errs.append(f"diagram_node_id must be '{node['id']}'")
            if a.code_entity_id is not None and a.code_entity_id not in ids:
                errs.append(f"code_entity_id '{a.code_entity_id}' is not one of the candidate ids")
            if a.code_entity_id is not None and not a.evidence:
                errs.append("a match needs at least one evidence string")
            return errs

        res = self.gw.structured("semantic_alignment", {"input_json": {"diagram_node": node, "candidates": shortlist}},
                                 AlignmentLLMAnswer, validator=check, task="semantic_alignment",
                                 meta={"diagram_node": node["id"]})
        if not res.ok:
            return AlignmentSuggestion(diagram_node_id=node["id"], code_entity_id=None, method="llm", confidence=0.0,
                                       evidence=[f"llm abstained: {e}" for e in res.errors[:2]], verdict="UNCERTAIN")
        a: AlignmentLLMAnswer = res.parsed
        if a.code_entity_id is None:
            verdict = "NO_MATCH" if node.get("type") in NO_CODE_TYPES else "UNCERTAIN"
            return AlignmentSuggestion(diagram_node_id=node["id"], code_entity_id=None, method="llm",
                                       confidence=a.confidence, evidence=a.evidence or [a.reason], verdict=verdict)
        verdict = "MATCHED" if a.confidence >= self.accept_at else "UNCERTAIN"
        return AlignmentSuggestion(diagram_node_id=node["id"], code_entity_id=a.code_entity_id, method="llm",
                                   confidence=a.confidence, evidence=a.evidence, verdict=verdict)

    def align(self, nodes: list[dict], entities: list[dict]) -> list[AlignmentSuggestion]:
        out = []
        for n in nodes:
            s = self._deterministic(n, entities)
            if s is None:
                if self.use_llm:
                    s = self._llm(n, entities)
                else:
                    verdict = "NO_MATCH" if n.get("type") in NO_CODE_TYPES else "UNCERTAIN"
                    s = AlignmentSuggestion(diagram_node_id=n["id"], code_entity_id=None, method="none",
                                            confidence=0.0, evidence=["no deterministic match"], verdict=verdict)
            out.append(s)
        # conflict rule: one code entity claimed by several nodes
        claims = defaultdict(list)
        for s in out:
            if s.verdict == "MATCHED" and s.code_entity_id:
                claims[s.code_entity_id].append(s)
        for eid, ss in claims.items():
            if len(ss) > 1:
                strong = [s for s in ss if s.method in ("exact", "normalized", "alias")]
                keep = strong[0] if len(strong) == 1 else None
                for i, s in enumerate(out):
                    if s in ss and s is not keep:
                        out[i] = s.model_copy(update={"verdict": "UNCERTAIN",
                                                      "evidence": s.evidence + [f"conflict: {eid} also claimed by another node"]})
        return out


def score_alignment(pred: list[AlignmentSuggestion], gold: dict[str, str | None]) -> dict:
    """Accuracy-style metrics. A MATCHED prediction is correct iff it equals gold; gold None + no match is correct."""
    tp = fp = fn = tn = unc = 0
    rows = []
    for s in pred:
        g = gold.get(s.diagram_node_id)
        matched = s.code_entity_id if s.verdict == "MATCHED" else None
        if s.verdict == "UNCERTAIN":
            unc += 1
        if matched is not None and matched == g:
            tp += 1; status = "correct"
        elif matched is not None:
            fp += 1; status = "wrong_match"
            if g is not None:
                fn += 1
        elif g is not None:
            fn += 1; status = "missed" if s.verdict != "UNCERTAIN" else "abstained"
        else:
            tn += 1; status = "correct_no_match"
        rows.append({"node": s.diagram_node_id, "pred": matched, "gold": g, "method": s.method, "verdict": s.verdict, "status": status})
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
            "wrong_matches": fp, "uncertain": unc, "n": len(pred), "rows": rows}

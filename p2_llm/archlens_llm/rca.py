"""Sprint 7: evidence-grounded root-cause analysis.

analyze(package) ->
  1. index the evidence the chosen variant is allowed to see (ablations)
  2. call the LLM with rca_grounded (or rca_llm_only for the baseline)
  3. hard checks -> repair: cited evidence IDs exist, introducing commit is a supplied commit,
     affected components exist in the evidence
  4. soft checks -> flagged: file names / hashes in free text that are not in the evidence
  5. system status = SUPPORTED only if the model says so, confidence >= threshold, at least one
     citation, and no unsupported claims remain. Otherwise UNCERTAIN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .gateway import LLMGateway
from .grounding import (EVIDENCE_GROUPS, EvidenceIndex, HallucinationLog, check_components, check_ids,
                        index_evidence, text_mentions)
from .schemas import EvidencePackage, RCAOutput


@dataclass
class RCAResult:
    violation_id: str
    variant: str
    output: RCAOutput | None
    status: str                      # SUPPORTED | UNCERTAIN  (system decision)
    model_status: str | None         # what the model claimed
    unsupported: list[dict] = field(default_factory=list)
    grounding_score: float = 0.0     # supported assertions / all checkable assertions
    reasons: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"violation_id": self.violation_id, "variant": self.variant, "status": self.status,
                "model_status": self.model_status, "output": self.output.model_dump() if self.output else None,
                "unsupported": self.unsupported, "grounding_score": self.grounding_score, "reasons": self.reasons,
                "evidence_ids": self.evidence_ids, "provenance": self.provenance}


def _hard_issues(o: RCAOutput, idx: EvidenceIndex, variant: str) -> list[dict]:
    issues = [{"type": "unknown_evidence_id", "value": i} for i in check_ids([c.evidence_id for c in o.evidence], idx)]
    if o.introducing_commit and o.introducing_commit not in idx.commits:
        issues.append({"type": "unknown_introducing_commit", "value": o.introducing_commit})
    issues += [{"type": "unknown_commit_in_ranking", "value": c} for c in o.candidate_commit_ranking if c not in idx.commits]
    if variant != "llm_only":
        issues += [{"type": "unknown_component", "value": c} for c in check_components(o.affected_components, idx)]
    return issues


def _soft_issues(o: RCAOutput, idx: EvidenceIndex) -> list[dict]:
    text = " ".join([o.violation_explanation, o.root_cause, o.recommendation] + [c.claim for c in o.evidence])
    return text_mentions(text, idx)


class RCAAnalyzer:
    def __init__(self, gateway: LLMGateway, variant: str = "grounded_full", uncertain_below: float = 0.45,
                 max_repairs: int = 2, hallucination_log: str | Path | None = None):
        if variant not in EVIDENCE_GROUPS:
            raise ValueError(f"variant must be one of {list(EVIDENCE_GROUPS)}")
        self.gw, self.variant, self.thr, self.max_repairs = gateway, variant, uncertain_below, max_repairs
        self.hlog = HallucinationLog(hallucination_log or Path(gateway.run_dir) / "hallucinations.jsonl")

    def build_input(self, pkg: EvidencePackage) -> tuple[dict, EvidenceIndex]:
        idx = index_evidence(pkg, EVIDENCE_GROUPS[self.variant])
        v = {k: pkg.violation.get(k) for k in ("type", "source", "target", "verdict")}
        if self.variant == "llm_only":
            return {"violation": v}, idx
        data = {"violation": v, "evidence_items": idx.items}
        if "path" in EVIDENCE_GROUPS[self.variant]:
            data["dependency_path"] = pkg.dependency_path
        if "impact" in EVIDENCE_GROUPS[self.variant]:
            data["affected_components"] = pkg.affected_components
        return data, idx

    def analyze(self, pkg: EvidencePackage | dict) -> RCAResult:
        pkg = pkg if isinstance(pkg, EvidencePackage) else EvidencePackage.model_validate(pkg)
        data, idx = self.build_input(pkg)
        prompt = "rca_llm_only" if self.variant == "llm_only" else "rca_grounded"
        res = self.gw.structured(prompt, {"input_json": data}, RCAOutput,
                                 validator=lambda o: [f"{i['type']}: {i['value']}" for i in _hard_issues(o, idx, self.variant)],
                                 max_repairs=self.max_repairs, task="rca",
                                 meta={"violation_id": pkg.violation_id, "variant": self.variant})
        prov = {"prompt": prompt, "prompt_version": res.prompt_version, "model": res.model, "attempts": res.attempts,
                "tokens": {"input": res.input_tokens, "output": res.output_tokens}}
        if not res.ok:
            # keep the last parse attempt for analysis if it was schema-valid
            last = None
            from .jsonutil import extract_json
            for raw in reversed(res.raw_outputs):
                obj, _ = extract_json(raw)
                try:
                    last = RCAOutput.model_validate(obj)
                    break
                except Exception:
                    continue
            unsupported = (_hard_issues(last, idx, self.variant) + _soft_issues(last, idx)) if last else []
            self.hlog.write(pkg.violation_id, "rca", self.variant, res.model, unsupported)
            return RCAResult(pkg.violation_id, self.variant, last, "UNCERTAIN",
                             last.root_cause_status if last else None, unsupported, 0.0,
                             ["model output failed validation after repairs"] + res.errors[:5],
                             sorted(idx.ids), prov)
        o: RCAOutput = res.parsed
        unsupported = _soft_issues(o, idx)
        self.hlog.write(pkg.violation_id, "rca", self.variant, res.model, unsupported)
        n_checkable = len(o.evidence) + len(o.affected_components) + (1 if o.introducing_commit else 0) + len(unsupported)
        score = round(1 - len(unsupported) / n_checkable, 3) if n_checkable else 0.0
        if not o.evidence:
            score = 0.0
        reasons = []
        if o.root_cause_status == "UNCERTAIN":
            reasons.append("model reported UNCERTAIN")
        if o.confidence < self.thr:
            reasons.append(f"confidence {o.confidence} < {self.thr}")
        if not o.evidence:
            reasons.append("no evidence cited")
        if unsupported:
            reasons.append(f"{len(unsupported)} unsupported mention(s)")
        status = "UNCERTAIN" if reasons else "SUPPORTED"
        return RCAResult(pkg.violation_id, self.variant, o, status, o.root_cause_status, unsupported, score,
                         reasons, sorted(idx.ids), prov)

"""Sprint 5: VLM extraction module (component name/type + relation candidates).

Modes (the Sprint-5 shared comparison):
  cv_only          deterministic baseline: OCR name + label-dictionary type + geometry relations (no model)
  vlm_only         image only; the VLM proposes components and relations itself
  cv_vlm           detector boxes (+OCR) given; VLM labels every box and reads arrows
  cv_vlm_geometry  as cv_vlm plus geometric relation candidates to confirm/reject

Guarantees on the output (D22, D24):
  * every relation endpoint refers to an existing component id (else repair -> reject)
  * in cv_* modes every detected id is labelled exactly once and no ids are invented
  * low-confidence components abstain; uncertain relations carry status 'uncertain'
  * if the model fails after repairs, we fall back to cv_only and mark provenance 'fallback'
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .gateway import LLMGateway
from .labels import infer_type
from .relations import validate_relations
from .schemas import COMPONENT_TYPES, RELATION_TYPES, ComponentLabel, DiagramExtraction, RelationCandidate

FEWSHOT_PATH = Path(__file__).parent / "prompts" / "fewshot_diagram_conventions.json"
MODES = ("cv_only", "vlm_only", "cv_vlm", "cv_vlm_geometry")


@dataclass
class ExtractionResult:
    diagram_id: str
    mode: str
    extraction: DiagramExtraction
    relation_issues: list[dict] = field(default_factory=list)
    model_errors: list[str] = field(default_factory=list)
    fallback: bool = False
    provenance: dict = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)

    def to_graph(self) -> dict:
        """Design §4.9 intended-graph JSON, with provenance on every node and edge."""
        src = "fallback:cv_only" if self.fallback else self.mode
        return {
            "diagram_id": self.diagram_id,
            "components": [{**c.model_dump(exclude={"abstain"}), "abstained": c.abstain, "provenance": src}
                           for c in self.extraction.components],
            "relationships": [{**r.model_dump(), "provenance": src}
                              for r in self.extraction.relationships],
            "meta": self.provenance,
        }


def _fewshot_block() -> str:
    ex = json.loads(FEWSHOT_PATH.read_text())["examples"]
    lines = ["EXAMPLES OF DIAGRAM CONVENTIONS (how to interpret, not part of this diagram):"]
    lines += [f"- {e['convention']} => {json.dumps(e['output'])}" for e in ex]
    return "\n".join(lines)


def cv_only_baseline(components: list[dict], geometry: list[dict] | None, uncertain_below: float = 0.5) -> DiagramExtraction:
    comps = []
    for c in components:
        text = (c.get("ocr_text") or "").strip()
        t, conf, alias = infer_type(text) if text else ("unknown", 0.2, "")
        comps.append(ComponentLabel(id=c["id"], name=text, type=t, confidence=conf if text else 0.2,
                                    evidence=[f"ocr:{text}"] + ([f"alias:{alias}"] if alias else []),
                                    bbox=c.get("bbox"), abstain=not text))
    rels = [RelationCandidate(source=g["source"], target=g["target"], confidence=float(g.get("confidence", 0.5)),
                              evidence=[f"geometry:{g.get('id', '?')}"]) for g in (geometry or [])]
    rels, _ = validate_relations(rels, comps, uncertain_below)
    return DiagramExtraction(components=comps, relationships=rels, notes="cv_only baseline")


class VLMExtractor:
    def __init__(self, gateway: LLMGateway | None, mode: str = "cv_vlm_geometry", fewshot: bool = True,
                 relation_uncertain_below: float = 0.5, component_abstain_below: float = 0.35, max_repairs: int = 2):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if mode != "cv_only" and gateway is None:
            raise ValueError("a gateway is required for VLM modes")
        self.gw, self.mode, self.fewshot = gateway, mode, fewshot
        self.rel_thr, self.comp_thr, self.max_repairs = relation_uncertain_below, component_abstain_below, max_repairs

    def _input(self, components, geometry):
        if self.mode == "vlm_only":
            return {"note": "no detector output; read the image"}
        payload = {"components": [{"id": c["id"], "bbox": c.get("bbox"), "detector_class": c.get("class"),
                                   "detector_confidence": c.get("confidence"), "ocr_text": c.get("ocr_text", ""),
                                   "ocr_confidence": c.get("ocr_conf")} for c in components]}
        if self.mode == "cv_vlm_geometry":
            payload["geometry_candidates"] = geometry or []
        return payload

    def _validator(self, components):
        det_ids = [c["id"] for c in components]

        def check(x: DiagramExtraction) -> list[str]:
            errs = []
            ids = [c.id for c in x.components]
            if len(ids) != len(set(ids)):
                errs.append("duplicate component ids in output")
            if self.mode != "vlm_only":
                missing = sorted(set(det_ids) - set(ids))
                extra = sorted(set(ids) - set(det_ids))
                if missing:
                    errs.append(f"these detected components were not labelled: {missing}")
                if extra:
                    errs.append(f"these ids do not exist in the input, do not invent components: {extra}")
            idset = set(ids)
            for r in x.relationships:
                if r.source not in idset or r.target not in idset:
                    errs.append(f"relationship {r.source}->{r.target} refers to a component id that does not exist")
            return errs
        return check

    def extract(self, diagram_id: str, image_path: str | None, components: list[dict] | None = None,
                geometry: list[dict] | None = None) -> ExtractionResult:
        components = components or []
        if self.mode == "cv_only":
            ex = cv_only_baseline(components, geometry, self.rel_thr)
            return ExtractionResult(diagram_id, self.mode, ex, provenance={"mode": "cv_only", "model": None})
        variables = {"mode": self.mode, "component_types": ", ".join(COMPONENT_TYPES),
                     "relation_types": ", ".join(RELATION_TYPES),
                     "fewshot_block": _fewshot_block() if self.fewshot else "",
                     "input_json": self._input(components, geometry)}
        res = self.gw.structured("vlm_extraction", variables, DiagramExtraction,
                                 validator=self._validator(components), images=[image_path] if image_path else [],
                                 max_repairs=self.max_repairs, task="diagram_semantics",
                                 meta={"diagram_id": diagram_id, "mode": self.mode, "fewshot": self.fewshot})
        prov = {"mode": self.mode, "fewshot": self.fewshot, "prompt": res.prompt_name,
                "prompt_version": res.prompt_version, "model": res.model, "attempts": res.attempts}
        tokens = {"input": res.input_tokens, "output": res.output_tokens}
        if not res.ok:
            ex = cv_only_baseline(components, geometry, self.rel_thr)
            return ExtractionResult(diagram_id, self.mode, ex, model_errors=res.errors, fallback=True,
                                    provenance=prov, tokens=tokens)
        ex: DiagramExtraction = res.parsed
        comps = [c.model_copy(update={"abstain": True}) if (c.confidence < self.comp_thr and not c.abstain) else c
                 for c in ex.components]
        rels, issues = validate_relations(ex.relationships, comps, self.rel_thr)
        ex = ex.model_copy(update={"components": comps, "relationships": rels})
        return ExtractionResult(diagram_id, self.mode, ex, relation_issues=issues, provenance=prov, tokens=tokens)

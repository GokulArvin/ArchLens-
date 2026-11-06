"""Deterministic offline provider.

Why it exists: lets the whole P2 pipeline (prompts -> parsing -> validation -> repair ->
abstention -> grounding checks -> evaluation) run and be unit-tested with no API key.

What it is NOT: a language model. It reads the INPUT_JSON block of the prompt and applies
transparent heuristics. Numbers produced with it are pipeline smoke tests, NEVER research
results. Real experiments use provider.kind = gemini | openai_compatible.

Fault injection (for tests): faults=["malformed_once", "hallucinate_once", "always_invalid",
"network_once", "low_confidence"].
"""
from __future__ import annotations

import json
import re

from ..labels import alignment_key, infer_type, normalize_name
from .base import LLMRequest, LLMResponse, ProviderError

_TASK = re.compile(r"^TASK:\s*(\S+)", re.M)
_MODE = re.compile(r"^MODE:\s*(\S+)", re.M)
_KEYWORDS = {"return", "import", "private", "public", "final", "static", "class", "throw", "throws", "while",
             "double", "float", "string", "false", "true", "const", "async", "await", "elif", "except", "lambda",
             "yield", "super", "this", "void", "boolean", "package", "extends", "implements", "interface"}
_INPUT = re.compile(r"INPUT_JSON:\s*<<<\s*(.*?)\s*>>>", re.S)


class MockProvider:
    name = "mock"
    model = "heuristic-v1"
    supports_images = True

    def __init__(self, faults: list[str] | None = None):
        self.faults = list(faults or [])
        self.calls = 0

    def _fault(self, f: str) -> bool:
        if f in self.faults:
            if f.endswith("_once"):
                self.faults.remove(f)
            return True
        return False

    def generate(self, req: LLMRequest, timeout_s: float) -> LLMResponse:
        self.calls += 1
        if self._fault("network_once"):
            raise ProviderError("simulated 503", retryable=True)
        prompt = req.prompt
        is_repair = prompt.startswith("Your previous answer")
        task_m = _TASK.search(prompt)
        task = task_m.group(1) if task_m else "unknown"
        inp_m = _INPUT.search(prompt)
        data = json.loads(inp_m.group(1)) if inp_m else {}
        mode_m = _MODE.search(prompt)
        mode = mode_m.group(1) if mode_m else ""

        if self._fault("always_invalid"):
            text = "I think the answer is probably the database."
        elif not is_repair and self._fault("malformed_once"):
            text = "```json\n{\"components\": [ {\"id\": \"c1\",, }\n```"
        else:
            out = getattr(self, f"_t_{task}", self._t_unknown)(data, mode)
            if not is_repair and self._fault("hallucinate_once"):
                out = self._hallucinate(task, out)
            text = json.dumps(out)
        tok_in = len(prompt) // 4
        return LLMResponse(text=text, provider=self.name, model=self.model,
                           input_tokens=tok_in, output_tokens=len(text) // 4)

    # ------------------------------------------------------------------ tasks
    def _t_unknown(self, data, mode):
        return {"error": "unknown task"}

    def _t_vlm_extraction(self, data, mode):
        comps, rels = [], []
        for c in data.get("components", []):
            text = (c.get("ocr_text") or "").strip()
            if not text:
                comps.append({"id": c["id"], "name": "", "type": "unknown", "confidence": 0.2,
                              "evidence": ["no readable text"], "bbox": c.get("bbox"), "abstain": True})
                continue
            t, conf, alias = infer_type(text)
            hint = c.get("detector_class")
            if t == "component" and hint in ("database", "queue", "user", "external_system", "service"):
                t, conf = hint, 0.6
            ev = [f"ocr:{text}"] + ([f"alias:{alias}"] if alias else []) + ([f"detector:{hint}"] if hint else [])
            comps.append({"id": c["id"], "name": text, "type": t, "confidence": round(conf, 2),
                          "evidence": ev, "bbox": c.get("bbox"), "abstain": False})
        for g in data.get("geometry_candidates", []):
            conf = float(g.get("confidence", 0.5))
            rels.append({"source": g["source"], "target": g["target"], "type": "depends_on",
                         "confidence": round(conf, 2),
                         "evidence": [f"geometry candidate {g.get('id', '?')} confirmed"],
                         "status": "candidate" if conf >= 0.5 else "uncertain"})
        return {"components": comps, "relationships": rels,
                "notes": "mock: names from OCR, types from label dictionary, relations only from geometry"}

    def _t_dependency_role(self, data, mode):
        def role(n):
            n = n.lower()
            for k, r in [("controller", "Controller"), ("service", "Service"), ("repository", "Repository"),
                         ("dao", "Repository"), ("client", "Infrastructure"), ("view", "UI"), ("ui", "UI"),
                         ("gateway", "Gateway"), ("producer", "Messaging"), ("consumer", "Messaging")]:
                if k in n:
                    return r
            return "Domain"
        s, t = role(data.get("source", "")), role(data.get("target", ""))
        return {"source_role": s, "target_role": t,
                "architectural_meaning": f"{s} -> {t} dependency", "confidence": 0.6}

    def _t_semantic_alignment(self, data, mode):
        node = data["diagram_node"]
        key = set(alignment_key(node["name"]).split())
        best, best_s, second = None, 0.0, 0.0
        for c in data.get("candidates", []):
            ck = set(alignment_key(c["name"] + " " + c.get("path", "")).split())
            s = len(key & ck) / max(1, len(key | ck))
            if s > best_s:
                best, best_s, second = c, s, best_s
            elif s > second:
                second = s
        if best is None or best_s < 0.2 or best_s - second < 0.1:
            return {"diagram_node_id": node["id"], "code_entity_id": None, "confidence": 0.3,
                    "evidence": ["no candidate clearly better than the others"], "reason": "ambiguous"}
        conf = 0.2 if self._fault("low_confidence") else min(0.9, 0.5 + best_s)
        return {"diagram_node_id": node["id"], "code_entity_id": best["id"], "confidence": round(conf, 2),
                "evidence": [f"token overlap {best_s:.2f} between '{node['name']}' and '{best['name']}'"],
                "reason": "lexical overlap"}

    def _t_rca_grounded(self, data, mode):
        items = {e["id"]: e for e in data.get("evidence_items", [])}
        v = data.get("violation", {})
        src, tgt = v.get("source", "?"), v.get("target", "?")
        commits = [e for e in data.get("evidence_items", []) if e["kind"] == "commit"]
        diffs = {e["commit"]: e for e in data.get("evidence_items", []) if e["kind"] == "diff"}
        code = items.get("E-CODE", {})
        snippet_toks = set(re.findall(r"[A-Za-z_]{5,}", code.get("snippet", ""))) - _KEYWORDS

        def touches(c):  # blame-like heuristic: same file AND an added/removed line shares identifiers with the snippet
            if c["commit"] not in diffs or code.get("file") not in c.get("files", []):
                return False
            changed = " ".join(l for l in diffs[c["commit"]]["content"].splitlines() if l[:1] in "+-")
            return bool(snippet_toks & set(re.findall(r"[A-Za-z_]{5,}", changed)))
        touching = [c for c in commits if touches(c)]
        cites = []
        if "E-RULE" in items:
            cites.append({"evidence_id": "E-RULE", "claim": f"{src} -> {tgt} is not allowed by the rule set"})
        if "E-PATH" in items:
            cites.append({"evidence_id": "E-PATH", "claim": "dependency path " + " -> ".join(data.get("dependency_path", []))})
        if "E-CODE" in items:
            cites.append({"evidence_id": "E-CODE", "claim": f"code in {items['E-CODE'].get('file', '?')} references {tgt}"})
        affected = sorted({src, tgt} | {a["component"] for a in data.get("affected_components", [])})
        if touching:
            c = touching[0]
            cites.append({"evidence_id": c["id"], "claim": f"commit {c['commit']} message: {c['content'][:80]}"})
            cites.append({"evidence_id": diffs[c['commit']]["id"], "claim": f"diff adds a reference to {tgt}"})
            rank = [c["commit"] for c in touching] + [c["commit"] for c in commits if c not in touching]
            return {"violation_explanation": f"{src} depends directly on {tgt}, which the architecture forbids.",
                    "root_cause": f"Commit {c['commit']} ('{c['content'][:60]}') added a direct reference from {src} to {tgt}.",
                    "evidence": cites, "affected_components": affected,
                    "recommendation": f"Remove the direct {src} -> {tgt} dependency and route it through the allowed layer.",
                    "introducing_commit": c["commit"], "candidate_commit_ranking": rank,
                    "root_cause_status": "SUPPORTED", "confidence": 0.75}
        return {"violation_explanation": f"{src} depends directly on {tgt}, which the architecture forbids.",
                "root_cause": "Undetermined: no supplied commit/diff touches the offending dependency.",
                "evidence": cites, "affected_components": affected,
                "recommendation": f"Remove the direct {src} -> {tgt} dependency and route it through the allowed layer.",
                "introducing_commit": None, "candidate_commit_ranking": [c["commit"] for c in commits],
                "root_cause_status": "UNCERTAIN", "confidence": 0.35}

    def _t_rca_llm_only(self, data, mode):
        v = data.get("violation", {})
        src, tgt = v.get("source", "?"), v.get("target", "?")
        return {"violation_explanation": f"{src} depends on {tgt}.",
                "root_cause": "Likely a shortcut taken during a refactoring to avoid going through the service layer.",
                "evidence": [], "affected_components": [src, tgt],
                "recommendation": f"Route {src} through the service layer instead of calling {tgt} directly.",
                "introducing_commit": None, "candidate_commit_ranking": [],
                "root_cause_status": "SUPPORTED", "confidence": 0.6}

    def _t_impact_recommendation(self, data, mode):
        v = data.get("violation", {})
        src, tgt, vtype = v.get("source"), v.get("target"), v.get("type")
        affected = data.get("affected_components", [])
        impacts = [{"component": a["component"],
                    "impact": f"{'directly' if a.get('distance', 1) <= 1 else 'transitively'} coupled to {tgt} via the violating edge",
                    "evidence_ids": ["E-PATH"] if a.get("distance", 1) <= 1 else ["E-GRAPH-C"]}
                   for a in affected[:8]]
        via = data.get("allowed_intermediary")
        if vtype == "missing_dependency":
            rec = {"summary": f"Implement the required dependency {src} -> {tgt}.",
                   "steps": [f"Add a call from {src} to the public interface of {tgt}.", "Add a test covering the interaction."],
                   "remove_edges": [], "add_edges": [[src, tgt]],
                   "rationale": "The intended architecture requires this relationship.", "evidence_ids": ["E-RULE", "E-GRAPH-I"]}
        else:
            add = [[src, via]] if via else []
            rec = {"summary": f"Remove the direct dependency {src} -> {tgt}" + (f" and go through {via}." if via else "."),
                   "steps": [f"Delete the import/usage of {tgt} in {src}.",
                             (f"Call {via} from {src} for the needed operation." if via else "Expose the needed operation through an allowed interface."),
                             "Add a conformance test so the edge cannot reappear."],
                   "remove_edges": [[src, tgt]], "add_edges": add,
                   "rationale": "Restores the intended layering without introducing forbidden edges.",
                   "evidence_ids": ["E-RULE", "E-CODE"]}
        return {"impacts": impacts, "recommendation": rec, "confidence": 0.7, "abstain": False, "abstain_reason": ""}

    # ------------------------------------------------------------ faults
    def _hallucinate(self, task, out):
        if task == "vlm_extraction" and out.get("relationships") is not None:
            out["relationships"].append({"source": "c99", "target": "c1", "type": "depends_on",
                                         "confidence": 0.9, "evidence": ["invented"], "status": "candidate"})
        if task.startswith("rca"):
            out["evidence"].append({"evidence_id": "E-COMMIT-deadbeef", "claim": "commit deadbeef broke it"})
            out["affected_components"].append("BillingService")
            out["introducing_commit"] = "deadbeef"
            out["root_cause"] += " See LegacyAdapter.java."
        if task == "impact_recommendation":
            out["impacts"].append({"component": "GhostService", "impact": "?", "evidence_ids": ["E-NOPE"]})
        if task == "semantic_alignment":
            out["code_entity_id"] = "not-a-candidate"
        return out

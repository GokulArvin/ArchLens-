# ArchLens: P2 LLM/VLM layer

This is the semantic reasoning layer of ArchLens: **diagram semantics → diagram-to-code alignment → evidence-grounded root cause → impact + recommendation.** The LLM explains and recommends. It never decides a structural fact (Design §14).

```
P1 detections + OCR ──► VLMExtractor ──► intended graph G_I (names, types, relations, confidence, provenance)
P3 code entities ─────► Aligner ───────► diagram node ↔ code module (MATCHED / UNCERTAIN / NO_MATCH)
P4 evidence package ──► RCAAnalyzer ───► root cause + cited evidence + introducing commit (SUPPORTED / UNCERTAIN)
                    └─► ImpactRecommender ► impacts on computed affected set + rule-checked fix (VALIDATED / UNCERTAIN)
```

## Quick start
```bash
pip install -r requirements.txt          # pydantic, networkx, opencv-python, pillow, pytesseract, pytest
# Tesseract binary: apt install tesseract-ocr  |  brew install tesseract  |  Windows installer (UB Mannheim)
python scripts/make_fixtures.py          # synthetic V1–V6 fixtures (already committed)
pytest -q                                # 68 tests, offline
python -m archlens_llm.cli demo S02_layered      # one violation end to end
python -m archlens_llm.cli experiment            # all P2 comparisons on prompt_dev
```

## Using a real model (do this first)
1. Copy `config/llm_config.json` to `config/gemini.json` and set `"provider": {"kind": "gemini", "model": "<current model id>", "api_key_env": "GEMINI_API_KEY"}`. For a local model use the `ollama` example instead.
2. `export GEMINI_API_KEY=...`
3. `python -m archlens_llm.cli --config config/gemini.json smoke`. This is the Sprint 1 smoke test. Failures go to `runs/smoke/smoke_failures.json`.
4. Tune on `prompt_dev` only, then run `... freeze` and `... experiment --split held_out_test`.

The **mock** provider is a deterministic heuristic, so the tests and the pipeline run without a key. Its numbers are labelled as not research results, and they must never go in the report.

## Module map
| File | Sprint | What it does |
|---|---|---|
| `schemas.py` | S1 | all output contracts (pydantic, strict) |
| `gateway/` | S1 | provider-agnostic gateway: retries, cache, logging, schema validation, repair, abstain |
| `prompts/` | S1/S5/S6/S7/S8 | versioned templates and few-shot conventions |
| `annotation.py` | S2/S3 | annotation validation, audit, inter-annotator agreement, write-once split |
| `labels.py` | S3 | label normalisation dictionary, abbreviations, name keys |
| `preprocess_compare.py` | S2 | denoise/contrast variants vs OCR label accuracy |
| `ocr.py` | S3/S4 | per-box OCR, text↔component association rules |
| `relations.py` | S4 | relation validation rules R1–R8 (UNCERTAIN handling) |
| `vlm_extraction.py` | S5 | 4 extraction modes plus cv_only fallback |
| `alignment.py` | S6 | exact → normalized → alias → token → LLM cascade |
| `grounding.py`, `rca.py` | S7 | evidence IDs, hallucination checks, 4 RCA ablation variants |
| `impact.py` | S8 | impact + recommendation with deterministic rule/cycle checks |
| `evaluation/` | S9 | metrics, frozen-config runner, blinded rubric |
| `service.py` | S8/S10 | **the functions P4's FastAPI layer calls** |

Docs: `docs/P2_SPRINT_TRACKER.md` (status per sprint task), `docs/design_notes.md`, `docs/uncertainty_policy.md`, `docs/annotation_guide_v1.md`, `docs/paper_section_llm_rca.md`.

## Contracts with teammates
Look at `fixtures/synthetic/S02_layered/` for one example of each file.

| From | File/shape | Used by |
|---|---|---|
| P1 | `detections.json` `[{id, bbox, class, confidence}]`, `geometry_candidates.json` `[{id, source, target, confidence}]` | `service.analyze_diagram_semantics` |
| P3 | `code_entities.json` `[{id, name, kind, path}]`; affected set `[{component, distance, direction}]` | `service.align_components`, impact |
| P4 | evidence package `violation.json` (Design §8.1 plus `candidate_commits`, `current_edges`, `intended_edges`, `layer_of`) | `service.analyze_violation` |

## Integrating teammates' outputs
`archlens_llm/adapters.py` turns the formats teammates produce today into the contracts above. The functions are pure (no I/O), and each docstring names its source format. Tests: `tests/test_adapters.py`.

**P1 (CV): detections and arrow candidates**
```python
from archlens_llm import adapters as A, service
dets = A.from_p1_detections(mapped)          # MappedDetection.to_dict() or P4 detect(); ids d1, d2... if missing
# or, from ArchComponent dicts (bbox {x1,y1,x2,y2}, id kept so relations still match):
dets = A.from_p1_components(graph["components"])
geo  = A.from_p1_relations(candidates)       # RelationCandidate.to_dict(); directed=False by default
out  = service.analyze_diagram_semantics("diag1", "diagram.png", dets, geo)
```
P1 stores each relation pair sorted, so its direction is unknown. With `directed=False` the confidence is capped at 0.49, below P2's `relation_uncertain_below` (0.5), so a relation stays `uncertain` unless the VLM confirms its direction. Pass `directed=True` only once P1 keeps arrow direction.

**P3 (static analysis): code entities, layers, rules, verdicts, edges**
```python
id_to_name = {c["id"]: c["name"] for c in g_c["components"]}
entities   = A.from_p3_entities(g_c["components"])     # {id, name, kind<-type, path<-file (or id)}
layer_of   = A.layer_of_from_p3(g_c["components"])     # {"OrderController": "Controller", ...}
rule       = A.from_p3_rules(ruleset)                  # {"allowed": ["Controller->Service"], "forbidden": [...], "required": [...]}
violation  = A.from_p3_verdict(verdict, id_to_name)    # {type, source, target, verdict} with display names
current    = A.edges_from_p3(g_c["relationships"], id_to_name)
mappings   = service.align_components(diagram_nodes, entities)
```
Type-based rule sides become layer labels (`controller` → `Controller`, the same rule `layer_of_from_p3` uses). Name-based sides stay as they are.

**P4 (backend): evidence package**
```python
raw = GitEvidenceExtractor(repo).build_evidence_package(violation, source_file, target_symbol, architecture_rule=ruleset)
pkg = A.from_p4_evidence(raw, current_edges=current, intended_edges=intended, layer_of=layer_of)
result = service.analyze_violation(pkg)
```
`candidate_commits` is `[commit] + recent_commits`, de-duplicated by hash. A P3 rule list or RuleSet in `architecture_rule` is converted automatically. P4 doesn't produce `current_edges`, `intended_edges` or `layer_of` yet, so pass them in from P3 as shown above.

**What the adapters can't fix: ask teammates for these**
- **P1:** keep arrow direction in relation candidates (today each pair is sorted).
- **P4:** send `code.lines` and `code.snippet`, and the `files` each commit touched. Without them, grounded RCA has nothing that ties a commit to the offending line, so it returns `UNCERTAIN`; with them it returns `SUPPORTED` (both cases are tested in `test_adapters.py`). Also send `current_edges`, `intended_edges` and `layer_of`, or call the P3 adapters before `service.analyze_violation`.
- **P4:** `/analyze-violation` and `/analyze-diagram` don't call `archlens_llm.service` yet.

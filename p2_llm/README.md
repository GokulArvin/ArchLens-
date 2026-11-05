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

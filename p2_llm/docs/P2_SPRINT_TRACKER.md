# P2 (LLM/VLM lead): sprint tracker

Status key:
- ✅ **Done.** Code plus tests in this repo.
- 🟡 **Done on synthetic fixtures.** Works, but must be re-run on the real ArchLens data once P1/P3/P4 deliver.
- 👥 **Needs a human or a teammate.** It can't be automated away. The tooling is ready.

| Sprint | Plan item (P2) | Where | Status |
|---|---|---|---|
| **S1** | D1 semantic tasks that need / don't need an LLM | `docs/design_notes.md` §1 | ✅ |
| | D2 structured outputs (component, relation, explanation, recommendation) | `archlens_llm/schemas.py` | ✅ |
| | D3 prompt templates + JSON validation strategy | `archlens_llm/prompts/*.txt`, `jsonutil.py`, `gateway/gateway.py` | ✅ |
| | D4 provider comparison + model-agnostic gateway | `gateway/` (Gemini, OpenAI-compatible/Ollama, mock), `docs/design_notes.md` §3 | ✅ |
| | D5 smoke test on 3–5 diagrams, failures logged | `python -m archlens_llm.cli smoke` → `runs/smoke/` | 🟡 run once with a real key |
| **S2** | D6 annotated pilot subset | `fixtures/synthetic/*/annotation.json` | 👥 annotate real diagrams in this format |
| | D7 denoise/contrast alternatives compared | `preprocess_compare.py` → `runs/preprocess_compare/` | 🟡 |
| | D8 annotation instructions | `docs/annotation_guide_v1.md`, `annotation.validate_annotation` | ✅ |
| | D9 double-check subset with another member | `annotation.agreement()` (kappa, relation F1, disagreement list) | 👥 needs 2nd annotator |
| | D10 prompt-dev split separate from held-out | `cli split` → `config/split.json` (write-once) | ✅ |
| **S3** | D11 audit annotation quality | `annotation.audit_annotations`, `cli audit` | ✅ |
| | D12 label normalization rules | `labels.py` (TYPE_ALIASES, ABBREVIATIONS) | ✅ |
| | D13 can OCR supplement detector output? | `ocr.ocr_components` + finding in `design_notes.md` §5 | 🟡 |
| | D14 hard-case set | `design_notes.md` §6 + S02 (noisy) / S03 (abbreviated) fixtures | 🟡 add real hard cases |
| | D15 where semantic classification is still needed | `design_notes.md` §4 | ✅ |
| **S4** | D16 component ↔ text association format | `ocr.associate_text` (rules A1–A4) | ✅ |
| | D17 labels stay attached to right regions | `ocr.evaluate_text_association` | 🟡 |
| | D18 relation-candidate format | `schemas.RelationCandidate` | ✅ |
| | D19 ambiguous connectors → UNCERTAIN | `relations.py` R5–R8, `docs/uncertainty_policy.md` | ✅ |
| | D20 validation rules for malformed relations | `relations.py` R1–R4 + tests | ✅ |
| **S5** | D21 structured VLM prompt | `prompts/vlm_extraction.txt` | ✅ |
| | D22 IDs must reference existing components | `VLMExtractor._validator` (repair, then reject) | ✅ |
| | D23 few-shot for ambiguous conventions | `prompts/fewshot_diagram_conventions.json` | ✅ |
| | D24 parse / validate / retry / abstain | gateway `structured()` + cv_only fallback | ✅ |
| | D25 eval on prompt-dev set, log model/version/tokens | `cli experiment` E1, `llm_calls.jsonl` | 🟡 needs real VLM |
| **S6** | D26 semantic alignment only for unresolved mappings | `alignment.Aligner` cascade | ✅ |
| | D27 evidence + confidence per mapping | `AlignmentLLMAnswer` + validator | ✅ |
| | D28 exact vs semantic comparison | runner E2 | 🟡 |
| | D29 tests for ambiguous matches + abstention | `tests/test_s5_s6_*` | ✅ |
| | D30 when to return UNCERTAIN | `docs/uncertainty_policy.md` | ✅ |
| **S7** | D31 evidence-only RCA prompt | `prompts/rca_grounded.txt` | ✅ |
| | D32 rule, edge, code, commit message, diff included | `grounding.index_evidence` (evidence IDs) | ✅ |
| | D33 parsing + evidence-reference checks | `rca._hard_issues/_soft_issues` | ✅ |
| | D34 LLM-only vs grounded | variants `llm_only`, `grounded_no_git`, `grounded_git_no_graph`, `grounded_full` | 🟡 needs real LLM |
| | D35 failure log (unsupported claims, wrong commit, vague RC) | `runs/*/hallucinations.jsonl` | ✅ |
| **S8** | D36 impact/recommendation prompt fields | `prompts/impact_recommendation.txt`, `schemas.ImpactRecommendation` | ✅ |
| | D37 reason only over affected nodes | validator: impacts ⊆ computed affected set | ✅ |
| | D38 recommendations with evidence IDs | `Recommendation.evidence_ids` | ✅ |
| | D39 unsupported-claim checks + abstention | `impact._checks` (forbidden edges, cycles, offending edge removed) | ✅ |
| | D40 rubric review with another member | `cli rubric RUN_DIR` (blinded CSV) + `rubric.aggregate` | 👥 needs 2 raters |
| **S9** | D41 freeze prompts / model / decoding | `cli freeze` → `config/experiment.lock.json`; held-out refuses to run otherwise | ✅ |
| | D42 VLM-only vs CV+VLM | E1 | 🟡 needs real VLM |
| | D43 LLM-only vs grounded RCA | E3 | 🟡 needs real LLM |
| | D44 score validity, grounding, RC quality, recommendation quality | `evaluation/metrics.py` + rubric | 🟡/👥 |
| | D45 sensitivity notes + failure examples | E1 few-shot on/off; rerun with a 2nd model/temperature | 🟡 |
| **S10** | D46 rerun final experiments | `cli experiment --split held_out_test` | 🟡 |
| | D47 audit grounding examples | `hallucinations.jsonl` + rubric | 👥 |
| | D48 LLM/RCA methodology + results section | `docs/paper_section_llm_rca.md` (results left as placeholders on purpose) | 🟡 fill in numbers |
| | D49 model/provider settings, prompts, cost/limits | `docs/paper_section_llm_rca.md` §Reproducibility | ✅ |
| | D50 present RCA path | `cli demo S02_layered` | ✅ |

## What still depends on teammates (agree on this in the next standup)
- **P1** gives you `detections.json` in the shape `[{id, bbox:[x1,y1,x2,y2], class, confidence}]`, plus geometry candidates `[{id, source, target, confidence}]` if they produce them.
- **P3** gives you `code_entities.json` `[{id, name, kind, path}]` and the impact function output `[{component, distance, direction}]`. If P3 doesn't deliver, `impact.compute_affected` is a working fallback.
- **P4** builds the evidence package. Its shape is in `fixtures/synthetic/*/violation.json`, and the only fields required are `violation`, `architecture_rule`, `code`, `dependency_path`, `candidate_commits`, `current_edges`, `intended_edges` and `layer_of`. P4 calls `service.analyze_violation(pkg)` from `POST /analyze-violation`.

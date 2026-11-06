# Draft paper section: Evidence-grounded LLM reasoning (P2, S10 D48–D49)

> Method text is complete. **Every number in the Results subsection is a placeholder.** Fill them only from `runs/<exp>/results.md` produced with the frozen lock on `held_out_test` using a real model. Mock-provider runs are pipeline tests and must never appear here.

## X. Semantic Reasoning Layer

### X.1 Design principle
ArchLens never treats an LLM as the authority on a deterministic architectural fact. Static analysis establishes dependencies, and a rule-based conformance engine issues the verdicts (CONFORMANT, VIOLATION, MISSING, UNEXPECTED, UNCERTAIN). The language and vision-language models are confined to four interpretive tasks:
1. semantic interpretation of diagram elements and dependencies;
2. root-cause analysis;
3. impact explanation;
4. recommendations.

Every model output is constrained to a JSON schema, checked against the supplied evidence, and either accepted, repaired or abstained on.

### X.2 Diagram semantics
Given detector boxes, per-box OCR text and optional geometric relation candidates, a VLM labels each box with a name, one of 13 component types, a confidence and evidence strings. It also confirms, rejects or re-types relation candidates.

The validator requires two things:
- every detected id is labelled exactly once and none are invented;
- every relation endpoint refers to an existing id.

Violations trigger a repair prompt that lists the exact errors. After two failed repairs the system falls back to a deterministic baseline (OCR plus a label dictionary plus geometry) and marks the provenance accordingly.

Relations pass through eight rules (R1–R8). The rules reject unknown endpoints and self-loops, merge duplicates, and mark a relation UNCERTAIN when its direction is ambiguous, its confidence is low, it has no evidence, or an endpoint is unreliable. We compare four settings: CV-only, VLM-only, CV+VLM and CV+VLM+geometry. For the full setting we also turn few-shot conventions on and off.

### X.3 Diagram-to-code alignment
Diagram nodes are mapped to code entities through a deterministic cascade:
1. exact match;
2. normalised match (camel-case splitting, abbreviation expansion);
3. alias table;
4. token-set similarity with a margin.

Only nodes the cascade leaves unresolved reach the LLM. The LLM sees a top-k shortlist and must choose from it or answer null, giving evidence and a confidence. Answers below the acceptance threshold, and conflicting claims on one entity, become UNCERTAIN.

### X.4 Evidence-grounded root-cause analysis
For each violation an evidence package is assembled, and each item receives a stable identifier:
- the architecture rule and layer map (`E-RULE`, `E-LAYERS`);
- the offending code location (`E-CODE`);
- the dependency path (`E-PATH`);
- the intended and current graphs (`E-GRAPH-I`, `E-GRAPH-C`);
- the computed affected set (`E-IMPACT`);
- candidate commits and their diffs (`E-COMMIT-<h>`, `E-DIFF-<h>`).

The model returns an explanation, a root cause, per-claim citations, the affected components, a recommendation, the introducing commit and a candidate ranking, a status and a confidence.

The **hard checks** are:
- every cited ID exists;
- the introducing commit and the ranked commits are among those supplied;
- the affected components appear in the evidence.

Hard-check failures are sent back for repair. The **soft checks** flag file names and commit hashes in free text that are absent from the evidence, and each one is logged as a hallucination.

A result is SUPPORTED only if all of these hold:
- the model claims support;
- the confidence exceeds the threshold;
- at least one citation exists;
- no unsupported mention remains.

Otherwise it is UNCERTAIN.

### X.5 Impact and recommendation
The affected set is computed by graph traversal (upstream dependants of the source, downstream reach of the target). The LLM explains impact for members of this set only and proposes `remove_edges` and `add_edges` with rationale and evidence IDs. A deterministic checker then rejects a recommendation if it does any of the following:
- adds an edge the rules forbid;
- leaves the offending edge in place (or fails to add a missing required edge);
- leaves a cycle in place;
- cites unknown evidence;
- mentions components outside the affected set.

Recommendations are reported as validated suggestions, never as guaranteed corrections.

### X.6 Experimental setup
- **Data:** ArchLens benchmark, `prompt_dev` / `held_out_test` split (seed and SHA in `config/split.json`). Prompts and thresholds were tuned on `prompt_dev` only.
- **Freeze:** prompt versions (content hashed), few-shot file hash, configuration hash and split hash are recorded in `config/experiment.lock.json`. The runner refuses to evaluate `held_out_test` if any of them changed.
- **RCA ablations** (Design §10.2, ablations 2 and 4):

  | Variant | Evidence supplied |
  |---|---|
  | `llm_only` | violation only |
  | `grounded_no_git` | rule, code, path, graph, impact |
  | `grounded_git_no_graph` | rule, code, commits/diffs |
  | `grounded_full` | all of the above |

- **Metrics:**
  - structured-output validity;
  - status correctness and over-claim rate (SUPPORTED when ground truth is UNCERTAIN);
  - introducing-commit Top-1/3/5;
  - grounding score (1 − unsupported / checkable assertions);
  - unsupported-claim count;
  - root-cause keyword recall (automatic proxy);
  - human rubric: architecture correctness, evidence grounding, root-cause accuracy, actionability and hallucination, each 1–5, from two blinded raters, with quadratic-weighted κ reported.

### X.7 Results (placeholders: do not fill from mock runs)
| Variant | Valid | Status acc. | Over-claim | Top-1 | Top-3 | Grounding | Unsupported/violation | Rubric (mean) |
|---|---|---|---|---|---|---|---|---|
| llm_only | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| grounded_no_git | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| grounded_git_no_graph | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| grounded_full | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

Also report:
- the diagram-semantics table (E1);
- the alignment table (E2: deterministic vs deterministic+LLM);
- impact validity (E4);
- at least three anonymised failure examples from `hallucinations.jsonl`, covering a wrong commit, an unsupported claim and a vague root cause.

### X.8 Threats to validity
- The benchmark is small. Report per-system results and avoid strong claims from tiny samples.
- Controlled violations are injected, so commit messages may be more informative than in real projects.
- The keyword-recall proxy rewards lexical overlap. The rubric is the primary root-cause quality measure.
- Results depend on the model. Report a second model or temperature (sensitivity, S9 D45).

## Reproducibility notes (S10 D49)
- **Providers:** set in `config/llm_config.json`, recorded in every `llm_calls.jsonl` line and in the lock.
- **Decoding:** temperature 0.0, and seed 7 where the API supports it. JSON response mode is on. Max tokens is 2048.
- **Prompts:** `archlens_llm/prompts/*.txt` (vlm_extraction, semantic_alignment, rca_grounded, rca_llm_only, impact_recommendation, dependency_role, repair) plus `fewshot_diagram_conventions.json`.
- **Robustness:** 3 transport retries with exponential backoff; up to 2 schema/evidence repairs, then abstention; an on-disk response cache keyed by provider, model, temperature, prompt and image bytes, so reruns are free and identical.
- **Cost:** token counts per call are in `llm_calls.jsonl`, and the totals per experiment are in `results.json → usage`. Report the totals and the calls per violation. [Likely] Free API tiers impose request-per-minute limits. A full held-out run is roughly 4 RCA variants × N violations + 5 extraction settings × M diagrams + alignment calls, so schedule it, don't run it interactively.
- **Command:** `python -m archlens_llm.cli --config <cfg> freeze && python -m archlens_llm.cli --config <cfg> experiment --split held_out_test`

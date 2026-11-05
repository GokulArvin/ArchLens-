# When P2 returns UNCERTAIN (S4 D19, S6 D30, S7 D35, S8 D39)

The principle: **a wrong confident answer costs more than an honest UNCERTAIN.** Each stage has explicit, testable triggers. All thresholds live in `config/llm_config.json → thresholds`, and freezing them is part of the experiment lock.

| Stage | Output becomes UNCERTAIN / abstains when… | Code |
|---|---|---|
| Component label | VLM `abstain=true`; confidence < `component_abstain_below` (0.35); OCR found no text and the VLM couldn't read it | `vlm_extraction.py` |
| Relation | R5 both directions within 0.15 confidence; R6 confidence < `relation_uncertain_below` (0.5); R7 no evidence; R8 an endpoint is unknown or abstained. **Rejected** (not uncertain): unknown endpoint (R1), self-loop (R2) | `relations.py` |
| Whole extraction | output still invalid after 2 repairs → cv_only fallback, flagged `fallback:cv_only` | `vlm_extraction.py` |
| Alignment | LLM confidence < `alignment_accept_at` (0.6); the model picked an id outside the shortlist even after repair; two nodes claim one entity and neither match is exact or normalized; no deterministic match and the LLM returned null (unless the node is a user or external system, which gives NO_MATCH) | `alignment.py` |
| RCA | model says UNCERTAIN; confidence < `rca_uncertain_below` (0.45); **no evidence cited**; any unsupported mention (unknown file or hash) left after repair; output invalid after repairs. `llm_only` therefore can never be SUPPORTED | `rca.py` |
| Impact / recommendation | model abstains; confidence < `impact_abstain_below` (0.4); the proposed edge isn't in the intended architecture (warning). **Rejected → repair → UNCERTAIN**: impact on a component outside the computed affected set, unknown evidence id, adding a FORBIDDEN edge, offending edge not removed (or the missing edge not added), cycle still present | `impact.py` |

Every UNCERTAIN result carries `reasons` or `uncertain_reasons`, so the dashboard can show *why*.

Hallucinations (anything asserted that the evidence doesn't contain) go to `runs/<run>/hallucinations.jsonl` with stage, variant, model and value. That log feeds the S7 D35 failure analysis and the S10 D47 audit.

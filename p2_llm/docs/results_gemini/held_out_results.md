> **Real model (gemini-3.5-flash-lite), SYNTHETIC pilot fixtures (6 systems, 3 held out). Not the final ArchLens benchmark.**

# P2 experiment 20261105-115829_held_out_test_gemini

Split: `held_out_test` (3 systems). Provider: `{'kind': 'gemini', 'model': 'gemini-3.5-flash-lite', 'api_key_env': 'GEMINI_API_KEY'}`.

## E1 Diagram extraction

| setting | name_accuracy | type_accuracy | relation_precision | relation_recall | relation_f1 | valid_structured_output | n |
|---|---|---|---|---|---|---|---|
| cv_only | 0.889 | 0.861 | 1.0 | 0.672 | 0.802 | 1.0 | 3 |
| vlm_only | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 3 |
| cv_vlm | 1.0 | 0.806 | 0.889 | 0.889 | 0.889 | 1.0 | 3 |
| cv_vlm_geometry | 1.0 | 0.806 | 0.889 | 0.889 | 0.889 | 1.0 | 3 |
| cv_vlm_geometry_no_fewshot | 1.0 | 0.806 | 0.889 | 0.889 | 0.889 | 1.0 | 3 |

## E2 Component alignment

| setting | precision | recall | f1 | wrong_matches | uncertain | n |
|---|---|---|---|---|---|---|
| deterministic_only | 1.0 | 0.878 | 0.933 | 0.0 | 0.667 | 3 |
| deterministic_plus_llm | 1.0 | 0.933 | 0.963 | 0.0 | 0.333 | 3 |

## E3 Root-cause analysis (ablations)

| setting | valid_structured_output | status_correct | overclaim | introducing_commit_correct | top1 | top3 | grounding_score | unsupported_claims | root_cause_keyword_recall | n |
|---|---|---|---|---|---|---|---|---|---|---|
| llm_only | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.528 | 3 |
| grounded_no_git | 1.0 | 0.333 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.333 | 3 |
| grounded_git_no_graph | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.917 | 3 |
| grounded_full | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 3 |

## E4 Impact + recommendation

| setting | valid_structured_output | fix_correct | forbidden_edges_proposed | abstained | n |
|---|---|---|---|---|---|
| impact_recommendation | 1.0 | 1.0 | 0.0 | 0.0 | 3 |

Usage: {'calls': 38, 'input_tokens': 82682, 'output_tokens': 22338, 'cache_hits': 0}

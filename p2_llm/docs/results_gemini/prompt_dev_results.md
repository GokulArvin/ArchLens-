# P2 experiment 20261105-115228_prompt_dev_gemini

Split: `prompt_dev` (3 systems). Provider: `{'kind': 'gemini', 'model': 'gemini-3.5-flash-lite', 'api_key_env': 'GEMINI_API_KEY'}`.

## E1 Diagram extraction

| setting | name_accuracy | type_accuracy | relation_precision | relation_recall | relation_f1 | valid_structured_output | n |
|---|---|---|---|---|---|---|---|
| cv_only | 1.0 | 0.867 | 1.0 | 0.764 | 0.863 | 1.0 | 3 |
| vlm_only | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 3 |
| cv_vlm | 1.0 | 0.933 | 1.0 | 1.0 | 1.0 | 1.0 | 3 |
| cv_vlm_geometry | 1.0 | 0.933 | 1.0 | 0.958 | 0.978 | 1.0 | 3 |
| cv_vlm_geometry_no_fewshot | 1.0 | 0.933 | 1.0 | 1.0 | 1.0 | 1.0 | 3 |

## E2 Component alignment

| setting | precision | recall | f1 | wrong_matches | uncertain | n |
|---|---|---|---|---|---|---|
| deterministic_only | 1.0 | 0.819 | 0.891 | 0.0 | 1.0 | 3 |
| deterministic_plus_llm | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 3 |

## E3 Root-cause analysis (ablations)

| setting | valid_structured_output | status_correct | overclaim | introducing_commit_correct | top1 | top3 | grounding_score | unsupported_claims | root_cause_keyword_recall | n |
|---|---|---|---|---|---|---|---|---|---|---|
| llm_only | 1.0 | 0.333 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5 | 3 |
| grounded_no_git | 1.0 | 0.0 | 0.333 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 3 |
| grounded_git_no_graph | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.875 | 3 |
| grounded_full | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 3 |

## E4 Impact + recommendation

| setting | valid_structured_output | fix_correct | forbidden_edges_proposed | abstained | n |
|---|---|---|---|---|---|
| impact_recommendation | 1.0 | 1.0 | 0.0 | 0.0 | 3 |

Usage: {'calls': 37, 'input_tokens': 76501, 'output_tokens': 22889, 'cache_hits': 0}

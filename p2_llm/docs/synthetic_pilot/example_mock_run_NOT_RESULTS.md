# P2 experiment 20261104-102346_held_out_test_mock

> **mock provider: pipeline smoke test only, NOT research results**

Split: `held_out_test` (3 systems). Provider: `{'kind': 'mock'}`.

## E1 Diagram extraction

| setting | name_accuracy | type_accuracy | relation_precision | relation_recall | relation_f1 | valid_structured_output | n |
|---|---|---|---|---|---|---|---|
| cv_only | 0.833 | 0.861 | 1.0 | 0.739 | 0.849 | 1.0 | 3 |
| vlm_only | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 3 |
| cv_vlm | 0.833 | 0.861 | 0.0 | 0.0 | 0.0 | 1.0 | 3 |
| cv_vlm_geometry | 0.833 | 0.861 | 0.667 | 0.472 | 0.552 | 1.0 | 3 |
| cv_vlm_geometry_no_fewshot | 0.833 | 0.861 | 0.667 | 0.472 | 0.552 | 1.0 | 3 |

## E2 Component alignment

| setting | precision | recall | f1 | wrong_matches | uncertain | n |
|---|---|---|---|---|---|---|
| deterministic_only | 1.0 | 0.878 | 0.933 | 0.0 | 0.667 | 3 |
| deterministic_plus_llm | 1.0 | 0.878 | 0.933 | 0.0 | 0.667 | 3 |

## E3 Root-cause analysis (ablations)

| setting | valid_structured_output | status_correct | overclaim | introducing_commit_correct | top1 | top3 | grounding_score | unsupported_claims | root_cause_keyword_recall | n |
|---|---|---|---|---|---|---|---|---|---|---|
| llm_only | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.083 | 3 |
| grounded_no_git | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 3 |
| grounded_git_no_graph | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 3 |
| grounded_full | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 3 |

## E4 Impact + recommendation

| setting | valid_structured_output | fix_correct | forbidden_edges_proposed | abstained | n |
|---|---|---|---|---|---|
| impact_recommendation | 1.0 | 1.0 | 0.0 | 0.0 | 3 |

Usage: {'calls': 31, 'input_tokens': 27016, 'output_tokens': 7334, 'cache_hits': 0}

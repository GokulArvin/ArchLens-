# Sprint 9: Baselines, Ablations, Final Evaluation (D41-D45)

> Re-run in full after two diagrams (`spring_cloud_brewery_overview`,
> `spring_cloud_brewery_dependency_graph`) were replaced with
> `aws_retail_store_sample_app` and `azure_aks_store_demo` - see
> `docs/dataset_candidates.md` for why. The split was re-frozen with the
> same seed/algorithm against the corrected 10-diagram set, and every number
> below was re-measured from scratch, not copied from the prior run.

## D41: Frozen split

`data/annotations/splits.json` (seed 42, generated once by
`backend/scripts/freeze_splits.py`, which refuses to overwrite an existing
split file): **train** (6) = `aws_retail_store_sample_app,
azure_aks_store_demo, gcp_bank_of_anthos, gcp_microservices_demo,
istio_bookinfo_derived, spring_petclinic_microservices`; **val** (2) =
`dotnet_eshop, sock_shop`; **test** (2) = `flask_microservice_demo,
roman_bilyak_microservice_architecture`. No baseline's thresholds/parameters
were tuned using these results - all three baselines (YOLO confidence 0.25,
region-cropping's area-fraction filter, Hough-line parameters) kept the
same defaults chosen in Sprints 3-5, before the split existed.

## D42 + D43: Baseline evaluation on the frozen test split

`backend/scripts/evaluate_on_frozen_test_split.py` reruns all three CV
baselines against `flask_microservice_demo` and
`roman_bilyak_microservice_architecture` only (`experiments/results/sprint9_test_split_evaluation.json`):

| baseline | test-split P | test-split R | test-split F1 | full-dataset F1 (Sprints 3-5) |
|---|---|---|---|---|
| Detector (YOLOv8n/COCO) | 0.000 | 0.000 | 0.000 | 0.000 |
| Segmentation (region-cropping) | 0.117 | 0.938 | 0.208 | 0.324 (3-diagram subset evaluated in Sprint 4, not directly comparable) |
| Geometry relations (Hough) | 0.842 | 0.762 | 0.800 | 0.591 |

See `experiments/results/sprint9_baseline_comparison.png` for the figure.
Held-out performance is consistent with (geometry: better; detector:
identical zero; segmentation: lower precision but higher recall) the
full-dataset numbers - no sign of the full-dataset numbers having been
inflated by overfitting to easy cases, since the held-out set was never
used to pick parameters.

## D44: Error categorization on the test split

Specific, real failures observed on the two held-out diagrams (measured
directly from `experiments/results/sprint9_test_split_evaluation.json`):

1. **Missed arrows (geometry baseline)**: `flask_microservice_demo` missed 1
   of 4 real edges (TP=3, FP=0, FN=1). `roman_bilyak_microservice_architecture`
   missed 4 of 17 real edges (TP=13, FP=3, FN=4) - its denser fan-out from
   the API Gateway and Ingress nodes produces more opportunities for
   endpoint-matching misses than the smaller flask demo.
2. **Heavy over-segmentation (segmentation baseline)**: `flask_microservice_demo`
   produced 44 region proposals for 4 real components (40 false positives);
   `roman_bilyak_microservice_architecture` produced even more - 84 proposals
   for 12 real components (73 false positives) - consistent with the
   Sprint 4 finding that Canny+contour proposals fragment on any
   text-containing region, and worse on denser diagrams with more text.
3. **Zero detections (detector baseline)**: the COCO-pretrained YOLOv8n
   produced 0 raw detections on both held-out diagrams (16/16 real
   components missed) - this matches the full-dataset result (0.000 F1),
   confirming it is not a fluke of this particular split.
4. **OCR issues**: `flask_microservice_demo`'s 4 components all OCR'd
   correctly (plain text labels, no icons). `roman_bilyak_microservice_architecture`
   only matched OCR text on 5 of 12 components (`ingress`, `appangular`,
   `authservice`, `apigateway`, `appreact`) - the 7 misses (`browser`,
   `identityservice`, `movieservice`, `paymentservice`, `reviewservice`,
   `testservice`, `rabbitmq`) are all icon-labeled nodes with little or no
   in-box text, the same label-outside-the-box pattern already documented
   in Sprint 5 (`docs/cv_failure_cases.md`).

## D45: Final tables and figures

- `experiments/results/sprint9_test_split_evaluation.json` - full per-
  diagram and aggregate results for all three baselines on the frozen test
  split.
- `experiments/results/sprint9_baseline_comparison.png` - F1 comparison
  figure (full dataset vs. frozen test split, all three baselines).
- Headline, honest conclusion: **geometry-based relation extraction is the
  strongest CV baseline in this project** (F1=0.800 on held-out data),
  consistently outperforming both the pretrained-detector and segmentation
  baselines by a wide margin, on both the full dataset and the frozen test
  split - a stable, non-overfit finding.

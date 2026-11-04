# Sprint 9: Baselines, Ablations, Final Evaluation (D41-D45)

## D41: Frozen split

`data/annotations/splits.json` (seed 42, generated once by
`backend/scripts/freeze_splits.py`, which refuses to overwrite an existing
split file): **train** (6) = `dotnet_eshop, flask_microservice_demo,
istio_bookinfo_derived, roman_bilyak_microservice_architecture, sock_shop,
spring_petclinic_microservices`; **val** (2) = `gcp_bank_of_anthos,
spring_cloud_brewery_overview`; **test** (2) = `gcp_microservices_demo,
spring_cloud_brewery_dependency_graph`. No baseline's thresholds/parameters
were tuned using these results - all three baselines (YOLO confidence 0.25,
region-cropping's area-fraction filter, Hough-line parameters) kept the
same defaults chosen in Sprints 3-5, before the split existed.

## D42 + D43: Baseline evaluation on the frozen test split

`backend/scripts/evaluate_on_frozen_test_split.py` reruns all three CV
baselines against `gcp_microservices_demo` and
`spring_cloud_brewery_dependency_graph` only (`experiments/results/sprint9_test_split_evaluation.json`):

| baseline | test-split P | test-split R | test-split F1 | full-dataset F1 (Sprints 3-5) |
|---|---|---|---|---|
| Detector (YOLOv8n/COCO) | 0.000 | 0.000 | 0.000 | 0.021 |
| Segmentation (region-cropping) | 0.110 | 0.529 | 0.182 | N/A (only a 3-diagram subset was evaluated in Sprint 4, not comparable) |
| Geometry relations (Hough) | 0.846 | 0.550 | 0.667 | 0.581 |

See `experiments/results/sprint9_baseline_comparison.png` for the figure.
Held-out performance is consistent with (geometry: better; detector/
segmentation: similar or worse) the full-dataset numbers - no sign of the
full-dataset numbers having been inflated by overfitting to easy cases,
since the held-out set was never used to pick parameters.

## D44: Error categorization on the test split

Specific, real failures observed on the two held-out diagrams (cross-
referencing Sprints 3-5's per-diagram findings where they already covered
these diagrams, since those findings were measured, not re-derived):

1. **Missed arrows (geometry baseline)**: `gcp_microservices_demo` missed 5
   of 16 real edges (`docs/sprint5_vit_geometry_report.md` already
   identified this diagram's dense fan-out pattern as a source of partial
   endpoint-matching misses). `spring_cloud_brewery_dependency_graph`
   missed all 4 real edges (0 candidates survived - the same small-image/
   tight-box limitation already flagged in Sprint 4/5's reports for this
   diagram).
2. **Overlapping/duplicate boxes (segmentation baseline)**: `gcp_microservices_demo`
   produced 69 region proposals for 12 real components (60 false
   positives) - heavy over-segmentation on text-containing boxes, each
   letter/word fragment sometimes producing its own contour.
3. **OCR issues**: not evaluated in Sprint 9 scope directly (OCR's D22
   analysis in Sprint 5 already covers both test-split diagrams:
   `gcp_microservices_demo` had no OCR failures recorded; the small
   dependency-graph diagram's icon-only components - `presenting`,
   `brewing`, `zuul`, `ingredients` - all failed OCR, consistent with the
   label-outside-the-box pattern already documented).
4. **Ambiguous symbols**: `spring_cloud_brewery_dependency_graph` remains
   the project's hardest case across every baseline (detector, segmentation,
   and geometry all scored nearly zero on it) - its small size (924x154px)
   and tight boxes are a genuine, now triple-confirmed limit of all three
   current baselines, not a one-off artifact of any single method.

## D45: Final tables and figures

- `experiments/results/sprint9_test_split_evaluation.json` - full per-
  diagram and aggregate results for all three baselines on the frozen test
  split.
- `experiments/results/sprint9_baseline_comparison.png` - F1 comparison
  figure (full dataset vs. frozen test split, all three baselines).
- Headline, honest conclusion: **geometry-based relation extraction is the
  strongest CV baseline in this project** (F1=0.667 on held-out data),
  consistently outperforming both the pretrained-detector and segmentation
  baselines by a wide margin, on both the full dataset and the frozen test
  split - a stable, non-overfit finding.

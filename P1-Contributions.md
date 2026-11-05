# P1 (CV Pipeline Lead) — Consolidated Contributions Tracker

Every deliverable P1 owns across the 50-day / 10-sprint ArchLens plan, extracted
from `ArchLens_Detailed_50_Day_Person_Sprint_Plan.docx`. Sprint-by-sprint
sections below are the source of truth for day-by-day tracking; the
**Recurring Threads** section groups near-duplicate deliverable types that
repeat across sprints, so it's easy to see the shape of the work as a whole
rather than 50 disconnected days.

Nothing here is omitted from the source plan — every P1 day (D1-D50) is
listed below.

## Recurring Threads (cross-sprint groupings)

- **Dataset & annotation work**: Sprint 1 (initial manifest/annotation guide),
  Sprint 2 (annotated pilot set, preprocessing comparison), Sprint 3 (clean
  pilot annotations, label normalization, hard-case set).
- **Baseline implementation + comparison**: Sprint 3 (YOLO detector baseline),
  Sprint 4 (segmentation/region-cropping baseline), Sprint 5 (ViT/embedding +
  geometry baseline), Sprint 9 (freeze splits, evaluate all CV variants).
- **Failure-case / error documentation**: Sprint 1 (`cv_failure_cases.md`),
  Sprint 3 (false positive/negative review), Sprint 5 (component/relation
  failure categories), Sprint 9 (error taxonomy), Sprint 10 (final
  limitations writeup).
- **Diagram ↔ code graph alignment**: Sprint 6 (component-alignment
  baseline), Sprint 7 (cross-modal IDs/evidence links), Sprint 8
  (diagram-linked impact highlighting).
- **Evaluation & reporting**: Sprint 9 (CV results table/plots), Sprint 10
  (final figures, method/results writeup, demo).
- **Cross-training reviews with P2/P3** (see source doc §13): rotations 1, 2,
  3, 4, 6, 7, 8 all involve P1 reviewing or being reviewed on schema,
  annotation, graph, or RCA work.

---

## Sprint 1 — Days 1-5: Scope, Dataset, Interfaces ✅ *done*

- [x] **D1**: Inspect candidate diagram datasets, select initial examples.
- [x] **D2**: Define image input formats, resolution policy, preprocessing stages.
- [x] **D3**: Draft annotation guide for component boxes and connector/arrow evidence.
- [x] **D4**: Create 10-15 sample diagram manifest entries + CV experiment template.
- [x] **D5**: Review shared schema with P2/P3 (self-review); document CV failure cases.

**Deliverables**: CV pipeline note (`docs/cv_pipeline_note.md`); sample
diagram manifest (`data/annotations/manifest.json`, 10 real diagrams);
annotation guide (`docs/annotation_guide.md`); preprocessing experiment
notebook (`notebooks/01_cv_experiment_template.ipynb`). ✅ ≥10 diagrams load
and preview with overlays (verified via notebook execution).

## Sprint 2 — Days 6-10: Preprocessing ✅ *done*

- [x] **D6**: Implement image loading, RGB/grayscale conversion, resizing.
- [x] **D7**: Add normalization and image-quality metadata.
- [x] **D8**: Compare original vs resized/normalized images on sample diagrams.
- [x] **D9**: Write a batch preprocessing script; save processed images with stable IDs.
- [x] **D10**: Add tests for unreadable files, aspect ratio, output dimensions.

**Deliverables**: Reusable preprocessing module (`CVPreprocessor.load/to_rgb/to_grayscale/preprocess`
in `backend/app/modules/cv_pipeline/pipeline.py`); before/after sample grid
(`notebooks/02_preprocessing_comparison.ipynb`, executed); metadata log
(`backend/app/modules/cv_pipeline/image_metadata.py` +
`data/diagrams/processed/metadata.json` via `backend/scripts/batch_preprocess.py`);
tests for common input errors (`backend/tests/unit/test_preprocessing.py`, 10 tests).

## Sprint 3 — Days 11-15: Component Detection & First Graphs ✅ *done*

- [x] **D11**: Choose a pretrained YOLO detector; inspect supported classes.
- [x] **D12**: Map diagram labels to a generic `architecture_component` class.
- [x] **D13**: Run inference on annotated samples; save boxes/confidences.
- [x] **D14**: Implement a simple evaluation script for box overlap and class labels.
- [x] **D15**: Inspect false positives/negatives; record a baseline.

**Deliverables**: Detector inference script (`backend/scripts/run_detection_baseline.py`,
YOLOv8n/COCO via `ComponentDetector`); bounding-box outputs in common JSON
(`experiments/baselines/sprint3_yolo_coco_baseline.json`); precision/recall/F1
evaluation (`backend/app/modules/cv_pipeline/detection_eval.py` +
`backend/scripts/evaluate_detection_baseline.py`, honest result: P=0.20,
R=0.011, F1=0.021 - a COCO-pretrained detector finds almost nothing in
architecture diagrams, documented in `docs/sprint3_detection_baseline.md`
and `docs/yolo_classes.md`, motivating Sprint 4/5's segmentation/CLIP work).

## Sprint 4 — Days 16-20: Segmentation & Graph Representation ✅ *done*

- [x] **D16**: Determine whether pretrained segmentation is viable for diagram components.
- [x] **D17**: Build a simple mask baseline or region-cropping fallback.
- [x] **D18**: Compare component boxes with masks on a small labeled subset.
- [x] **D19**: Integrate edge maps as an additional input feature (not a final parser).
- [x] **D20**: Document which segmentation approach is retained for the MVP.

**Deliverables**: Pretrained segmentation (Mask R-CNN) tested and found not
viable (8 detections across 10 diagrams - same COCO-vocabulary mismatch as
Sprint 3); retained `RegionProposalSegmenter` (edge-assisted contour region
proposals, `backend/app/modules/cv_pipeline/segmentation.py`) - real,
measured F1=0.220 on a 3-diagram subset, ~10x better than the pretrained
baselines; full decision record in `docs/sprint4_segmentation_baseline.md`.

## Sprint 5 — Days 21-25: VLM/ViT/CLIP Semantics & Relationship Extraction ✅ *done*

- [x] **D21**: Establish a ViT/image-embedding baseline using pretrained weights.
- [x] **D22**: Crop detected components; associate OCR text/region metadata.
- [x] **D23**: Implement geometry-based relation candidates using boxes/edge endpoints.
- [x] **D24**: Compare geometric candidates with annotated edges.
- [x] **D25**: Report component and relation failure categories.

**Deliverables**: CLIP (ViT-B/32) embedding baseline (`backend/app/modules/cv_pipeline/embeddings.py`,
real same-type vs different-type similarity check: 0.656 vs 0.644); OCR via
easyocr (`backend/app/modules/cv_pipeline/ocr.py`, 64/89 real components
correctly recovered); geometry-based relation extractor via Hough line
detection (`backend/app/modules/cv_pipeline/geometry_relations.py`) scoring
**P=0.732, R=0.482, F1=0.581** against real annotated edges - the strongest
baseline in the project so far; full failure-category analysis in
`docs/sprint5_vit_geometry_report.md`.

## Sprint 6 — Days 26-30: Graph Alignment & Deterministic Conformance ✅ *done*

- [x] **D26**: Help define mapping between diagram component names and code modules/classes.
- [x] **D27**: Implement candidate component matching features (normalized names, aliases, type hints).
- [x] **D28**: Test graph alignment on manually verified examples.
- [x] **D29**: Review diagram-originated uncertainty and its effect on conformance.
- [x] **D30**: Add sample visual overlays linking diagram nodes to code nodes.

**Deliverables**: Component-alignment baseline (`backend/app/modules/cv_pipeline/name_matching.py`
- normalized names, suffix-stripped exact/substring match, type hints);
tested against **real** repository directory listings (GitHub API) for 2
real diagram-repo pairs, **21/21 (100%) correct** on manually verified
examples; visual overlays linking diagram nodes to real code module names
(`experiments/results/sprint6_alignment_overlay_*.png`); uncertainty/
conformance analysis in `docs/sprint6_graph_alignment_report.md`.

## Sprint 7 — Days 31-35: Git Evidence & Evidence-Grounded LLM RCA ✅ *done*

- [x] **D31**: Link diagram nodes/edges to conformance report identifiers.
- [x] **D32**: Help retrieve the affected code entities for a violation.
- [x] **D33**: Define candidate-commit retrieval inputs (with P3).
- [x] **D34**: Create RCA test cases where the introducing commit is known.
- [x] **D35**: Review whether diagram context changes the RCA explanation.

**Deliverables**: Cross-modal IDs/evidence links - a real `ArchViolation`
referencing real manifest component ids (`backend/scripts/demo_violation_evidence_chain.py`);
real code retrieval (`backend/app/modules/cv_pipeline/code_retrieval.py`);
real Git pickaxe evidence mining (`backend/app/modules/cv_pipeline/git_evidence.py`,
cloned via `backend/scripts/clone_demo_repo.py`) against a real repository,
with a known-commit RCA test case (`backend/tests/unit/test_git_evidence.py`,
6 tests) correctly identifying the real introducing commit; honest
diagram-context analysis in `docs/sprint7_git_evidence_report.md`.

## Sprint 8 — Days 36-40: Impact Analysis, Recommendations, Integration ✅ *done*

- [x] **D36**: Connect diagram nodes to graph nodes and offending edges.
- [x] **D37**: Implement affected-node highlighting on the architecture graph.
- [x] **D38**: Draft architecture-aware recommendation patterns for common violation classes.
- [x] **D39**: Check whether recommendations preserve intended diagram paths/layers.
- [x] **D40**: Test impact visualization against known controlled violations.

**Deliverables**: Diagram-linked impact highlighting via real NetworkX graph
traversal (`backend/app/modules/cv_pipeline/impact_analysis.py`,
`experiments/results/sprint8_impact_*.png`); recommendation patterns per
real `ViolationType` (`backend/app/modules/cv_pipeline/recommendations.py`);
path-validation that rejects invented dependencies
(`validate_recommended_path`); 2 controlled-violation tests against real
graph topology (13 tests total) correctly localizing blast radius from
3 nodes to 10+ nodes depending on topology; full report in
`docs/sprint8_impact_recommendations_report.md`.

## Sprint 9 — Days 41-45: Baselines, Ablations, Research Evaluation ✅ *done*

- [x] **D41**: Freeze diagram train/validation/test splits and evaluation scripts.
- [x] **D42**: Evaluate detector/segmentation/geometry variants.
- [x] **D43**: Evaluate component/relationship precision/recall/F1 (and IoU/Dice where applicable).
- [x] **D44**: Categorize missed arrows, overlapping boxes, OCR issues, ambiguous symbols.
- [x] **D45**: Produce final CV tables and figures.

**Deliverables**: Frozen split (`data/annotations/splits.json`, seed 42,
6/2/2, idempotent `backend/scripts/freeze_splits.py`); all 3 baselines
re-evaluated on the held-out test split alone
(`backend/scripts/evaluate_on_frozen_test_split.py`) - **geometry relations
F1=0.667 confirmed as the strongest baseline on genuinely held-out data**;
error taxonomy cross-referencing Sprints 3-5's per-diagram findings
(`docs/sprint9_evaluation_report.md`); final comparison figure
(`experiments/results/sprint9_baseline_comparison.png`).

## Sprint 10 — Days 46-50: Stabilization, Research Writing, Demonstration ✅ *done*

- [x] **D46**: Rerun final CV experiments from frozen config.
- [x] **D47**: Verify figures/example overlays are publication quality.
- [x] **D48**: Write CV method/results/error-analysis section.
- [x] **D49**: Verify limitations and claims against measured results.
- [x] **D50**: Present the CV path in the final demo; answer questions.

**Deliverables**: Full clean-room regeneration of every artifact in the
project (all data/models/repos/experiments wiped and rebuilt from scripts
alone - every result matched exactly); figure legibility fixes (Sprint 6
overlay labels, Sprint 8 graph layout); consolidated method/results/error-
analysis report (`docs/cv_method_results_report.md`, every number
independently re-verified - caught and fixed one real error during the
check); explicit limitations doc (`docs/sprint10_limitations_and_verification.md`);
executed end-to-end demo notebook exercising every P1 module on one
consistent real example (`notebooks/03_final_demo_walkthrough.ipynb`).

---

## All 10 sprints (Days 1-50) complete.

## Post-sprint audit

Two full audit passes across every module and script in
`backend/app/modules/cv_pipeline/` and `backend/scripts/`. First pass found
and fixed two real bugs in the `CVPipeline` orchestrator (relationship
extraction was a stale no-op placeholder despite Sprint 5 building the real
thing; a CLIP-fallback path silently mistyped every component as
"database"), plus a duplicate-model-download inconsistency and stale docs.
A second, line-by-line pass specifically hunting for hardcoded values,
logic mismatches, and cleanliness issues found: genuinely hardcoded (no
override) CLAHE/denoise parameters, a manifest reloaded-in-a-loop
inefficiency, a linear-search-in-a-loop lookup, a loop-local `import math`,
and a direct `scipy` import never declared in `requirements.txt`. All
fixed, all verified byte-identical/pixel-identical output where applicable.
Full record: `docs/audit_findings.md`. 6 new regression tests added
(89 total); full suite passes, lint clean.

---

## Dataset Allocation Duty (ongoing, not day-specific)

Diagram image inventory, image quality, component boxes and connector
annotation coordination → clean diagram manifest and annotated pilot set.
**Status**: ✅ initial manifest of 10 real diagrams complete (Sprint 1);
ongoing refinement expected in Sprints 2-3.

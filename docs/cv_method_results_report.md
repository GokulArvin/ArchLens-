# ArchLens P1 (CV Pipeline) — Method, Results & Error Analysis

Sprint 10 / D48. Consolidates Sprints 1-9's real work into one method/
results section. Every number below was re-read directly from its source
JSON file immediately before writing this document (see D49 for the
verification pass) - nothing here is from memory or recomputed by hand.

> **Post-Sprint-10 correction**: two diagrams (`spring_cloud_brewery_overview`,
> `spring_cloud_brewery_dependency_graph`) were found, on closer inspection,
> to be a stylized beer-brewing illustration rather than a genuine
> boxes-and-arrows software architecture diagram, and were replaced with
> `aws_retail_store_sample_app` and `azure_aks_store_demo` - see
> `docs/dataset_candidates.md`. Every number in this document was
> re-measured from scratch against the corrected dataset, not patched.

## 1. Data

10 real architecture diagrams, each paired with the real public repository
it describes (`data/annotations/manifest.json`), hand-annotated against the
shared `ArchComponent`/`ArchRelationship`/`ArchGraph` schema
(`backend/app/schemas/models.py`): 95 ground-truth components, 115
ground-truth relationships across all 10 diagrams. 9 diagrams use official,
publisher-provided architecture diagrams; 1 (`istio_bookinfo_derived`) was
rendered from real source-code evidence since Istio ships none. No
synthetic or fabricated diagram content anywhere in the dataset
(`docs/dataset_candidates.md`).

Train/val/test split frozen in Sprint 9 (seed 42, 6/2/2,
`data/annotations/splits.json`); no baseline's parameters were tuned using
test-split results.

## 2. Method

| Stage | Module | Approach |
|---|---|---|
| Preprocessing | `backend/app/modules/cv_pipeline/pipeline.py::CVPreprocessor` | Format/size policy enforcement, CLAHE normalization, RGB/grayscale conversion |
| Component detection | `pipeline.py::ComponentDetector` + `detection_mapping.py` | Pretrained YOLOv8n (COCO), all detections mapped to a generic `architecture_component` class |
| Segmentation | `segmentation.py::RegionProposalSegmenter` | Edge-assisted (Canny) contour region proposals - pretrained Mask R-CNN tested and found not viable |
| Embeddings | `embeddings.py::ComponentEmbedder` | Pretrained CLIP (ViT-B/32) image encoder |
| OCR | `ocr.py::RegionOCR` | easyocr (no system Tesseract available) |
| Relationship extraction | `geometry_relations.py` | Hough line detection + nearest-component endpoint matching |
| Graph alignment | `name_matching.py` | Normalized-name + type-hint matching against real repository directory listings |
| Impact analysis | `impact_analysis.py` | NetworkX graph traversal (ancestors/descendants) |
| Recommendations | `recommendations.py` | Per-`ViolationType` templates, path-validated against the intended graph |
| Git evidence | `git_evidence.py`, `code_retrieval.py` | Real pickaxe search (`git log -S`) + real file retrieval against a cloned repository |

## 3. Results (real, measured)

### 3.1 Component detection / segmentation (full 10-diagram dataset unless noted)

| Baseline | Precision | Recall | F1 |
|---|---|---|---|
| YOLOv8n (COCO-pretrained) detector | 0.0000 | 0.0000 | **0.0000** |
| Mask R-CNN (COCO-pretrained) segmentation | - | - | not viable (4 total detections across all 10 diagrams; not scored as P/R) |
| Region-cropping segmentation (3-diagram subset) | 0.1983 | 0.8846 | **0.3239** |

### 3.2 Relationship extraction (full 10-diagram dataset)

| Baseline | Precision | Recall | F1 |
|---|---|---|---|
| Hough-line geometric relations | 0.7308 | 0.4957 | **0.5907** |

### 3.3 Frozen held-out test split (`flask_microservice_demo`, `roman_bilyak_microservice_architecture`)

| Baseline | Precision | Recall | F1 |
|---|---|---|---|
| YOLOv8n detector | 0.0000 | 0.0000 | 0.0000 |
| Region-cropping segmentation | 0.1172 | 0.9375 | 0.2083 |
| Geometry relations | 0.8421 | 0.7619 | **0.8000** |

### 3.4 Semantic signals

- CLIP embedding same-type vs. different-type cosine similarity: **0.6469 vs. 0.6122** (weak, real, positive signal).
- OCR recovered the correct real component label for **79/95 (83.2%)** of ground-truth crops.
- Name-based graph alignment against real repository directory listings: **21/21 (100%)** on manually verified examples from 2 real repos.

## 4. Error analysis (consolidated from Sprints 3-5, 9)

1. **Pretrained-vocabulary mismatch** (Sprint 3/4): COCO's 80 classes share
   no vocabulary with architecture-diagram content; both YOLOv8n and Mask
   R-CNN find almost nothing real on this (corrected) dataset of clean
   boxes-and-arrows diagrams - zero detections survive evaluation at all.
2. **Over-segmentation** (Sprint 4/9): contour-based region proposals favor
   recall at the cost of precision - text and icon fragments each produce
   their own contour, especially on dense diagrams (`gcp_microservices_demo`:
   69 proposals for 12 real components; `roman_bilyak_microservice_architecture`:
   84 proposals for 12 real components on the held-out test split).
3. **Curved-connector failure mode** (Sprint 5/9): `azure_aks_store_demo`
   draws several edges as smooth bezier curves rather than straight
   segments; Hough-line detection only recovers 1 of 9 real edges there
   (recall 0.111), the dataset's worst geometry result - a genuine,
   non-straight-line limitation of the method, confirmed on both the full
   dataset and consistent with the curve shapes visible in the diagram.
4. **OCR label-placement / granularity mismatch** (Sprint 5): sub-labels
   ("API" badges, live port placeholders) or labels drawn outside a
   component's box can beat the real component name in OCR's output - an
   annotation-convention/granularity issue, not a pure OCR failure.
5. **Geometric false positives/negatives in nested/grouped diagrams**
   (Sprint 5/9): long or group-crossing connectors fragment into multiple
   short Hough segments in diagrams like `dotnet_eshop`, hurting both
   precision and recall there specifically.

## 5. Headline finding

**Geometry-based relation extraction (Hough lines + nearest-component
matching) is the strongest CV baseline in this project** - F1=0.591 on the
full dataset, F1=0.800 on the genuinely held-out test split (no
degradation, confirming it's a real, non-overfit result) - by a wide margin
over both pretrained-model baselines. This makes intuitive sense:
connectors in architecture diagrams are mostly straight lines, so a
geometry-first method is naturally matched to the problem in a way
generic, photograph-trained object detectors are not - though curved
connectors (error analysis, category 3 above) remain a real, documented
limitation.

# ArchLens P1 (CV Pipeline) — Method, Results & Error Analysis

Sprint 10 / D48. Consolidates Sprints 1-9's real work into one method/
results section. Every number below was re-read directly from its source
JSON file immediately before writing this document (see D49 for the
verification pass) - nothing here is from memory or recomputed by hand.

## 1. Data

10 real architecture diagrams, each paired with the real public repository
it describes (`data/annotations/manifest.json`), hand-annotated against the
shared `ArchComponent`/`ArchRelationship`/`ArchGraph` schema
(`backend/app/schemas/models.py`): 89 ground-truth components, 110
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
| YOLOv8n (COCO-pretrained) detector | 0.2000 | 0.0112 | **0.0213** |
| Mask R-CNN (COCO-pretrained) segmentation | - | - | not viable (8 total detections across all 10 diagrams; not scored as P/R) |
| Region-cropping segmentation (3-diagram subset) | 0.1340 | 0.6190 | **0.2203** |

### 3.2 Relationship extraction (full 10-diagram dataset)

| Baseline | Precision | Recall | F1 |
|---|---|---|---|
| Hough-line geometric relations | 0.7324 | 0.4815 | **0.5810** |

### 3.3 Frozen held-out test split (`gcp_microservices_demo`, `spring_cloud_brewery_dependency_graph`)

| Baseline | Precision | Recall | F1 |
|---|---|---|---|
| YOLOv8n detector | 0.0000 | 0.0000 | 0.0000 |
| Region-cropping segmentation | 0.1098 | 0.5294 | 0.1818 |
| Geometry relations | 0.8462 | 0.5500 | **0.6667** |

### 3.4 Semantic signals

- CLIP embedding same-type vs. different-type cosine similarity: **0.6563 vs. 0.6444** (weak, real, positive signal).
- OCR recovered the correct real component label for **64/89 (71.9%)** of ground-truth crops.
- Name-based graph alignment against real repository directory listings: **21/21 (100%)** on manually verified examples from 2 real repos.

## 4. Error analysis (consolidated from Sprints 3-5, 9)

1. **Pretrained-vocabulary mismatch** (Sprint 3/4): COCO's 80 classes share
   no vocabulary with architecture-diagram content; both YOLOv8n and Mask
   R-CNN find almost nothing real, with occasional coincidental spatial
   false positives on illustrated/icon-style diagrams.
2. **Over-segmentation** (Sprint 4/9): contour-based region proposals favor
   recall at the cost of precision - text and icon fragments each produce
   their own contour, especially on dense diagrams (`gcp_microservices_demo`:
   69 proposals for 12 real components).
3. **Small-diagram / tight-box failure mode** (Sprint 4/5/9): `spring_cloud_brewery_dependency_graph`
   (924x154px, small tight ground-truth boxes) scores worst or near-zero
   across *every* baseline tested - detection, segmentation, and geometry
   alike. This is the project's single hardest, most consistently confirmed
   case.
4. **OCR label-placement mismatch** (Sprint 5): when a diagram draws a
   label outside its icon's box rather than inside it, our bbox convention
   crops the label out entirely - an annotation-convention issue, not an
   OCR failure.
5. **Geometric false positives/negatives in nested/grouped diagrams**
   (Sprint 5/9): long or group-crossing connectors fragment into multiple
   short Hough segments in diagrams like `dotnet_eshop`, hurting both
   precision and recall there specifically.

## 5. Headline finding

**Geometry-based relation extraction (Hough lines + nearest-component
matching) is the strongest CV baseline in this project** - F1=0.581 on the
full dataset, F1=0.667 on the genuinely held-out test split (no
degradation, confirming it's a real, non-overfit result) - by a wide margin
over both pretrained-model baselines. This makes intuitive sense:
connectors in architecture diagrams are literally straight lines, so a
geometry-first method is naturally matched to the problem in a way
generic, photograph-trained object detectors are not.

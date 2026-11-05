# CV Pipeline Note (Sprint 1 / D2)

Describes the resolution policy and stage list for `backend/app/modules/cv_pipeline/pipeline.py`
(Module B). The module already exists as a stub on `main` with real stage
classes; Sprint 1 only specifies/codifies the policy, implementation of each
stage is spread across Sprints 2-5 per the roadmap.

## Accepted input formats

- PNG and JPEG (both appear in the Sprint 1 dataset: 9 PNGs, 1 JPG).
- Enforced via `ALLOWED_INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg"}` in
  `pipeline.py`; `CVPreprocessor.preprocess()` raises `ValueError` on any
  other extension rather than silently attempting to load it (tested in
  `backend/tests/unit/test_cv_pipeline_policy.py`).
- Loaded via OpenCV (`cv2.imread`), which returns BGR arrays - `CVPreprocessor`
  already assumes this convention throughout.

## Resolution policy

`DEFAULT_MAX_SIZE = 1920` (longest side, in pixels) is now a named constant in
`pipeline.py`, not just the constructor's default value - `CVPreprocessor`
uses it unless overridden. Images with `max(height, width) > max_size` are
downscaled, aspect ratio preserved, via `cv2.resize`. No padding is applied -
the pipeline works on the image's native aspect ratio.

This is sufficient as a policy for Sprint 1: all 10 dataset diagrams are well
under 1920px on their longest side (max is `2940x1648` for `dotnet_eshop.png`,
which *will* be downscaled - worth noting as the first real resize case to
sanity-check in Sprint 2 when batch preprocessing is implemented).

## Normalization

`CVPreprocessor._normalize` already applies CLAHE (Contrast Limited Adaptive
Histogram Equalization) in LAB color space - appropriate for diagrams that mix
dark-background images (e.g. `dotnet_eshop.png`) with light-background ones
(the other 9).

## Stage list (as implemented in `pipeline.py`, current as of Sprint 10)

This section originally described the Sprint 1 stub; updated after later
sprints actually wired each stage in (most recently, a final audit pass
wired Stage 8 into `CVPipeline.analyze()` - it had been left as a stale
placeholder even after Sprint 5 built the real implementation separately).

1. **Preprocessing** (`CVPreprocessor`) - load, resize, CLAHE normalize. Optional
   `denoise()` (`fastNlMeansDenoisingColored`) remains available but still not
   wired into the default `analyze()` flow (no diagram in the dataset needed
   it; left as an opt-in method).
2. **Edge detection** (`EdgeDetector`) - Canny, used both as a Sprint 2/4
   diagnostic (`analyze()` reports `edge_pixel_count`) and internally by
   Stage 4's segmentation and Stage 8's relationship extraction.
3. **Component detection** (`ComponentDetector`) - pretrained YOLOv8n/COCO
   (Sprint 3). Empirically finds almost nothing real on architecture
   diagrams (`docs/sprint3_detection_baseline.md`) - a documented, expected
   limitation, not a bug.
4. **Segmentation** - `RegionProposalSegmenter` (Sprint 4), the project's
   retained MVP approach after pretrained segmentation was tested and found
   not viable. Not yet called from `CVPipeline.analyze()` (detection is the
   primary path there); available standalone via
   `backend/scripts/evaluate_segmentation_baseline.py`.
5. **CLIP zero-shot classification** (`CLIPClassifier`) - classifies each
   detected region; degrades to `"unknown"` (not an arbitrary type) if CLIP
   isn't installed - an audit-pass fix, since the original fallback silently
   mistyped every component as `"database"` via an unguarded `max()` tie-break
   on all-zero scores.
6. **Relationship extraction** (`CVPipeline._extract_relationships`) - wired
   to the real Sprint 5 geometry extractor (`geometry_relations.py`, the
   project's strongest CV baseline, F1=0.581) as of this audit pass. Returns
   `[]` only when there are zero detected components to relate (there is
   nothing to wire into when detection finds nothing, which - per Stage 3 -
   is most diagrams in this dataset).

## What Sprint 1 actually delivers here

The policy/spec above, now enforced as real constants + a format check in
`pipeline.py` (not just this description), plus the real dataset
(`data/annotations/manifest.json`) the later stages will be developed and
evaluated against. The preprocessing/edge/detection/CLIP *logic* itself is
unchanged this sprint - it's already a correctly-shaped stub; Sprint 2
implements the preprocessing stage for real against this data.

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

## Stage list (as implemented in `pipeline.py`)

1. **Preprocessing** (`CVPreprocessor`) - load, resize, CLAHE normalize. Optional
   `denoise()` (`fastNlMeansDenoisingColored`) available but not yet wired into
   the default `analyze()` flow.
2. **Edge detection** (`EdgeDetector`) - Canny (used by default), LoG and DoG
   available as alternatives. Sprint 2 deliverable: baseline comparison.
3. **Component detection** (`ComponentDetector`) - YOLO wrapper; currently
   returns `[]` with no model loaded. Sprint 3 deliverable: wire a pretrained
   detector.
4. **Segmentation** - not yet a class in `pipeline.py`; Sprint 4 deliverable
   per the roadmap (U-Net or region-cropping fallback).
5. **CLIP zero-shot classification** (`CLIPClassifier`) - classifies each
   detected region against a fixed prompt list; degrades to all-zero scores
   if CLIP isn't installed. Sprint 5 deliverable: evaluate against real
   components.
6. **Relationship extraction** (`CVPipeline._extract_relationships`) -
   explicit `TODO`, returns `[]`. Sprint 5 deliverable per the module's own
   docstring.

## What Sprint 1 actually delivers here

The policy/spec above, now enforced as real constants + a format check in
`pipeline.py` (not just this description), plus the real dataset
(`data/annotations/manifest.json`) the later stages will be developed and
evaluated against. The preprocessing/edge/detection/CLIP *logic* itself is
unchanged this sprint - it's already a correctly-shaped stub; Sprint 2
implements the preprocessing stage for real against this data.

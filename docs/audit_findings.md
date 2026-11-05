# Final Audit: Logic Issues, Dead Code, Errors (Post-Sprint-10)

> **Third pass (post-dataset-correction, post-Docker containerization)**:
> `backend/scripts/derive_bookinfo_diagram.py` loaded `ImageFont.truetype("arial.ttf", 18)`
> with a bare `except OSError: font = ImageFont.load_default()` fallback.
> `arial.ttf` resolves on Windows but not inside the Linux Docker container
> built for this project, so the container silently rendered the
> `istio_bookinfo_derived` diagram with PIL's tiny bitmap default font
> instead - a visibly different image that produced different
> Canny/contour-based segmentation proposal counts (15 proposals locally vs.
> 7 in the container) and a few OCR mismatches (79/95 vs. 77/95), discovered
> by actually running the full pipeline inside the built Docker image and
> diffing the results against the local run, not assumed. Fixed by pointing
> at a fixed, bundled TrueType font instead of an OS-provided one:
> `matplotlib.get_data_path()/fonts/ttf/DejaVuSans.ttf` (matplotlib is
> already a pinned dependency, so this needs no new font file or license in
> the repo). Verified: the regenerated diagram now produces byte-identical
> re-renders across repeated local runs, and every downstream baseline
> (segmentation, embeddings/OCR, geometry relations) now produces
> value-identical results whether run on the Windows host or inside the
> Linux container - confirmed by actually re-running both and diffing.
>
> Two passes: an initial targeted review (below), then a full line-by-line
> re-read of every module in `backend/app/modules/cv_pipeline/` and every
> script in `backend/scripts/` specifically hunting for hardcoded values,
> logic mismatches, and code-cleanliness issues. Second-pass findings:
>
> 1. **`CVPreprocessor._normalize()`/`denoise()` had genuinely hardcoded
>    CLAHE/denoising parameters** (`clipLimit=2.0`, `tileGridSize=(8,8)`,
>    `10, 10, 7, 21`) with no way to override them, inconsistent with the
>    rest of the class (`max_size` already a configurable constructor
>    param). Fixed: promoted to named constants
>    (`DEFAULT_CLAHE_CLIP_LIMIT`/`DEFAULT_CLAHE_TILE_GRID_SIZE`) and
>    constructor/method parameters, same default behavior, now overridable.
> 2. **`render_alignment_overlay.py` reloaded and re-parsed the entire
>    manifest from disk inside `render()`**, called once per diagram -
>    redundant I/O/parsing on every call. Fixed: manifest loaded once in
>    `main()`, the right `ArchGraph` passed in directly. Verified the
>    regenerated PNGs are byte-identical to the previous (correct) output -
>    pure cleanup, no behavior change.
> 3. **`evaluate_detection_baseline.py` rebuilt a linear-search list inside
>    a loop** (`[e["diagram_id"] for e in baseline["results"]].index(...)`)
>    to look up a diagram's entry by id, once per matched true-positive.
>    Fixed: built a `{diagram_id: entry}` dict once instead. Verified
>    byte-identical output.
> 4. **`derive_bookinfo_diagram.py` had `import math` inside a loop body**
>    (re-executed 3 times for no reason). Moved to the top of the file.
>    Verified pixel-identical output (confirmed the image is unaffected;
>    the file's PNG byte size varies a few dozen bytes run-to-run from
>    Pillow's encoder regardless of this change - already investigated and
>    confirmed harmless in Sprint 10's D46 reproducibility check).
> 5. **`scipy` is directly imported** (`EdgeDetector.log()`,
>    `from scipy.ndimage import gaussian_laplace`) **but was never declared
>    in `backend/requirements.txt`** - only present by luck, as a
>    transitive dependency of `scikit-image`/`easyocr`/`ultralytics`. Added
>    explicitly (`scipy==1.17.1`, the version actually resolved in this
>    environment) so the dependency is correct regardless of what other
>    packages happen to pull in.
>
> Everything else checked and found clean: all 17 `cv_pipeline` modules and
> 19 scripts read in full; no other redundant-reload or loop-local-import
> patterns found (`grep` for every `load_manifest()` call site); every
> directly-imported third-party package cross-checked against
> `requirements.txt`; every doc/notebook/experiment artifact referenced in
> `P1-Contributions.md` confirmed to exist on disk. Full suite (89 tests)
> passes and `ruff` is clean after every fix above.

A full pass over every module built across Sprints 1-10, after all 10
sprints were already committed: broader static analysis (`ruff` with
bugbear/simplify/comprehension/ruff-specific rules, `vulture` for dead
code), then manual review of integration points between modules.

## Real issues found and fixed

1. **`CVPipeline._extract_relationships` was a stale placeholder that
   always returned `[]`**, despite its own docstring saying "Full
   implementation in Sprint 5" - and Sprint 5 *did* build a real, tested,
   working geometry-based relation extractor (`geometry_relations.py`,
   the project's strongest CV baseline at F1=0.591). It was simply never
   wired into the orchestrator class. Fixed: `_extract_relationships` now
   calls the real `detect_lines`/`propose_relations` functions. Verified
   end-to-end against a real diagram with real YOLO detections (no crash,
   produces real relationship candidates) and covered by a new regression
   test (`test_extract_relationships_uses_real_geometry_extraction`).
2. **CLIP-unavailable fallback silently mistyped every component as
   `"database"`.** `CLIPClassifier.classify()` returns all-zero scores when
   no CLIP model is loaded; the caller's `max(clip_scores, key=clip_scores.get)`
   tie-broke to the first dict entry ("database") on an all-zero tie,
   presenting a totally arbitrary default as a confident classification.
   Fixed: extracted `select_component_type()`, which returns `"unknown"`
   when CLIP produced no real signal. Covered by 4 new regression tests,
   including one that specifically asserts the old buggy default
   ("database") is no longer produced on a tie.
3. **`CLIPClassifier` and `ComponentEmbedder` downloaded the same ~338MB
   ViT-B/32 weights to two different cache locations**, since
   `CLIPClassifier._load_clip()` never passed `download_root`. Fixed: both
   now share `embeddings.py`'s `DEFAULT_DOWNLOAD_ROOT`
   (`backend/models/clip/`). Verified: a second run no longer re-downloads.
4. **Analyzed components had no stable `id` field**, so relationships
   extracted from them would have had nothing valid to reference as
   `source`/`target` once relationship extraction was actually wired in
   (finding #1 would have been un-testable without this). Fixed: each
   component in `CVPipeline.analyze()`'s output now gets `"id": str(i)`.
5. **Minor**: two unused loop-unpacking variables in `detection_eval.py`
   (`gt_id`, `score`) renamed to `_gt_id`/`_score` for clarity (both were
   genuinely unused - the loop already uses the corresponding index
   instead - not a correctness bug, just unclear naming flagged by
   `ruff --select B007`).

## Stale documentation fixed as a consequence

`docs/cv_pipeline_note.md`'s "Stage list" section was still describing the
Sprint 1 stub (e.g. "Sprint 3 deliverable: wire a pretrained detector" even
though Sprint 3 had long since done so) and explicitly repeated the now-
false "`_extract_relationships` ... explicit `TODO`, returns `[]`" claim.
Rewritten to describe the current, final state of every stage.
`notebooks/01_cv_experiment_template.ipynb`'s markdown and cached output
were also stale (predated the `clip` package being installed in Sprint 5) -
refreshed.

## Checked and confirmed NOT an issue

- `ruff --select RUF012` flags `CLIPClassifier`'s mutable class-level
  `COMPONENT_PROMPTS`/`COMPONENT_TYPE_MAP` lists/dicts - this is in the
  file's original Sprint-0 baseline (copied from `main`, not P1-authored
  code), read-only in practice, and changing it would touch shared-baseline
  code beyond this audit's scope.
- `vulture`'s "unused variable" findings in `backend/app/schemas/models.py`
  are false positives - Pydantic model fields and enum members it can't
  trace through instantiation/serialization, not actual dead code.
- `CVPreprocessor.denoise()` is genuinely never called anywhere - but this
  is intentional and already documented (`docs/cv_pipeline_note.md`): an
  opt-in method no current diagram needed, not a broken promise like
  `_extract_relationships` was.
- Remaining `ruff` style nitpicks (`B905` zip without `strict=`, `C408`/`C420`
  dict-literal preferences, `SIM300` Yoda condition) are cosmetic, mostly in
  test files or loops where the paired sequences are same-length by
  construction - not correctness bugs.

## Verification

All 89 tests pass (6 new regression tests added for the fixes above);
`ruff --select F,E,W` clean; manually re-ran the fixed `CVPipeline.analyze()`
end-to-end against a real diagram with real detections (no crash, varied
real component types, real relationship candidates where geometry
supports them).

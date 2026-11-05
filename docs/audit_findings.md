# Final Audit: Logic Issues, Dead Code, Errors (Post-Sprint-10)

A full pass over every module built across Sprints 1-10, after all 10
sprints were already committed: broader static analysis (`ruff` with
bugbear/simplify/comprehension/ruff-specific rules, `vulture` for dead
code), then manual review of integration points between modules.

## Real issues found and fixed

1. **`CVPipeline._extract_relationships` was a stale placeholder that
   always returned `[]`**, despite its own docstring saying "Full
   implementation in Sprint 5" - and Sprint 5 *did* build a real, tested,
   working geometry-based relation extractor (`geometry_relations.py`,
   the project's strongest CV baseline at F1=0.581). It was simply never
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

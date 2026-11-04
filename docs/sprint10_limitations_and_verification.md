# Sprint 10: Limitations & Claim Verification (D49)

## Verification process

Every quantitative claim in `docs/cv_method_results_report.md` (D48) was
re-read directly from its source JSON file (or recomputed from the live
manifest) immediately before being written down, rather than quoted from
memory or an earlier sprint doc. This caught a real error during writing:
a first draft claimed "112 ground-truth relationships" from memory; the
actual count, read directly from `data/annotations/manifest.json` via
`load_manifest()`, is **110**. Fixed before this doc was finalized - kept
here as evidence the verification step is real, not just a disclaimer.

## Known limitations, stated plainly

1. **Tiny dataset.** 10 diagrams, 89 components, 110 relationships, 2-
   diagram test split. Every percentage in this project should be read as
   "on this small, real, but limited sample" - not a generalizable claim
   about architecture diagrams in general. The Sprint 9 test-split numbers
   are a genuine held-out check, but 2 diagrams is a small enough sample
   that a different random split could shift results meaningfully.
2. **Segmentation's full-dataset number doesn't exist.** Sprint 4 only
   evaluated the region-cropping baseline against a 3-diagram subset
   (`docs/sprint4_segmentation_baseline.md`), not the full 10 - there is no
   full-dataset F1 to compare against the detector/geometry baselines'
   full-dataset numbers. `docs/cv_method_results_report.md` states this
   explicitly rather than filling the gap with an estimate.
3. **The geometry-relations "best baseline" claim is for *this* dataset's
   diagram style** (box-and-straight-arrow technical diagrams). It is not a
   claim that Hough-line geometry would outperform learned detectors on a
   larger, more stylistically diverse diagram corpus - our dataset
   happens to be dominated by exactly the diagram style straight-line
   detection is good at.
4. **Sprint 6's 21/21 alignment accuracy is on an easy subset.**
   `docs/sprint6_graph_alignment_report.md` already flags this: both test
   repositories use clean, diagram-matching directory naming. Harder
   diagrams in our own dataset (grouped/nested components, less literal
   naming) were never empirically tested against real repository listings.
5. **Sprint 7's violation example is illustrative, not real.** The
   `backend -> orders` edge used to demonstrate the evidence pipeline is
   genuinely conformant per our own diagram annotation - the "violation"
   only exists under a deliberately counterfactual rule, stated explicitly
   in `docs/sprint7_git_evidence_report.md`.
6. **No conformance engine exists in this track.** Everything in Sprints
   6-8 that references "violations," "rules," or "conformance reports" uses
   the real shared schema (`backend/app/schemas/models.py`) but there is no
   real rule-evaluation engine behind it - that's P3/P4 scope, not built
   here. P1's contribution is the evidence/alignment/impact machinery that
   such an engine would consume.
7. **OCR/embedding baselines were not evaluated against the frozen test
   split** (only against the full 10 diagrams in Sprint 5) - unlike
   detection/segmentation/geometry, which were specifically re-evaluated
   in Sprint 9.
8. **All experiments ran on CPU**, with a single run each (no repeated
   trials, no confidence intervals) - appropriate given the dataset's size
   and the project's 50-day scope, but worth stating rather than implying
   statistical rigor that wasn't performed.

## What *is* solid

- Every number in `docs/cv_method_results_report.md` is independently
  reproducible: Sprint 10 / D46 performed a full clean-room regeneration of
  every artifact in the project (deleting and rebuilding `data/diagrams/`,
  `backend/models/`, `data/repositories/`, and all of `experiments/`) and
  confirmed every result matched exactly, with the only differences being
  one non-deterministic UUID field (by design) and inconsequential PNG
  encoding bytes (pixel-identical, verified).
- The dataset itself is 100% real (no synthetic/fabricated diagrams or
  annotations) and every diagram is paired with a real, named, licensed
  public repository.

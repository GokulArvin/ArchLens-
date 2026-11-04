# ArchLens — P1 (CV Pipeline Lead) Track

This branch (`Gokul`) implements the **P1 (Computer Vision Pipeline Lead)** role of the
ArchLens project, sprint by sprint, inside the real project structure (see
`backend/app/modules/cv_pipeline/`). ArchLens itself is a 4-member team project —
architecture conformance checking via CV diagram extraction, static analysis, graph
comparison, and evidence-grounded LLM reasoning. See the `main` branch's README for the
full system overview; this branch focuses on P1's slice of it.

`backend/app/schemas/models.py` and `backend/app/modules/cv_pipeline/pipeline.py` were
seeded from the team's already-agreed baseline on `main` (the shared `ArchGraph`
contract and the existing P1 stub with Sprint 3/5/6 TODOs) so this work stays
merge-compatible. See `P1-Contributions.md` for the consolidated list of everything P1
owns across all 10 sprints.

## Setup

```bash
cd backend
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

If you don't have a CUDA GPU, install torch/torchvision from the CPU wheel
index first to avoid a multi-GB download (same pinned versions either way):

```bash
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

YOLOv8n weights (`backend/models/yolov8n.pt`, gitignored) auto-download on
first run of `backend/scripts/inspect_yolo_classes.py` or
`run_detection_baseline.py`.

## Project layout

- `backend/app/modules/cv_pipeline/` — P1's CV pipeline code (preprocessing, edge
  detection, component detection, segmentation, CLIP/ViT classification, relationship
  extraction)
- `backend/app/schemas/models.py` — shared `ArchComponent`/`ArchRelationship`/`ArchGraph`
  contract (owned jointly by the team; P1's output must conform to this)
- `backend/tests/unit/` — P1 unit tests
- `data/diagrams/` — real architecture diagram images, each paired with the real
  repository it describes
- `data/annotations/` — manifest + hand-annotated component/connector ground truth
- `data/repositories/` — references to the real repos each diagram is paired with
- `docs/` — pipeline notes, annotation guide, dataset rationale, schema review, failure
  case tracking
- `notebooks/` — experiment templates (load manifest → preview → run CV steps)

## Data policy

No synthetic or fabricated data is used anywhere in this project. Every diagram is a
real architecture diagram of a real, publicly available software repository, so that
later sprints can compare the diagram's intended structure against that same
repository's actual code/Git history.

## Sprint progress

Tracked in `P1-Contributions.md`.

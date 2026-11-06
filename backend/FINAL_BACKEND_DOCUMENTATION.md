# ArchLens Backend – Final Technical Documentation

## 1. Project Overview
ArchLens is a hybrid architecture conformance checking system combining computer vision, static analysis, deterministic graph comparison and evidence-grounded LLM reasoning.

## 2. Backend Technology
- Python 3.11
- FastAPI
- Pydantic
- NetworkX
- SQLite
- OpenCV and OCR pipeline
- Pytest

## 3. Architecture Pipeline
1. Diagram ingestion and architecture component extraction.
2. Repository ingestion and AST-based dependency recovery.
3. Architecture graph construction and alignment.
4. Deterministic conformance checking.
5. Evidence collection from code and Git history.
6. Evidence-grounded RCA.
7. Report persistence and JSON/HTML export.

The complete multipart workflow is available at `POST /api/v1/analyze-and-check`.
It accepts an uploaded diagram, repository path, language, and optional JSON
manual mappings/ruleset, then persists the aligned conformance report.

The deterministic conformance engine is authoritative for violation decisions. The LLM provides explanations and recommendations only.

## 4. Setup
From the repository root:

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -e backend

If using the existing environment, activate it and install dependencies according to backend/pyproject.toml.

For live LLM root-cause analysis, copy `backend/.env.example` to
`backend/.env`. The default configuration uses local Ollama (`qwen2.5-coder:7b`)
and requires no API key; install Ollama and pull that model first. Hosted
providers remain available by setting `LLM_PROVIDER` and its API key. The
backend loads the environment file regardless of whether the server starts
from the repository root or backend directory.

## 5. Run the API
From the repository root:

    python -m uvicorn app.main:app --reload --app-dir backend

Swagger documentation:

    http://127.0.0.1:8000/docs

## 6. API Endpoints
- POST /api/v1/analyze-diagram
- POST /api/v1/analyze-and-check
- POST /api/v1/analyze-repository
- POST /api/v1/check-conformance
- POST /api/v1/check-conformance/inline
- POST /api/v1/align-graphs
- POST /api/v1/check-conformance/repository
- POST /api/v1/analyze-violation
- GET /api/v1/reports
- GET /api/v1/report/{report_id}
- GET /api/v1/report/{report_id}/export/json
- GET /api/v1/report/{report_id}/export/html
- GET /health

## 7. Testing
From the backend directory:

    python -m pytest -v

Latest recorded result: 322 passed. The real Git-history checks use the public
`flask-microservice-demo` clone in `data/repositories/`; run
`scripts/clone_demo_repo.py` if it is not present in a fresh checkout.

## 8. Experiment Reproduction
Experiment configurations are under configs/experiments/.
Run the adapter using:

    python -m app.modules.evaluation.experiment_adapter --config configs/experiments/static_baseline.json --output-dir data/evaluation

Experiment outputs are stored under data/evaluation/.
Sprint 9 summary artifacts are stored under data/experiments/sprint9_summary/.

## 9. Known Limitations
- The default CV fallback emits low-confidence region proposals, not semantic
  component classifications. Set `CV_YOLO_MODEL_PATH` to use a trained detector;
  region candidates may need manual mappings.
- Hough-line relationship candidates may have uncertain direction.
- Same-graph alignment and conformance runs are integration smoke tests, not independent accuracy evaluations.
- RCA requires sufficient structured evidence; the recorded RCA smoke test returned insufficient_evidence.
- No held-out benchmark accuracy or confidence intervals are claimed.
- LLM RCA requires a configured provider and API credentials for live model analysis.

## 10. Final Validation
The following endpoints returned HTTP 200:
- GET /
- GET /health
- GET /api/v1/reports

The latest recorded backend test suite passed all 322 tests.

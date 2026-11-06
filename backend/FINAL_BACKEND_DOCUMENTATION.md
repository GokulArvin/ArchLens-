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

The deterministic conformance engine is authoritative for violation decisions. The LLM provides explanations and recommendations only.

## 4. Setup
From the repository root:

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -e backend

If using the existing environment, activate it and install dependencies according to backend/pyproject.toml.

## 5. Run the API
From the repository root:

    python -m uvicorn app.main:app --reload --app-dir backend

Swagger documentation:

    http://127.0.0.1:8000/docs

## 6. API Endpoints
- POST /api/v1/analyze-diagram
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

Latest recorded result: 45 passed, 1 non-blocking deprecation warning.

## 8. Experiment Reproduction
Experiment configurations are under configs/experiments/.
Run the adapter using:

    python -m app.modules.evaluation.experiment_adapter --config configs/experiments/static_baseline.json --output-dir data/evaluation

Experiment outputs are stored under data/evaluation/.
Sprint 9 summary artifacts are stored under data/experiments/sprint9_summary/.

## 9. Known Limitations
- The CV detector is an interim OpenCV-based implementation.
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

The latest recorded backend test suite passed all 45 tests.

# ArchLens — Project Setup & Architecture Report

**Document Version:** 1.0.0  
**Date:** October 28, 2026  
**Status:** Completed & Verified  
**Repository:** [https://github.com/GokulArvin/ArchLens-.git](https://github.com/GokulArvin/ArchLens-.git)  
**Authors:** ArchLens Engineering Team (P1, P2, P3, P4)  

---

## 1. Executive Summary

This report documents the foundation setup and initial implementation of **ArchLens**, a multimodal, evidence-grounded software architecture conformance checking platform. 

The project connects two sources of architectural truth:
1. **Intended Architecture ($G_I$)**: Extracted from visual architecture diagrams (UML, microservice flowcharts, C4 models) using Computer Vision (OpenCV, YOLO, ViT, CLIP zero-shot classification).
2. **Implemented/Current Architecture ($G_C$)**: Recovered deterministically from source code repositories using Static Program Analysis (Abstract Syntax Trees, import tracking, and dependency call graphs).

These two graphs are fed into a **deterministic rule-based Conformance Engine** that classifies relationships into explicit verdicts (`CONFORMANT`, `VIOLATION`, `MISSING`, `UNEXPECTED`, `UNCERTAIN`). Detected violations are automatically correlated with version control history via **Git Evidence Extraction** (blame, commit history, and diff pickaxe), and an **Evidence-Grounded LLM Gateway** performs root-cause analysis (RCA), component impact tracing, and architectural remediation recommendations.

---

## 2. Environment & Toolchain Specifications

The environment was configured and validated with the following dependencies:

| Tool / Runtime | Version | Scope |
|---|---|---|
| **OS** | Windows 11 AMD64 | Development Environment |
| **Python** | 3.13.3 (64-bit) | Backend Core, Static Analysis, CV, ML |
| **Node.js** | v24.1.0 | Frontend Dashboard Runtime |
| **npm** | 9.8.1 (upgradeable to 12.2.1) | Package Manager |
| **Git** | 2.51.0.windows.2 | Version Control & Git Evidence Mining |
| **FastAPI** | 0.162.0 | High-performance Async REST API Framework |
| **Uvicorn** | 0.54.0 | ASGI Server |
| **Pydantic** | 2.14.1 | Schema Validation & Data Serialization |
| **NetworkX** | 3.7 | Graph Data Structure & Cycle Analysis |
| **GitPython** | 3.2.1 | Programmatic Git Repository Analysis |
| **React** | 18.3.1 | Single-Page Application Framework |
| **Vite** | 6.4.5 | Frontend Build Tool & Dev Server |
| **TailwindCSS** | 3.4.16 | Utility-first Design System |
| **Docker** | Compose v3.9 compatibility | Multi-container Deployment |

---

## 3. Repository Architecture & GitHub Setup

The project was linked to the official GitHub remote:
```
origin  https://github.com/GokulArvin/ArchLens-.git (fetch)
origin  https://github.com/GokulArvin/ArchLens-.git (push)
```

### Complete Directory Layout
```
ArchLens/
├── .gitignore                      # Configured for Python, Node, data caches, test artifacts
├── README.md                       # Comprehensive project documentation
├── docker-compose.yml              # Multi-container orchestration (FastAPI, React, Postgres)
├── docs/                           # Project documentation & design artifacts
│   ├── ArchLens_50_Day_Scrum_Document (1).docx
│   ├── ArchLens_Implementation_Design.docx
│   ├── PROJECT_SETUP_REPORT.md     # This comprehensive setup document
│   ├── api/                        # OpenAPI specifications & endpoint docs
│   └── research/                   # Benchmark schemas & research notes
├── backend/                        # FastAPI application & ML pipelines
│   ├── .env.example                # Environment variable template
│   ├── Dockerfile                  # Container definition with OpenCV system libs
│   ├── pyproject.toml              # Pytest & build system configuration
│   ├── requirements.txt            # Python dependencies
│   ├── venv/                       # Isolated virtual environment (Python 3.13)
│   ├── app/
│   │   ├── main.py                 # FastAPI application factory & router mounting
│   │   ├── api/routes/             # REST API endpoints
│   │   │   ├── diagram.py          # POST /api/v1/analyze-diagram
│   │   │   ├── repository.py       # POST /api/v1/analyze-repository
│   │   │   ├── conformance.py      # POST /api/v1/check-conformance
│   │   │   ├── violations.py       # POST /api/v1/analyze-violation
│   │   │   └── reports.py          # GET  /api/v1/report/{id}
│   │   ├── core/
│   │   │   └── config.py           # Pydantic Settings (CORS, keys, thresholds)
│   │   ├── modules/
│   │   │   ├── cv_pipeline/        # Module B: Image preprocessing, YOLO, CLIP
│   │   │   ├── architecture_recovery/ # Module D: AST parsing, module graph builder
│   │   │   ├── conformance_engine/ # Module E: Graph matching & rule verification
│   │   │   ├── git_evidence/       # Git blame, log, diff, pickaxe extractor
│   │   │   ├── llm_rca/            # Module F: LLM multi-provider gateway & RCA
│   │   │   ├── graph/              # Module C: Graph model conversion
│   │   │   └── evaluation/         # Module G: Metrics, baselines & ablations
│   │   ├── schemas/
│   │   │   └── models.py           # Shared Pydantic data models
│   │   └── utils/                  # Shared helper functions
│   └── tests/
│       ├── unit/
│       │   └── test_conformance_engine.py  # Unit tests for Module E (5/5 passed)
│       └── integration/
├── frontend/                       # React 18 + Vite dashboard
│   ├── index.html                  # HTML entry point
│   ├── package.json                # Frontend dependencies
│   ├── vite.config.js              # Vite bundler & API reverse proxy configuration
│   ├── tailwind.config.js          # Tailwind CSS styling setup
│   ├── postcss.config.js           # PostCSS plugins
│   ├── dist/                       # Tested production build artifact
│   └── src/
│       ├── main.jsx                # React DOM root mounting
│       ├── App.jsx                 # Client-side router configuration
│       ├── index.css               # Tailwind directives & base styles
│       ├── components/
│       │   └── Layout.jsx          # App shell with responsive sidebar & nav
│       ├── pages/
│       │   ├── Dashboard.jsx       # Overview, metrics & quick start
│       │   ├── DiagramAnalysis.jsx # Diagram upload & CV inspector
│       │   ├── RepositoryAnalysis.jsx # AST repository scanner
│       │   └── ConformanceReport.jsx  # Violation & RCA viewer
│       └── services/
│           └── api.js              # Axios HTTP client service
├── data/                           # Datasets, uploads & benchmark data
│   ├── annotations/
│   ├── benchmarks/
│   ├── datasets/
│   ├── diagrams/
│   ├── repositories/
│   └── uploads/
└── experiments/                    # Baselines, ablations & experimental metrics
    ├── ablations/
    ├── baselines/
    └── results/
```

---

## 4. Architectural Modules Implementation Status

### Module A & Schemas: Architecture Representations
- **File:** [`backend/app/schemas/models.py`](file:///c:/Users/bhumi/OneDrive/Documents/Projects/Archlens/ArchLens/backend/app/schemas/models.py)
- **Implemented Entities:**
  - `ArchComponent`: Component entity with bounding box coordinates, component type (`service`, `database`, `queue`, `gateway`, `frontend`, `cache`, `external`), confidence score, and metadata.
  - `ArchRelationship`: Directed edge with source ID, target ID, relationship type (`depends_on`, `calls`, `inherits`, `implements`, `uses`, `contains`), and confidence.
  - `ArchGraph`: Unified graph model representing either intended architecture ($G_I$) or current architecture ($G_C$).
  - `ArchViolation`: Detailed violation record with explicit verdict (`CONFORMANT`, `VIOLATION`, `MISSING`, `UNEXPECTED`, `UNCERTAIN`), violation category (`layer_violation`, `forbidden_dependency`, `missing_dependency`, `cycle_violation`), and severity rating (`low`, `medium`, `high`, `critical`).
  - `GitEvidence` & `GitCommit`: Structured representations of introducing commits, file paths, and commit diffs.
  - `RCAOutput`: Strictly typed root-cause analysis with violation explanation, root-cause identification, cited evidence list, affected components list, architectural recommendation, and confidence score.

### Module B: Computer Vision Pipeline
- **File:** [`backend/app/modules/cv_pipeline/pipeline.py`](file:///c:/Users/bhumi/OneDrive/Documents/Projects/Archlens/ArchLens/backend/app/modules/cv_pipeline/pipeline.py)
- **Implemented Stages:**
  - `CVPreprocessor`: Dynamic aspect-ratio resizing, CLAHE (Contrast Limited Adaptive Histogram Equalization) in LAB color space, and Non-Local Means denoising.
  - `EdgeDetector`: Standardized baselines for Canny edge detection, Laplacian of Gaussian (LoG), and Difference of Gaussians (DoG).
  - `ComponentDetector`: Interface for YOLO-based component bounding-box localization.
  - `CLIPClassifier`: Zero-shot semantic classification of diagram subregions against architectural prompts ("a database component", "a web service", "a message queue", etc.).
  - `CVPipeline`: End-to-end coordinator transforming uploaded diagram images into $G_I$.

### Module D: Source-Code Architecture Recovery (AST)
- **File:** [`backend/app/modules/architecture_recovery/ast_parser.py`](file:///c:/Users/bhumi/OneDrive/Documents/Projects/Archlens/ArchLens/backend/app/modules/architecture_recovery/ast_parser.py)
- **Features:**
  - `PythonASTParser`: Recursively parses Python source files into Abstract Syntax Trees, extracting classes, inheritance hierarchies, standard imports (`import x`), from-imports (`from x import y`), functions, and call expressions.
  - `DependencyGraphBuilder`: Resolves imports against the repository root, filters external packages, maps file paths to dotted module identifiers, and infers component roles (controller, service, repository, model, utility).
  - Produces current architecture graph $G_C$.

### Module E: Conformance Engine
- **File:** [`backend/app/modules/conformance_engine/engine.py`](file:///c:/Users/bhumi/OneDrive/Documents/Projects/Archlens/ArchLens/backend/app/modules/conformance_engine/engine.py)
- **Deterministic Rules Implemented:**
  - `LayeredArchitectureRule`: Enforces strict layering constraints (e.g., controllers must not bypass services to directly import repositories or databases).
  - `ForbiddenDependencyRule`: Flags edges present in $G_C$ that violate explicit domain constraints.
  - `MissingDependencyRule`: Flags expected architectural edges present in $G_I$ that are missing in $G_C$.
  - `UnexpectedDependencyRule`: Detects unmapped connections in implementation not accounted for in design.
  - `CycleDetectionRule`: Uses NetworkX Tarjan/Johnson cycle algorithms to detect circular architectural dependencies.

### Git Evidence Extractor
- **File:** [`backend/app/modules/git_evidence/extractor.py`](file:///c:/Users/bhumi/OneDrive/Documents/Projects/Archlens/ArchLens/backend/app/modules/git_evidence/extractor.py)
- **Features:**
  - Leverages `GitPython` to perform blame analysis on target files.
  - Implements Git pickaxe (`git log -S <symbol>`) to identify the exact historical commit that introduced the offending import or dependency.
  - Extracts the patch diff and commit message, packaging them into an evidence container for LLM reasoning.

### Module F: Evidence-Grounded LLM RCA
- **File:** [`backend/app/modules/llm_rca/analyzer.py`](file:///c:/Users/bhumi/OneDrive/Documents/Projects/Archlens/ArchLens/backend/app/modules/llm_rca/analyzer.py)
- **Features:**
  - Multi-provider client abstraction supporting OpenAI (`gpt-4o`), Google Gemini (`gemini-1.5-pro` / `gemini-2.0-flash`), and Anthropic (`claude-3-5-sonnet`).
  - Exponential backoff retry handler with `tenacity`.
  - System prompt enforcing strict evidence grounding: prevents the model from hallucinating non-existent files or dependencies.
  - Fallback placeholder analyzer for offline or non-API testing.

---

## 5. Verification & Testing Results

### 1. Backend Unit Test Suite
Ran `pytest` within the activated Python virtual environment:
```powershell
backend\venv\Scripts\pytest
```
**Results:**
```
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\bhumi\OneDrive\Documents\Projects\Archlens\ArchLens\backend
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.1, cov-7.1.0
collected 5 items

tests/unit/test_conformance_engine.py::test_conformant_graph PASSED          [ 20%]
tests/unit/test_conformance_engine.py::test_forbidden_dependency_detected PASSED [ 40%]
tests/unit/test_conformance_engine.py::test_missing_dependency_detected PASSED [ 60%]
tests/unit/test_conformance_engine.py::test_cycle_detection PASSED           [ 80%]
tests/unit/test_conformance_engine.py::test_summary_counts PASSED            [100%]

============================== 5 passed in 1.29s ==============================
```

### 2. Frontend Production Build Verification
Ran `npm run build` within `frontend/`:
```
> archlens-frontend@0.1.0 build
> vite build

vite v6.4.5 building for production...
transforming...
✓ 1690 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.54 kB │ gzip:  0.36 kB
dist/assets/index-E0E8gX1S.css   11.77 kB │ gzip:  3.07 kB
dist/assets/index-DV8TP2Ax.js   271.25 kB │ gzip: 89.30 kB
✓ built in 14.41s
```

### 3. Git Commit & Push Verification
All code changes were staged and pushed to the upstream repository:
- **Commit SHA:** `fd05dba1abb3140266eb33232ffb88d4c25a9ce0`
- **Branch:** `main` tracking `origin/main`
- **Status:** Clean working tree, 55 files committed, 7,162 insertions.

---

## 6. Sprint Roadmap & Alignment (50-Day Scrum Plan)

The implementation maps to the 10-sprint plan:

```
[Sprint 1: Days 1-5]   -> COMPLETED: Foundation, Schemas, Architecture, Git, Initial Test Suite
[Sprint 2: Days 6-10]  -> NEXT UP: CV Preprocessing + Static Source Code Ingestion Pipeline
[Sprint 3: Days 11-15] -> Component Detection (YOLO) + Java/Tree-sitter Dependency Extraction
[Sprint 4: Days 16-20] -> Segmentation (U-Net) + Graph Confidence Metrics & Visualization
[Sprint 5: Days 21-25] -> VLM / ViT / CLIP Relationship Extraction & Geometry Reasoning
[Sprint 6: Days 26-30] -> Graph Matching, Alignment, Conformance Engine Verification
[Sprint 7: Days 31-35] -> Git Evidence Collector Integration + Evidence-Grounded LLM RCA
[Sprint 8: Days 36-40] -> Dependency Traversal, Impact Analysis & Recommendation Generator
[Sprint 9: Days 41-45] -> Evaluation, Baselines (LLM-only, Static-only, CV-only), Ablations
[Sprint 10: Days 46-50]-> Final System Integration, Live Benchmark Evaluation, Paper & Demo
```

---

## 7. Next Actions for Sprint 2 (Days 6–10)
1. **P1 (CV Lead):** Refine CLAHE, image normalization parameters, and benchmark diagram dataset preprocessing.
2. **P2 (VLM/Prompting Lead):** Build diagram annotation templates and initial prompt engineering for structured VLM output.
3. **P3 (Static Analysis Lead):** Add Java AST / Tree-sitter grammars to support cross-language repositories.
4. **P4 (Backend/Integration Lead):** Connect SQLite / PostgreSQL persistence to store graphs and generated conformance reports.

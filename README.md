# ArchLens 🔍

**Architecture Conformance Checking with Computer Vision, Static Analysis and Evidence-Grounded LLM Reasoning**

ArchLens is a multimodal, evidence-grounded conformance pipeline that:
1. Uses **Computer Vision / VLMs** to convert architecture diagrams → structured architectural intent graph (G_I)
2. Uses **Static Program Analysis** (AST) to recover the implemented architecture graph (G_C)
3. Uses **Deterministic Graph Rules** to detect conformance violations
4. Uses **LLM + Git evidence** to perform root-cause, impact, and recommendation analysis

> **Design Principle**: The LLM is a *semantic reasoning* component, not the final authority on deterministic architectural facts.

---

## 📁 Project Structure

```
ArchLens/
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── api/routes/        # REST API endpoints
│   │   ├── core/              # Config, logging, settings
│   │   ├── modules/
│   │   │   ├── cv_pipeline/       # Module B: CV diagram analysis
│   │   │   ├── architecture_recovery/ # Module D: AST-based recovery
│   │   │   ├── graph/             # Module C: Architecture graph model
│   │   │   ├── conformance_engine/ # Module E: Conformance rules
│   │   │   ├── git_evidence/      # Git blame/log/diff analysis
│   │   │   ├── llm_rca/           # Module F: LLM RCA reasoning
│   │   │   └── evaluation/        # Module G: Baselines & metrics
│   │   ├── schemas/           # Pydantic data models
│   │   └── utils/             # Shared utilities
│   └── tests/
├── frontend/                  # React dashboard
│   └── src/
│       ├── components/
│       ├── pages/
│       └── services/
├── data/                      # Datasets, diagrams, benchmarks
├── experiments/               # Baselines, ablations, results
├── docs/                      # Research docs, API docs
├── scripts/                   # Utility scripts
└── docker/                    # Docker configs
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

### Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker-compose up --build
```

---

## 🏗️ System Architecture

```
ARCHITECTURE DIAGRAM
       |
       v
CV Pipeline (resize, denoise, edge detection)
       |
   +---+---+
   v       v
Detection  Segmentation
   |       |
   +---+---+
       v
ViT / VLM / CLIP semantic analysis
       |
       v
INTENDED GRAPH (G_I)

SOURCE CODE → AST + Static Analysis → CURRENT GRAPH (G_C)

G_I + G_C → CONFORMANCE ENGINE → VIOLATION?
                                      |
                              EVIDENCE COLLECTOR
                              (code + git diff)
                                      |
                                  LLM / AGENT
                                      |
                     Root Cause → Impact → Recommendation
```

---

## 📋 50-Day Sprint Plan

| Sprint | Days | Focus |
|--------|------|-------|
| 1 | 1–5 | Foundation, dataset, architecture design |
| 2 | 6–10 | CV preprocessing + source-code ingestion |
| 3 | 11–15 | Component detection + architecture recovery |
| 4 | 16–20 | Segmentation + architecture graph |
| 5 | 21–25 | VLM, ViT, CLIP, relationship extraction |
| 6 | 26–30 | Conformance engine |
| 7 | 31–35 | Git evidence + LLM RCA |
| 8 | 36–40 | Impact analysis + recommendations |
| 9 | 41–45 | Evaluation, baselines, ablations |
| 10 | 46–50 | Final integration, paper, demo |

---

## 🔬 Research Questions

- **RQ1**: How accurately can architecture components/relationships be extracted from diagrams using CV/VLM?
- **RQ2**: How accurately can intended and implemented architectures be aligned?
- **RQ3**: Does static analysis + LLM reasoning improve conformance detection?
- **RQ4**: Does Git evidence improve root-cause localization?
- **RQ5**: Which evidence sources contribute most?

---

## 📦 Tech Stack

| Layer | Tools |
|-------|-------|
| Computer Vision | OpenCV, PyTorch, YOLO, U-Net, ViT, CLIP |
| Program Analysis | Python AST, Tree-sitter |
| Version Control | GitPython |
| Graph Reasoning | NetworkX |
| LLM | OpenAI / Gemini API (structured JSON output) |
| Backend | FastAPI |
| Frontend | React + Vite |
| Experimentation | pandas, scikit-learn, MLflow |
| Deployment | Docker |

---

## 🤝 Team

4-member research team (P1, P2, P3, P4) following Scrum methodology with 5-day sprints.

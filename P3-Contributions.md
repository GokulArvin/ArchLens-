# P3 (Static Analysis / Graph Conformance Lead) — Consolidated Contributions Tracker

Every deliverable P3 owns across the 50-day / 10-sprint ArchLens plan, extracted from `ArchLens_Detailed_50_Day_Person_Sprint_Plan.docx`.

---

## Recurring Threads (Cross-Sprint Groupings)

- **AST Parsing & Architecture Recovery**:
  - Sprint 1 (Parser strategy & initial graph schemas)
  - Sprint 2 (Python AST visitor & Java Tree-sitter integration)
  - Sprint 3 (Dependency graph builder with `CALLS` and `INHERITS` edges)
- **Graph Modeling & Integrity**:
  - Sprint 4 (NetworkX `ArchGraphBuilder`, `PackageGraphAggregator`)
  - Sprint 5 (Graph integrity auditing: endpoints, self-loops, cycle detection, round-trip serialization)
  - Sprint 6 (Directed relation candidate detection via endpoint edge density)
- **Deterministic Conformance Engine**:
  - Sprint 1 (5-verdict taxonomy & `ALLOW`/`FORBID`/`REQUIRE` rule schema)
  - Sprint 7 (Layer violation rules, boundary violation rules, circular dependency checks)
  - Sprint 8 (Architecture-aware correction safety validation)
- **Impact & Evidence Mining**:
  - Sprint 7 (`git_evidence_p3.py` candidate commit retrieval, blame analysis, specificity ranking)
  - Sprint 8 (Upstream/downstream graph traversal, transitive BFS blast-radius calculation)
- **Evaluation & Release Stabilization**:
  - Sprint 9 (`ConformanceEvaluator`, `RCAEvaluator`, baseline comparison script & JSON output)
  - Sprint 10 (End-to-end demo walkthrough, methodology paper section, limitations audit)

---

## Sprint 1 — Days 1–5: Scope, Interfaces & Shared Graph Schemas ✅ *done*
- [x] **D1**: Define node/edge vocabulary and violation categories.
- [x] **D2**: Specify intended graph $G_I$ and current graph $G_C$ versioned schemas.
- [x] **D3**: Define `ALLOW`/`FORBID`/`REQUIRE` rule representation and 5-verdict taxonomy (`CONFORMANT`, `VIOLATION`, `MISSING`, `UNEXPECTED`, `UNCERTAIN`).
- [x] **D4**: Select parser strategy for target languages (Python built-in AST + Java Tree-sitter).
- [x] **D5**: Write graph and conformance unit-test fixtures (`test_conformance_engine.py`).

**Deliverables**: `app/schemas/models.py`, `app/schemas/vocabulary.py`, `docs/SPRINT_1_P3_COMPLETION_REPORT.md`.

---

## Sprint 2 — Days 6–10: Multi-Language AST Parsers ✅ *done*
- [x] **D6**: Implement `BaseLanguageParser` ABC.
- [x] **D7**: Implement `PythonASTParser` extracting classes, functions, imports, from-imports, call targets.
- [x] **D8**: Implement `JavaTreeSitterParser` for multi-language repositories.
- [x] **D9**: Normalize parser outputs into common node/edge models.
- [x] **D10**: Unit test suite for parsing on sample code.

**Deliverables**: `app/modules/architecture_recovery/ast_parser.py`, `tests/unit/test_ast_parser.py`, `tests/unit/test_java_parser.py`.

---

## Sprint 3 — Days 11–15: Dependency Graph & Second Detector Baseline ✅ *done*
- [x] **D11**: Compare second detector baseline (`FasterRCNNDetector` on COCO weights).
- [x] **D12**: Extract method calls and inheritance evidence from code.
- [x] **D13**: Construct `DependencyGraphBuilder` aggregating file/class nodes.
- [x] **D14**: Build current graph $G_C$ with NetworkX.
- [x] **D15**: Test dependency edges and confidence scoring.

**Deliverables**: `FasterRCNNDetector` in `pipeline.py`, `tests/unit/test_component_detection.py`, `tests/unit/test_confidence_metrics.py`.

---

## Sprint 4 — Days 16–20: NetworkX Graph Builder & Package Aggregation ✅ *done*
- [x] **D11**: Expose `ArchGraphBuilder` for Pydantic/JSON ↔ NetworkX conversion.
- [x] **D12**: Map file/class entities to packages (`PackageGraphAggregator`).
- [x] **D13**: Filter intra-package cycles while retaining maximum edge confidence.
- [x] **D14**: Construct $G_C$ from recovered dependencies.
- [x] **D15**: Unit test graph edges against inspected examples.

**Deliverables**: `app/modules/graph/builder.py`, `tests/unit/test_graph_builder.py`.

---

## Sprint 5 — Days 21–25: Graph Integrity & Serialization Round-Trips ✅ *done*
- [x] **D16**: Audit connector evidence and confidence tracking.
- [x] **D17**: Define node/edge provenance and confidence attributes.
- [x] **D18**: Implement geometric candidate relation checks.
- [x] **D19**: Implement `GraphIntegrityChecker` (missing endpoints, self-loops, out-of-range confidence, simple cycles).
- [x] **D20**: Serialization round-trip validation (`to_schema_dict`, `to_json`, `to_dot`).

**Deliverables**: `app/modules/graph/integrity.py`, `test_graph_builder.py` round-trip tests.

---

## Sprint 6 — Days 26–30: Directed Connectors & Relation Comparison ✅ *done*
- [x] **D21**: CLIP zero-shot classification evaluation.
- [x] **D22**: Compare prompt keywords for architectural component types.
- [x] **D23**: Implement `propose_directed_relations()` utilizing local edge density around Hough line endpoints.
- [x] **D24**: Graph consistency checks rejecting impossible endpoints.
- [x] **D25**: Relation method comparison script (`compare_relation_methods.py`) and dev-split baseline artifact.

**Deliverables**: `geometry_relations.py` directed extension, `backend/scripts/compare_relation_methods.py`, `experiments/baselines/sprint6_p3_relation_comparison.json`.

---

## Sprint 7 — Days 31–35: Conformance Rules & Git History Evidence ✅ *done*
- [x] **D26**: Implement `LayerViolationRule` enforcing top-down architectural hierarchy.
- [x] **D27**: Implement `BoundaryViolationRule` enforcing module domain isolation.
- [x] **D28**: Implement Tarjan/Johnson cycle violation detection on $G_C$.
- [x] **D31**: Enumerate candidate introducing commits via git pickaxe (`find_candidate_commits_p3`).
- [x] **D32**: Blame line-range commit attribution (`blame_line_range`).
- [x] **D34**: Specificity ranking (`rank_candidate_commits`) with merge and rename penalties.
- [x] **D35**: Document known limits for merge commits, renames, and shallow clones.

**Deliverables**: `conformance_engine/engine.py` extensions, `app/modules/cv_pipeline/git_evidence_p3.py`, `tests/unit/test_git_evidence_p3.py`, `docs/sprint7_p3_conformance_report.md`.

---

## Sprint 8 — Days 36–40: Impact Traversal & Correction Safety ✅ *done*
- [x] **D36**: Upstream and downstream traversal on $G_C$.
- [x] **D37**: Direct and transitive blast-radius calculation (`transitive_impact`).
- [x] **D38**: Architecture-aware correction safety validation (`validate_correction_edges`).
- [x] **D39**: Test suite for cycles, disconnected nodes, and repeated paths.
- [x] **D40**: Machine-readable impact summary (`compute_impact_summary`) with severity classification.

**Deliverables**: `app/modules/cv_pipeline/impact_analysis.py` extensions, `tests/unit/test_impact_extended.py`.

---

## Sprint 9 — Days 41–45: Baselines, Ablations & Conformance Evaluation ✅ *done*
- [x] **D41**: Verify ground-truth conformance labels.
- [x] **D42**: Build `ConformanceEvaluator` measuring Precision, Recall, and F1 across verdicts.
- [x] **D43**: Build `RCAEvaluator` measuring Top-1, Top-3, and Top-5 introducing-commit accuracy.
- [x] **D44**: Implement runnable comparison script `evaluate_conformance_baselines.py`.
- [x] **D45**: Generate baseline evaluation JSON artifact (`sprint9_p3_conformance_evaluation.json`).

**Deliverables**: `app/modules/evaluation/conformance_metrics.py`, `app/modules/evaluation/__init__.py`, `scripts/evaluate_conformance_baselines.py`, `tests/unit/test_conformance_metrics.py`, `experiments/baselines/sprint9_p3_conformance_evaluation.json`.

---

## Sprint 10 — Days 46–50: Stabilization, Paper Section & Demo Walkthrough ✅ *done*
- [x] **D46**: Rerun conformance suite and verify controlled violation scenarios.
- [x] **D47**: Audit schemas, rule representations, and metric computations.
- [x] **D48**: Author conformance and graph methodology paper section with explicit limitations.
- [x] **D49**: Clean-room test verification (92 automated tests passing) and code stabilization.
- [x] **D50**: End-to-end runnable demonstration walkthrough covering $G_I \to G_C \to$ Conformance $\to$ Blast Radius $\to$ Git Evidence $\to$ Evaluation.

**Deliverables**:
- `docs/sprint10_p3_conformance_methodology_and_limitations.md`
- `backend/scripts/demo_p3_conformance_pipeline.py`
- `P3-Contributions.md`

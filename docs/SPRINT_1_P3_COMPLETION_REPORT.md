# ArchLens — Sprint 1 (Person 3: Static Analysis & Graph Lead) Completion Report

**Sprint:** Sprint 1 — Days 1–5 (Scope, Dataset, Interfaces and Shared Schemas)  
**Role:** P3 — Static Analysis & Graph Lead  
**Branch:** `Bhumika`  
**Status:** 100% Complete & Verified  

---

## 1. Executive Summary

All items assigned to **Person 3 (P3)** in **Sprint 1** of the 50-day Scrum Plan have been implemented, tested, and verified against project requirements and acceptance criteria.

### Sprint 1 P3 Deliverables & Acceptance Criteria
> **Acceptance Criteria:** Versioned graph schema; rule schema; example graphs; initial unit tests for `CONFORMANT`, `VIOLATION`, `MISSING`, `UNEXPECTED` and `UNCERTAIN`.

| Day | Task Description | Status | Deliverables & Artifacts |
|---|---|---|---|
| **D1** | Define node/edge vocabulary and violation categories | **Complete** | [`app/schemas/vocabulary.py`](file:///backend/app/schemas/vocabulary.py), [`app/schemas/models.py`](file:///backend/app/schemas/models.py) |
| **D2** | Specify intended graph $G_I$ and current graph $G_C$ schemas | **Complete** | [`ArchGraph`, `IntendedGraph`, `CurrentGraph`](file:///backend/app/schemas/models.py), [`example_GI.json`](file:///backend/app/schemas/examples/example_GI.json), [`example_GC_conformant.json`](file:///backend/app/schemas/examples/example_GC_conformant.json) |
| **D3** | Define ALLOW/FORBID/REQUIRE rule representation and verdict taxonomy | **Complete** | [`RuleAction`, `RuleSet`, `ArchitectureRule`](file:///backend/app/schemas/models.py), [`example_ruleset.json`](file:///backend/app/schemas/examples/example_ruleset.json), Conformance Engine 5-verdict support |
| **D4** | Select parser strategy for first target language & test small repository | **Complete** | Python AST deterministic parser in [`app/modules/architecture_recovery/ast_parser.py`](file:///backend/app/modules/architecture_recovery/ast_parser.py), sample repository fixture in [`tests/fixtures/sample_repo`](file:///backend/tests/fixtures/sample_repo) |
| **D5** | Write graph and conformance unit-test examples | **Complete** | 18 automated tests passing in [`tests/unit/test_conformance_engine.py`](file:///backend/tests/unit/test_conformance_engine.py), [`tests/unit/test_ast_parser.py`](file:///backend/tests/unit/test_ast_parser.py), [`tests/integration/test_conformance_api.py`](file:///backend/tests/integration/test_conformance_api.py) |

---

## 2. Detailed Technical Breakdown

### D1: Node/Edge Vocabulary & Violation Categories
- **Node Vocabulary (`ComponentType`)**:
  - Module C core types: `component`, `service`, `database`, `queue`, `gateway`, `frontend`, `cache`, `external`, `external_system`, `module`, `interface`.
  - Layered architecture roles inferred from static analysis: `controller`, `repository`, `model`, `utility`.
- **Edge Vocabulary (`RelationshipType`)**:
  - `depends_on`, `calls`, `inherits`, `implements`, `uses`, `contains`, `publishes_to`, `reads_from`, `writes_to`.
- **Violation Categories (`ViolationType`)**:
  - `layer_violation`, `forbidden_dependency`, `missing_dependency`, `unexpected_dependency`, `cycle_violation`, `interface_violation`, `uncertain_dependency`.

### D2: Versioned Graph Schemas ($G_I$ and $G_C$)
- Both graph schemas inherit from `ArchGraph` with `schema_version = "1.0.0"`.
- `IntendedGraph`: Graph representation for visual diagrams ($G_I$).
- `CurrentGraph`: Graph representation recovered from source code AST ($G_C$).
- Example graphs provided:
  - `example_GI.json`: C4 / 3-tier intended architecture (Frontend → Controller → Service → Repository → Database).
  - `example_GC_conformant.json`: Validated conformant implementation graph.
  - `example_GC_violations.json`: Implementation graph containing forbidden bypasses, missing relationships, unexpected dependencies, and low-confidence uncertain edges.

### D3: ALLOW / FORBID / REQUIRE Rule Schema & Verdict Taxonomy
- **Rule Representation**:
  - `RuleAction`: `ALLOW`, `FORBID`, `REQUIRE`.
  - `ArchitectureRule`: Models constraint name, action, source/target filters, relation types, and severity.
  - `RuleSet`: Versioned collection of architectural rules (`schema_version = "1.0.0"`) with configurable `confidence_threshold` (default `0.6`).
- **5-Verdict Taxonomy**:
  1. `CONFORMANT`: Expected edge exists and is allowed.
  2. `VIOLATION`: A forbidden dependency exists (e.g., Controller → Repository bypass, circular dependency).
  3. `MISSING`: A required relationship defined in $G_I$ or in a `REQUIRE` rule is absent in $G_C$.
  4. `UNEXPECTED`: Implementation contains an architectural dependency not represented in $G_I$ and not allowed.
  5. `UNCERTAIN`: Extraction confidence is below threshold or evidence is ambiguous.

### D4: Target Language Parser Strategy & Small Repository Fixture
- **Strategy**: Python standard `ast` module (deterministic AST-based dependency recovery).
- **Extraction Capabilities**:
  - File-level & package-level imports (`import x`, `from x import y`).
  - Relative import resolution (`from . import x`, `from ..services import y`).
  - Class definitions, methods, function calls, and decorators.
  - Heuristic architectural role inference (`controller`, `service`, `repository`, `model`).
- **Sample Repository Fixture** (`backend/tests/fixtures/sample_repo/`):
  - Standard 3-tier structure (`controllers`, `services`, `repositories`, `models`).
  - Includes an intentional architectural layer violation (`OrderController` directly importing `OrderRepository`) for automated verification.

### D5: Test Suite & Verification Results
- **18 / 18 tests passing** (14 unit tests, 4 integration tests):
  - `test_parse_single_file`: AST class and method extraction.
  - `test_parse_directory`: Directory traversal and filtering.
  - `test_dependency_graph_builder`: Edge generation and role inference.
  - `test_architecture_recovery_pipeline_end_to_end`: Pydantic validation of recovered graph.
  - `test_conformant_graph`: Verified `CONFORMANT` verdict.
  - `test_forbidden_dependency_detected`: Verified `VIOLATION` verdict.
  - `test_cycle_detection`: Verified circular dependency violation.
  - `test_missing_dependency_detected`: Verified `MISSING` verdict.
  - `test_unexpected_dependency_detected`: Verified `UNEXPECTED` verdict.
  - `test_uncertain_verdict_low_confidence`: Verified `UNCERTAIN` verdict.
  - `test_allow_forbid_require_ruleset`: Verified custom `RuleSet` evaluation.
  - `test_summary_counts`: Verified multi-verdict summary counts.
  - `test_versioned_schemas_serialization`: Verified schema round-trip serialization.
  - `test_example_json_fixtures`: Verified JSON examples against conformance engine.
  - Integration API tests for `/api/v1/check-conformance/inline` and `/api/v1/analyze-repository`.

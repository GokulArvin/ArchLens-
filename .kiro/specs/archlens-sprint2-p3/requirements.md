# Requirements Document

## Introduction

Sprint 2 Person 3 (P3 — Static Analysis & Graph Lead) extends the ArchLens backend with multi-language static analysis, graph confidence scoring, and CI/CD automation. Building on the Sprint 1 foundation (Python AST parser, DependencyGraphBuilder, ArchitectureRecoveryPipeline, ConformanceEngine with 5-verdict taxonomy, and versioned Pydantic schemas), this sprint delivers:

1. A `BaseLanguageParser` abstract class that `PythonASTParser` and a new `JavaTreeSitterParser` both implement, establishing a common parse schema across languages.
2. Multi-language support in `ArchitectureRecoveryPipeline` via auto-detection of `.py` and `.java` files under a `"mixed"` language mode.
3. Confidence scores on extracted graph edges and component nodes, feeding directly into the `ConformanceEngine`'s `UNCERTAIN` verdict at threshold 0.6.
4. Java fixture files (mirroring the Python 3-tier sample repo) and comprehensive pytest tests covering the Java parser, graph builder, and all confidence levels.
5. A GitHub Actions CI workflow that runs pytest with coverage and ruff lint on every push/PR to `main` and `Bhumika` branches.

## Glossary

- **BaseLanguageParser**: The abstract base class that defines the common interface all language parsers must implement: `parse_file`, `parse_directory`, `supported_extensions`.
- **PythonASTParser**: The existing Python source parser (Sprint 1) refactored to extend `BaseLanguageParser`.
- **JavaTreeSitterParser**: The new Java source parser built on the `tree-sitter` library with the `tree-sitter-java` grammar, extending `BaseLanguageParser`.
- **DependencyGraphBuilder**: The existing graph builder extended with `build_from_java()` and confidence scoring.
- **ArchitectureRecoveryPipeline**: The existing orchestrator extended with `"mixed"` language mode.
- **CurrentGraph**: The Pydantic schema for the extracted current architecture graph (G_C), output of the pipeline.
- **ConformanceEngine**: The existing deterministic conformance checker; the `UNCERTAIN` verdict fires when edge confidence < 0.6.
- **ParseResult**: The common dict schema produced by any parser: `{file, classes, imports, methods, metadata}`.
- **ConfidenceScore**: A float in [0.0, 1.0] assigned to graph edges and component nodes indicating extraction certainty.
- **CI_Workflow**: The GitHub Actions YAML file that automates build, test, and lint on every relevant push or pull request.
- **sample_java_repo**: The Java fixture directory under `backend/tests/fixtures/` mirroring the Python `sample_repo` 3-tier structure.

---

## Requirements

### Requirement 1: Abstract Base Parser Interface

**User Story:** As a backend engineer, I want a common abstract parser interface, so that all language parsers share the same API and can be used interchangeably by the pipeline.

#### Acceptance Criteria

1. THE `BaseLanguageParser` SHALL define an abstract method `parse_file(path: str) -> Dict[str, Any]` that subclasses must implement.
2. THE `BaseLanguageParser` SHALL define an abstract method `parse_directory(path: str) -> List[Dict[str, Any]]` that subclasses must implement.
3. THE `BaseLanguageParser` SHALL define an abstract method `supported_extensions() -> List[str]` that returns the file extensions handled by the subclass.
4. WHEN a subclass does not implement all abstract methods, THE `BaseLanguageParser` SHALL raise `TypeError` on instantiation.
5. THE `PythonASTParser` SHALL extend `BaseLanguageParser` and implement all three abstract methods, preserving its existing behaviour.
6. THE `PythonASTParser.supported_extensions()` SHALL return `[".py"]`.

---

### Requirement 2: Java Tree-sitter Parser

**User Story:** As a backend engineer, I want a Java parser using `tree-sitter`, so that the system can extract architectural entities from Java source files in the same schema as the Python parser.

#### Acceptance Criteria

1. THE `JavaTreeSitterParser` SHALL extend `BaseLanguageParser` and implement `parse_file`, `parse_directory`, and `supported_extensions`.
2. THE `JavaTreeSitterParser.supported_extensions()` SHALL return `[".java"]`.
3. WHEN `JavaTreeSitterParser.parse_file(path)` is called on a valid `.java` file, THE `JavaTreeSitterParser` SHALL return a dict containing keys: `file`, `classes`, `imports`, `methods`, `package`, and `metadata`.
4. THE `JavaTreeSitterParser` SHALL extract all top-level class declarations from the file and populate the `classes` list, where each entry contains at minimum `name`, `bases` (superclass/interfaces), `line`, and `decorators` (annotations).
5. THE `JavaTreeSitterParser` SHALL extract all import statements from the file and populate the `imports` list as a flat list of fully qualified import strings.
6. THE `JavaTreeSitterParser` SHALL extract all method declarations from the file and populate the `methods` list as a list of method name strings.
7. THE `JavaTreeSitterParser` SHALL extract the package declaration from the file and populate the `package` field as a string (empty string if absent).
8. IF `JavaTreeSitterParser.parse_file(path)` encounters a file that cannot be parsed, THEN THE `JavaTreeSitterParser` SHALL return `{"file": path, "error": "<description>"}` without raising an exception.
9. WHEN `JavaTreeSitterParser.parse_directory(path)` is called, THE `JavaTreeSitterParser` SHALL recursively discover all `.java` files under `path`, ignoring `.git`, `target`, `build`, and `__pycache__` directories, and return a list of per-file parse results.
10. THE `ParseResult` dict produced by `JavaTreeSitterParser` SHALL be structurally compatible with the dict produced by `PythonASTParser` so that `DependencyGraphBuilder` can consume both without conditional branching on language.

---

### Requirement 3: Multi-Language Architecture Recovery Pipeline

**User Story:** As a backend engineer, I want the pipeline to auto-detect languages in a mixed repository, so that both Python and Java modules appear in the same dependency graph.

#### Acceptance Criteria

1. WHEN `ArchitectureRecoveryPipeline.analyze_repository(repo_path, language="mixed")` is called, THE `ArchitectureRecoveryPipeline` SHALL discover all `.py` files and route them to `PythonASTParser`, and discover all `.java` files and route them to `JavaTreeSitterParser`.
2. THE `ArchitectureRecoveryPipeline` SHALL merge the parsed results from both parsers into a single `CurrentGraph`-compatible dict with unified `components` and `relationships` lists.
3. WHILE `language="python"` is passed, THE `ArchitectureRecoveryPipeline` SHALL use only `PythonASTParser`, preserving Sprint 1 behaviour.
4. WHILE `language="java"` is passed, THE `ArchitectureRecoveryPipeline` SHALL use only `JavaTreeSitterParser`.
5. THE `DependencyGraphBuilder` SHALL expose a `build_from_java(parsed_files, repo_root)` method that produces a `CurrentGraph`-compatible dict, equivalent in structure to the output of `build_from_python`.
6. THE output dict of `analyze_repository` in all language modes SHALL validate against the `CurrentGraph` Pydantic schema without raising a `ValidationError`.

---

### Requirement 4: Graph Confidence Scoring

**User Story:** As a backend engineer, I want edges and nodes in the extracted graph to carry confidence scores, so that the ConformanceEngine can flag low-certainty relationships as UNCERTAIN.

#### Acceptance Criteria

1. WHEN an import in a parsed file is found as an exact match in the internal module map, THE `DependencyGraphBuilder` SHALL assign `confidence=1.0` to the resulting edge.
2. WHEN an import partially matches an internal module (prefix or suffix resolution), THE `DependencyGraphBuilder` SHALL assign `confidence=0.8` to the resulting edge.
3. WHEN an import matches multiple candidate modules, THE `DependencyGraphBuilder` SHALL assign `confidence=0.5` to the resulting edge.
4. THE `DependencyGraphBuilder` SHALL assign `inference_confidence` on each component node: `1.0` when the component type was determined by a keyword match, and `0.6` when the component type defaulted to `MODULE` due to no keyword match.
5. WHEN the `ConformanceEngine` processes an edge whose `confidence` is strictly below its `confidence_threshold` (default `0.6`), THE `ConformanceEngine` SHALL produce a verdict of `UNCERTAIN` for that edge; edges with `confidence` equal to or above the threshold SHALL NOT produce an `UNCERTAIN` verdict solely due to confidence.
6. THE `DependencyGraphBuilder` SHALL store each edge confidence value in the `confidence` field of the relationship dict, so it propagates correctly into the `ArchRelationship.confidence` field of the Pydantic schema.

---

### Requirement 5: Java Fixture Repository

**User Story:** As a QA engineer, I want a Java fixture repository mirroring the Python sample repo 3-tier structure, so that Java parser and graph builder tests have a realistic, self-contained input.

#### Acceptance Criteria

1. THE `sample_java_repo` SHALL contain at minimum four Java source files: `controllers/OrderController.java`, `services/OrderService.java`, `repositories/OrderRepository.java`, and `models/Order.java`.
2. THE `OrderController.java` SHALL import `services.OrderService` (valid layer call) AND directly import `repositories.OrderRepository` (intentional architectural violation: controller bypasses service layer).
3. THE `OrderService.java` SHALL import `repositories.OrderRepository` (valid layer call).
4. THE `OrderRepository.java` SHALL import `models.Order` (valid model dependency).
5. THE `Order.java` SHALL define an `Order` class with no external imports beyond standard library.
6. WHEN `JavaTreeSitterParser.parse_directory(sample_java_repo)` is called, THE `JavaTreeSitterParser` SHALL return exactly four parse results, one per Java file.
7. WHEN `DependencyGraphBuilder.build_from_java(parsed_results, sample_java_repo)` is called on the fixture, THE `DependencyGraphBuilder` SHALL produce a graph with at least 4 components and at least 4 relationships, including a direct Controller→Repository edge representing the intentional violation.

---

### Requirement 6: Unit Tests — Java Parser and Graph Builder

**User Story:** As a backend engineer, I want comprehensive unit tests for the Java parser and graph builder, so that regressions in Sprint 2 P3 code are caught automatically.

#### Acceptance Criteria

1. THE `test_java_parser.py` test suite SHALL contain a test that calls `JavaTreeSitterParser.parse_file` on `OrderController.java` and asserts: the `classes` list contains an entry with `name == "OrderController"`, the `imports` list contains at least two entries (one for `OrderService`, one for `OrderRepository`), and the `methods` list is non-empty.
2. THE `test_java_parser.py` test suite SHALL contain a test that calls `JavaTreeSitterParser.parse_directory(sample_java_repo)` and asserts that exactly four results are returned and all four expected filenames are present.
3. THE `test_java_parser.py` test suite SHALL contain a test that calls `DependencyGraphBuilder.build_from_java` on the fixture and asserts: at least 4 components exist, component types are correctly inferred (controller, service, repository, model), and at least 4 relationships exist including a Controller→Repository edge.
4. THE `test_java_parser.py` test suite SHALL contain an end-to-end test that calls `ArchitectureRecoveryPipeline.analyze_repository(sample_java_repo, language="java")` and validates the returned dict against the `CurrentGraph` Pydantic schema.
5. THE `test_java_parser.py` test suite SHALL contain a test verifying that calling `ArchitectureRecoveryPipeline.analyze_repository(repo, language="mixed")` on a directory containing both `.py` and `.java` files produces a single graph with components from both languages.
6. WHEN all tests in `test_java_parser.py` are executed, THE test suite SHALL pass without errors (all assertions pass, no exceptions raised).

---

### Requirement 7: Unit Tests — Confidence Metrics

**User Story:** As a backend engineer, I want dedicated tests for all three confidence levels and the UNCERTAIN verdict, so that confidence scoring logic is verified in isolation.

#### Acceptance Criteria

1. THE `test_confidence_metrics.py` test suite SHALL contain a test that constructs a scenario where an import resolves exactly and asserts the resulting edge has `confidence == 1.0`.
2. THE `test_confidence_metrics.py` test suite SHALL contain a test that constructs a scenario where an import partially resolves and asserts the resulting edge has `confidence == 0.8`.
3. THE `test_confidence_metrics.py` test suite SHALL contain a test that constructs a scenario where an import is ambiguous (multiple candidates) and asserts the resulting edge has `confidence == 0.5`.
4. THE `test_confidence_metrics.py` test suite SHALL contain a test that passes a graph with an edge of `confidence=0.45` to `ConformanceEngine.check_conformance` and asserts the overall verdict is `UNCERTAIN` and the violations list contains an entry with `verdict == "UNCERTAIN"`.
5. THE `test_confidence_metrics.py` test suite SHALL contain a test that passes a graph with an edge of `confidence=0.65` (above the 0.6 threshold) to `ConformanceEngine.check_conformance` and asserts the edge does NOT produce an `UNCERTAIN` verdict for that edge.
6. THE `test_confidence_metrics.py` test suite SHALL contain a test verifying that component nodes classified by keyword match carry `inference_confidence == 1.0`, and nodes defaulting to `MODULE` type carry `inference_confidence == 0.6`.
7. WHEN all tests in `test_confidence_metrics.py` are executed, THE test suite SHALL pass without errors.

---

### Requirement 8: GitHub Actions CI Workflow

**User Story:** As a team lead, I want a GitHub Actions CI workflow, so that every push and pull request to `main` and `Bhumika` branches is automatically validated by tests and linting before merge.

#### Acceptance Criteria

1. THE `CI_Workflow` SHALL be defined in `.github/workflows/ci.yml` at the repository root and SHALL trigger on `push` and `pull_request` events targeting both `main` and `Bhumika` branches.
2. THE `CI_Workflow` SHALL include a job that checks out the repository, sets up Python 3.13, installs dependencies from `backend/requirements.txt`, and runs `pytest` with coverage reporting to console.
3. THE `CI_Workflow` SHALL include a step that runs `ruff` lint on `backend/app/` to enforce code style, using the `ruff` version already available or installed as a dev dependency.
4. IF any pytest test fails, THEN THE `CI_Workflow` SHALL fail the job (`continue-on-error: false`) so that failing tests block pull request merges.
5. IF any `ruff` lint error is detected, THEN THE `CI_Workflow` SHALL fail the job so that lint errors block pull request merges.
6. THE `CI_Workflow` SHALL install a CPU-only lightweight fallback for heavy ML packages (torch, torchvision, ultralytics) when running in the CI environment, so that all unit tests (including those that import ML modules via stubs or mocks) can execute without GPU resources or timeouts; ML-dependent tests SHALL be exercised against stubs rather than excluded.
7. THE `CI_Workflow` SHALL report pytest coverage output to the console without requiring an external coverage service (no Codecov or similar).

---

### Requirement 9: Regression — Existing Tests Must Continue to Pass

**User Story:** As a backend engineer, I want all 18 Sprint 1 tests to remain green after Sprint 2 P3 changes, so that new features do not break the established foundation.

#### Acceptance Criteria

1. WHEN the full pytest suite is executed after Sprint 2 P3 implementation, THE test suite SHALL report all Sprint 1 tests (in `test_ast_parser.py` and `test_conformance_engine.py`) as passing.
2. THE refactored `PythonASTParser` (now extending `BaseLanguageParser`) SHALL produce identical output to the Sprint 1 `PythonASTParser` for all existing test inputs.
3. THE `DependencyGraphBuilder.build_from_python` method SHALL continue to produce `CurrentGraph`-compatible output with the same structure and field names as Sprint 1.
4. THE `ArchitectureRecoveryPipeline.analyze_repository(repo, language="python")` call SHALL continue to behave exactly as in Sprint 1, with no change to its return value structure.

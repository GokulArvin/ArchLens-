# Implementation Plan: Sprint 2 P3 — Multi-Language Static Analysis, Confidence Scoring & CI

## Overview

Extends `ast_parser.py` with a `BaseLanguageParser` ABC, a `JavaTreeSitterParser` using tree-sitter 0.23.2, three-tier confidence scoring in `DependencyGraphBuilder`, and `"java"`/`"mixed"` modes in `ArchitectureRecoveryPipeline`. Covered by two new test files and a GitHub Actions CI workflow. All 18 Sprint 1 tests remain green throughout.

## Tasks

- [x] 1. Add dependencies to `backend/requirements.txt`
  - Append `tree-sitter-java==0.23.1` (grammar package, works with `tree-sitter==0.23.2` already present)
  - Append `hypothesis==6.122.3` (property-based testing)
  - Append `ruff==0.8.6` (lint; used by CI and local dev)
  - No other changes to the file; leave all existing pinned versions untouched
  - _Requirements: 2.1, 7.1–7.7, 8.3_

- [x] 2. Create Java fixture repository under `backend/tests/fixtures/sample_java_repo/`
  - [x] 2.1 Create `controllers/OrderController.java`
    - Package `controllers`; imports `services.OrderService` and `repositories.OrderRepository`
    - Class `OrderController` with fields for both dependencies and methods `handleCreate` and `handleDirectLookup`
    - `handleDirectLookup` bypasses the service layer intentionally (direct `repository.findById` call)
    - _Requirements: 5.1, 5.2_

  - [x] 2.2 Create `services/OrderService.java`
    - Package `services`; imports `repositories.OrderRepository`
    - Class `OrderService` with a `createOrder` method that delegates to the repository
    - _Requirements: 5.1, 5.3_

  - [x] 2.3 Create `repositories/OrderRepository.java`
    - Package `repositories`; imports `models.Order`
    - Class `OrderRepository` with `findById` and `save` methods returning `Order`
    - _Requirements: 5.1, 5.4_

  - [x] 2.4 Create `models/Order.java`
    - Package `models`; no imports beyond standard library
    - Class `Order` with `id`, `customerId`, `amount` fields and getter methods
    - _Requirements: 5.1, 5.5_

- [x] 3. Refactor `ast_parser.py`: add `BaseLanguageParser` ABC and refactor `PythonASTParser`
  - [x] 3.1 Add `BaseLanguageParser` abstract base class
    - Import `ABC` and `abstractmethod` from `abc` at the top of `ast_parser.py`
    - Define `BaseLanguageParser(ABC)` with three `@abstractmethod` methods: `parse_file(path: str) -> Dict[str, Any]`, `parse_directory(path: str) -> List[Dict[str, Any]]`, `supported_extensions() -> List[str]`
    - Add docstrings as specified in the design document
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 3.2 Refactor `PythonASTParser` to extend `BaseLanguageParser`
    - Change class declaration to `class PythonASTParser(BaseLanguageParser):`
    - Add `supported_extensions(self) -> List[str]: return [".py"]` method
    - Keep `parse_file` and `parse_directory` implementations byte-for-byte identical to Sprint 1
    - Run existing `test_ast_parser.py` mentally to confirm no behaviour change
    - _Requirements: 1.5, 1.6, 9.1, 9.2_

- [x] 4. Add `JavaTreeSitterParser` to `ast_parser.py`
  - [x] 4.1 Add imports and `_JavaTreeSitterVisitor` helper class
    - Add at top of `ast_parser.py`: `from tree_sitter import Language, Parser` and `import tree_sitter_java as tsjava`
    - Add `from typing import Tuple` to the existing typing import line
    - Implement `_JavaTreeSitterVisitor` class exactly as specified in the design: `__init__`, `_text`, `visit`, `_visit_package_declaration`, `_visit_import_declaration`, `_visit_class_declaration`, `_visit_method_declaration`
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 4.2 Implement `JavaTreeSitterParser` class
    - Define `JavaTreeSitterParser(BaseLanguageParser)` with class-level `_language` and `_parser` singletons
    - Implement `_get_parser(cls)` classmethod for lazy initialisation: `Language(tsjava.language())`, `Parser()`, `parser.set_language(language)`
    - Implement `supported_extensions(self) -> List[str]: return [".java"]`
    - Implement `parse_file(self, path: str)`: open as bytes, call `_get_parser().parse(source_bytes)`, instantiate `_JavaTreeSitterVisitor`, call `visitor.visit(tree.root_node)`, return the six-key dict; wrap in try/except for OSError and general Exception returning `{"file": path, "error": str(e)}`
    - Implement `parse_directory(self, path: str)`: use `Path(path).rglob("*.java")`; skip paths containing `.git`, `target`, `build`, or `__pycache__`; return list of `parse_file` results
    - _Requirements: 2.1, 2.2, 2.3, 2.8, 2.9, 2.10_

- [x] 5. Extend `DependencyGraphBuilder` with Java support and confidence scoring
  - [x] 5.1 Update `build_from_python` to emit `inference_confidence` on nodes
    - In the first-pass loop of `build_from_python`, after calling `_infer_component_type`, compute `inference_confidence = 1.0 if comp_type != ComponentType.MODULE.value else 0.6`
    - Add `"inference_confidence": inference_confidence` to the node dict stored in `self.nodes`
    - All other fields and all existing edge logic remain unchanged
    - _Requirements: 4.4, 9.3_

  - [x] 5.2 Add `_add_edge_with_confidence` and update `_add_edge`
    - Add `_add_edge_with_confidence(self, source, target, rel_type, confidence)`: deduplicates by source+target+type, then appends `{"source", "target", "type", "confidence"}` dict to `self.edges`
    - Update existing `_add_edge` to delegate: `self._add_edge_with_confidence(source, target, rel_type, confidence=1.0)` — this preserves all Sprint 1 edge output exactly
    - _Requirements: 4.6, 9.3_

  - [x] 5.3 Add `_resolve_java_import` three-tier confidence method
    - Implement `_resolve_java_import(self, import_str, module_map) -> Tuple[Optional[str], float]`
    - Tier 1 (exact): if `import_str in module_map` return `(import_str, 1.0)`
    - Tier 2 (partial single): collect `candidates` where `mod_stem == import_last` or suffix/prefix match; if `len(candidates) == 1` return `(candidates[0], 0.8)`
    - Tier 3 (ambiguous): if `len(candidates) > 1` return `(candidates[0], 0.5)`
    - External (no match): return `(None, 0.0)`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 5.4 Add `build_from_java` method
    - First pass: for each non-error file, compute `module_name` via `_path_to_module`, infer component type via `_infer_component_type`, compute `inference_confidence`, build node dict including `"package"` and `"source_language": "java"` in metadata
    - Second pass: for each import in each non-error file, call `_resolve_java_import` to get `(target_module, confidence)`; if target is not None and not equal to source, call `_add_edge_with_confidence`
    - Return the `CurrentGraph`-compatible dict with `"graph_type": "current"`, `"schema_version": "1.0.0"`, `"language": "java"` in metadata
    - _Requirements: 3.5, 4.4, 4.6, 5.7_

- [x] 6. Extend `ArchitectureRecoveryPipeline` with Java and mixed modes
  - [x] 6.1 Update `__init__` to instantiate `JavaTreeSitterParser`
    - Add `self.java_parser = JavaTreeSitterParser()` alongside existing `self.python_parser` and `self.graph_builder`
    - _Requirements: 3.1, 3.4_

  - [x] 6.2 Add `"java"` and `"mixed"` branches to `analyze_repository`
    - Replace the existing `else` fallback with an explicit `elif language == "java":` branch that calls `self.java_parser.parse_directory(repo_path)` then `self.graph_builder.build_from_java(parsed, repo_path)`
    - Add `elif language == "mixed":` branch that calls `self._merge_graphs(py_parsed, java_parsed, repo_path)`
    - Keep `language == "python"` branch and the final `else` fallback (with warning log) identical to Sprint 1
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 6.3 Add `_merge_graphs` method
    - Instantiate two fresh `DependencyGraphBuilder` instances to avoid shared state
    - Build `py_graph` via `build_from_python` and `java_graph` via `build_from_java`
    - Concatenate their `components` and `relationships` lists into a single `CurrentGraph`-compatible dict with `"language": "mixed"` in metadata
    - _Requirements: 3.2, 3.6_

- [ ] 7. Checkpoint — verify Sprint 1 regression
  - Run `pytest backend/tests/unit/test_ast_parser.py backend/tests/unit/test_conformance_engine.py -v` from the `backend/` directory and confirm all 18 tests pass. Ask the user if any failures arise before continuing.

- [x] 8. Write `backend/tests/unit/test_java_parser.py`
  - [x] 8.1 Add example-based unit tests for `JavaTreeSitterParser` and graph builder
    - `test_parse_single_java_file`: call `parse_file(OrderController.java)`, assert `classes` contains entry with `name == "OrderController"`, `imports` ≥ 2, `methods` non-empty; _Requirements: 6.1_
    - `test_parse_directory_returns_four_files`: call `parse_directory(sample_java_repo)`, assert exactly 4 results, all four filenames present; _Requirements: 6.2_
    - `test_build_from_java_graph`: call `build_from_java` on fixture results, assert ≥4 components, types correctly inferred, ≥4 relationships, Controller→Repository edge exists; _Requirements: 6.3_
    - `test_pipeline_java_end_to_end`: call `analyze_repository(sample_java_repo, language="java")`, validate result with `CurrentGraph(**result)`; _Requirements: 6.4_
    - `test_pipeline_mixed_mode`: build a temp directory containing both `.py` and `.java` files (or point at a combined fixture), assert result has components from both parsers; _Requirements: 6.5_
    - `test_java_parser_is_base_subclass`: `assert issubclass(JavaTreeSitterParser, BaseLanguageParser)`; _Requirements: 1.1–1.3_
    - `test_abstract_base_raises_on_incomplete_subclass`: define a local incomplete subclass, assert `pytest.raises(TypeError)` on instantiation; _Requirements: 1.4_
    - `test_python_parser_is_base_subclass`: `assert issubclass(PythonASTParser, BaseLanguageParser)`; _Requirements: 1.5_
    - `test_supported_extensions`: assert `PythonASTParser().supported_extensions() == [".py"]` and `JavaTreeSitterParser().supported_extensions() == [".java"]`; _Requirements: 1.6, 2.2_

  - [ ]* 8.2 Write property test for Property 1 — Java ParseResult structural completeness
    - Use `@given(st.text(min_size=1))` to generate arbitrary Java source strings; write to a temp `.java` file; call `parse_file`; assert result contains all six keys (`file`, `classes`, `imports`, `methods`, `package`, `metadata`) and every entry in `classes` has `name`, `bases`, `line`, `decorators`
    - **Property 1: Java ParseResult structural completeness**
    - **Validates: Requirements 2.3, 2.4, 2.5, 2.6**

  - [ ]* 8.3 Write property test for Property 2 — Error handling never raises
    - Use `@given(st.binary())` to generate arbitrary bytes; write to a temp `.java` file; call `parse_file`; assert result is a dict with keys `file` and `error` (or a valid ParseResult), never an exception
    - **Property 2: Error handling never raises — always returns error dict**
    - **Validates: Requirements 2.8**

  - [ ]* 8.4 Write property test for Property 3 — parse_directory excludes ignored subdirectories
    - Use `@given(st.sampled_from([".git", "target", "build", "__pycache__"]))` for ignored dir name; create temp dir tree with `.java` file inside ignored dir and outside; call `parse_directory`; assert file in ignored dir is absent from results and file outside is present
    - **Property 3: parse_directory excludes ignored subdirectories**
    - **Validates: Requirements 2.9**

  - [ ]* 8.5 Write property test for Property 4 — CurrentGraph schema validation across language modes
    - Use `@given(st.sampled_from(["python", "java", "mixed"]))` for language; call `analyze_repository(sample_java_repo_or_fixture, language=lang)` where a combined fixture exists; assert `CurrentGraph(**result)` does not raise
    - **Property 4: CurrentGraph schema validation across all language modes**
    - **Validates: Requirements 3.6, 3.5, 3.2**

  - [ ]* 8.6 Write property test for Property 9 — PythonASTParser output preservation after refactoring
    - Use `@given(st.sampled_from(py_files_in_sample_repo))` for file paths; call the refactored `PythonASTParser().parse_file(path)`; assert returned dict has keys `file`, `classes`, `imports`, `from_imports`, `functions`, `function_calls` and no unexpected exception
    - **Property 9: PythonASTParser output preservation after refactoring**
    - **Validates: Requirements 1.5, 9.2**

- [x] 9. Write `backend/tests/unit/test_confidence_metrics.py`
  - [x] 9.1 Add example-based unit tests for confidence tiers and UNCERTAIN verdict
    - `test_exact_match_confidence_1_0`: build `module_map = {"order_service": "..."}`, call `_resolve_java_import("order_service", module_map)`, assert confidence `== 1.0`; _Requirements: 7.1_
    - `test_partial_match_confidence_0_8`: build module_map with `"services.order_service"`, call with `"order_service"`, assert confidence `== 0.8`; _Requirements: 7.2_
    - `test_ambiguous_match_confidence_0_5`: build module_map with `"a.order_service"` and `"b.order_service"`, call with `"order_service"`, assert confidence `== 0.5`; _Requirements: 7.3_
    - `test_uncertain_verdict_below_threshold`: build a minimal graph dict with one edge `confidence=0.45`; pass to `ConformanceEngine().check_conformance(empty_gi, gc)`; assert `result["verdict"] == "UNCERTAIN"` and at least one violation has `verdict == "UNCERTAIN"`; _Requirements: 7.4_
    - `test_no_uncertain_verdict_above_threshold`: build graph with `confidence=0.65`; pass to `ConformanceEngine().check_conformance`; assert no violation for that edge has `verdict == "UNCERTAIN"`; _Requirements: 7.5_
    - `test_inference_confidence_keyword_match`: call `DependencyGraphBuilder()._infer_component_type("order_controller", {})`, then construct a node as the builder would; assert `inference_confidence == 1.0`; _Requirements: 7.6_
    - `test_inference_confidence_default_module`: call `_infer_component_type("utils_misc", {})`, assert resulting type is MODULE hence `inference_confidence == 0.6`; _Requirements: 7.6_

  - [ ]* 9.2 Write property test for Property 5 — Exact match import produces confidence 1.0
    - Use `@given(st.text(alphabet=st.characters(whitelist_categories=("Lu","Ll")), min_size=1))` for module name; build `module_map = {name: "fake/path"}`, call `_resolve_java_import(name, module_map)`, assert confidence `== 1.0`
    - **Property 5: Exact-match import produces confidence 1.0**
    - **Validates: Requirements 4.1, 4.6**

  - [ ]* 9.3 Write property test for Property 6 — Partial match produces confidence 0.8
    - Generate a base name, construct `module_map = {"prefix." + base: "path"}`, call with just `base` (not exact key); assert confidence `== 0.8` when exactly one candidate matches
    - **Property 6: Partial-match import produces confidence 0.8**
    - **Validates: Requirements 4.2**

  - [ ]* 9.4 Write property test for Property 7 — Ambiguous import produces confidence 0.5
    - Generate a shared suffix, construct `module_map = {"a." + suffix: "p1", "b." + suffix: "p2"}`, call with `suffix`; assert confidence `== 0.5`
    - **Property 7: Ambiguous import produces confidence 0.5**
    - **Validates: Requirements 4.3**

  - [ ]* 9.5 Write property test for Property 8 — inference_confidence follows keyword-match rule
    - Use `@given(st.text(min_size=1))` for module name; call `DependencyGraphBuilder()._infer_component_type(name, {})`; assert `inference_confidence == 1.0` when result is not MODULE, and `== 0.6` when result is MODULE
    - **Property 8: inference_confidence follows keyword-match rule**
    - **Validates: Requirements 4.4**

- [x] 10. Checkpoint — run full test suite
  - Run `pytest backend/tests/ -v` and confirm all tests pass (18 Sprint 1 tests + new Sprint 2 P3 tests). Ask the user if any failures arise before continuing.

- [x] 11. Create `.github/workflows/ci.yml`
  - [x] 11.1 Create the GitHub Actions CI workflow file at `.github/workflows/ci.yml`
    - Trigger on `push` and `pull_request` to branches `main` and `Bhumika`
    - Single job `test-and-lint` on `ubuntu-latest`
    - Steps in order: `actions/checkout@v4`, `actions/setup-python@v5` with `python-version: "3.13"`, CPU-only torch install step (`pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu`), `pip install -r requirements.txt` with `working-directory: backend`, `ruff check app/` with `working-directory: backend`, `pytest --cov=app --cov-report=term-missing -v` with `working-directory: backend`
    - No `continue-on-error` overrides; all steps must pass to let PR merges through
    - No external coverage service; `--cov-report=term-missing` writes to console only
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Run `pytest backend/tests/ --cov=app --cov-report=term-missing -v` and confirm the full suite is green. Ask the user if any failures arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; the core implementation tasks (1–7, 9.1, 11) are required.
- Task ordering is strict: `requirements.txt` (1) before parser code (3–6), fixtures (2) before parser tests (8), graph builder confidence additions (5) before confidence tests (9), and CI (11) last so it exercises the complete suite.
- The three-tier confidence algorithm (`_resolve_java_import`) and `_add_edge_with_confidence` must be implemented in task 5 before `build_from_java` (also task 5) uses them — sub-task order within task 5 must be followed: 5.1 → 5.2 → 5.3 → 5.4.
- `build_from_python` only gains `inference_confidence` on nodes (task 5.1); all edge logic remains identical to Sprint 1 so the 18 existing tests continue to pass.
- The `_add_edge` method is updated to call `_add_edge_with_confidence(..., confidence=1.0)` (task 5.2) rather than replacing it, preserving the Sprint 1 call sites in `build_from_python`.
- Property tests use Hypothesis; import as `from hypothesis import given, settings` and `from hypothesis import strategies as st`.
- Each property test MUST include the comment `# Feature: archlens-sprint2-p3, Property N: <property title>` immediately above the `@given` decorator.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2.1", "2.2", "2.3", "2.4"] },
    { "id": 1, "tasks": ["3.1"] },
    { "id": 2, "tasks": ["3.2", "4.1"] },
    { "id": 3, "tasks": ["4.2"] },
    { "id": 4, "tasks": ["5.1", "5.2"] },
    { "id": 5, "tasks": ["5.3"] },
    { "id": 6, "tasks": ["5.4", "6.1"] },
    { "id": 7, "tasks": ["6.2"] },
    { "id": 8, "tasks": ["6.3"] },
    { "id": 9, "tasks": ["8.1", "9.1"] },
    { "id": 10, "tasks": ["8.2", "8.3", "8.4", "8.5", "8.6", "9.2", "9.3", "9.4", "9.5"] },
    { "id": 11, "tasks": ["11.1"] }
  ]
}
```

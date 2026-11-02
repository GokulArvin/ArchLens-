# Implementation Plan: Sprint 3 P3 — CALLS/INHERITS Edges, FasterRCNN Backend & Package Graph

## Overview

Extends `ast_parser.py` to emit `CALLS` and `INHERITS` edges from Python and Java parse results, adds a `build_package_graph()` method to `DependencyGraphBuilder`, introduces a `BaseComponentDetector` ABC in `pipeline.py` with a new `FasterRCNNDetector` backend, and covers all new behaviour with three new test files. All 75 existing Sprint 2 tests must stay green throughout.

## Tasks

- [ ] 1. Extend `_PythonASTVisitor` with `call_targets` collection
  - Add `self.call_targets: List[Dict[str, str]] = []` to `__init__`
  - In `visit_Call`, after the existing `ast.unparse` line, add a branch: if `node.func` is `ast.Attribute`, append `{"object": ast.unparse(node.func.value), "method": node.func.attr}` to `call_targets`; guard the append in the existing `try/except` so malformed attribute access is silently skipped
  - Do NOT remove or rename the existing `function_calls` list or any other field
  - _Requirements: 1.1_

- [ ] 2. Extend `PythonASTParser.parse_file` to include `call_targets` in returned dict
  - Add `"call_targets": visitor.call_targets` to the dict returned by `parse_file`, alongside the existing six keys
  - No other changes to `parse_file` or `parse_directory`
  - _Requirements: 1.1_

- [ ] 3. Extend `_JavaTreeSitterVisitor` with `method_invocations` collection
  - Add `self.method_invocations: List[Dict[str, str]] = []` to `__init__`
  - Implement `_visit_method_invocation(self, node)`: iterate `node.children`, track the first qualifying object expression before the `.` separator and the first `identifier` after it; if both found, append `{"object": obj_name, "method": method_name}`; guard with a bare `except` so unexpected grammar shapes are skipped silently
  - Register the handler so `visit()` dispatches it: add `"method_invocation"` to the dispatch lookup in `visit()`
  - Do NOT remove the existing `methods` list or any other field
  - _Requirements: 3.1_

- [ ] 4. Extend `JavaTreeSitterParser.parse_file` to include `method_invocations` in returned dict
  - Add `"method_invocations": visitor.method_invocations` to the dict returned by `parse_file`, alongside the existing keys
  - No other changes to `parse_file` or `parse_directory`
  - _Requirements: 3.1_

- [ ] 5. Add `_build_class_to_module_map` helper to `DependencyGraphBuilder`
  - Implement `_build_class_to_module_map(self, parsed_files: List[Dict[str, Any]], repo_root: Path) -> Dict[str, str]`
  - Iterate over non-error `file_data` entries; for each class in `file_data.get("classes", [])`, map `cls["name"]` → `self._path_to_module(file_data["file"], repo_root)`
  - Return the resulting `{class_name: module_id}` dict
  - _Requirements: 1.2, 2.1, 3.2, 4.1_

- [ ] 6. Add third pass (CALLS + INHERITS edges) to `DependencyGraphBuilder.build_from_python`
  - After the existing second pass (import resolution), add a third pass:
    1. Call `class_map = self._build_class_to_module_map(parsed_files, repo_root_path)`
    2. For each non-error `file_data`, get `source_module`
    3. **CALLS**: for each entry in `file_data.get("call_targets", [])`, extract `candidate = entry["object"].split(".")[-1]`; look up `class_map.get(candidate) or class_map.get(candidate.title())`; if resolved and `!= source_module`, call `self._add_edge_with_confidence(source_module, target, RelationshipType.CALLS.value, 0.7)`
    4. **INHERITS**: for each class in `file_data.get("classes", [])`, for each base in `cls.get("bases", [])`, extract `base_simple = base.split(".")[-1]`; look up `class_map.get(base_simple)`; if resolved and `!= source_module`, call `self._add_edge_with_confidence(source_module, target, RelationshipType.INHERITS.value, 0.9)`
  - Deduplication is handled automatically by the existing `_add_edge_with_confidence` implementation
  - Pass 1 and Pass 2 remain completely unchanged
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4_

- [ ] 7. Add third pass (CALLS + INHERITS edges) to `DependencyGraphBuilder.build_from_java`
  - After the existing second pass, add an identical third pass using `method_invocations` instead of `call_targets`:
    1. Call `class_map = self._build_class_to_module_map(parsed_files, repo_root_path)`
    2. For each non-error `file_data`, get `source_module`
    3. **CALLS**: for each entry in `file_data.get("method_invocations", [])`, extract `candidate = entry["object"].split(".")[-1]`; look up `class_map.get(candidate) or class_map.get(candidate.title())`; if resolved and `!= source_module`, call `self._add_edge_with_confidence(source_module, target, RelationshipType.CALLS.value, 0.7)`
    4. **INHERITS**: same algorithm as Python third pass — iterate `classes[*].bases`, strip module prefix, look up `class_map`, emit with confidence 0.9
  - Pass 1 and Pass 2 remain completely unchanged
  - _Requirements: 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4_

- [ ] 8. Checkpoint — verify Sprint 2 regression
  - Run `pytest backend/tests/ -v` from the `backend/` directory and confirm all 75 pre-existing tests pass. Ask the user if any failures arise before continuing.

- [ ] 9. Add `build_package_graph` method to `DependencyGraphBuilder`
  - Implement `build_package_graph(self) -> Dict[str, Any]` exactly as specified in the design:
    1. Build `container: Dict[str, List[str]]` by splitting each `module_id` in `self.nodes` on `"."` and taking `[0]` as the package key
    2. Assign `self.container_graph = container`
    3. Build `pkg_nodes` list: one `{"id": pkg, "type": "package", "component_count": len(members)}` per package, sorted by package name
    4. Build `pkg_edges` list: iterate `self.edges`; for each edge where `src_pkg != tgt_pkg`, add `{"source": src_pkg, "target": tgt_pkg, "type": "package_dependency"}` if the `(src_pkg, tgt_pkg)` pair hasn't been seen yet
    5. Return `{"nodes": pkg_nodes, "edges": pkg_edges, "container_graph": container}`
    6. If called when `self.nodes` is empty, return `{"nodes": [], "edges": [], "container_graph": {}}`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [ ] 10. Add `BaseComponentDetector` ABC to `pipeline.py`
  - At the top of `pipeline.py`, import `ABC` and `abstractmethod` from `abc` (they are already used by `ast_parser.py` — apply the same pattern)
  - Define `BaseComponentDetector(ABC)` before `ComponentDetector`:
    - Single `@abstractmethod`: `detect(self, img: np.ndarray) -> List[Dict[str, Any]]`
    - Docstring describing `DetectionResult` dict shape (`bbox`, `confidence`, `class_id`, `class_name`) and the contract to return `[]` never raise
  - Change `ComponentDetector` class declaration to `class ComponentDetector(BaseComponentDetector):`
  - No other changes to `ComponentDetector`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

- [ ] 11. Implement `FasterRCNNDetector` in `pipeline.py`
  - Define full 91-entry `COCO_CLASSES` list as a class attribute (use the standard torchvision COCO label map order, starting with `"__background__"`)
  - Implement `__init__(self, confidence: float = 0.5)`: store `self.confidence`, set `self._model = None` and `self._init_attempted = False`
  - Implement `_get_model(self)`: if `self._model is None and not self._init_attempted`, set `self._init_attempted = True`, then inside `try`: `import torch`, `import torchvision`, load `FasterRCNN_ResNet50_FPN_Weights.DEFAULT`, call `torchvision.models.detection.fasterrcnn_resnet50_fpn(weights=weights)`, call `.eval()`, assign to `self._model`; on any `Exception`, log warning and leave `self._model` as `None`; return `self._model`
  - Implement `detect(self, img: np.ndarray) -> List[Dict[str, Any]]`: call `_get_model()`; if `None`, return `[]`; inside `try`: BGR→RGB (`img[:,:,::-1].copy()`), `/255.0`, `np.transpose(...,(2,0,1))`, `torch.from_numpy`, `model([t])` under `torch.no_grad()`; filter `scores >= self.confidence`; build `DetectionResult` dicts; return list; on any `Exception`, log warning and return `[]`
  - _Requirements: 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [ ] 12. Write `backend/tests/unit/test_calls_inheritance.py`
  - [ ] 12.1 Write example-based tests for CALLS/INHERITS edge extraction
    - `test_python_calls_edge_emitted`: create two temp Python files (`module_a.py` with `class B: pass` and `module_b.py` with `b = B(); b.method()`), call `DependencyGraphBuilder().build_from_python(...)`, assert at least one `CALLS` edge with `confidence == 0.7` exists
    - `test_python_inherits_edge_emitted`: `module_a.py` defines `class Base`, `module_b.py` defines `class Child(Base)`, assert `INHERITS` edge from `module_b` → `module_a` with `confidence == 0.9`
    - `test_python_no_duplicate_calls_edges`: create fixture where module_b calls module_a's class twice, assert exactly one `CALLS` edge between the pair
    - `test_python_depends_on_coexists_with_calls`: module_b imports module_a AND calls a method on a class from module_a; assert both `DEPENDS_ON` and `CALLS` edges present for the pair
    - `test_java_calls_edge_emitted`: create two temp `.java` files using `tmp_path`, parse with `JavaTreeSitterParser`, call `build_from_java`, assert a `CALLS` edge with `confidence == 0.7` exists
    - `test_java_inherits_edge_emitted`: create fixture with `class Base` in one `.java` file and `class Child extends Base` in another, assert `INHERITS` edge with `confidence == 0.9`
    - `test_java_no_duplicate_inherits_edges`: assert at most one `INHERITS` edge per `(source, target)` pair
    - `test_unresolvable_base_emits_no_edge`: class inherits from `list` (stdlib); assert no `INHERITS` edge emitted for it
    - All tests use `tmp_path` or in-memory string fixtures only — no network calls or GPU access
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 12.2 Write property test for Property 1 — CALLS edges have confidence 0.7
    - Use Hypothesis to generate lists of 2–5 module pairs where module A calls a class from module B; run `build_from_python`; assert every edge with `type == "calls"` has `confidence == 0.7`
    - **Property 1: CALLS edges have confidence 0.7**
    - **Validates: Requirements 1.4, 3.4**

  - [ ]* 12.3 Write property test for Property 2 — INHERITS edges have confidence 0.9
    - Use Hypothesis to generate class hierarchies across module pairs; run `build_from_python`; assert every edge with `type == "inherits"` has `confidence == 0.9`
    - **Property 2: INHERITS edges have confidence 0.9**
    - **Validates: Requirements 2.3, 4.3**

  - [ ]* 12.4 Write property test for Property 3 — Edge deduplication invariant
    - Use Hypothesis to generate repeated call/inherit references from module A to the same class in module B; run `build_from_python`; assert at most one `CALLS` edge and at most one `INHERITS` edge per `(source, target)` pair
    - **Property 3: Edge deduplication invariant**
    - **Validates: Requirements 1.3, 2.2, 3.3, 4.2**

  - [ ]* 12.5 Write property test for Property 4 — DEPENDS_ON edges are preserved
    - Use Hypothesis to generate module pairs with both an import and a call reference; run `build_from_python`; assert `DEPENDS_ON` edges present with `confidence == 1.0` and coexist with `CALLS` edges
    - **Property 4: DEPENDS_ON edges are preserved (regression)**
    - **Validates: Requirements 1.5, 3.5, 11.2, 11.3**

- [ ] 13. Write `backend/tests/unit/test_package_graph.py`
  - [ ] 13.1 Write example-based tests for `build_package_graph`
    - `test_package_graph_node_count_matches_unique_packages`: build synthetic `parsed_files` with modules from packages `app` and `tests`; call `build_from_python` then `build_package_graph`; assert `len(nodes) == 2`, each node has `type == "package"`
    - `test_package_graph_cross_package_edges_deduplicated`: three module-level edges from `app.a` → `tests.b`; assert exactly one `PackageGraph` edge from `app` → `tests`
    - `test_container_graph_stored_as_attribute`: call `build_package_graph()`; assert `builder.container_graph` is accessible and maps package names to component ID lists correctly
    - `test_single_package_zero_cross_edges`: all modules share same top-level package; assert `PackageGraph` has one node and zero edges
    - `test_package_graph_handles_calls_and_inherits_edges`: verify that `CALLS` and `INHERITS` cross-package edges are also folded into `PackageGraph` edges
    - `test_build_package_graph_before_build_returns_empty`: call `build_package_graph()` on a fresh `DependencyGraphBuilder` (no prior `build_from_*`); assert returns `{"nodes": [], "edges": [], "container_graph": {}}`
    - All tests use in-memory `parsed_files` lists and `tmp_path` roots
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 13.2 Write property test for Property 5 — PackageGraph node count equals unique package count
    - Use Hypothesis to generate lists of `(pkg_prefix, n_modules)` tuples (1–5 packages, 1–4 modules each); build synthetic `parsed_files`; call `build_from_python` then `build_package_graph`; assert `len(nodes) == number_of_unique_packages`
    - **Property 5: PackageGraph node count equals unique package count**
    - **Validates: Requirements 7.1, 7.2, 7.4**

  - [ ]* 13.3 Write property test for Property 6 — Cross-package edges are deduplicated
    - Use Hypothesis to generate multiple module-level edges between the same package pair; call `build_package_graph`; assert at most one directed `PackageGraph` edge per `(src_pkg, tgt_pkg)` pair
    - **Property 6: Cross-package edges are deduplicated**
    - **Validates: Requirements 7.3, 7.5**

- [ ] 14. Write `backend/tests/unit/test_component_detection.py`
  - [ ] 14.1 Write example-based tests for `BaseComponentDetector`, `ComponentDetector`, and `FasterRCNNDetector`
    - `test_base_detector_is_abc`: assert `BaseComponentDetector` cannot be instantiated directly (raises `TypeError`)
    - `test_abstract_subclass_raises_type_error`: define local subclass missing `detect`; assert `pytest.raises(TypeError)`
    - `test_component_detector_is_subclass`: `assert issubclass(ComponentDetector, BaseComponentDetector)`
    - `test_faster_rcnn_detector_is_subclass`: `assert issubclass(FasterRCNNDetector, BaseComponentDetector)`
    - `test_yolo_detect_no_model_returns_empty_list`: instantiate `ComponentDetector()` without a model path; assert `detect(np.zeros((100,100,3), dtype=np.uint8)) == []`
    - `test_faster_rcnn_detect_unavailable_torch_returns_empty`: use `unittest.mock.patch` to raise `ImportError` on `torch` import inside `_get_model`; assert `detect(...)` returns `[]` without raising
    - `test_faster_rcnn_detect_returns_detection_result_format`: mock `torchvision.models.detection.fasterrcnn_resnet50_fpn` to return a fake model; mock model `__call__` to return a synthetic prediction dict with `boxes`, `labels`, `scores` tensors; assert every returned dict has keys `bbox`, `confidence`, `class_id`, `class_name` with correct value types
    - `test_faster_rcnn_confidence_threshold_filters_low_scores`: set `confidence=0.8`; mock model to return scores `[0.9, 0.5, 0.3]`; assert only the `0.9` prediction is returned
    - `test_faster_rcnn_no_model_returns_empty`: set `_init_attempted = True` and `_model = None`; assert `detect(...)` returns `[]`
    - All tests use `unittest.mock.patch`; no GPU, no real model download
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 14.2 Write property test for Property 7 — FasterRCNNDetector confidence threshold filtering
    - Use Hypothesis to generate a list of float scores in `[0, 1]` and a threshold `T` in `(0, 1)`; mock the model to return those scores; assert returned results contain only scores `>= T` and nothing below `T`
    - **Property 7: FasterRCNNDetector confidence threshold filtering**
    - **Validates: Requirements 6.3**

  - [ ]* 14.3 Write property test for Property 8 — DetectionResult format consistency between backends
    - Use Hypothesis to generate one synthetic prediction; mock both `ComponentDetector` and `FasterRCNNDetector` to return one result each; assert both return dicts with the same key set `{"bbox", "confidence", "class_id", "class_name"}` and the same value types
    - **Property 8: DetectionResult format consistency between backends**
    - **Validates: Requirements 6.7**

- [ ] 15. Final checkpoint — Ensure all tests pass
  - Run `pytest backend/tests/ -v` and confirm all tests pass (75 pre-existing + all new Sprint 3 tests). Ask the user if any failures arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; all unmarked tasks are required.
- Task ordering is strict: visitor extensions (1–4) before graph builder extensions (5–7), CALLS/INHERITS passes (6–7) before package graph (9), ABC (10) before `FasterRCNNDetector` (11), and test files (12–14) after the corresponding production code they test.
- Sub-task order within task 12 matters: 12.1 (example tests) before 12.2–12.5 (property tests); same pattern for 13 and 14.
- `_build_class_to_module_map` (task 5) must exist before both pass-3 additions (tasks 6, 7).
- The existing `_add_edge_with_confidence` deduplication already covers `(source, target, type)` triples — no new deduplication logic is needed.
- Property tests must include the tag `# Feature: archlens-sprint3-p3, Property N: <property_text>` immediately above their `@given` decorator.
- Hypothesis `@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])` for all property tests.
- `FasterRCNNDetector` follows the exact same lazy-init pattern as `JavaTreeSitterParser` (`_init_attempted` sentinel + `_get_model()` classmethod-style helper).
- No changes to `requirements.txt` — `torch`, `torchvision`, and `hypothesis` are already present from Sprint 2.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "3"] },
    { "id": 1, "tasks": ["2", "4"] },
    { "id": 2, "tasks": ["5", "10"] },
    { "id": 3, "tasks": ["6", "7", "11"] },
    { "id": 4, "tasks": ["9"] },
    { "id": 5, "tasks": ["12.1", "13.1", "14.1"] },
    { "id": 6, "tasks": ["12.2", "12.3", "12.4", "12.5", "13.2", "13.3", "14.2", "14.3"] }
  ]
}
```

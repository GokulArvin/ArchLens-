# Requirements Document

## Introduction

Sprint 3 P3 extends ArchLens's static-analysis and computer-vision pipeline across five days (D11–D15). The work deepens the dependency graph by adding `CALLS` and `INHERITS` relationship extraction for both Python and Java, introduces a `FasterRCNNDetector` as a second component-detection backend alongside YOLO, groups modules by package into a `ContainerGraph`, and covers all new behaviour with unit tests. All 75 existing Sprint 2 tests must remain green throughout.

## Glossary

- **AST_Parser**: The `PythonASTParser` class in `ast_parser.py` that uses Python's built-in `ast` module.
- **Python_Visitor**: The `_PythonASTVisitor` inner class used by `AST_Parser` to traverse Python AST nodes.
- **Java_Visitor**: The `_JavaTreeSitterVisitor` inner class used by `JavaTreeSitterParser` to walk tree-sitter Java AST nodes.
- **Graph_Builder**: The `DependencyGraphBuilder` class that converts parsed file data into a `CurrentGraph`-compatible dict of nodes and edges.
- **CALLS_Edge**: A directed edge of `RelationshipType.CALLS` emitted when one module's function/method invokes a class or method defined in another internal module.
- **INHERITS_Edge**: A directed edge of `RelationshipType.INHERITS` emitted when a class in one module extends or implements a class defined in another internal module.
- **DEPENDS_ON_Edge**: A directed edge of `RelationshipType.DEPENDS_ON` emitted for import-based module dependencies (existing Sprint 2 behaviour).
- **BaseComponentDetector**: A new abstract base class in `pipeline.py` that all component-detector backends must extend.
- **YOLO_Detector**: The refactored `ComponentDetector` class, now extending `BaseComponentDetector`, that uses the `ultralytics` YOLO backend.
- **FasterRCNN_Detector**: A new `FasterRCNNDetector` class extending `BaseComponentDetector` that uses `torchvision.models.detection.fasterrcnn_resnet50_fpn` as its detection backend.
- **ContainerGraph**: A `dict` mapping top-level package/directory name (`str`) to a list of component ID strings belonging to that package.
- **PackageGraph**: The summary `CurrentGraph`-compatible dict returned by `build_package_graph()` where each node represents a package and edges represent cross-package dependencies.
- **DetectionResult**: The standardised detection output dict with keys `bbox`, `confidence`, `class_id`, and `class_name`.
- **Repo_Root**: The absolute path of the repository directory passed to `Graph_Builder.build_from_python` or `Graph_Builder.build_from_java`.

---

## Requirements

### Requirement 1: Python CALLS Edge Extraction

**User Story:** As a software architect, I want the Python static analyser to detect inter-module method calls, so that I can see which modules actively invoke behaviour in other modules beyond mere imports.

#### Acceptance Criteria

1. WHEN `Python_Visitor` visits a `ast.Call` node whose `func` attribute is an `ast.Attribute` (i.e., `object.method()` form), THE `Python_Visitor` SHALL record the resolved call target as a structured entry in a `call_targets` list, containing the object name and method name.
2. WHEN `Graph_Builder.build_from_python` resolves a recorded call target and the object name matches a class defined in another internal module, THE `Graph_Builder` SHALL emit a `CALLS_Edge` from the source module to that target module independently of any existing `DEPENDS_ON_Edge` between the same pair.
3. THE `Graph_Builder` SHALL NOT emit duplicate `CALLS_Edge` entries between the same source and target module pair; a `CALLS_Edge` and a `DEPENDS_ON_Edge` between the same pair are distinct edges and SHALL both be retained.
4. WHEN `Graph_Builder.build_from_python` emits a `CALLS_Edge`, THE `Graph_Builder` SHALL assign it a `confidence` value of `0.7`.
5. THE `Graph_Builder` SHALL continue to emit all `DEPENDS_ON_Edge` entries from import resolution unchanged (Sprint 2 behaviour preserved).

### Requirement 2: Python INHERITS Edge Extraction

**User Story:** As a software architect, I want the Python static analyser to map inheritance chains across modules, so that I can understand which modules extend classes from other modules.

#### Acceptance Criteria

1. WHEN `Python_Visitor` records a class with non-empty `bases` and a base name is resolvable to a class in another internal module, THE `Graph_Builder.build_from_python` SHALL emit an `INHERITS_Edge` from the source module to that other module.
2. THE `Graph_Builder` SHALL NOT emit duplicate `INHERITS_Edge` entries between the same source and target module pair.
3. WHEN `Graph_Builder.build_from_python` emits an `INHERITS_Edge`, THE `Graph_Builder` SHALL assign it a `confidence` value of `0.9`.
4. IF a base class name cannot be resolved to any internal module, THEN THE `Graph_Builder` SHALL skip that base without emitting an edge or raising an exception.

### Requirement 3: Java CALLS Edge Extraction

**User Story:** As a software architect, I want the Java static analyser to detect method invocations between modules, so that the dependency graph reflects runtime call relationships in Java codebases.

#### Acceptance Criteria

1. WHEN `Java_Visitor.visit` traverses a tree-sitter node of type `method_invocation`, THE `Java_Visitor` SHALL record the method invocation target (object name and method name) in a `method_invocations` list.
2. WHEN `Graph_Builder.build_from_java` processes recorded method invocations and the invocation object name matches a class declared in another internal module, THE `Graph_Builder` SHALL emit a `CALLS_Edge` from the source module to that target module independently of any existing `DEPENDS_ON_Edge` between the same pair.
3. THE `Graph_Builder` SHALL NOT emit duplicate `CALLS_Edge` entries between the same source and target module pair; a `CALLS_Edge` and a `DEPENDS_ON_Edge` between the same pair are distinct edges and SHALL both be retained.
4. WHEN `Graph_Builder.build_from_java` emits a `CALLS_Edge`, THE `Graph_Builder` SHALL assign it a `confidence` value of `0.7`.
5. THE `Graph_Builder` SHALL continue to emit all `DEPENDS_ON_Edge` entries from import resolution with their three-tier confidence scores unchanged (Sprint 2 behaviour preserved).

### Requirement 4: Java INHERITS Edge Extraction

**User Story:** As a software architect, I want the Java static analyser to emit inheritance edges when one module's class extends or implements a class from another module, so that class hierarchies are visible in the dependency graph.

#### Acceptance Criteria

1. WHEN `Graph_Builder.build_from_java` finds a class in one module whose `bases` list resolves to a class defined in another internal module, THE `Graph_Builder` SHALL emit an `INHERITS_Edge` from the source module to that other module.
2. THE `Graph_Builder` SHALL NOT emit duplicate `INHERITS_Edge` entries between the same source and target module pair.
3. WHEN `Graph_Builder.build_from_java` emits an `INHERITS_Edge`, THE `Graph_Builder` SHALL assign it a `confidence` value of `0.9`.
4. IF a base class name cannot be resolved to any internal module, THEN THE `Graph_Builder` SHALL skip that base without emitting an edge or raising an exception.

### Requirement 5: BaseComponentDetector Abstract Base Class

**User Story:** As a developer, I want all component detectors to share a common interface, so that the CV pipeline can swap backends without changing calling code.

#### Acceptance Criteria

1. THE `BaseComponentDetector` SHALL be an abstract base class (using Python's `abc.ABC`) defined in `pipeline.py`.
2. THE `BaseComponentDetector` SHALL declare one abstract method: `detect(img: np.ndarray) -> List[Dict[str, Any]]`.
3. IF a subclass of `BaseComponentDetector` does not implement `detect`, THEN instantiating that subclass SHALL raise `TypeError`.
4. THE `YOLO_Detector` (existing `ComponentDetector` class) SHALL extend `BaseComponentDetector`.
5. THE `FasterRCNN_Detector` SHALL extend `BaseComponentDetector`.
6. THE `YOLO_Detector` `detect` method SHALL return a list of `DetectionResult` dicts; WHEN no model is loaded, THE `YOLO_Detector` SHALL return an empty list without raising an exception.

### Requirement 6: FasterRCNNDetector Backend

**User Story:** As a computer-vision researcher, I want a Faster R-CNN detection backend, so that I can benchmark it against YOLO on architecture diagram component detection.

#### Acceptance Criteria

1. THE `FasterRCNN_Detector` SHALL use `torchvision.models.detection.fasterrcnn_resnet50_fpn` with a pretrained COCO checkpoint as its model.
2. WHEN `FasterRCNN_Detector.detect` is called with a BGR `np.ndarray` image, THE `FasterRCNN_Detector` SHALL convert the image to a normalised float32 RGB tensor and pass it to the model.
3. WHEN `FasterRCNN_Detector.detect` completes inference, THE `FasterRCNN_Detector` SHALL return a list of `DetectionResult` dicts containing `bbox` (as `[x1, y1, x2, y2]` floats), `confidence`, `class_id`, and `class_name` for every prediction whose confidence meets or exceeds the configured threshold.
4. WHEN the `torchvision` or `torch` package is unavailable, THE `FasterRCNN_Detector` SHALL log a warning and return an empty list without raising an exception.
5. WHEN the pretrained model weights cannot be downloaded (network unavailable), THE `FasterRCNN_Detector` SHALL log a warning and return an empty list without raising an exception.
6. THE `FasterRCNN_Detector` SHALL accept a `confidence` float parameter at construction time with a default of `0.5`.
7. THE `FasterRCNN_Detector` `detect` method SHALL return results in the same `DetectionResult` dict format as `YOLO_Detector.detect`.

### Requirement 7: ContainerGraph and build_package_graph

**User Story:** As a software architect, I want modules grouped by their top-level package, so that I can reason about architectural boundaries at the package level rather than individual file level.

#### Acceptance Criteria

1. WHEN `Graph_Builder.build_package_graph` is called after a `build_from_python` or `build_from_java` call, THE `Graph_Builder` SHALL return a `PackageGraph` dict containing `nodes` (one per unique top-level package), `edges` (one per unique cross-package dependency pair), and a `container_graph` dict mapping package name to list of component IDs.
2. THE `Graph_Builder` SHALL derive the top-level package for each component from the first segment of its dotted module ID.
3. WHEN two components in different packages are connected by any edge (`DEPENDS_ON`, `CALLS`, or `INHERITS`), THE `Graph_Builder` SHALL emit exactly one cross-package edge between those package nodes regardless of the number of inter-module edges.
4. THE `PackageGraph` `nodes` list SHALL contain one entry per unique top-level package, with at minimum the fields `id` (package name) and `type` set to `"package"`.
5. THE `PackageGraph` `edges` list SHALL contain one entry per unique directed cross-package dependency, with at minimum the fields `source`, `target`, and `type`.
6. IF all components belong to a single top-level package, THEN THE `Graph_Builder` SHALL return a `PackageGraph` with one node and zero cross-package edges.
7. THE `Graph_Builder` SHALL store the `ContainerGraph` dict as a property (`container_graph`) accessible after calling `build_package_graph`.

### Requirement 8: Test Coverage — CALLS/INHERITS Extraction

**User Story:** As a QA engineer, I want dedicated unit tests for CALLS and INHERITS edge extraction from both Python and Java fixtures, so that regressions are caught immediately.

#### Acceptance Criteria

1. THE test file `backend/tests/unit/test_calls_inheritance.py` SHALL contain tests that verify `CALLS_Edge` emission from both Python and Java fixture files with realistic cross-module method-call patterns.
2. THE test file SHALL verify that `INHERITS_Edge` entries are emitted when fixture classes inherit from classes in other internal modules.
3. THE test file SHALL verify that no duplicate `CALLS_Edge` or `INHERITS_Edge` entries exist in the returned graph.
4. THE test file SHALL verify that `DEPENDS_ON_Edge` entries are still present alongside `CALLS_Edge` and `INHERITS_Edge` entries (no regression).
5. THE test file SHALL use only in-memory string fixtures or `tmp_path` directories — no real network calls or GPU access.

### Requirement 9: Test Coverage — FasterRCNNDetector

**User Story:** As a QA engineer, I want unit tests for the FasterRCNN detector that run without a GPU or network, so that CI always passes regardless of environment.

#### Acceptance Criteria

1. THE test file `backend/tests/unit/test_component_detection.py` SHALL use `unittest.mock.patch` or `pytest-mock` to mock `torchvision.models.detection.fasterrcnn_resnet50_fpn` and the underlying torch inference call.
2. THE test file SHALL verify that `FasterRCNN_Detector.detect` returns `DetectionResult`-shaped dicts when the mock returns synthetic prediction tensors.
3. THE test file SHALL verify that `FasterRCNN_Detector.detect` returns an empty list when `torchvision` is mocked as unavailable.
4. THE test file SHALL verify that `FasterRCNN_Detector` and `YOLO_Detector` are both subclasses of `BaseComponentDetector`.
5. THE test file SHALL verify that an abstract subclass missing `detect` raises `TypeError` on instantiation.
6. THE test file SHALL verify that `YOLO_Detector.detect` returns an empty list when no model is loaded (existing behaviour regression guard).

### Requirement 10: Test Coverage — Package Graph

**User Story:** As a QA engineer, I want unit tests for `build_package_graph`, so that package-level grouping and cross-package edges are verified without relying on external resources.

#### Acceptance Criteria

1. THE test file `backend/tests/unit/test_package_graph.py` SHALL test `build_package_graph` using synthetic in-memory `parsed_files` lists and `tmp_path` roots to avoid file-system dependencies.
2. THE test file SHALL verify that the `PackageGraph` nodes list contains exactly one entry per unique top-level package.
3. THE test file SHALL verify that cross-package edges are correctly emitted and deduplicated.
4. THE test file SHALL verify that `container_graph` maps each package name to its correct list of component IDs.
5. THE test file SHALL verify the single-package edge case: when all components are in the same package, zero cross-package edges are returned.

### Requirement 11: Regression — All Existing Tests Remain Green

**User Story:** As a developer, I want all 75 Sprint 2 tests to keep passing after Sprint 3 changes, so that no previously working behaviour is broken.

#### Acceptance Criteria

1. WHEN the full test suite `pytest backend/tests/` is executed after all Sprint 3 changes, THE test runner SHALL report zero failures and zero errors across all pre-existing test files.
2. THE `Graph_Builder.build_from_python` method SHALL continue to emit `DEPENDS_ON_Edge` entries with `confidence=1.0` for all import-based edges, identical to Sprint 2 output.
3. THE `Graph_Builder.build_from_java` method SHALL continue to emit `DEPENDS_ON_Edge` entries with three-tier confidence scores, identical to Sprint 2 output.
4. THE `YOLO_Detector` (renamed `ComponentDetector`) SHALL retain its existing public interface: `__init__(model_path, confidence)` and `detect(img) -> List[Dict]`.

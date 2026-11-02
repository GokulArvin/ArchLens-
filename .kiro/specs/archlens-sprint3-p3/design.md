# Design Document — archlens-sprint3-p3

## Overview

Sprint 3 P3 deepens ArchLens's static-analysis and computer-vision pipelines across five days (D11–D15). It adds `CALLS` and `INHERITS` semantic edges to both the Python and Java dependency graphs, introduces a `FasterRCNNDetector` as a second component-detection backend behind a shared abstract interface, and groups recovered modules by top-level package into a `PackageGraph`. All 75 existing Sprint 2 tests must stay green throughout.

### Design Goals

1. **Richer dependency semantics** — `DEPENDS_ON` edges (import-level) already exist. `CALLS` (method invocation) and `INHERITS` (class hierarchy) edges give architects a more complete view of cross-module coupling.
2. **Pluggable CV backends** — YOLO and Faster R-CNN share a uniform `BaseComponentDetector` interface so the CV pipeline can swap or run both backends without changing calling code.
3. **Package-level abstraction** — `build_package_graph()` lets architects reason at the package boundary rather than individual file level.
4. **Zero regression** — every extension is additive; existing public APIs and test expectations are preserved.

---

## Architecture

```mermaid
graph TD
    subgraph architecture_recovery [Module D — Architecture Recovery]
        BLP[BaseLanguageParser ABC]
        PAP[PythonASTParser] --> BLP
        JAP[JavaTreeSitterParser] --> BLP
        PAV[_PythonASTVisitor\n+ call_targets\n+ base_names]
        JTV[_JavaTreeSitterVisitor\n+ method_invocations]
        DGB[DependencyGraphBuilder\n+ build_from_python\n+ build_from_java\n+ build_package_graph\n+ container_graph]
        PAP --> PAV
        JAP --> JTV
        PAP --> DGB
        JAP --> DGB
    end

    subgraph cv_pipeline [Module B — CV Pipeline]
        BCD[BaseComponentDetector ABC\ndetect(img) → List[DetectionResult]]
        CD[ComponentDetector\n/YOLO/] --> BCD
        FRCNN[FasterRCNNDetector\n/Faster R-CNN/] --> BCD
        CVP[CVPipeline] --> BCD
    end

    DGB -->|PackageGraph| API
    CVP -->|IntendedGraph| API
```

### Key Principles

- **Additive extension** — `_PythonASTVisitor` gains a `call_targets` list alongside existing `function_calls`; `_JavaTreeSitterVisitor` gains `method_invocations` alongside existing `methods`. Neither old field is removed or renamed.
- **Single responsibility** — visitors collect raw data; `DependencyGraphBuilder` does all resolution and edge creation.
- **Graceful degradation** — every new class (`FasterRCNNDetector`, `build_package_graph`) handles missing optional dependencies and edge conditions without raising unhandled exceptions.
- **Lazy initialisation** — `FasterRCNNDetector` follows the same pattern as `JavaTreeSitterParser`: model loaded once on first `detect()` call, not at construction time.

---

## Components and Interfaces

### 3.1 `_PythonASTVisitor` — extended

```python
class _PythonASTVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        # existing fields preserved
        self.classes: List[Dict[str, Any]]        # unchanged
        self.imports: List[str]                    # unchanged
        self.from_imports: List[Dict[str, Any]]    # unchanged
        self.function_calls: List[str]             # unchanged (ast.unparse of all calls)
        self.functions: List[str]                  # unchanged

        # NEW — Sprint 3
        self.call_targets: List[Dict[str, str]]
        # Each entry: {"object": "obj_name", "method": "method_name"}
        # Populated only for ast.Attribute calls (object.method() form).

    def visit_Call(self, node: ast.Call) -> None:
        """Extended to record attribute-call targets separately from plain calls."""
        # 1. Existing behaviour: ast.unparse into function_calls (unchanged)
        # 2. NEW: if node.func is ast.Attribute, also record structured call_targets entry
        if isinstance(node.func, ast.Attribute):
            obj_name = ast.unparse(node.func.value)   # e.g. "self.service" → "self.service"
            method_name = node.func.attr               # e.g. "create_order"
            self.call_targets.append({"object": obj_name, "method": method_name})
        self.generic_visit(node)
```

The `visit_ClassDef` method already records `bases` via `ast.unparse(b)`. The base names (e.g. `"BaseLanguageParser"`, `"OrderService"`) are already present in each entry of `self.classes["bases"]`. No change needed to `visit_ClassDef` — the builder uses the existing field.

`PythonASTParser.parse_file` is extended to include `call_targets` in its returned dict:

```python
return {
    "file": file_path,
    "classes": visitor.classes,
    "imports": visitor.imports,
    "from_imports": visitor.from_imports,
    "function_calls": visitor.function_calls,   # unchanged
    "functions": visitor.functions,
    "call_targets": visitor.call_targets,        # NEW
}
```

---

### 3.2 `_JavaTreeSitterVisitor` — extended

```python
class _JavaTreeSitterVisitor:
    def __init__(self, source_bytes: bytes) -> None:
        # existing fields preserved
        self.classes: List[Dict[str, Any]]   # unchanged
        self.imports: List[str]               # unchanged
        self.methods: List[str]               # unchanged
        self.package: str                     # unchanged

        # NEW — Sprint 3
        self.method_invocations: List[Dict[str, str]]
        # Each entry: {"object": "obj_name", "method": "method_name"}

    def _visit_method_invocation(self, node) -> None:
        """
        Tree-sitter grammar for method_invocation:
          method_invocation → expression? "." identifier argument_list
          OR: identifier argument_list   (bare call, no object)

        We record only qualified calls (object.method() form) — same
        restriction as the Python visitor.

        Grammar children traversal:
          child[0] = object expression (could be identifier, field_access, etc.)
          child with type == "." = separator (skip)
          child with type == "identifier" after "." = method name
        """
        obj_name: str = ""
        method_name: str = ""
        seen_dot: bool = False
        for child in node.children:
            if child.type == ".":
                seen_dot = True
            elif not seen_dot and child.type in ("identifier", "scoped_identifier",
                                                  "field_access", "this", "super"):
                obj_name = self._text(child)
            elif seen_dot and child.type == "identifier":
                method_name = self._text(child)
                break
        if obj_name and method_name:
            self.method_invocations.append({"object": obj_name, "method": method_name})
```

`JavaTreeSitterParser.parse_file` is extended to include `method_invocations`:

```python
return {
    "file": path,
    "classes": visitor.classes,
    "imports": visitor.imports,
    "methods": visitor.methods,
    "package": visitor.package,
    "method_invocations": visitor.method_invocations,   # NEW
    "metadata": { ... },
}
```

---

### 3.3 `DependencyGraphBuilder` — CALLS/INHERITS resolution

Two new helper methods, plus extensions to the second pass of `build_from_python` and `build_from_java`.

#### New helper: `_build_class_to_module_map`

```python
def _build_class_to_module_map(
    self, parsed_files: List[Dict[str, Any]], repo_root: Path
) -> Dict[str, str]:
    """Return {class_name: module_id} for every class in every internal module.

    When two modules define a class with the same name the last one wins
    (alphabetically deterministic because build passes iterate in insertion order).
    Used by both Python and Java edge resolution.
    """
    class_map: Dict[str, str] = {}
    for file_data in parsed_files:
        if "error" in file_data:
            continue
        module_id = self._path_to_module(file_data["file"], repo_root)
        for cls in file_data.get("classes", []):
            class_map[cls["name"]] = module_id
    return class_map
```

#### CALLS/INHERITS resolution algorithm

Both `build_from_python` and `build_from_java` gain a **third pass** after the existing two passes (register nodes; resolve imports). The algorithm is identical for both languages:

```
Third pass — CALLS and INHERITS edges:
  class_map = _build_class_to_module_map(parsed_files, repo_root)

  For each file_data in parsed_files:
    source_module = _path_to_module(file_data["file"], repo_root)

    # CALLS edges
    for entry in file_data.get("call_targets" | "method_invocations", []):
      obj_name = entry["object"]
      # Strip dotted prefixes: "self.service" → "service"; "OrderService" → "OrderService"
      # Take the last component of any dotted chain as the candidate class name
      candidate = obj_name.split(".")[-1]
      # Capitalise first letter for Python (object names are often lowercase instances)
      # but also try exact match for Java (object could be a type reference)
      target_module = class_map.get(candidate) or class_map.get(_title_case(candidate))
      if target_module and target_module != source_module:
        _add_edge_with_confidence(source_module, target_module, CALLS, confidence=0.7)

    # INHERITS edges
    for cls in file_data.get("classes", []):
      for base_name in cls.get("bases", []):
        # Strip module prefix if present: "services.OrderService" → "OrderService"
        base_simple = base_name.split(".")[-1]
        target_module = class_map.get(base_simple)
        if target_module and target_module != source_module:
          _add_edge_with_confidence(source_module, target_module, INHERITS, confidence=0.9)
```

Deduplication is handled by the existing `_add_edge_with_confidence` which skips insertion when `(source, target, type)` already exists.

#### Updated `build_from_python` signature (unchanged, third pass added)

```python
def build_from_python(
    self, parsed_files: List[Dict[str, Any]], repo_root: str
) -> Dict[str, Any]:
    """Build dependency graph from parsed Python files.

    Pass 1: register nodes (unchanged).
    Pass 2: resolve import → DEPENDS_ON edges (unchanged, confidence=1.0).
    Pass 3 (NEW): resolve call_targets → CALLS edges (confidence=0.7);
                  resolve class bases    → INHERITS edges (confidence=0.9).
    """
```

#### Updated `build_from_java` signature (unchanged, third pass added)

```python
def build_from_java(
    self, parsed_files: List[Dict[str, Any]], repo_root: str
) -> Dict[str, Any]:
    """Build dependency graph from parsed Java files.

    Pass 1: register nodes (unchanged).
    Pass 2: resolve imports → DEPENDS_ON edges (unchanged, three-tier confidence).
    Pass 3 (NEW): resolve method_invocations → CALLS edges (confidence=0.7);
                  resolve class bases          → INHERITS edges (confidence=0.9).
    """
```

---

### 3.4 `build_package_graph` — new method on `DependencyGraphBuilder`

```python
def build_package_graph(self) -> Dict[str, Any]:
    """Group modules by top-level package and build a package-level dependency graph.

    Must be called AFTER build_from_python() or build_from_java() — operates on
    self.nodes and self.edges populated by those methods.

    Returns:
        PackageGraph dict with keys:
          "nodes"           : List[Dict] — one entry per unique top-level package
                              Each node: {"id": pkg_name, "type": "package",
                                          "component_count": int}
          "edges"           : List[Dict] — one entry per unique directed cross-package
                              dependency pair (any edge type)
                              Each edge: {"source": pkg_a, "target": pkg_b, "type": "package_dependency"}
          "container_graph" : Dict[str, List[str]] — package_name → [component_id, ...]

    Side effect:
        Stores the container_graph as self.container_graph for direct attribute access.
    """

    # --- Step 1: build ContainerGraph ---
    container: Dict[str, List[str]] = {}
    for module_id in self.nodes:
        pkg = module_id.split(".")[0]          # first segment = top-level package
        container.setdefault(pkg, []).append(module_id)
    self.container_graph = container            # persist as attribute

    # --- Step 2: build PackageGraph nodes ---
    pkg_nodes = [
        {"id": pkg, "type": "package", "component_count": len(members)}
        for pkg, members in sorted(container.items())
    ]

    # --- Step 3: build cross-package edges (deduplicated) ---
    seen_pkg_edges: Set[Tuple[str, str]] = set()
    pkg_edges: List[Dict[str, str]] = []
    for edge in self.edges:
        src_pkg = edge["source"].split(".")[0]
        tgt_pkg = edge["target"].split(".")[0]
        if src_pkg != tgt_pkg:
            key = (src_pkg, tgt_pkg)
            if key not in seen_pkg_edges:
                seen_pkg_edges.add(key)
                pkg_edges.append({
                    "source": src_pkg,
                    "target": tgt_pkg,
                    "type": "package_dependency",
                })

    return {
        "nodes": pkg_nodes,
        "edges": pkg_edges,
        "container_graph": container,
    }
```

---

### 3.5 `BaseComponentDetector` ABC — new class in `pipeline.py`

```python
from abc import ABC, abstractmethod

class BaseComponentDetector(ABC):
    """Abstract base class for all component-detection backends.

    Subclasses must implement detect(). The CV pipeline interacts exclusively
    with this interface, making backends swappable without changing calling code.
    """

    @abstractmethod
    def detect(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Detect architectural components in a BGR image.

        Args:
            img: H×W×3 BGR uint8 numpy array.

        Returns:
            List of DetectionResult dicts:
            {
                "bbox":       [x1, y1, x2, y2],  # float coordinates
                "confidence": float,              # detection score
                "class_id":   int,
                "class_name": str,
            }
            Returns [] (empty list) on any failure — never raises.
        """
```

`ComponentDetector` is modified to extend `BaseComponentDetector`:

```python
class ComponentDetector(BaseComponentDetector):
    """Stage 3: YOLO-based component detection (renamed YOLO_Detector in design)."""
    # __init__(model_path, confidence) — unchanged public interface
    # detect(img) — unchanged behaviour, return [] when no model loaded
```

---

### 3.6 `FasterRCNNDetector` — new class in `pipeline.py`

```python
class FasterRCNNDetector(BaseComponentDetector):
    """Faster R-CNN component detector using torchvision pretrained COCO model.

    Lazy initialisation: model loaded on first detect() call, not at construction.
    Graceful degradation: returns [] if torch/torchvision unavailable or download fails.
    """

    # COCO class names (91-class; indices match torchvision COCO label map)
    COCO_CLASSES: List[str] = [
        "__background__", "person", "bicycle", "car", "motorcycle",
        "airplane", "bus", "train", "truck", "boat",
        # ... (full 91-entry list)
    ]

    def __init__(self, confidence: float = 0.5) -> None:
        self.confidence = confidence
        self._model = None               # lazy init sentinel
        self._init_attempted = False     # avoid repeated failed downloads

    def _get_model(self):
        """Lazy-initialise Faster R-CNN. Returns None on any failure."""
        if self._model is None and not self._init_attempted:
            self._init_attempted = True
            try:
                import torch
                import torchvision
                weights = torchvision.models.detection.FasterRCNN_ResNet50_FPN_Weights.DEFAULT
                model = torchvision.models.detection.fasterrcnn_resnet50_fpn(weights=weights)
                model.eval()
                self._model = model
            except Exception as e:
                logger.warning(f"FasterRCNNDetector: model unavailable — {e}")
        return self._model

    def detect(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Run Faster R-CNN inference on a BGR image.

        Inference pipeline:
          1. BGR → RGB channel reorder  (img[:, :, ::-1])
          2. uint8 [0,255] → float32 [0.0,1.0]  (/ 255.0)
          3. HWC → CHW layout  (np.transpose(rgb, (2,0,1)))
          4. Wrap in list of tensors  ([torch.from_numpy(chw)])
          5. model([tensor]) → [{boxes, labels, scores}]
          6. Filter predictions where scores >= self.confidence
          7. Build DetectionResult dicts from filtered predictions

        Returns [] without raising on any exception (torch unavailable, OOM, etc.).
        """
        model = self._get_model()
        if model is None:
            return []
        try:
            import torch
            # Step 1-4: preprocessing
            rgb = img[:, :, ::-1].copy()            # BGR → RGB
            tensor = rgb.astype(np.float32) / 255.0  # normalise
            chw = np.transpose(tensor, (2, 0, 1))    # HWC → CHW
            t = torch.from_numpy(chw)

            # Step 5: inference
            with torch.no_grad():
                preds = model([t])[0]

            # Step 6-7: filter and format
            results = []
            boxes   = preds["boxes"].cpu().numpy()
            labels  = preds["labels"].cpu().numpy()
            scores  = preds["scores"].cpu().numpy()

            for box, label, score in zip(boxes, labels, scores):
                if float(score) >= self.confidence:
                    class_id = int(label)
                    class_name = (
                        self.COCO_CLASSES[class_id]
                        if class_id < len(self.COCO_CLASSES)
                        else str(class_id)
                    )
                    results.append({
                        "bbox":       [float(v) for v in box],
                        "confidence": float(score),
                        "class_id":   class_id,
                        "class_name": class_name,
                    })
            return results

        except Exception as e:
            logger.warning(f"FasterRCNNDetector.detect failed: {e}")
            return []
```

---

## Data Models

### DetectionResult dict (standardised format)

Both `ComponentDetector.detect` and `FasterRCNNDetector.detect` return lists of this shape:

```python
{
    "bbox":       List[float],  # [x1, y1, x2, y2] pixel coordinates
    "confidence": float,        # detection score in [0.0, 1.0]
    "class_id":   int,          # model class index
    "class_name": str,          # human-readable class label
}
```

### Edge dict — enhanced

Sprint 3 extends the edge dict with two additional `type` values:

| `type`       | `confidence` | Emitted by                          |
|--------------|--------------|-------------------------------------|
| `depends_on` | 0.5–1.0      | Import resolution (Sprint 2, unchanged) |
| `calls`      | 0.7          | `call_targets` / `method_invocations` resolution (Sprint 3 new) |
| `inherits`   | 0.9          | Class `bases` resolution (Sprint 3 new) |

```python
{
    "source":     str,    # module ID (dotted path)
    "target":     str,    # module ID (dotted path)
    "type":       str,    # RelationshipType value
    "confidence": float,
}
```

### ContainerGraph dict

```python
ContainerGraph = Dict[str, List[str]]
# Example:
{
    "app":   ["app.controllers.order_controller", "app.services.order_service"],
    "tests": ["tests.unit.test_ast_parser"],
}
```

### PackageGraph dict

```python
{
    "nodes": [
        {"id": "app",   "type": "package", "component_count": 4},
        {"id": "tests", "type": "package", "component_count": 5},
    ],
    "edges": [
        {"source": "app", "target": "tests", "type": "package_dependency"},
    ],
    "container_graph": {
        "app":   [...],
        "tests": [...],
    },
}
```

### `DependencyGraphBuilder` — updated attribute list

| Attribute         | Type                         | Set by                        |
|-------------------|------------------------------|-------------------------------|
| `nodes`           | `Dict[str, Dict]`            | `build_from_python/java`      |
| `edges`           | `List[Dict]`                 | `build_from_python/java`      |
| `container_graph` | `Dict[str, List[str]]`       | `build_package_graph()` (NEW) |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: CALLS edges have confidence 0.7

*For any* set of parsed Python or Java files that contain cross-module method-call references, every `CALLS` edge in the output graph SHALL have `confidence == 0.7`.

**Validates: Requirements 1.4, 3.4**

---

### Property 2: INHERITS edges have confidence 0.9

*For any* set of parsed Python or Java files where classes inherit from classes defined in another internal module, every `INHERITS` edge in the output graph SHALL have `confidence == 0.9`.

**Validates: Requirements 2.3, 4.3**

---

### Property 3: Edge deduplication invariant

*For any* set of parsed Python or Java files — regardless of how many times a source module references a target module — the output graph SHALL contain at most one `CALLS` edge and at most one `INHERITS` edge between any given ordered `(source, target)` pair; a `CALLS` edge and a `DEPENDS_ON` edge between the same pair are distinct and both SHALL be present.

**Validates: Requirements 1.3, 2.2, 3.3, 4.2**

---

### Property 4: DEPENDS_ON edges are preserved (regression)

*For any* set of parsed Python files that would have produced `DEPENDS_ON` edges under Sprint 2, the Sprint 3 output SHALL contain all the same `DEPENDS_ON` edges with the same confidence values, in addition to any new `CALLS` or `INHERITS` edges.

**Validates: Requirements 1.5, 3.5, 11.2, 11.3**

---

### Property 5: PackageGraph node count equals unique package count

*For any* set of parsed files with `N` distinct top-level packages, `build_package_graph()` SHALL return a `PackageGraph` with exactly `N` nodes, each having `id` equal to the package name and `type == "package"`.

**Validates: Requirements 7.1, 7.2, 7.4**

---

### Property 6: Cross-package edges are deduplicated

*For any* dependency graph where multiple module-level edges exist between packages A and B (of any type — `DEPENDS_ON`, `CALLS`, or `INHERITS`), `build_package_graph()` SHALL emit exactly one `PackageGraph` edge from A to B.

**Validates: Requirements 7.3, 7.5**

---

### Property 7: FasterRCNNDetector confidence threshold filtering

*For any* synthetic set of prediction scores returned by the model, `FasterRCNNDetector.detect` SHALL return only `DetectionResult` entries whose score is greater than or equal to the configured `confidence` threshold; entries below the threshold SHALL be excluded from the result.

**Validates: Requirements 6.3**

---

### Property 8: DetectionResult format consistency between backends

*For any* detection call returning non-empty results, the `DetectionResult` dicts returned by `FasterRCNNDetector.detect` SHALL contain the same keys (`bbox`, `confidence`, `class_id`, `class_name`) with the same value types as those returned by `ComponentDetector.detect`.

**Validates: Requirements 6.7**

---

## Error Handling

### `_PythonASTVisitor.visit_Call` — robustness

The existing `try/except` block around `ast.unparse(node.func)` is extended to guard the new `call_targets` append; if `ast.Attribute` attribute access raises (malformed AST), the entry is silently skipped.

### `_JavaTreeSitterVisitor._visit_method_invocation` — robustness

All child-node access is guarded. If the `method_invocation` node has unexpected structure (e.g. no dot separator, anonymous call), no entry is appended and traversal continues.

### `DependencyGraphBuilder` — unresolvable references

Both the CALLS and INHERITS resolution passes follow the pattern: "if `class_map.get(candidate)` returns `None`, skip without logging at WARNING level (too noisy for external library references)." This matches the existing behaviour for unresolvable imports.

### `FasterRCNNDetector` — layered fallback

| Failure point                       | Behaviour                                      |
|-------------------------------------|------------------------------------------------|
| `torch` / `torchvision` not installed | `ImportError` caught in `_get_model()`, `_init_attempted=True`, returns `[]` |
| Pretrained weights download fails    | Exception caught in `_get_model()`, returns `[]` |
| OOM / inference error               | Exception caught in `detect()`, returns `[]`    |

### `build_package_graph` — pre-condition

If called before `build_from_python` or `build_from_java` (i.e. `self.nodes` and `self.edges` are empty), the method returns a valid empty PackageGraph `{"nodes": [], "edges": [], "container_graph": {}}`.

---

## Testing Strategy

### New test files

| File                                              | Scope                                  |
|---------------------------------------------------|----------------------------------------|
| `backend/tests/unit/test_calls_inheritance.py`    | CALLS/INHERITS edges — Python & Java   |
| `backend/tests/unit/test_component_detection.py`  | `BaseComponentDetector`, `FasterRCNNDetector` |
| `backend/tests/unit/test_package_graph.py`        | `build_package_graph`, `ContainerGraph` |

All new tests use `unittest.mock.patch`, `pytest` fixtures, `tmp_path`, and in-memory string fixtures. No real network calls, GPU access, or file-system fixtures required beyond `tmp_path`.

### Dual testing approach

- **Unit/example tests** — specific scenarios, error conditions, structural checks (ABC enforcement, empty-list fallbacks, confidence threshold boundary)
- **Property-based tests** (Hypothesis) — universal properties covering all eight correctness properties above; minimum 100 examples per property

### Property test configuration

```python
# Hypothesis settings for all Sprint 3 property tests
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(...)
def test_property_<name>(...):
    # Feature: archlens-sprint3-p3, Property N: <property_text>
    ...
```

Tag format in every property test: `# Feature: archlens-sprint3-p3, Property N: <property_text>`

### Test sketches for each property

**Property 1 & 2 — Confidence values:**

```python
# Build synthetic parsed_files:
#   module_a has call_targets=[{"object":"B", "method":"foo"}]  and  classes=[{"name":"B", "bases":[]}]
#   module_b has classes=[{"name":"B", ...}]
# Verify: all CALLS edges confidence==0.7, all INHERITS edges confidence==0.9
```

**Property 3 — Deduplication:**

```python
# module_a has two call_targets both pointing to class B in module_b
# Verify: len([e for e in edges if e["type"]=="calls" and e["source"]==module_a and e["target"]==module_b]) == 1
```

**Property 4 — DEPENDS_ON regression:**

```python
# module_a imports module_b AND calls a method on a class from module_b
# Verify: both DEPENDS_ON and CALLS edges present for (module_a, module_b)
```

**Property 5 & 6 — PackageGraph:**

```python
# Hypothesis: generate list of (pkg_prefix, n_modules) tuples
# Build parsed_files with those modules, run build_from_python, then build_package_graph
# Verify node count == number of unique pkg prefixes
# Verify cross-package edges == unique (src_pkg, tgt_pkg) pairs from inter-module edges
```

**Property 7 — Threshold filtering:**

```python
# Mock model returns N predictions with random scores in [0,1]
# For threshold T, verify: all returned results have score >= T, none below T
```

**Property 8 — Format consistency:**

```python
# Mock both detectors to return one prediction each
# Verify returned dicts have identical key sets and value types
```

### Regression guard

The full existing suite (`pytest backend/tests/`) must pass after each Sprint 3 commit. CI runs all tests; Sprint 3 tasks are gated on zero failures across the 75 pre-existing tests plus all new ones.

### PBT library

[Hypothesis](https://hypothesis.readthedocs.io/) — already used in the Sprint 2 test suite (`test_java_parser.py`). No new dependency introduced.

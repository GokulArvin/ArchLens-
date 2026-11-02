"""
Module D: Source-Code Architecture Recovery (Sprint 1 D4).
Deterministic AST-based dependency extraction.

Principle: This stage does NOT primarily use an LLM.
Static analysis = structural truth; LLM = semantic interpretation.

Supports:
- Python: built-in ast module for deterministic AST analysis
  (classes, functions, calls, imports, relative imports, and module dependencies)
- Java: tree-sitter 0.23.2 + tree-sitter-java grammar for multi-language repos.
"""

import ast
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import logging

from app.schemas.models import ComponentType, RelationshipType

logger = logging.getLogger(__name__)

# Optional tree-sitter imports — module still loads if tree-sitter-java is not installed
try:
    from tree_sitter import Language, Parser as TSParser
    import tree_sitter_java as tsjava
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    _TREE_SITTER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Task 3.1 — BaseLanguageParser ABC
# ---------------------------------------------------------------------------

class BaseLanguageParser(ABC):
    """Abstract base class for all language-specific source parsers.

    Every subclass MUST implement the three abstract methods below.
    Python's ABC mechanism enforces this at instantiation time — any
    incomplete subclass raises TypeError.
    """

    @abstractmethod
    def parse_file(self, path: str) -> Dict[str, Any]:
        """Parse a single source file and return a ParseResult dict.

        On success: returns ParseResult (see schema in design doc).
        On failure: returns {"file": path, "error": "<description>"}
                    WITHOUT raising an exception.
        """

    @abstractmethod
    def parse_directory(self, path: str) -> List[Dict[str, Any]]:
        """Recursively parse all supported files under `path`.

        Returns a list of ParseResult dicts, one per file.
        Ignores .git, target, build, __pycache__ directories.
        """

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return the list of file extensions this parser handles.

        Example: [".py"] for PythonASTParser, [".java"] for JavaTreeSitterParser.
        """


# ---------------------------------------------------------------------------
# Task 3.2 — PythonASTParser (refactored to extend BaseLanguageParser)
# ---------------------------------------------------------------------------

class PythonASTParser(BaseLanguageParser):
    """Python source code parser using the built-in ast module."""

    def supported_extensions(self) -> List[str]:
        return [".py"]

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Extract classes, imports, function calls, and dependencies from a single file."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return {"file": file_path, "error": str(e)}

        visitor = _PythonASTVisitor()
        visitor.visit(tree)

        return {
            "file": file_path,
            "classes": visitor.classes,
            "imports": visitor.imports,
            "from_imports": visitor.from_imports,
            "function_calls": visitor.function_calls,
            "functions": visitor.functions,
            "call_targets": visitor.call_targets,  # Sprint 3
        }

    def parse_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """Parse all Python files in a directory, ignoring virtualenvs and caches."""
        results = []
        for py_file in Path(dir_path).rglob("*.py"):
            path_str = str(py_file)
            if any(ignore in path_str for ignore in [".venv", "venv", "__pycache__", ".git", ".pytest_cache"]):
                continue
            results.append(self.parse_file(path_str))
        return results


class _PythonASTVisitor(ast.NodeVisitor):
    """AST visitor to extract architectural entities."""

    def __init__(self):
        self.classes: List[Dict[str, Any]] = []
        self.imports: List[str] = []
        self.from_imports: List[Dict[str, Any]] = []
        self.function_calls: List[str] = []
        self.functions: List[str] = []
        # Sprint 3: structured call targets for cross-module CALLS edge extraction
        self.call_targets: List[Dict[str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = [ast.unparse(b) for b in node.bases]
        self.classes.append({
            "name": node.name,
            "bases": bases,
            "line": node.lineno,
            "decorators": [ast.unparse(d) for d in node.decorator_list],
        })
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        level = node.level or 0
        names = [alias.name for alias in node.names]
        self.from_imports.append({
            "module": module,
            "names": names,
            "level": level,
        })

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append(node.name)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call):
        try:
            self.function_calls.append(ast.unparse(node.func))
            # Sprint 3: record attribute-call targets (object.method() form) for CALLS edge extraction
            if isinstance(node.func, ast.Attribute):
                obj_name = ast.unparse(node.func.value)
                method_name = node.func.attr
                self.call_targets.append({"object": obj_name, "method": method_name})
        except Exception:
            pass
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Task 4.1 — _JavaTreeSitterVisitor helper class
# ---------------------------------------------------------------------------

class _JavaTreeSitterVisitor:
    """Walks a tree-sitter Java AST and extracts architectural entities."""

    def __init__(self, source_bytes: bytes):
        self._src = source_bytes
        self.classes: List[Dict[str, Any]] = []
        self.imports: List[str] = []
        self.methods: List[str] = []
        self.package: str = ""
        # Sprint 3: method invocation targets for CALLS edge extraction
        self.method_invocations: List[Dict[str, str]] = []

    def _text(self, node) -> str:
        """Extract UTF-8 text for a node from source bytes."""
        return self._src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def visit(self, node) -> None:
        """Recursive DFS traversal of the tree-sitter node tree."""
        handler = getattr(self, f"_visit_{node.type}", None)
        if handler:
            handler(node)
        for child in node.children:
            self.visit(child)

    def _visit_package_declaration(self, node) -> None:
        # Grammar: package_declaration → "package" scoped_identifier ";"
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                self.package = self._text(child)
                return

    def _visit_import_declaration(self, node) -> None:
        # Grammar: import_declaration → "import" ("static")? scoped_identifier ("." "*")? ";"
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                self.imports.append(self._text(child))
                return

    def _visit_class_declaration(self, node) -> None:
        # Grammar: class_declaration → modifiers? "class" identifier
        #          superclass? super_interfaces? class_body
        name = ""
        bases: List[str] = []
        decorators: List[str] = []
        line = node.start_point[0] + 1  # tree-sitter rows are 0-indexed

        for child in node.children:
            if child.type == "identifier":
                name = self._text(child)
            elif child.type == "superclass":
                # superclass → "extends" type_identifier
                for sc in child.children:
                    if sc.type == "type_identifier":
                        bases.append(self._text(sc))
            elif child.type == "super_interfaces":
                # super_interfaces → "implements" type_list
                for si in child.children:
                    if si.type == "type_list":
                        for iface in si.children:
                            if iface.type == "type_identifier":
                                bases.append(self._text(iface))
            elif child.type == "modifiers":
                # Collect annotations as decorators
                for mod in child.children:
                    if mod.type in ("marker_annotation", "annotation"):
                        decorators.append(self._text(mod))

        if name:
            self.classes.append({
                "name": name,
                "bases": bases,
                "line": line,
                "decorators": decorators,
            })

    def _visit_method_declaration(self, node) -> None:
        # Grammar: method_declaration → modifiers? type_identifier identifier formal_parameters ...
        for child in node.children:
            if child.type == "identifier":
                self.methods.append(self._text(child))
                return

    def _visit_method_invocation(self, node) -> None:
        """Extract object.method() call targets for CALLS edge resolution (Sprint 3).

        Grammar: method_invocation → expression "." identifier argument_list
        Records only qualified calls (object.method form).
        """
        try:
            obj_name: str = ""
            method_name: str = ""
            seen_dot: bool = False
            for child in node.children:
                if child.type == ".":
                    seen_dot = True
                elif not seen_dot and child.type in (
                    "identifier", "scoped_identifier", "field_access", "this", "super"
                ):
                    obj_name = self._text(child)
                elif seen_dot and child.type == "identifier":
                    method_name = self._text(child)
                    break
            if obj_name and method_name:
                self.method_invocations.append({"object": obj_name, "method": method_name})
        except Exception:
            pass  # unexpected grammar shape — skip silently


# ---------------------------------------------------------------------------
# Task 4.2 — JavaTreeSitterParser class
# ---------------------------------------------------------------------------

class JavaTreeSitterParser(BaseLanguageParser):
    """Java source parser using tree-sitter 0.23.2 + tree-sitter-java grammar."""

    # Class-level singleton to avoid repeated Language/Parser construction
    _language: Optional[Any] = None
    _parser: Optional[Any] = None
    # Sentinel so we can distinguish "not tried yet" from "tried and failed"
    _init_attempted: bool = False

    # Sentinel so we can distinguish "not tried yet" from "tried and failed"
    _init_attempted: bool = False

    @classmethod
    def _get_parser(cls):
        """Lazy-initialise the tree-sitter Language and Parser."""
        if cls._parser is None and not cls._init_attempted:
            cls._init_attempted = True
            try:
                from tree_sitter import Language, Parser
                import tree_sitter_java as tsjava
                cls._language = Language(tsjava.language())
                # tree-sitter 0.23.x: language is passed to Parser constructor
                cls._parser = Parser(cls._language)
            except Exception as e:
                logger.warning(f"tree-sitter-java not available: {e}")
                return None
        return cls._parser

    def supported_extensions(self) -> List[str]:
        return [".java"]

    def parse_file(self, path: str) -> Dict[str, Any]:
        """Parse a single .java file using tree-sitter.

        Returns ParseResult dict on success; {"file": path, "error": str} on failure.
        """
        try:
            with open(path, "rb") as f:
                source_bytes = f.read()
        except OSError as e:
            return {"file": path, "error": f"Cannot read file: {e}"}

        parser = self._get_parser()
        if parser is None:
            return {
                "file": path,
                "classes": [],
                "imports": [],
                "methods": [],
                "package": "",
                "metadata": {"source_language": "java", "error": "tree-sitter-java unavailable"},
            }

        try:
            tree = parser.parse(source_bytes)
        except Exception as e:
            return {"file": path, "error": f"tree-sitter parse error: {e}"}

        visitor = _JavaTreeSitterVisitor(source_bytes)
        visitor.visit(tree.root_node)

        return {
            "file": path,
            "classes": visitor.classes,
            "imports": visitor.imports,
            "methods": visitor.methods,
            "package": visitor.package,
            "method_invocations": visitor.method_invocations,  # Sprint 3
            "metadata": {
                "source_language": "java",
                "node_count": tree.root_node.child_count,
            },
        }

    def parse_directory(self, path: str) -> List[Dict[str, Any]]:
        """Recursively parse all .java files under `path`.

        Ignored directory names: .git, target, build, __pycache__
        """
        _IGNORE = {".git", "target", "build", "__pycache__"}
        results = []
        for java_file in Path(path).rglob("*.java"):
            if any(part in _IGNORE for part in java_file.parts):
                continue
            results.append(self.parse_file(str(java_file)))
        return results


# ---------------------------------------------------------------------------
# DependencyGraphBuilder (unchanged for tasks 3.1–4.2; extended in task 5)
# ---------------------------------------------------------------------------

class DependencyGraphBuilder:
    """
    Builds G_C (current architecture graph) from parsed AST data.
    Maps files/modules to architectural components and extracts dependencies.
    """

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    def build_from_python(
        self, parsed_files: List[Dict[str, Any]], repo_root: str
    ) -> Dict[str, Any]:
        """Build dependency graph from parsed Python files."""
        repo_root_path = Path(repo_root).resolve()
        self.nodes = {}
        self.edges = []

        # First pass: register all internal modules
        module_file_map = {}
        for file_data in parsed_files:
            if "error" in file_data:
                continue
            file_path = file_data["file"]
            module_name = self._path_to_module(file_path, repo_root_path)
            module_file_map[module_name] = file_path

            comp_type = self._infer_component_type(module_name, file_data)
            keyword_match = comp_type != ComponentType.MODULE.value
            inference_confidence = 1.0 if keyword_match else 0.6
            self.nodes[module_name] = {
                "id": module_name,
                "name": Path(file_path).stem,
                "type": comp_type,
                "file": file_path,
                "classes": [c["name"] for c in file_data.get("classes", [])],
                "inference_confidence": inference_confidence,
                "metadata": {
                    "functions": file_data.get("functions", []),
                    "classes_full": file_data.get("classes", []),
                },
            }

        # Second pass: resolve internal dependencies
        for file_data in parsed_files:
            if "error" in file_data:
                continue

            file_path = file_data["file"]
            source_module = self._path_to_module(file_path, repo_root_path)

            # Direct imports: e.g. 'import app.services.order_service'
            for imp in file_data.get("imports", []):
                target_module = self._resolve_internal_target(imp, module_file_map, repo_root_path)
                if target_module and target_module != source_module:
                    self._add_edge(source_module, target_module, RelationshipType.DEPENDS_ON.value)

            # From imports: e.g. 'from app.services import order_service' or relative 'from ..services import ...'
            for from_imp in file_data.get("from_imports", []):
                target_module = self._resolve_from_import(
                    from_imp, source_module, module_file_map, repo_root_path
                )
                if target_module and target_module != source_module:
                    self._add_edge(source_module, target_module, RelationshipType.DEPENDS_ON.value)

        # Third pass (Sprint 3): CALLS + INHERITS edges from Python
        class_map = self._build_class_to_module_map(parsed_files, repo_root_path)
        for file_data in parsed_files:
            if "error" in file_data:
                continue
            source_module = self._path_to_module(file_data["file"], repo_root_path)

            # Build a local-name → module_id map from this file's imports
            # e.g. "from module_a import OrderService" → {"OrderService": "module_a"}
            local_import_map: Dict[str, str] = {}
            for from_imp in file_data.get("from_imports", []):
                resolved = self._resolve_from_import(
                    from_imp, source_module, {
                        self._path_to_module(fd["file"], repo_root_path): fd["file"]
                        for fd in parsed_files if "error" not in fd
                    }, repo_root_path
                )
                if resolved:
                    for name in from_imp.get("names", []):
                        local_import_map[name] = resolved

            # CALLS edges: if this file has method calls AND imports from internal modules,
            # emit CALLS edges to those imported modules.
            # (Python instance variables can't be reliably resolved to class names
            # without type inference; using the import set as the proxy is deterministic.)
            if file_data.get("call_targets"):
                for target_module in set(local_import_map.values()):
                    if target_module != source_module:
                        self._add_edge_with_confidence(
                            source_module, target_module, RelationshipType.CALLS.value, 0.7
                        )
                # Also match cases where the object IS the class name (e.g. static calls)
                for entry in file_data.get("call_targets", []):
                    candidate = entry["object"].split(".")[-1]
                    direct = class_map.get(candidate) or class_map.get(candidate.title())
                    if direct and direct != source_module:
                        self._add_edge_with_confidence(
                            source_module, direct, RelationshipType.CALLS.value, 0.7
                        )

            for cls in file_data.get("classes", []):
                for base in cls.get("bases", []):
                    base_simple = base.split(".")[-1]
                    target = class_map.get(base_simple) or local_import_map.get(base_simple)
                    if target and target != source_module:
                        self._add_edge_with_confidence(
                            source_module, target, RelationshipType.INHERITS.value, 0.9
                        )

        return {
            "schema_version": "1.0.0",
            "id": f"gc-{repo_root_path.name}",
            "name": repo_root_path.name or "RecoveredCurrentArchitecture",
            "graph_type": "current",
            "source": str(repo_root_path),
            "components": list(self.nodes.values()),
            "relationships": self.edges,
            "metadata": {
                "total_components": len(self.nodes),
                "total_relationships": len(self.edges),
                "language": "python",
            },
        }

    def _add_edge_with_confidence(self, source: str, target: str, rel_type: str, confidence: float) -> None:
        """Add a directed edge with explicit confidence, deduplicating by source+target+type."""
        for e in self.edges:
            if e["source"] == source and e["target"] == target and e["type"] == rel_type:
                return
        self.edges.append({
            "source": source,
            "target": target,
            "type": rel_type,
            "confidence": confidence,
        })

    def _add_edge(self, source: str, target: str, rel_type: str) -> None:
        """Add an edge with default confidence=1.0 (preserves Sprint 1 behaviour)."""
        self._add_edge_with_confidence(source, target, rel_type, confidence=1.0)

    def _path_to_module(self, file_path: str, repo_root: Path) -> str:
        """Convert file path to dotted module name relative to repo root."""
        try:
            rel = Path(file_path).resolve().relative_to(repo_root)
            parts = list(rel.with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            return ".".join(parts) if parts else Path(file_path).stem
        except Exception:
            return Path(file_path).stem

    def _resolve_internal_target(
        self, import_name: str, module_map: Dict[str, str], repo_root: Path
    ) -> Optional[str]:
        """Find corresponding internal module name for an import."""
        if import_name in module_map:
            return import_name
        for mod in module_map:
            if mod == import_name or import_name.startswith(mod + ".") or mod.startswith(import_name + "."):
                return mod
        return None

    def _resolve_from_import(
        self,
        from_imp: Dict[str, Any],
        source_module: str,
        module_map: Dict[str, str],
        repo_root: Path,
    ) -> Optional[str]:
        """Resolve from-imports including relative imports (level > 0)."""
        module = from_imp.get("module") or ""
        level = from_imp.get("level", 0)

        if level > 0:
            src_parts = source_module.split(".")
            if len(src_parts) >= level:
                base_parts = src_parts[:-level]
            else:
                base_parts = []

            if module:
                resolved_mod = ".".join(base_parts + module.split(".")) if base_parts else module
            else:
                resolved_mod = ".".join(base_parts)

            if resolved_mod in module_map:
                return resolved_mod
            for name in from_imp.get("names", []):
                candidate = f"{resolved_mod}.{name}" if resolved_mod else name
                if candidate in module_map:
                    return candidate
            return resolved_mod if resolved_mod else None

        if module:
            match = self._resolve_internal_target(module, module_map, repo_root)
            if match:
                return match
            for name in from_imp.get("names", []):
                candidate = f"{module}.{name}"
                if candidate in module_map:
                    return candidate

        return None

    def build_package_graph(self) -> Dict[str, Any]:
        """Group modules by top-level package and build a package-level dependency graph.

        Must be called AFTER build_from_python() or build_from_java().
        Returns a PackageGraph dict with nodes (one per package), edges (cross-package
        dependencies, deduplicated), and a container_graph mapping package → component IDs.

        Side effect: stores container_graph as self.container_graph.
        """
        if not self.nodes:
            self.container_graph: Dict[str, List[str]] = {}
            return {"nodes": [], "edges": [], "container_graph": {}}

        # Step 1 — ContainerGraph: package → [component_ids]
        container: Dict[str, List[str]] = {}
        for module_id in self.nodes:
            pkg = module_id.split(".")[0]
            container.setdefault(pkg, []).append(module_id)
        self.container_graph = container

        # Step 2 — Package nodes (sorted for determinism)
        pkg_nodes = [
            {"id": pkg, "type": "package", "component_count": len(members)}
            for pkg, members in sorted(container.items())
        ]

        # Step 3 — Cross-package edges (deduplicated)
        seen_pkg_edges: set = set()
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

        return {"nodes": pkg_nodes, "edges": pkg_edges, "container_graph": container}

    def _build_class_to_module_map(
        self, parsed_files: List[Dict[str, Any]], repo_root: Path
    ) -> Dict[str, str]:
        """Return {class_name: module_id} for every class in every internal module.

        Used by the CALLS/INHERITS resolution third pass in build_from_python and build_from_java.
        When two modules define a class with the same name, the last one encountered wins.
        """
        class_map: Dict[str, str] = {}
        for file_data in parsed_files:
            if "error" in file_data:
                continue
            module_id = self._path_to_module(file_data["file"], repo_root)
            for cls in file_data.get("classes", []):
                class_map[cls["name"]] = module_id
        return class_map

    def _infer_component_type(self, module_name: str, file_data: Dict[str, Any]) -> str:
        """Heuristically infer component type from module name and classes."""
        name_lower = module_name.lower()
        if any(k in name_lower for k in ["controller", "router", "view", "api", "endpoint"]):
            return ComponentType.CONTROLLER.value
        if any(k in name_lower for k in ["service", "business", "domain", "handler"]):
            return ComponentType.SERVICE.value
        if any(k in name_lower for k in ["repository", "repo", "dao", "db", "database", "store"]):
            return ComponentType.REPOSITORY.value
        if any(k in name_lower for k in ["model", "schema", "entity", "dto"]):
            return ComponentType.MODEL.value
        if any(k in name_lower for k in ["queue", "kafka", "rabbit", "broker"]):
            return ComponentType.QUEUE.value
        if any(k in name_lower for k in ["gateway", "proxy"]):
            return ComponentType.GATEWAY.value
        if any(k in name_lower for k in ["util", "helper", "common", "shared"]):
            return ComponentType.UTILITY.value
        if any(k in name_lower for k in ["interface", "protocol", "abc"]):
            return ComponentType.INTERFACE.value
        return ComponentType.MODULE.value

    def _resolve_java_import(
        self, import_str: str, module_map: Dict[str, str]
    ) -> Tuple[Optional[str], float]:
        """Resolve a Java import string to an internal module with a confidence score.

        Tiers:
          1.0 — exact match
          0.8 — single partial match (last segment equality / prefix / suffix)
          0.5 — ambiguous (multiple candidates)
          (None, 0.0) — external / no match
        """
        # Tier 1: exact match
        if import_str in module_map:
            return import_str, 1.0

        # Collect partial matches by last-segment comparison
        import_last = import_str.split(".")[-1].lower()
        candidates = []
        for mod in module_map:
            mod_stem = mod.split(".")[-1].lower()
            if (
                mod == import_str
                or import_str.endswith("." + mod)
                or mod.endswith("." + import_last)
                or mod_stem == import_last
            ):
                candidates.append(mod)

        if len(candidates) == 1:
            return candidates[0], 0.8
        elif len(candidates) > 1:
            return sorted(candidates)[0], 0.5  # deterministic: pick first alphabetically

        return None, 0.0

    def build_from_java(
        self, parsed_files: List[Dict[str, Any]], repo_root: str
    ) -> Dict[str, Any]:
        """Build dependency graph from parsed Java files.

        Produces a CurrentGraph-compatible dict equivalent in structure
        to the output of build_from_python().
        """
        repo_root_path = Path(repo_root).resolve()
        self.nodes = {}
        self.edges = []

        # First pass: register all internal Java modules
        module_file_map: Dict[str, str] = {}
        for file_data in parsed_files:
            if "error" in file_data:
                continue
            file_path = file_data["file"]
            module_name = self._path_to_module(file_path, repo_root_path)
            module_file_map[module_name] = file_path

            comp_type = self._infer_component_type(module_name, file_data)
            keyword_match = comp_type != ComponentType.MODULE.value
            inference_confidence = 1.0 if keyword_match else 0.6

            self.nodes[module_name] = {
                "id": module_name,
                "name": Path(file_path).stem,
                "type": comp_type,
                "file": file_path,
                "classes": [c["name"] for c in file_data.get("classes", [])],
                "inference_confidence": inference_confidence,
                "metadata": {
                    "package": file_data.get("package", ""),
                    "classes_full": file_data.get("classes", []),
                    "methods": file_data.get("methods", []),
                    "source_language": "java",
                },
            }

        # Second pass: resolve import dependencies with confidence scoring
        for file_data in parsed_files:
            if "error" in file_data:
                continue
            file_path = file_data["file"]
            source_module = self._path_to_module(file_path, repo_root_path)

            for imp in file_data.get("imports", []):
                target_module, confidence = self._resolve_java_import(imp, module_file_map)
                if target_module and target_module != source_module:
                    self._add_edge_with_confidence(
                        source_module, target_module,
                        RelationshipType.DEPENDS_ON.value,
                        confidence
                    )

        # Third pass (Sprint 3): CALLS + INHERITS edges from Java
        class_map = self._build_class_to_module_map(parsed_files, repo_root_path)
        module_file_map_java = {
            self._path_to_module(fd["file"], repo_root_path): fd["file"]
            for fd in parsed_files if "error" not in fd
        }
        for file_data in parsed_files:
            if "error" in file_data:
                continue
            source_module = self._path_to_module(file_data["file"], repo_root_path)

            # Build local import alias map from Java import statements
            # e.g. "import services.OrderService" → last segment "OrderService" → target module
            local_import_map_java: Dict[str, str] = {}
            for imp in file_data.get("imports", []):
                target_mod, _ = self._resolve_java_import(imp, module_file_map_java)
                if target_mod:
                    local_name = imp.split(".")[-1]
                    local_import_map_java[local_name] = target_mod

            # CALLS edges: if this file has method invocations AND internal imports,
            # emit CALLS edges to those imported modules.
            if file_data.get("method_invocations"):
                for target_mod in set(local_import_map_java.values()):
                    if target_mod != source_module:
                        self._add_edge_with_confidence(
                            source_module, target_mod, RelationshipType.CALLS.value, 0.7
                        )
                # Also match direct class-name references (e.g. static calls)
                for entry in file_data.get("method_invocations", []):
                    candidate = entry["object"].split(".")[-1]
                    direct = class_map.get(candidate) or class_map.get(candidate.title())
                    if direct and direct != source_module:
                        self._add_edge_with_confidence(
                            source_module, direct, RelationshipType.CALLS.value, 0.7
                        )
            for cls in file_data.get("classes", []):
                for base in cls.get("bases", []):
                    base_simple = base.split(".")[-1]
                    target = class_map.get(base_simple) or local_import_map_java.get(base_simple)
                    if target and target != source_module:
                        self._add_edge_with_confidence(
                            source_module, target, RelationshipType.INHERITS.value, 0.9
                        )

        return {
            "schema_version": "1.0.0",
            "id": f"gc-{repo_root_path.name}",
            "name": repo_root_path.name or "RecoveredCurrentArchitecture",
            "graph_type": "current",
            "source": str(repo_root_path),
            "components": list(self.nodes.values()),
            "relationships": self.edges,
            "metadata": {
                "total_components": len(self.nodes),
                "total_relationships": len(self.edges),
                "language": "java",
            },
        }


# ---------------------------------------------------------------------------
# ArchitectureRecoveryPipeline — Sprint 2 P3 (Tasks 6.1–6.3)
# ---------------------------------------------------------------------------

class ArchitectureRecoveryPipeline:
    """Main orchestrator for multi-language source-code architecture recovery.

    Supports:
      language="python" — PythonASTParser only (Sprint 1 behaviour preserved)
      language="java"   — JavaTreeSitterParser only
      language="mixed"  — auto-detect, routes .py → Python, .java → Java
    """

    def __init__(self):
        self.python_parser = PythonASTParser()
        self.java_parser = JavaTreeSitterParser()
        self.graph_builder = DependencyGraphBuilder()

    def analyze_repository(
        self, repo_path: str, language: str = "python"
    ) -> Dict[str, Any]:
        """Full pipeline: repo directory → G_C (CurrentGraph-compatible dict)."""
        logger.info(f"Analyzing repository: {repo_path} (language: {language})")

        if language == "python":
            parsed = self.python_parser.parse_directory(repo_path)
            graph = self.graph_builder.build_from_python(parsed, repo_path)
        elif language == "java":
            parsed = self.java_parser.parse_directory(repo_path)
            graph = self.graph_builder.build_from_java(parsed, repo_path)
        elif language == "mixed":
            py_parsed = self.python_parser.parse_directory(repo_path)
            java_parsed = self.java_parser.parse_directory(repo_path)
            graph = self._merge_graphs(py_parsed, java_parsed, repo_path)
        else:
            logger.warning(f"Unknown language '{language}'; falling back to Python AST.")
            parsed = self.python_parser.parse_directory(repo_path)
            graph = self.graph_builder.build_from_python(parsed, repo_path)

        graph["source"] = repo_path
        logger.info(
            f"Recovery complete: {len(graph['components'])} components, "
            f"{len(graph['relationships'])} relationships"
        )
        return graph

    def _merge_graphs(
        self,
        py_parsed: List[Dict[str, Any]],
        java_parsed: List[Dict[str, Any]],
        repo_path: str,
    ) -> Dict[str, Any]:
        """Merge Python and Java parse results into a single CurrentGraph-compatible dict.

        Uses fresh DependencyGraphBuilder instances to avoid shared state.
        """
        repo_root = Path(repo_path).resolve()

        py_builder = DependencyGraphBuilder()
        java_builder = DependencyGraphBuilder()

        py_graph = py_builder.build_from_python(py_parsed, repo_path)
        java_graph = java_builder.build_from_java(java_parsed, repo_path)

        merged_components = py_graph["components"] + java_graph["components"]
        merged_relationships = py_graph["relationships"] + java_graph["relationships"]

        return {
            "schema_version": "1.0.0",
            "id": f"gc-{repo_root.name}-mixed",
            "name": repo_root.name or "RecoveredCurrentArchitecture",
            "graph_type": "current",
            "source": str(repo_root),
            "components": merged_components,
            "relationships": merged_relationships,
            "metadata": {
                "total_components": len(merged_components),
                "total_relationships": len(merged_relationships),
                "language": "mixed",
                "python_components": len(py_graph["components"]),
                "java_components": len(java_graph["components"]),
            },
        }

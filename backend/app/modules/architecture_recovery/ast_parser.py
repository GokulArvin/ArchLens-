
"""
Module D: Source-Code Architecture Recovery

Deterministic AST-based dependency extraction.

Principle:
    Static analysis = structural truth
    LLM = semantic interpretation

Currently supported:
    Python: built-in ast module

Planned:
    Java: tree-sitter / JavaParser
    Multi-language: tree-sitter
"""

import ast
import logging

from pathlib import Path
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)


# ─── Python AST Parser ────────────────────────────────────────────────────────

class PythonASTParser:
    """Extract classes, imports, functions and calls from Python files."""

    EXCLUDED_DIRECTORIES = {
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        ".pytest_cache",
        "site-packages",
        "node_modules",
    }

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a Python file using the built-in AST module."""

        try:
            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as file:
                source = file.read()

        except OSError as error:
            logger.warning(
                "Unable to read %s: %s",
                file_path,
                error,
            )
            return {
                "file": file_path,
                "error": str(error),
            }

        try:
            tree = ast.parse(source, filename=file_path)

        except SyntaxError as error:
            logger.warning(
                "Syntax error in %s: %s",
                file_path,
                error,
            )
            return {
                "file": file_path,
                "error": str(error),
            }

        visitor = _PythonASTVisitor()
        visitor.visit(tree)

        return {
            "file": file_path,
            "classes": visitor.classes,
            "imports": visitor.imports,
            "from_imports": visitor.from_imports,
            "function_calls": visitor.function_calls,
            "functions": visitor.functions,
        }

    def parse_directory(
        self,
        dir_path: str,
    ) -> List[Dict[str, Any]]:
        """Parse Python files recursively, excluding generated folders."""

        root = Path(dir_path).resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Repository path does not exist: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {root}"
            )

        results = []

        for py_file in sorted(root.rglob("*.py")):

            relative_parts = py_file.relative_to(root).parts

            if any(
                part in self.EXCLUDED_DIRECTORIES
                for part in relative_parts
            ):
                continue

            results.append(
                self.parse_file(str(py_file))
            )

        logger.info(
            "Parsed %s Python files from %s",
            len(results),
            root,
        )

        return results


# ─── AST Visitor ──────────────────────────────────────────────────────────────

class _PythonASTVisitor(ast.NodeVisitor):
    """Extract architectural information from Python AST nodes."""

    def __init__(self):

        self.classes: List[Dict[str, Any]] = []
        self.imports: List[str] = []
        self.from_imports: List[Dict[str, Any]] = []
        self.function_calls: List[str] = []
        self.functions: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):

        self.classes.append({
            "name": node.name,
            "bases": [
                ast.unparse(base)
                for base in node.bases
            ],
            "line": node.lineno,
            "decorators": [
                ast.unparse(decorator)
                for decorator in node.decorator_list
            ],
        })

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):

        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):

        self.from_imports.append({
            "module": node.module or "",
            "names": [
                alias.name
                for alias in node.names
            ],
            "level": node.level,
        })

    def visit_FunctionDef(self, node: ast.FunctionDef):

        self.functions.append(node.name)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call):

        try:
            self.function_calls.append(
                ast.unparse(node.func)
            )

        except Exception:
            pass

        self.generic_visit(node)


# ─── Dependency Graph Builder ─────────────────────────────────────────────────

class DependencyGraphBuilder:
    """
    Build G_C (current architecture graph) from parsed AST data.

    Guarantees:
        1. Every relationship references registered components.
        2. Component types follow the shared ComponentType taxonomy.
        3. Architectural roles are stored separately in metadata.layer.
        4. Repeated analyses do not reuse previous graph state.
        5. Duplicate directed relationships are removed.
    """

    def __init__(self):

        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    def build_from_python(
        self,
        parsed_files: List[Dict[str, Any]],
        repo_root: str,
    ) -> Dict[str, Any]:

        # Reset graph state for every repository analysis.
        self.nodes = {}
        self.edges = []

        repo_root = Path(repo_root).resolve()

        # ─── Pass 1: Register repository modules ─────────────────────

        for file_data in parsed_files:

            if "error" in file_data:
                continue

            file_path = file_data["file"]

            module_name = self._path_to_module(
                file_path,
                repo_root,
            )

            if not module_name:
                continue

            layer = self._infer_component_type(
                module_name,
                file_data,
            )

            component_type = self._map_component_type(layer)

            self.nodes[module_name] = {
                "id": module_name,
                "name": module_name,
                "type": component_type,
                "confidence": 1.0,
                "metadata": {
                    "layer": layer,
                    "file": str(file_path),
                    "classes": file_data.get("classes", []),
                    "functions": file_data.get("functions", []),
                    "function_calls": file_data.get(
                        "function_calls", []
                    ),
                },
            }

        available_modules = set(self.nodes.keys())

        # ─── Pass 2: Extract and resolve dependencies ────────────────

        for file_data in parsed_files:

            if "error" in file_data:
                continue

            file_path = file_data["file"]

            source = self._path_to_module(
                file_path,
                repo_root,
            )

            if source not in available_modules:
                continue

            # Ordinary imports.
            for imported_module in file_data.get("imports", []):

                target = self._resolve_import(
                    module=imported_module,
                    names=[],
                    level=0,
                    source_module=source,
                    available_modules=available_modules,
                )

                self._add_relationship(
                    source,
                    target,
                    file_path,
                    imported_module,
                )

            # From-import statements, including relative imports.
            for from_import in file_data.get("from_imports", []):

                target = self._resolve_import(
                    module=from_import.get("module", ""),
                    names=from_import.get("names", []),
                    level=from_import.get("level", 0),
                    source_module=source,
                    available_modules=available_modules,
                )

                import_label = from_import.get("module", "")

                if not import_label:
                    import_label = "." * from_import.get("level", 0)

                self._add_relationship(
                    source,
                    target,
                    file_path,
                    import_label,
                )

        # ─── Pass 3: Remove duplicate relationships ─────────────────

        unique_edges = {}

        for edge in self.edges:

            key = (
                edge["source"],
                edge["target"],
            )

            if key not in unique_edges:
                unique_edges[key] = edge

        self.edges = list(unique_edges.values())

        # ─── Build unified graph output ──────────────────────────────

        graph = {
            "name": "Current Repository Architecture",
            "graph_type": "current",
            "components": list(self.nodes.values()),
            "relationships": self.edges,
            "source": str(repo_root),
            "metadata": {
                "extraction_method": "python_ast",
                "component_count": len(self.nodes),
                "relationship_count": len(self.edges),
                "language": "python",
            },
        }

        logger.info(
            "Dependency graph built: %s components, %s relationships",
            len(graph["components"]),
            len(graph["relationships"]),
        )

        return graph

    def _add_relationship(
        self,
        source: str,
        target: Optional[str],
        file_path: str,
        imported_module: str,
    ):
        """Add a relationship only when both components are registered."""

        if not target:
            return

        if source not in self.nodes or target not in self.nodes:
            return

        if source == target:
            return

        self.edges.append({
            "source": source,
            "target": target,
            "type": "depends_on",
            "confidence": 1.0,
            "metadata": {
                "extraction_method": "python_ast",
                "evidence": {
                    "file": str(file_path),
                    "imported_module": imported_module,
                },
            },
        })

    def _resolve_import(
        self,
        module: str,
        names: List[str],
        level: int,
        source_module: str,
        available_modules: Set[str],
    ) -> Optional[str]:
        """
        Resolve an import to an existing repository module.

        Supports:
            import app.services.user
            from app.services import user
            from .services import user
            from ..models import user
        """

        candidates = []

        if level > 0:

            # Relative imports are resolved from the source package.
            source_parts = source_module.split(".")[:-1]

            # Python relative-import level 1 means current package.
            trim_count = level - 1

            if trim_count > len(source_parts):
                return None

            if trim_count:
                source_parts = source_parts[:-trim_count]

            base = ".".join(source_parts)

            if module:
                base = (
                    f"{base}.{module}"
                    if base
                    else module
                )

            candidates.append(base)

        elif module:
            candidates.append(module)

        # Try imported names as possible submodules.
        base_candidates = list(candidates)

        for base in base_candidates:

            for name in names:

                if name == "*":
                    continue

                candidate = (
                    f"{base}.{name}"
                    if base
                    else name
                )

                candidates.append(candidate)

        # Prefer the most specific registered module.
        for candidate in candidates:

            if not candidate:
                continue

            if candidate in available_modules:
                return candidate

            # Resolve to the closest registered parent module.
            parts = candidate.split(".")

            while len(parts) > 1:

                parts.pop()

                parent = ".".join(parts)

                if parent in available_modules:
                    return parent

        return None

    def _path_to_module(
        self,
        file_path: str,
        repo_root: Path,
    ) -> str:
        """Convert a repository-relative Python path to a module name."""

        try:

            relative_path = (
                Path(file_path)
                .resolve()
                .relative_to(repo_root)
            )

            parts = list(
                relative_path.with_suffix("").parts
            )

            # package/__init__.py represents the package itself.
            if parts and parts[-1] == "__init__":
                parts.pop()

            return ".".join(parts)

        except ValueError:

            logger.warning(
                "File is outside repository root: %s",
                file_path,
            )

            return ""

    def _map_component_type(self, layer: str) -> str:
        """
        Map architectural roles to the shared ComponentType taxonomy.

        Architectural role remains available in metadata.layer.
        """

        if layer == "service":
            return "service"

        return "unknown"

    def _infer_component_type(
        self,
        module_name: str,
        file_data: Dict[str, Any],
    ) -> str:
        """Infer an architectural layer from module names."""

        name_lower = module_name.lower()

        if any(
            keyword in name_lower
            for keyword in [
                "controller",
                "router",
                "view",
                "api",
            ]
        ):
            return "controller"

        if any(
            keyword in name_lower
            for keyword in [
                "repository",
                "repo",
                "dao",
            ]
        ):
            return "repository"

        if any(
            keyword in name_lower
            for keyword in [
                "service",
                "business",
                "domain",
            ]
        ):
            return "service"

        if any(
            keyword in name_lower
            for keyword in [
                "model",
                "schema",
                "entity",
            ]
        ):
            return "model"

        if any(
            keyword in name_lower
            for keyword in [
                "util",
                "helper",
                "common",
            ]
        ):
            return "utility"

        return "module"


# ─── Architecture Recovery Pipeline ──────────────────────────────────────────

class ArchitectureRecoveryPipeline:
    """Orchestrates repository analysis and current graph generation."""

    def __init__(self):

        self.python_parser = PythonASTParser()
        self.graph_builder = DependencyGraphBuilder()

    def analyze_repository(
        self,
        repo_path: str,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        Full pipeline:

            Repository -> AST parsing -> Dependency graph -> G_C
        """

        repo_path = str(Path(repo_path).resolve())

        logger.info(
            "Analyzing repository: %s (language: %s)",
            repo_path,
            language,
        )

        if language != "python":
            raise NotImplementedError(
                f"Language '{language}' is not supported yet. "
                "Currently only Python AST analysis is implemented."
            )

        parsed_files = self.python_parser.parse_directory(
            repo_path
        )

        graph = self.graph_builder.build_from_python(
            parsed_files,
            repo_path,
        )

        graph["source"] = repo_path

        logger.info(
            "Recovery complete: %s components, %s relationships",
            len(graph["components"]),
            len(graph["relationships"]),
        )

        return graph

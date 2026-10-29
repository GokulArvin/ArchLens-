"""
Module D: Source-Code Architecture Recovery (Sprint 1 D4).
Deterministic AST-based dependency extraction.

Principle: This stage does NOT primarily use an LLM.
Static analysis = structural truth; LLM = semantic interpretation.

Supports:
- Python: built-in ast module for deterministic AST analysis
  (classes, functions, calls, imports, relative imports, and module dependencies)
- Future extensions: Java (JavaParser) & Tree-sitter for multi-language repos.
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import logging

from app.schemas.models import ComponentType, RelationshipType

logger = logging.getLogger(__name__)


class PythonASTParser:
    """Python source code parser using the built-in ast module."""

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
        except Exception:
            pass
        self.generic_visit(node)


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
            self.nodes[module_name] = {
                "id": module_name,
                "name": Path(file_path).stem,
                "type": comp_type,
                "file": file_path,
                "classes": [c["name"] for c in file_data.get("classes", [])],
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

    def _add_edge(self, source: str, target: str, rel_type: str):
        """Add an edge if not already present."""
        for e in self.edges:
            if e["source"] == source and e["target"] == target and e["type"] == rel_type:
                return
        self.edges.append({
            "source": source,
            "target": target,
            "type": rel_type,
            "confidence": 1.0,
        })

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


class ArchitectureRecoveryPipeline:
    """Main orchestrator for source-code architecture recovery."""

    def __init__(self):
        self.python_parser = PythonASTParser()
        self.graph_builder = DependencyGraphBuilder()

    def analyze_repository(
        self, repo_path: str, language: str = "python"
    ) -> Dict[str, Any]:
        """
        Full pipeline: repo directory → G_C (current architecture graph).
        """
        logger.info(f"Analyzing repository: {repo_path} (language: {language})")

        if language == "python":
            parsed = self.python_parser.parse_directory(repo_path)
            graph = self.graph_builder.build_from_python(parsed, repo_path)
        else:
            logger.warning(f"Language '{language}' parser scheduled for Sprint 2/3. Fallback to Python AST.")
            parsed = self.python_parser.parse_directory(repo_path)
            graph = self.graph_builder.build_from_python(parsed, repo_path)

        graph["source"] = repo_path
        logger.info(
            f"Recovery complete: {len(graph['components'])} components, "
            f"{len(graph['relationships'])} relationships"
        )
        return graph

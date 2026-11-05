"""
Module D: Source-Code Architecture Recovery
Deterministic AST-based dependency extraction.

Principle: This stage does NOT primarily use an LLM.
Static analysis = structural truth; LLM = semantic interpretation.

Supports:
- Python: built-in ast module
- Java: tree-sitter (JavaParser)
- Multi-language: tree-sitter
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)


class PythonASTParser:
    """Python source code parser using the built-in ast module."""

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Extract classes, imports, function calls, and dependencies."""
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
        """Parse all Python files in a directory."""
        results = []
        for py_file in Path(dir_path).rglob("*.py"):
            if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                continue
            results.append(self.parse_file(str(py_file)))
        return results


class _PythonASTVisitor(ast.NodeVisitor):
    """AST visitor to extract architectural entities."""

    def __init__(self):
        self.classes: List[Dict] = []
        self.imports: List[str] = []
        self.from_imports: List[Dict] = []
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
        names = [alias.name for alias in node.names]
        self.from_imports.append({"module": module, "names": names})

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
        self.nodes: Dict[str, Dict] = {}
        self.edges: List[Dict] = []

    def build_from_python(
        self, parsed_files: List[Dict[str, Any]], repo_root: str
    ) -> Dict[str, Any]:
        """Build dependency graph from parsed Python files."""
        repo_root = Path(repo_root)

        for file_data in parsed_files:
            if "error" in file_data:
                continue

            file_path = file_data["file"]
            module_name = self._path_to_module(file_path, repo_root)

            # Register node
            self.nodes[module_name] = {
                "id": module_name,
                "name": module_name,
                "type": self._infer_component_type(module_name, file_data),
                "file": file_path,
                "classes": file_data.get("classes", []),
            }

            # Register edges from imports
            for imp in file_data.get("imports", []):
                if self._is_internal(imp, repo_root):
                    self.edges.append({
                        "source": module_name,
                        "target": imp,
                        "relation": "depends_on",
                    })

            for from_imp in file_data.get("from_imports", []):
                module = from_imp["module"]
                if self._is_internal(module, repo_root):
                    self.edges.append({
                        "source": module_name,
                        "target": module,
                        "relation": "depends_on",
                    })

        return {
            "graph_type": "current",
            "components": list(self.nodes.values()),
            "relationships": self.edges,
        }

    def _path_to_module(self, file_path: str, repo_root: Path) -> str:
        """Convert file path to dotted module name."""
        try:
            rel = Path(file_path).relative_to(repo_root)
            parts = rel.with_suffix("").parts
            return ".".join(parts)
        except ValueError:
            return Path(file_path).stem

    def _is_internal(self, module: str, repo_root: Path) -> bool:
        """Check if an import refers to an internal module."""
        if not module:
            return False
        # Heuristic: if top-level package matches any directory in repo
        top_level = module.split(".")[0]
        return (repo_root / top_level).exists() or (
            repo_root / top_level.replace(".", "/")
        ).exists()

    def _infer_component_type(
        self, module_name: str, file_data: Dict
    ) -> str:
        """Heuristically infer component type from module name and classes."""
        name_lower = module_name.lower()
        if any(k in name_lower for k in ["controller", "router", "view", "api"]):
            return "controller"
        if any(k in name_lower for k in ["service", "business", "domain"]):
            return "service"
        if any(k in name_lower for k in ["repository", "repo", "dao", "db", "database"]):
            return "repository"
        if any(k in name_lower for k in ["model", "schema", "entity"]):
            return "model"
        if any(k in name_lower for k in ["util", "helper", "common"]):
            return "utility"
        return "module"


class ArchitectureRecoveryPipeline:
    """Main orchestrator for source-code architecture recovery."""

    def __init__(self):
        self.python_parser = PythonASTParser()
        self.graph_builder = DependencyGraphBuilder()

    def analyze_repository(
        self, repo_path: str, language: str = "python"
    ) -> Dict[str, Any]:
        """
        Full pipeline: repo → G_C (current architecture graph).
        """
        logger.info(f"Analyzing repository: {repo_path} (language: {language})")

        if language == "python":
            parsed = self.python_parser.parse_directory(repo_path)
            graph = self.graph_builder.build_from_python(parsed, repo_path)
        else:
            # TODO: Add Java/tree-sitter support in Sprint 3
            logger.warning(f"Language '{language}' not yet supported. Using Python.")
            parsed = self.python_parser.parse_directory(repo_path)
            graph = self.graph_builder.build_from_python(parsed, repo_path)

        graph["source"] = repo_path
        logger.info(
            f"Recovery complete: {len(graph['components'])} components, "
            f"{len(graph['relationships'])} relationships"
        )
        return graph

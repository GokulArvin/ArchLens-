"""
Unit tests for Python AST Parser & Architecture Recovery (Sprint 1 D4).
Tests deterministic AST extraction on a small sample repository fixture.
"""

import pytest
from pathlib import Path
from app.modules.architecture_recovery.ast_parser import (
    PythonASTParser,
    DependencyGraphBuilder,
    ArchitectureRecoveryPipeline,
)
from app.schemas.models import ComponentType, RelationshipType, CurrentGraph


@pytest.fixture
def sample_repo_path():
    base_dir = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    assert base_dir.exists(), f"Sample repo fixture not found at {base_dir}"
    return str(base_dir)


@pytest.fixture
def parser():
    return PythonASTParser()


@pytest.fixture
def graph_builder():
    return DependencyGraphBuilder()


@pytest.fixture
def pipeline():
    return ArchitectureRecoveryPipeline()


def test_parse_single_file(parser, sample_repo_path):
    """Verify single file AST extraction (classes, methods, imports)."""
    controller_file = str(Path(sample_repo_path) / "controllers" / "order_controller.py")
    result = parser.parse_file(controller_file)

    assert "error" not in result
    assert result["file"] == controller_file

    # Classes
    class_names = [c["name"] for c in result["classes"]]
    assert "OrderController" in class_names

    # Functions / Methods
    assert "handle_create" in result["functions"]
    assert "handle_direct_lookup" in result["functions"]

    # From-imports
    from_modules = [fi["module"] for fi in result["from_imports"]]
    assert "services.order_service" in from_modules
    assert "repositories.order_repository" in from_modules


def test_parse_directory(parser, sample_repo_path):
    """Verify all Python files in the sample repo are parsed."""
    results = parser.parse_directory(sample_repo_path)
    assert len(results) >= 4

    files_parsed = [Path(r["file"]).name for r in results]
    assert "order_controller.py" in files_parsed
    assert "order_service.py" in files_parsed
    assert "order_repository.py" in files_parsed
    assert "order.py" in files_parsed


def test_dependency_graph_builder(parser, graph_builder, sample_repo_path):
    """Verify G_C graph construction from parsed AST data."""
    parsed_files = parser.parse_directory(sample_repo_path)
    graph = graph_builder.build_from_python(parsed_files, sample_repo_path)

    assert graph["graph_type"] == "current"
    assert graph["schema_version"] == "1.0.0"
    assert len(graph["components"]) >= 4

    # Component types correctly inferred
    comp_types = {c["name"]: c["type"] for c in graph["components"]}
    assert comp_types.get("order_controller") == ComponentType.CONTROLLER.value
    assert comp_types.get("order_service") == ComponentType.SERVICE.value
    assert comp_types.get("order_repository") == ComponentType.REPOSITORY.value
    assert comp_types.get("order") == ComponentType.MODEL.value

    # Verify relationships extracted
    edges = [(e["source"], e["target"]) for e in graph["relationships"]]
    # Controller -> Service
    assert any("order_controller" in s and "order_service" in t for s, t in edges)
    # Service -> Repository
    assert any("order_service" in s and "order_repository" in t for s, t in edges)
    # Repository -> Model
    assert any("order_repository" in s and "order" in t for s, t in edges)
    # Intentional violation: Controller -> Repository direct dependency
    assert any("order_controller" in s and "order_repository" in t for s, t in edges)


def test_architecture_recovery_pipeline_end_to_end(pipeline, sample_repo_path):
    """Verify end-to-end recovery pipeline on repository fixture."""
    graph = pipeline.analyze_repository(sample_repo_path, language="python")

    assert graph["graph_type"] == "current"
    assert graph["schema_version"] == "1.0.0"
    assert len(graph["components"]) >= 4
    assert len(graph["relationships"]) >= 4

    # Graph can be validated via Pydantic CurrentGraph schema
    validated = CurrentGraph(**graph)
    assert validated.schema_version == "1.0.0"
    assert len(validated.components) == len(graph["components"])

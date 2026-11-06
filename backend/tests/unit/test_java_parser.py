"""
Unit tests for JavaTreeSitterParser, DependencyGraphBuilder (Java),
ArchitectureRecoveryPipeline multi-language modes — Sprint 2 P3 (Task 8.1).

Acceptance Criteria:
- JavaTreeSitterParser.parse_file extracts classes, imports, methods
- parse_directory returns all 4 fixture files
- build_from_java produces CurrentGraph-compatible output with correct types
- Pipeline java/mixed language modes work end-to-end
- BaseLanguageParser ABC enforcement verified
"""

import shutil
import tempfile
import os
from pathlib import Path

import pytest
from hypothesis import given, settings as h_settings, HealthCheck
from hypothesis import strategies as st

from app.modules.architecture_recovery.ast_parser import (
    BaseLanguageParser,
    JavaTreeSitterParser,
    PythonASTParser,
    DependencyGraphBuilder,
    ArchitectureRecoveryPipeline,
)
from app.schemas.models import ComponentType, CurrentGraph


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_java_repo_path():
    base_dir = Path(__file__).resolve().parent.parent / "fixtures" / "sample_java_repo"
    assert base_dir.exists(), f"Java fixture not found at {base_dir}"
    return str(base_dir)


@pytest.fixture
def parser():
    return JavaTreeSitterParser()


@pytest.fixture
def graph_builder():
    return DependencyGraphBuilder()


@pytest.fixture
def pipeline():
    return ArchitectureRecoveryPipeline()


# ─── 1. ABC enforcement ───────────────────────────────────────────────────────

def test_java_parser_is_base_subclass():
    """JavaTreeSitterParser must extend BaseLanguageParser."""
    assert issubclass(JavaTreeSitterParser, BaseLanguageParser)


def test_python_parser_is_base_subclass():
    """PythonASTParser must extend BaseLanguageParser."""
    assert issubclass(PythonASTParser, BaseLanguageParser)


def test_abstract_base_raises_on_incomplete_subclass():
    """Instantiating a subclass that omits abstract methods must raise TypeError."""
    class IncompleteParser(BaseLanguageParser):
        pass  # does not implement any abstract methods

    with pytest.raises(TypeError):
        IncompleteParser()


def test_supported_extensions():
    """supported_extensions() must return the correct extension list."""
    assert PythonASTParser().supported_extensions() == [".py"]
    assert JavaTreeSitterParser().supported_extensions() == [".java"]


# ─── 2. parse_file ────────────────────────────────────────────────────────────

def test_parse_single_java_file(parser, sample_java_repo_path):
    """parse_file on OrderController.java extracts class, imports, methods."""
    controller_file = str(
        Path(sample_java_repo_path) / "controllers" / "OrderController.java"
    )
    result = parser.parse_file(controller_file)

    assert "error" not in result, f"Unexpected parse error: {result.get('error')}"
    assert result["file"] == controller_file

    # Classes
    class_names = [c["name"] for c in result["classes"]]
    assert "OrderController" in class_names

    # Imports — must contain both OrderService and OrderRepository
    imports_lower = [imp.lower() for imp in result["imports"]]
    assert any("orderservice" in imp or "order_service" in imp for imp in imports_lower), \
        f"OrderService import not found in: {result['imports']}"
    assert any("orderrepository" in imp or "order_repository" in imp for imp in imports_lower), \
        f"OrderRepository import not found in: {result['imports']}"
    assert len(result["imports"]) >= 2

    # Methods must be non-empty
    assert len(result["methods"]) > 0

    # Required keys present
    for key in ("file", "classes", "imports", "methods", "package", "metadata"):
        assert key in result, f"Missing key: {key}"


def test_parse_file_error_dict_on_missing_file(parser):
    """parse_file on a non-existent path must return error dict, not raise."""
    result = parser.parse_file("/nonexistent/path/Fake.java")
    assert "error" in result
    assert result["file"] == "/nonexistent/path/Fake.java"


# ─── 3. parse_directory ──────────────────────────────────────────────────────

def test_parse_directory_returns_four_files(parser, sample_java_repo_path):
    """parse_directory on the fixture must return exactly 4 results."""
    results = parser.parse_directory(sample_java_repo_path)

    # Filter out error results so test is resilient if tree-sitter isn't installed
    # but still check file count
    file_names = [Path(r["file"]).name for r in results]
    assert len(results) == 4, f"Expected 4 files, got {len(results)}: {file_names}"

    expected = {
        "OrderController.java",
        "OrderService.java",
        "OrderRepository.java",
        "Order.java",
    }
    assert set(file_names) == expected


def test_parse_directory_excludes_ignored_dirs(parser, tmp_path):
    """parse_directory must skip .git, target, build, __pycache__ subdirectories."""
    # Create a valid java file in an ignored dir and one in a normal dir
    ignored_dir = tmp_path / "target"
    ignored_dir.mkdir()
    (ignored_dir / "Ignored.java").write_text("public class Ignored {}")

    normal_dir = tmp_path / "src"
    normal_dir.mkdir()
    (normal_dir / "MyClass.java").write_text("public class MyClass {}")

    results = parser.parse_directory(str(tmp_path))
    file_names = [Path(r["file"]).name for r in results]

    assert "MyClass.java" in file_names
    assert "Ignored.java" not in file_names


# ─── 4. DependencyGraphBuilder — Java ────────────────────────────────────────

def test_build_from_java_graph(parser, graph_builder, sample_java_repo_path):
    """build_from_java produces a valid CurrentGraph with correct types and edges."""
    parsed = parser.parse_directory(sample_java_repo_path)
    graph = graph_builder.build_from_java(parsed, sample_java_repo_path)

    assert graph["graph_type"] == "current"
    assert graph["schema_version"] == "1.0.0"
    assert len(graph["components"]) >= 4

    # Component types correctly inferred
    comp_types = {c["name"].lower(): c["type"] for c in graph["components"]}
    assert comp_types.get("ordercontroller") == ComponentType.CONTROLLER.value
    assert comp_types.get("orderservice") == ComponentType.SERVICE.value
    assert comp_types.get("orderrepository") == ComponentType.REPOSITORY.value
    assert comp_types.get("order") == ComponentType.MODEL.value

    # At least 4 relationships
    assert len(graph["relationships"]) >= 4

    # Controller → Repository edge must exist (intentional violation in fixture)
    edges = [(e["source"].lower(), e["target"].lower()) for e in graph["relationships"]]
    assert any(
        "controller" in s and "repository" in t for s, t in edges
    ), f"Controller→Repository edge not found in: {edges}"


def test_build_from_java_nodes_have_inference_confidence(parser, graph_builder, sample_java_repo_path):
    """All nodes produced by build_from_java must have inference_confidence field."""
    parsed = parser.parse_directory(sample_java_repo_path)
    graph = graph_builder.build_from_java(parsed, sample_java_repo_path)

    for comp in graph["components"]:
        assert "inference_confidence" in comp, f"Missing inference_confidence on: {comp['name']}"
        assert comp["inference_confidence"] in (0.6, 1.0)


# ─── 5. Pipeline — end-to-end ────────────────────────────────────────────────

def test_pipeline_java_end_to_end(pipeline, sample_java_repo_path):
    """analyze_repository with language='java' validates against CurrentGraph schema."""
    graph = pipeline.analyze_repository(sample_java_repo_path, language="java")

    assert graph["graph_type"] == "current"
    assert graph["schema_version"] == "1.0.0"
    assert len(graph["components"]) >= 4

    # Must validate against Pydantic CurrentGraph schema
    validated = CurrentGraph(**graph)
    assert validated.schema_version == "1.0.0"
    assert len(validated.components) == len(graph["components"])


def test_pipeline_mixed_mode(pipeline, sample_java_repo_path):
    """language='mixed' on a dir with both .py and .java files returns components from both."""
    # sample_java_repo has only .java files — create a temp dir combining both
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # Copy java files
        java_src = Path(sample_java_repo_path)
        for java_file in java_src.rglob("*.java"):
            dest = tmp / java_file.relative_to(java_src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(java_file, dest)

        # Add a small python file
        py_dir = tmp / "python_module"
        py_dir.mkdir()
        (py_dir / "some_service.py").write_text(
            "class SomeService:\n    pass\n"
        )

        graph = pipeline.analyze_repository(str(tmp), language="mixed")

    assert graph["graph_type"] == "current"
    assert graph["metadata"]["language"] == "mixed"

    # Must have components from both languages
    assert graph["metadata"]["java_components"] >= 4
    assert graph["metadata"]["python_components"] >= 1
    assert len(graph["components"]) >= 5


def test_pipeline_python_mode_unchanged(pipeline):
    """language='python' still works exactly as Sprint 1 — regression guard."""
    sample_py_repo = str(
        Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    )
    graph = pipeline.analyze_repository(sample_py_repo, language="python")

    assert graph["graph_type"] == "current"
    assert graph["schema_version"] == "1.0.0"
    assert len(graph["components"]) >= 4
    assert len(graph["relationships"]) >= 4


# ─── Property-based tests (Tasks 8.2–8.6) ────────────────────────────────────

# Feature: archlens-sprint2-p3, Property 1: Java ParseResult structural completeness
@h_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(st.text(min_size=1, max_size=500))
def test_property_java_parsresult_structural_completeness(java_source: str):
    """For any text written as a .java file, parse_file returns a dict with all required keys."""
    p = JavaTreeSitterParser()
    with tempfile.NamedTemporaryFile(suffix=".java", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(java_source)
        path = f.name
    try:
        result = p.parse_file(path)
    finally:
        os.unlink(path)

    # Must always return a dict with at least "file" key
    assert isinstance(result, dict)
    assert "file" in result
    # If no error, all required keys must be present
    if "error" not in result:
        for key in ("classes", "imports", "methods", "package", "metadata"):
            assert key in result, f"Missing key '{key}' in parse result"
        for cls in result["classes"]:
            for sub in ("name", "bases", "line", "decorators"):
                assert sub in cls, f"Missing class sub-key '{sub}'"
        assert isinstance(result["methods"], list)


# Feature: archlens-sprint2-p3, Property 2: Error handling never raises
@h_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(st.binary(max_size=1000))
def test_property_parse_file_never_raises(content: bytes):
    """For any binary content written as a .java file, parse_file never raises an exception."""
    p = JavaTreeSitterParser()
    with tempfile.NamedTemporaryFile(suffix=".java", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = p.parse_file(path)
    finally:
        os.unlink(path)

    assert isinstance(result, dict)
    assert "file" in result
    # Result is either a valid ParseResult or an error dict — never an exception


# Feature: archlens-sprint2-p3, Property 3: parse_directory excludes ignored subdirectories
@h_settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
@given(st.sampled_from([".git", "target", "build", "__pycache__"]))
def test_property_parse_directory_excludes_ignored(ignored_dir: str):
    """Files inside any ignored directory are never included in parse_directory results."""
    p = JavaTreeSitterParser()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # File in ignored dir
        bad_dir = tmp_path / ignored_dir
        bad_dir.mkdir()
        (bad_dir / "ShouldSkip.java").write_text("public class ShouldSkip {}")
        # File in normal dir
        good_dir = tmp_path / "src"
        good_dir.mkdir()
        (good_dir / "ShouldInclude.java").write_text("public class ShouldInclude {}")

        results = p.parse_directory(tmp)
        file_names = [Path(r["file"]).name for r in results]

    assert "ShouldInclude.java" in file_names
    assert "ShouldSkip.java" not in file_names


# Feature: archlens-sprint2-p3, Property 4: CurrentGraph schema validation across language modes
@h_settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow])
@given(st.sampled_from(["python", "java", "mixed"]))
def test_property_current_graph_validates_all_modes(language: str):
    """analyze_repository output validates against CurrentGraph for every language mode."""
    sample_java = str(
        Path(__file__).resolve().parent.parent / "fixtures" / "sample_java_repo"
    )
    sample_py = str(
        Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    )

    pipe = ArchitectureRecoveryPipeline()
    # Use java fixture for java/mixed, python fixture for python
    repo = sample_py if language == "python" else sample_java
    graph = pipe.analyze_repository(repo, language=language)

    validated = CurrentGraph(**graph)
    assert validated.schema_version == "1.0.0"
    assert validated.graph_type == "current"


# Feature: archlens-sprint2-p3, Property 9: PythonASTParser output preservation after refactoring
@h_settings(max_examples=4, suppress_health_check=[HealthCheck.too_slow])
@given(st.just("order_controller"))  # representative fixture file
def test_property_python_parser_output_preserved(_name: str):
    """Refactored PythonASTParser.parse_file still returns Sprint 1 keys for every fixture file."""
    sample_repo = Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo"
    py_files = list(sample_repo.rglob("*.py"))
    assert py_files, "No .py files in sample_repo fixture"

    p = PythonASTParser()
    for py_file in py_files:
        result = p.parse_file(str(py_file))
        if "error" in result:
            continue
        for key in ("file", "classes", "imports", "from_imports", "functions", "function_calls"):
            assert key in result, f"Missing key '{key}' in {py_file.name}"

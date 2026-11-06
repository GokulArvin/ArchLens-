"""
Unit tests for DependencyGraphBuilder.build_package_graph — Sprint 3 P3 (Task 13.1).

Tests cover:
- Node count == unique top-level package count
- Cross-package edges correctly emitted and deduplicated
- container_graph accessible as attribute after call
- Single-package returns one node, zero edges
- CALLS and INHERITS cross-package edges included
- Empty builder returns empty PackageGraph
"""

import textwrap
from pathlib import Path


from app.modules.architecture_recovery.ast_parser import (
    PythonASTParser,
    DependencyGraphBuilder,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def write_py(tmp_path: Path, rel: str, content: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


def build_graph(tmp_path: Path, files: dict) -> tuple:
    """Write files, parse, build, return (graph, builder)."""
    for rel, content in files.items():
        write_py(tmp_path, rel, textwrap.dedent(content))
    parser = PythonASTParser()
    parsed = parser.parse_directory(str(tmp_path))
    builder = DependencyGraphBuilder()
    graph = builder.build_from_python(parsed, str(tmp_path))
    return graph, builder


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_package_graph_node_count_matches_unique_packages(tmp_path):
    """PackageGraph must have exactly one node per unique top-level package."""
    _, builder = build_graph(tmp_path, {
        "app/controller.py": "class Ctrl: pass\n",
        "app/service.py":    "class Svc: pass\n",
        "tests/test_a.py":   "class TestA: pass\n",
    })
    pkg_graph = builder.build_package_graph()

    pkg_ids = [n["id"] for n in pkg_graph["nodes"]]
    assert len(pkg_graph["nodes"]) == 2
    assert "app" in pkg_ids
    assert "tests" in pkg_ids
    for node in pkg_graph["nodes"]:
        assert node["type"] == "package"


def test_package_graph_cross_package_edges_deduplicated(tmp_path):
    """Multiple module-level edges between the same package pair → exactly one PackageGraph edge."""
    _, builder = build_graph(tmp_path, {
        "app/controller.py": "from app.service import Svc\nfrom app.repo import Repo\n",
        "app/service.py":    "class Svc: pass\n",
        "app/repo.py":       "class Repo: pass\n",
        "tests/test_ctrl.py": "from app.controller import Ctrl\nfrom app.service import Svc\n",
    })
    pkg_graph = builder.build_package_graph()

    # Find tests → app edges
    tests_to_app = [
        e for e in pkg_graph["edges"]
        if e["source"] == "tests" and e["target"] == "app"
    ]
    assert len(tests_to_app) == 1
    assert tests_to_app[0]["type"] == "package_dependency"


def test_container_graph_stored_as_attribute(tmp_path):
    """After build_package_graph(), builder.container_graph is accessible with correct mapping."""
    _, builder = build_graph(tmp_path, {
        "app/svc.py":      "class Svc: pass\n",
        "tests/test_a.py": "class TestA: pass\n",
    })
    builder.build_package_graph()

    assert hasattr(builder, "container_graph")
    cg = builder.container_graph
    assert "app" in cg
    assert "tests" in cg
    assert all("app" in mid for mid in cg["app"])
    assert all("tests" in mid for mid in cg["tests"])


def test_single_package_zero_cross_edges(tmp_path):
    """When all components are in one package, PackageGraph has one node and zero edges."""
    _, builder = build_graph(tmp_path, {
        "myapp/a.py": "class A: pass\n",
        "myapp/b.py": "from myapp.a import A\n",
    })
    pkg_graph = builder.build_package_graph()

    assert len(pkg_graph["nodes"]) == 1
    assert pkg_graph["nodes"][0]["id"] == "myapp"
    assert pkg_graph["edges"] == []


def test_package_graph_includes_calls_and_inherits_cross_edges(tmp_path):
    """CALLS and INHERITS cross-package edges are folded into PackageGraph edges."""
    write_py(tmp_path, "base_pkg/base.py", "class BaseClass:\n    def run(self): pass\n")
    write_py(tmp_path, "child_pkg/child.py", """\
        from base_pkg.base import BaseClass
        class Child(BaseClass):
            def go(self): self.run()
    """)

    parser = PythonASTParser()
    parsed = parser.parse_directory(str(tmp_path))
    builder = DependencyGraphBuilder()
    builder.build_from_python(parsed, str(tmp_path))
    pkg_graph = builder.build_package_graph()

    # child_pkg → base_pkg edge must exist (from DEPENDS_ON / INHERITS / CALLS)
    cross = [e for e in pkg_graph["edges"] if e["source"] == "child_pkg" and e["target"] == "base_pkg"]
    assert len(cross) == 1  # deduplicated to one package edge


def test_build_package_graph_before_build_returns_empty():
    """Calling build_package_graph on a fresh builder returns an empty PackageGraph."""
    builder = DependencyGraphBuilder()
    pkg_graph = builder.build_package_graph()

    assert pkg_graph["nodes"] == []
    assert pkg_graph["edges"] == []
    assert pkg_graph["container_graph"] == {}


def test_package_graph_component_count_in_nodes(tmp_path):
    """Each node's component_count must match the number of modules in that package."""
    _, builder = build_graph(tmp_path, {
        "pkg/a.py": "class A: pass\n",
        "pkg/b.py": "class B: pass\n",
        "pkg/c.py": "class C: pass\n",
    })
    pkg_graph = builder.build_package_graph()

    pkg_node = next(n for n in pkg_graph["nodes"] if n["id"] == "pkg")
    assert pkg_node["component_count"] == 3

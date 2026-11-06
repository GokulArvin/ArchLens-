"""
Unit tests for CALLS and INHERITS edge extraction — Sprint 3 P3 (Task 12.1).

Tests cover:
- Python CALLS edges from call_targets (object.method() form)
- Python INHERITS edges from class base resolution
- Java CALLS edges from method_invocations
- Java INHERITS edges from class bases
- Deduplication of CALLS and INHERITS edges
- Coexistence of DEPENDS_ON + CALLS between the same module pair
- Unresolvable bases (stdlib) produce no edges
"""

import textwrap
from pathlib import Path


from app.modules.architecture_recovery.ast_parser import (
    PythonASTParser,
    JavaTreeSitterParser,
    DependencyGraphBuilder,
)
from app.schemas.models import RelationshipType


# ─── Helpers ─────────────────────────────────────────────────────────────────

def write_py(tmp_path: Path, rel: str, content: str) -> Path:
    """Write a Python file under tmp_path and return its path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


def write_java(tmp_path: Path, rel: str, content: str) -> Path:
    """Write a Java file under tmp_path and return its path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


def edges_of_type(graph: dict, rel_type: str):
    return [e for e in graph["relationships"] if e["type"] == rel_type]


# ─── Python CALLS ────────────────────────────────────────────────────────────

def test_python_calls_edge_emitted(tmp_path):
    """build_from_python emits a CALLS edge when module B calls a class from module A."""
    write_py(tmp_path, "module_a.py", """\
        class OrderService:
            def create(self): pass
    """)
    write_py(tmp_path, "module_b.py", """\
        from module_a import OrderService
        svc = OrderService()
        svc.create()
    """)

    parser = PythonASTParser()
    parsed = parser.parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_python(parsed, str(tmp_path))

    calls = edges_of_type(graph, RelationshipType.CALLS.value)
    assert len(calls) >= 1
    assert all(e["confidence"] == 0.7 for e in calls)


def test_python_calls_edge_confidence_is_0_7(tmp_path):
    """Every CALLS edge must have confidence exactly 0.7."""
    write_py(tmp_path, "a.py", "class Alpha:\n    def run(self): pass\n")
    write_py(tmp_path, "b.py", "from a import Alpha\nx = Alpha()\nx.run()\n")

    parsed = PythonASTParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_python(parsed, str(tmp_path))

    calls = edges_of_type(graph, RelationshipType.CALLS.value)
    for e in calls:
        assert e["confidence"] == 0.7


def test_python_no_duplicate_calls_edges(tmp_path):
    """Multiple calls to the same class produce at most one CALLS edge per pair."""
    write_py(tmp_path, "svc.py", "class MyService:\n    def a(self): pass\n    def b(self): pass\n")
    write_py(tmp_path, "ctrl.py", """\
        from svc import MyService
        s = MyService()
        s.a()
        s.b()
        s.a()
    """)

    parsed = PythonASTParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_python(parsed, str(tmp_path))

    calls = edges_of_type(graph, RelationshipType.CALLS.value)
    src_tgt_pairs = [(e["source"], e["target"]) for e in calls]
    assert len(src_tgt_pairs) == len(set(src_tgt_pairs))


def test_python_depends_on_coexists_with_calls(tmp_path):
    """When module B imports and calls module A's class, both DEPENDS_ON and CALLS edges exist."""
    write_py(tmp_path, "repo.py", "class Repo:\n    def save(self): pass\n")
    write_py(tmp_path, "svc.py", "from repo import Repo\nr = Repo()\nr.save()\n")

    parsed = PythonASTParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_python(parsed, str(tmp_path))

    types = {e["type"] for e in graph["relationships"]}
    assert RelationshipType.DEPENDS_ON.value in types
    assert RelationshipType.CALLS.value in types


# ─── Python INHERITS ─────────────────────────────────────────────────────────

def test_python_inherits_edge_emitted(tmp_path):
    """build_from_python emits an INHERITS edge when a class extends a class in another module."""
    write_py(tmp_path, "base_module.py", "class BaseParser:\n    pass\n")
    write_py(tmp_path, "child_module.py", "from base_module import BaseParser\nclass MyParser(BaseParser):\n    pass\n")

    parsed = PythonASTParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_python(parsed, str(tmp_path))

    inherits = edges_of_type(graph, RelationshipType.INHERITS.value)
    assert len(inherits) >= 1
    assert all(e["confidence"] == 0.9 for e in inherits)


def test_python_no_duplicate_inherits_edges(tmp_path):
    """Multiple classes inheriting from the same base produce at most one INHERITS edge per pair."""
    write_py(tmp_path, "base.py", "class Base:\n    pass\n")
    write_py(tmp_path, "children.py", """\
        from base import Base
        class Child1(Base): pass
        class Child2(Base): pass
    """)

    parsed = PythonASTParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_python(parsed, str(tmp_path))

    inherits = edges_of_type(graph, RelationshipType.INHERITS.value)
    src_tgt = [(e["source"], e["target"]) for e in inherits]
    assert len(src_tgt) == len(set(src_tgt))


def test_python_unresolvable_base_emits_no_edge(tmp_path):
    """Inheriting from a stdlib class (like 'list') produces no INHERITS edge."""
    write_py(tmp_path, "mylist.py", "class MyList(list):\n    pass\n")

    parsed = PythonASTParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_python(parsed, str(tmp_path))

    inherits = edges_of_type(graph, RelationshipType.INHERITS.value)
    assert len(inherits) == 0


# ─── Java CALLS ──────────────────────────────────────────────────────────────

def test_java_calls_edge_emitted(tmp_path):
    """build_from_java emits a CALLS edge when a method invocation targets a class from another file."""
    write_java(tmp_path, "services/OrderService.java", """\
        package services;
        public class OrderService {
            public void create() {}
        }
    """)
    write_java(tmp_path, "controllers/OrderController.java", """\
        package controllers;
        import services.OrderService;
        public class OrderController {
            public void handle() {
                OrderService svc = new OrderService();
                svc.create();
            }
        }
    """)

    parser = JavaTreeSitterParser()
    parsed = parser.parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_java(parsed, str(tmp_path))

    calls = edges_of_type(graph, RelationshipType.CALLS.value)
    assert len(calls) >= 1
    assert all(e["confidence"] == 0.7 for e in calls)


def test_java_no_duplicate_calls_edges(tmp_path):
    """Multiple Java method invocations on same class produce at most one CALLS edge per pair."""
    write_java(tmp_path, "svc/Svc.java", """\
        package svc;
        public class Svc { public void a() {} public void b() {} }
    """)
    write_java(tmp_path, "ctrl/Ctrl.java", """\
        package ctrl;
        import svc.Svc;
        public class Ctrl {
            void run() { Svc s = new Svc(); s.a(); s.b(); s.a(); }
        }
    """)

    parsed = JavaTreeSitterParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_java(parsed, str(tmp_path))

    calls = edges_of_type(graph, RelationshipType.CALLS.value)
    src_tgt = [(e["source"], e["target"]) for e in calls]
    assert len(src_tgt) == len(set(src_tgt))


# ─── Java INHERITS ────────────────────────────────────────────────────────────

def test_java_inherits_edge_emitted(tmp_path):
    """build_from_java emits an INHERITS edge when a class extends a class from another file."""
    write_java(tmp_path, "base/Animal.java", """\
        package base;
        public class Animal {}
    """)
    write_java(tmp_path, "derived/Dog.java", """\
        package derived;
        import base.Animal;
        public class Dog extends Animal {}
    """)

    parsed = JavaTreeSitterParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_java(parsed, str(tmp_path))

    inherits = edges_of_type(graph, RelationshipType.INHERITS.value)
    assert len(inherits) >= 1
    assert all(e["confidence"] == 0.9 for e in inherits)


def test_java_no_duplicate_inherits_edges(tmp_path):
    """Multiple Java classes extending the same base produce at most one INHERITS edge per pair."""
    write_java(tmp_path, "base/Base.java", "package base;\npublic class Base {}\n")
    write_java(tmp_path, "children/ChildA.java", """\
        package children;
        import base.Base;
        public class ChildA extends Base {}
    """)
    write_java(tmp_path, "children/ChildB.java", """\
        package children;
        import base.Base;
        public class ChildB extends Base {}
    """)

    parsed = JavaTreeSitterParser().parse_directory(str(tmp_path))
    graph = DependencyGraphBuilder().build_from_java(parsed, str(tmp_path))

    inherits = edges_of_type(graph, RelationshipType.INHERITS.value)
    # ChildA and ChildB are in the same module file-wise — at most one INHERITS per source→target pair
    src_tgt = [(e["source"], e["target"]) for e in inherits]
    assert len(src_tgt) == len(set(src_tgt))

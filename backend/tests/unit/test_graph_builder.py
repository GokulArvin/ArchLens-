"""
Sprint 4 (P3 D14/D15) + Sprint 5 (P3 D20):
Unit tests for graph/builder.py (ArchGraphBuilder, PackageGraphAggregator)
and graph/integrity.py (GraphIntegrityChecker).

Acceptance criteria (Sprint 4 D15)
-----------------------------------
- Graph edges from known code samples are correctly created.
- Confidence and type attributes are preserved.

Acceptance criteria (Sprint 5 D20)
------------------------------------
- Round-trip: build(to_schema_dict(G)) produces an isomorphic graph.
- Integrity checks catch missing endpoints, self-loops, and invalid confidence.
"""

from __future__ import annotations

import json
import pytest
import networkx as nx

from app.modules.graph.builder import ArchGraphBuilder, PackageGraphAggregator
from app.modules.graph.integrity import GraphIntegrityChecker, IssueSeverity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_schema(components, relationships, graph_type="current"):
    return {
        "schema_version": "1.0.0",
        "name": "TestGraph",
        "graph_type": graph_type,
        "source": "/tmp/fake_repo",
        "components": components,
        "relationships": relationships,
    }


@pytest.fixture
def simple_schema():
    return _make_schema(
        components=[
            {"id": "ctrl", "name": "OrderController", "type": "controller", "confidence": 0.95},
            {"id": "svc",  "name": "OrderService",    "type": "service",    "confidence": 0.90},
            {"id": "repo", "name": "OrderRepository", "type": "repository", "confidence": 0.85},
        ],
        relationships=[
            {"source": "ctrl", "target": "svc",  "type": "depends_on", "confidence": 0.95},
            {"source": "svc",  "target": "repo", "type": "depends_on", "confidence": 0.90},
        ],
    )


@pytest.fixture
def simple_graph(simple_schema):
    return ArchGraphBuilder.build(simple_schema)


# ---------------------------------------------------------------------------
# Sprint 4 D14/D15 — ArchGraphBuilder basic construction
# ---------------------------------------------------------------------------

class TestArchGraphBuilder:

    def test_node_count(self, simple_graph):
        """Graph has the correct number of nodes."""
        assert simple_graph.number_of_nodes() == 3

    def test_edge_count(self, simple_graph):
        """Graph has the correct number of edges."""
        assert simple_graph.number_of_edges() == 2

    def test_node_attributes_preserved(self, simple_graph):
        """Node name, type and confidence are stored correctly."""
        ctrl = simple_graph.nodes["ctrl"]
        assert ctrl["name"] == "OrderController"
        assert ctrl["type"] == "controller"
        assert ctrl["confidence"] == pytest.approx(0.95)

    def test_edge_attributes_preserved(self, simple_graph):
        """Edge type and confidence are stored correctly."""
        edge = simple_graph.edges["ctrl", "svc"]
        assert edge["type"] == "depends_on"
        assert edge["confidence"] == pytest.approx(0.95)

    def test_edge_directionality(self, simple_graph):
        """Edges are directed: ctrl→svc exists, svc→ctrl does not."""
        assert simple_graph.has_edge("ctrl", "svc")
        assert not simple_graph.has_edge("svc", "ctrl")

    def test_graph_metadata(self, simple_graph):
        """Graph-level metadata is preserved."""
        assert simple_graph.graph["schema_version"] == "1.0.0"
        assert simple_graph.graph["graph_type"] == "current"

    def test_auto_node_creation_for_unknown_endpoint(self):
        """Nodes referenced only in relationships are auto-created."""
        schema = _make_schema(
            components=[{"id": "a", "name": "A", "type": "service"}],
            relationships=[{"source": "a", "target": "b", "type": "calls", "confidence": 0.7}],
        )
        G = ArchGraphBuilder.build(schema)
        assert "b" in G.nodes
        assert G.nodes["b"]["type"] == "unknown"

    def test_pydantic_model_accepted(self):
        """ArchGraphBuilder.build() accepts a Pydantic ArchGraph model."""
        from app.schemas.models import ArchGraph, ArchComponent, ArchRelationship
        graph = ArchGraph(
            name="PydanticGraph",
            graph_type="current",
            components=[ArchComponent(id="x", name="X", type="service")],
            relationships=[],
        )
        G = ArchGraphBuilder.build(graph)
        assert "x" in G.nodes

    def test_duplicate_edge_keeps_highest_confidence(self):
        """When two edges share (src, tgt), only the higher-confidence one is kept."""
        schema = _make_schema(
            components=[
                {"id": "a", "name": "A", "type": "service"},
                {"id": "b", "name": "B", "type": "service"},
            ],
            relationships=[
                {"source": "a", "target": "b", "type": "calls", "confidence": 0.4},
                {"source": "a", "target": "b", "type": "calls", "confidence": 0.9},
            ],
        )
        G = ArchGraphBuilder.build(schema)
        assert G.number_of_edges() == 1
        assert G.edges["a", "b"]["confidence"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Sprint 5 D20 — Serialization round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:

    def test_to_schema_dict_round_trip(self, simple_graph):
        """build(to_schema_dict(G)) must be isomorphic to the original graph."""
        schema_out = ArchGraphBuilder.to_schema_dict(simple_graph)
        G2 = ArchGraphBuilder.build(schema_out)
        assert set(G2.nodes()) == set(simple_graph.nodes())
        assert set(G2.edges()) == set(simple_graph.edges())

    def test_to_json_round_trip(self, simple_graph, tmp_path):
        """JSON serialization round-trip produces the same graph."""
        p = tmp_path / "graph.json"
        json_str = ArchGraphBuilder.to_json(simple_graph, path=str(p))
        assert p.exists()
        loaded = json.loads(json_str)
        G2 = ArchGraphBuilder.build(loaded)
        assert G2.number_of_nodes() == simple_graph.number_of_nodes()
        assert G2.number_of_edges() == simple_graph.number_of_edges()

    def test_to_adjacency_dict(self, simple_graph):
        """Adjacency dict contains all nodes as keys."""
        adj = ArchGraphBuilder.to_adjacency_dict(simple_graph)
        assert set(adj.keys()) == set(simple_graph.nodes())
        assert "svc" in adj["ctrl"]

    def test_to_dot(self, simple_graph):
        """DOT output contains expected node and edge labels."""
        dot = ArchGraphBuilder.to_dot(simple_graph)
        assert "digraph" in dot
        assert "OrderController" in dot
        assert "->" in dot


# ---------------------------------------------------------------------------
# Sprint 4 D13 — PackageGraphAggregator
# ---------------------------------------------------------------------------

class TestPackageGraphAggregator:

    def test_intra_package_edges_dropped(self):
        """Edges between nodes in the same package are removed."""
        schema = _make_schema(
            components=[
                {"id": "orders.controller", "name": "orders.controller", "type": "controller"},
                {"id": "orders.service",    "name": "orders.service",    "type": "service"},
                {"id": "users.service",     "name": "users.service",     "type": "service"},
            ],
            relationships=[
                {"source": "orders.controller", "target": "orders.service", "confidence": 1.0},
                {"source": "orders.service",    "target": "users.service",  "confidence": 0.8},
            ],
        )
        G = ArchGraphBuilder.build(schema)
        P = PackageGraphAggregator.aggregate(G)
        # orders→orders intra-package edge should be gone
        assert not P.has_edge("orders", "orders")
        # cross-package edge should remain
        assert P.has_edge("orders", "users")

    def test_confidence_is_max_over_constituents(self):
        """Aggregated edge confidence is the maximum of constituent edges."""
        schema = _make_schema(
            components=[
                {"id": "a.x", "name": "a.x", "type": "service"},
                {"id": "a.y", "name": "a.y", "type": "service"},
                {"id": "b.z", "name": "b.z", "type": "service"},
            ],
            relationships=[
                {"source": "a.x", "target": "b.z", "confidence": 0.6},
                {"source": "a.y", "target": "b.z", "confidence": 0.9},
            ],
        )
        G = ArchGraphBuilder.build(schema)
        P = PackageGraphAggregator.aggregate(G)
        assert P.edges["a", "b"]["confidence"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Sprint 5 D19 — GraphIntegrityChecker
# ---------------------------------------------------------------------------

class TestGraphIntegrityChecker:

    def setup_method(self):
        self.checker = GraphIntegrityChecker()

    def test_valid_graph_passes(self, simple_graph):
        """A well-formed graph produces no ERROR-level issues."""
        report = self.checker.check(simple_graph)
        assert report.is_valid
        assert len(report.errors()) == 0

    def test_missing_target_node_is_error(self):
        """
        An edge whose target has no registered attributes (silently auto-created
        by NetworkX) is flagged as a MISSING_TARGET_NODE ERROR.
        """
        G = nx.DiGraph()
        # Register only source with proper attributes
        G.add_node("a", name="A", type="service", confidence=1.0,
                   provenance="test", metadata={})
        # add_edge auto-creates "GHOST" with zero attributes — detectable by checker
        G.add_edge("a", "GHOST")  # GHOST has no name/type → integrity error
        report = self.checker.check(G)
        assert not report.is_valid
        codes = [i.code for i in report.errors()]
        assert "MISSING_TARGET_NODE" in codes

    def test_self_loop_is_warning(self):
        """A self-loop produces a WARNING, not an ERROR."""
        G = nx.DiGraph()
        G.add_node("a", name="A", type="service", confidence=1.0,
                   provenance="test", metadata={})
        G.add_edge("a", "a")
        report = self.checker.check(G)
        # Still valid (WARNING only)
        assert report.is_valid
        codes = [i.code for i in report.warnings()]
        assert "SELF_LOOP" in codes

    def test_invalid_confidence_is_error(self):
        """Non-numeric confidence triggers an ERROR."""
        G = nx.DiGraph()
        G.add_node("a", name="A", type="service", confidence=1.0,
                   provenance="test", metadata={})
        G.add_node("b", name="B", type="service", confidence=1.0,
                   provenance="test", metadata={})
        G.add_edge("a", "b", confidence="not-a-number")
        report = self.checker.check(G)
        assert not report.is_valid
        codes = [i.code for i in report.errors()]
        assert "INVALID_CONFIDENCE" in codes

    def test_cycle_detection(self):
        """A cycle produces a WARNING and sets cycle_count > 0."""
        G = nx.DiGraph()
        for n in ["a", "b", "c"]:
            G.add_node(n, name=n, type="service", confidence=1.0,
                       provenance="test", metadata={})
        G.add_edge("a", "b", confidence=1.0, type="calls",
                   provenance="test", metadata={})
        G.add_edge("b", "c", confidence=1.0, type="calls",
                   provenance="test", metadata={})
        G.add_edge("c", "a", confidence=1.0, type="calls",
                   provenance="test", metadata={})
        report = self.checker.check(G)
        assert report.cycle_count > 0
        codes = [i.code for i in report.warnings()]
        assert "CYCLE_DETECTED" in codes

    def test_isolated_node_is_info(self):
        """A node with no edges is reported as INFO."""
        G = nx.DiGraph()
        G.add_node("orphan", name="Orphan", type="service", confidence=1.0,
                   provenance="test", metadata={})
        report = self.checker.check(G)
        assert report.isolated_node_count == 1
        codes = [i.code for i in report.issues]
        assert "ISOLATED_NODE" in codes

    def test_summary_structure(self, simple_graph):
        """report.summary() returns expected keys."""
        report = self.checker.check(simple_graph)
        s = report.summary()
        for key in ("is_valid", "total_issues", "errors", "warnings",
                    "cycle_count", "isolated_node_count"):
            assert key in s


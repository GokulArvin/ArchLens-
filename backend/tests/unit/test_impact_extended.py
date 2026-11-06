"""
Sprint 8 / D38–D40 — Extended impact analysis tests.

Covers:
- D38: validate_correction_edges() — forbidden vs. safe proposed corrections
- D40: compute_impact_summary()   — machine-readable impact summary structure
        and severity classification
- D37: transitive_impact()         — multi-source downstream propagation
- D39: cycles, disconnected nodes, repeated paths
"""

from __future__ import annotations

import networkx as nx
import pytest

from app.modules.cv_pipeline.impact_analysis import (
    CorrectionValidation,
    compute_affected_nodes,
    compute_impact_summary,
    transitive_impact,
    validate_correction_edges,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_node(g: nx.DiGraph, node_id: str, component_type: str) -> None:
    """Add a node with a 'type' attribute matching the vocabulary strings."""
    g.add_node(node_id, type=component_type, name=node_id)


def _simple_layered_graph() -> tuple[nx.DiGraph, nx.DiGraph]:
    """Return (G_I, G_C) with a clean 4-node layered architecture:
       gateway -> controller -> service -> repository
    """
    G_I = nx.DiGraph()
    for nid, ntype in [
        ("gw", "gateway"),
        ("ctrl", "controller"),
        ("svc", "service"),
        ("repo", "repository"),
    ]:
        _make_node(G_I, nid, ntype)
    G_I.add_edges_from([("gw", "ctrl"), ("ctrl", "svc"), ("svc", "repo")])

    G_C = G_I.copy()
    return G_I, G_C


# ─── D38: validate_correction_edges ──────────────────────────────────────────

class TestValidateCorrectionEdges:
    def test_correction_valid_when_no_forbidden_edges(self):
        """Adding a service→repository edge is an ALLOWED layer transition."""
        G_I, G_C = _simple_layered_graph()
        # Propose a valid service → repository edge (not in graph yet, but type-safe)
        extra_svc = "svc2"
        extra_repo = "repo2"
        _make_node(G_C, extra_svc, "service")
        _make_node(G_C, extra_repo, "repository")

        result = validate_correction_edges(G_I, G_C, "svc2", "repo2", [("svc2", "repo2")])

        assert isinstance(result, CorrectionValidation)
        assert result.valid is True
        assert result.violations == []
        assert ("svc2", "repo2") in result.safe_edges

    def test_correction_invalid_when_creates_forbidden_edge(self):
        """Adding controller→database violates DEFAULT_FORBIDDEN_DEPENDENCIES."""
        G_I = nx.DiGraph()
        G_C = nx.DiGraph()
        for nid, ntype in [("ctrl", "controller"), ("db", "database")]:
            _make_node(G_I, nid, ntype)
            _make_node(G_C, nid, ntype)

        result = validate_correction_edges(G_I, G_C, "ctrl", "db", [("ctrl", "db")])

        assert result.valid is False
        assert len(result.violations) == 1
        assert "controller" in result.violations[0]
        assert "database" in result.violations[0]
        assert result.safe_edges == []

    def test_correction_mixed_some_safe_some_forbidden(self):
        """When a batch contains both safe and forbidden edges, only safe ones pass."""
        G_I = nx.DiGraph()
        G_C = nx.DiGraph()
        for nid, ntype in [
            ("ctrl", "controller"),
            ("db", "database"),
            ("svc", "service"),
            ("repo", "repository"),
        ]:
            _make_node(G_I, nid, ntype)
            _make_node(G_C, nid, ntype)

        proposed = [("ctrl", "db"), ("svc", "repo")]
        result = validate_correction_edges(G_I, G_C, "ctrl", "db", proposed)

        assert result.valid is False
        assert len(result.violations) == 1
        assert ("svc", "repo") in result.safe_edges

    def test_correction_empty_proposed_edges_is_valid(self):
        G_I, G_C = _simple_layered_graph()
        result = validate_correction_edges(G_I, G_C, "gw", "ctrl", [])

        assert result.valid is True
        assert result.violations == []
        assert result.safe_edges == []


# ─── D40: compute_impact_summary ─────────────────────────────────────────────

class TestComputeImpactSummary:
    def _linear_chain(self, n: int = 10) -> nx.DiGraph:
        """Linear graph: 0→1→2→…→(n-1)."""
        g = nx.DiGraph()
        for i in range(n):
            g.add_node(str(i), type="service", name=str(i))
        for i in range(n - 1):
            g.add_edge(str(i), str(i + 1))
        return g

    def test_impact_summary_structure(self):
        """compute_impact_summary() returns all expected keys."""
        g = self._linear_chain(5)
        summary = compute_impact_summary(g, "1", "2", "forbidden_dependency")

        expected_keys = {
            "violation_edge",
            "upstream_count",
            "downstream_count",
            "upstream_affected",
            "downstream_affected",
            "blast_radius_fraction",
            "impact_severity",
            "violation_type",
        }
        assert expected_keys == set(summary.keys())

    def test_impact_summary_violation_edge(self):
        g = self._linear_chain(5)
        summary = compute_impact_summary(g, "1", "3", "forbidden_dependency")
        assert summary["violation_edge"] == ("1", "3")

    def test_impact_summary_severity_critical_for_large_blast_radius(self):
        """Hub node at center of star → blast radius ≥ 0.6 → 'critical'."""
        g = nx.DiGraph()
        # Hub with many spokes: 1 hub + 20 leaves
        g.add_node("hub", type="service", name="hub")
        for i in range(20):
            leaf = f"leaf{i}"
            g.add_node(leaf, type="service", name=leaf)
            g.add_edge("hub", leaf)
        # Also add an upstream node
        g.add_node("upstream", type="service", name="upstream")
        g.add_edge("upstream", "hub")

        summary = compute_impact_summary(g, "upstream", "hub", "forbidden_dependency")
        # downstream from hub = 20 leaves; upstream from upstream = 0
        # total = 22 nodes, affected = 20 → ~0.91 → critical
        assert summary["impact_severity"] == "critical"
        assert summary["blast_radius_fraction"] >= 0.6

    def test_impact_summary_severity_low_for_small_graph(self):
        """Isolated violation with no upstream or downstream → blast_radius < 0.1 → 'low'."""
        g = nx.DiGraph()
        for nid in ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"]:
            g.add_node(nid, type="service", name=nid)
        # Only a→b edge; rest are isolated
        g.add_edge("a", "b")

        summary = compute_impact_summary(g, "a", "b", "forbidden_dependency")
        # upstream of a = 0, downstream of b = 0 → fraction = 0.0 → low
        assert summary["impact_severity"] == "low"
        assert summary["blast_radius_fraction"] < 0.1

    def test_impact_summary_counts_correct(self):
        """upstream_count and downstream_count match list lengths."""
        g = self._linear_chain(8)
        # source=2, target=5: upstream=[0,1], downstream=[6,7]
        summary = compute_impact_summary(g, "2", "5", "layer_violation")
        assert summary["upstream_count"] == len(summary["upstream_affected"])
        assert summary["downstream_count"] == len(summary["downstream_affected"])

    def test_impact_summary_raises_for_unknown_node(self):
        g = self._linear_chain(4)
        with pytest.raises(ValueError):
            compute_impact_summary(g, "not-here", "1", "forbidden_dependency")


# ─── D37: transitive_impact ───────────────────────────────────────────────────

class TestTransitiveImpact:
    def test_transitive_impact_includes_all_descendants(self):
        """Propagation from multiple sources covers all reachable descendants."""
        g = nx.DiGraph()
        # a → c → e
        # b → d → e
        for n in ["a", "b", "c", "d", "e"]:
            g.add_node(n)
        g.add_edges_from([("a", "c"), ("c", "e"), ("b", "d"), ("d", "e")])

        result = transitive_impact(g, {"a", "b"})
        assert result == {"c", "d", "e"}

    def test_transitive_impact_single_source(self):
        g = nx.DiGraph()
        for n in ["x", "y", "z"]:
            g.add_node(n)
        g.add_edges_from([("x", "y"), ("y", "z")])

        assert transitive_impact(g, {"x"}) == {"y", "z"}

    def test_transitive_impact_empty_sources_returns_empty(self):
        g = nx.DiGraph()
        g.add_nodes_from(["a", "b"])
        g.add_edge("a", "b")
        assert transitive_impact(g, set()) == set()

    def test_transitive_impact_leaf_sources_return_empty(self):
        """Leaf nodes have no outgoing edges → no reachable descendants."""
        g = nx.DiGraph()
        g.add_nodes_from(["a", "b", "c"])
        g.add_edges_from([("a", "c"), ("b", "c")])
        # 'c' is a leaf
        assert transitive_impact(g, {"c"}) == set()


# ─── D39: cycles, disconnected nodes, repeated paths ─────────────────────────

class TestEdgeCases:
    def test_cycle_in_graph_does_not_hang_traversal(self):
        """Cyclic graph must not cause infinite recursion or hang."""
        g = nx.DiGraph()
        for n in ["a", "b", "c", "d"]:
            g.add_node(n, type="service", name=n)
        # a→b→c→a cycle, plus d reachable from b
        g.add_edges_from([("a", "b"), ("b", "c"), ("c", "a"), ("b", "d")])

        # transitive_impact must terminate
        result = transitive_impact(g, {"a"})
        # all of b, c, d are reachable (and a itself is reachable via cycle, but not in sources)
        assert "b" in result
        assert "c" in result
        assert "d" in result

        # compute_affected_nodes should also terminate
        impact = compute_affected_nodes(g, "a", "b")
        assert isinstance(impact.upstream_affected, list)
        assert isinstance(impact.downstream_affected, list)

    def test_disconnected_node_not_in_impact(self):
        """An isolated node has no effect on impact of an unrelated violation."""
        g = nx.DiGraph()
        for n in ["a", "b", "c", "isolated"]:
            g.add_node(n, type="service", name=n)
        g.add_edges_from([("a", "b"), ("b", "c")])
        # 'isolated' has no edges

        impact = compute_affected_nodes(g, "a", "b")
        assert "isolated" not in impact.upstream_affected
        assert "isolated" not in impact.downstream_affected

        reachable = transitive_impact(g, {"a"})
        assert "isolated" not in reachable

    def test_repeated_path_deduplicated(self):
        """Multiple paths to the same node count it only once."""
        g = nx.DiGraph()
        for n in ["root", "left", "right", "shared"]:
            g.add_node(n, type="service", name=n)
        # root → left → shared
        # root → right → shared
        g.add_edges_from([("root", "left"), ("root", "right"), ("left", "shared"), ("right", "shared")])

        result = transitive_impact(g, {"root"})
        # 'shared' must appear exactly once
        assert "shared" in result
        result_list = sorted(result)
        assert result_list.count("shared") == 1
        assert set(result_list) == {"left", "right", "shared"}

    def test_compute_affected_nodes_on_cyclic_graph(self):
        """nx.ancestors / nx.descendants handle cycles without issues."""
        g = nx.DiGraph()
        for n in ["p", "q", "r"]:
            g.add_node(n, type="service", name=n)
        g.add_edges_from([("p", "q"), ("q", "r"), ("r", "p")])

        # In a cycle every node is an ancestor/descendant of every other
        impact = compute_affected_nodes(g, "p", "q")
        # All nodes reachable from q (downstream) includes r and p (via cycle)
        assert "r" in impact.downstream_affected
        assert "p" in impact.downstream_affected
